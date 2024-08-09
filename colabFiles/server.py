"""
Runs a simple HTTP server that provides access to GLID-3-XL image editing operations.
"""

from datetime import datetime
from threading import Thread, Lock
from typing import Any, Dict

import flask  # type: ignore
from flask import Flask, request, jsonify, make_response, abort, current_app
from flask_cors import CORS, cross_origin
from src.util.image_utils import pil_image_from_base64, image_to_base64
from src.glid_3_xl.ml_utils import foreach_image_in_sample  # type: ignore
from src.glid_3_xl.create_sample_function import create_sample_function  # type: ignore
from src.glid_3_xl.generate_samples import generate_samples  # type: ignore


def start_server(device, model_params, model, diffusion, ldm_model, bert_model, clip_model, clip_preprocess, normalize):
    """
    Starts a Flask server to handle inpainting requests from a remote UI.

    Note that this server can only handle a single client. In the future, using a direct connection would probably
    be superior, but it's not worth the extra effort right now.
    """

    print("Starting server...")
    app = Flask(__name__)
    CORS(app)
    context = app.app_context()
    context.push()

    with context:
        current_app.lastRequest = None
        current_app.lastError = None
        current_app.in_progress = False
        current_app.thread = None
        current_app.samples = {}
        current_app.lock = Lock()

    @app.route("/", methods=["GET"])
    @cross_origin()
    def health_check() -> flask.Response:
        """Call to check if the server is up."""
        return jsonify(success=True)

    # Start an inpainting request:
    @app.route("/", methods=["POST"])
    @cross_origin()
    def start_inpainting():
        # Extract arguments from body, convert images from base64
        json = request.get_json(force=True)

        def requested_or_default(key, default_value):
            if key in json:
                return json[key]
            return default_value

        batch_size = requested_or_default('batch_size', 1)
        num_batches = requested_or_default('num_batches', 1)
        width = requested_or_default('width', 256)
        height = requested_or_default('height', 256)

        edit = None
        mask = None
        try:
            edit = pil_image_from_base64(json["edit"])
        except Exception as err:
            print(f"loading edit image failed, {err}")
            abort(make_response({"error": f"loading edit image failed, {err}"}, 400))
        try:
            mask = pil_image_from_base64(json["mask"])
        except Exception as err:
            print(f"loading mask image failed, {err}")
            abort(make_response({"error": f"loading mask image failed, {err}"}, 400))

        sample_fn = None
        try:
            sample_fn, clip_score_fn = create_sample_function(
                device,
                model,
                model_params,
                bert_model,
                clip_model,
                clip_preprocess,
                ldm_model,
                diffusion,
                normalize,
                edit=edit,
                mask=mask,
                prompt=requested_or_default("prompt", ""),
                negative=requested_or_default("negative", ""),
                guidance_scale=requested_or_default("guidanceScale", 5.0),
                batch_size=batch_size,
                width=width,
                height=height,
                cutn=requested_or_default("cutn", 16),
                skip_timesteps=requested_or_default("skipSteps", False))
        except Exception as err:
            abort(make_response({"error": f"creating sample function failed, {err}"}, 500))

        def save_sample(i, sample, clip_score=False):
            with current_app.lock:
                timestamp = datetime.timestamp(datetime.now())
                try:
                    def add_image_to_response(k, image):
                        name = f'{i * batch_size + k:05}'
                        current_app.samples[name] = {"image": image_to_base64(image), "timestamp": timestamp}

                    foreach_image_in_sample(sample, batch_size, ldm_model, add_image_to_response)
                except Exception as save_err:
                    current_app.lastError = f"sample save error: {save_err}"
                    print(current_app.lastError)

        def run_thread():
            with context:
                generate_samples(device,
                                 ldm_model,
                                 diffusion,
                                 sample_fn,
                                 save_sample,
                                 batch_size,
                                 num_batches,
                                 width,
                                 height)
                with current_app.lock:
                    current_app.in_progress = False

        # Start image generation thread:
        with current_app.lock:
            if current_app.in_progress or current_app.thread and current_app.thread.is_alive():
                abort(make_response({'error': "Cannot start a new operation, an existing operation is still running"},
                                    409))
            current_app.samples = {}
            current_app.in_progress = True
            current_app.thread = Thread(target=run_thread)
            current_app.thread.start()

        return jsonify(success=True)

    # Request updated images:
    @app.route("/sample", methods=["GET"])
    @cross_origin()
    def list_updated() -> Dict[str, Dict[Any, Any]]:
        json = request.get_json(force=True)
        # Parse (sampleName, timestamp) pairs from request.samples
        # Check (sampleName, timestamp) pairs from the most recent request. If any missing from the request or have a
        # newer timestamp, set response.samples[sampleName] = { timestamp, base64Image }
        response: Dict[str, Dict[Any, Any]] = {"samples": {}}
        with current_app.lock:
            for key, sample in current_app.samples.items():
                if key not in json["samples"] or json["samples"][key] < sample["timestamp"]:
                    response["samples"][key] = sample
            # If any errors were saved for the most recent request, use those to set response.errors
            if current_app.lastError != "":
                response["error"] = current_app.lastError

            # Check if the most recent request is finished, use this to set response.in_progress.
            response["in_progress"] = current_app.in_progress
        return response

    return app
