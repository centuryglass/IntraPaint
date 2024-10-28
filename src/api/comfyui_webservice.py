"""
Accesses ComfyUI through its REST API, providing access to image generation and editing through stable-diffusion.
"""
import json
import logging
import re
import uuid
from contextlib import contextmanager
from enum import StrEnum, Enum
from io import BytesIO
from typing import cast, Optional, TypedDict, NotRequired, Any, Generator

import requests  # type: ignore
from PIL import Image  # type: ignore
import websocket
from PySide6.QtCore import QBuffer
from PySide6.QtGui import QImage

import src.api.comfyui.comfyui_types as comfy_type
from src.api.comfyui.diffusion_workflow_builder import DiffusionWorkflowBuilder, ExtensionModelType
from src.api.comfyui.nodes.ksampler_node import SAMPLER_OPTIONS, SCHEDULER_OPTIONS
from src.api.controlnet_preprocessor import ControlNetPreprocessor
from src.api.webservice import WebService, MULTIPART_FORM_DATA_TYPE
from src.config.cache import Cache
from src.util.shared_constants import EDIT_MODE_TXT2IMG

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Identifies login failures."""


UPSCALE_SCRIPT = 'ultimate sd upscale'
DEFAULT_TIMEOUT = 30
EXTENDED_TIMEOUT = 90
TYPE_PNG_IMAGE = 'image/png'
INTRAPAINT_UPLOAD_SUBFOLDER = 'IntraPaint'
LORA_EXTENSION = '.safetensors'


class ComfyEndpoints:
    """REST API endpoint constants."""
    # GET:
    WEBSOCKET = '/ws'
    EMBEDDINGS = '/embeddings'
    MODELS = '/models'
    EXTENSIONS = '/extensions'
    VIEW_IMAGE = '/view'
    SYSTEM_STATS = '/system_stats'
    OBJECT_INFO = '/object_info'
    # POST:
    IMG_UPLOAD = '/upload/image'
    MASK_UPLOAD = '/upload/mask'
    INTERRUPT = '/interrupt'
    FREE = '/free'
    # Both:
    PROMPT = '/prompt'
    QUEUE = '/queue'
    HISTORY = '/history'


class ComfyModelType(StrEnum):
    """Model type names, as returned by get_models.  Hardcoded here because it's very unlikely the core items on this
       list will change, and we're going to need to reference them to do things like load LORA options."""
    CHECKPOINT = 'checkpoints'
    CONFIG = 'configs'
    LORA = 'loras'
    VAE = 'vae'
    CLIP = 'clip'
    EMBEDDING = 'embeddings'
    CONTROLNET = 'controlnet'
    CUSTOM_NODES = 'custom_nodes'
    HYPERNETWORKS = 'hypernetworks'
    UPSCALING = 'upscale_models'
    # Everything below this point is only included for completeness, and is unlikely to ever see support in IntraPaint
    # unless someone requests it.
    DIFFUSION_MODEL = 'diffusion_models'
    CLIP_VISION = 'clip_vision'
    STYLE_MODEL = 'style_models'
    DIFFUSER = 'diffusers'
    VAE_APPROX = 'vae_approx'
    GLIGEN = 'gligen'
    PHOTOMAKER = 'photomaker'
    CLASSIFIERS = 'classifiers'
    ANIMATE_DIFF = 'AnimateDiffEvolved_Models'
    ANIMATE_DIFF_LORA = 'AnimateDiffMotion_LoRA'
    VIDEO_FORMATS = 'video_formats'
    IP_ADAPTER = 'ipadapter'


class AsyncTaskStatus(Enum):
    """Represents a queued task's status."""
    PENDING = 0
    ACTIVE = 1
    FINISHED = 2
    FAILED = 3
    NOT_FOUND = 4


class AsyncTaskProgress(TypedDict):
    """The status of an async ComfyUI task, including queue index and generated image data when relevant."""
    status: AsyncTaskStatus
    index: NotRequired[int]  # Only used if statis is PENDING
    outputs: NotRequired[comfy_type.PromptExecOutputs]  # Only used if status is FINISHED


class ComfyUiWebservice(WebService):
    """
    ComfyUiWebservice provides access to Stable-Diffusion through the ComfyUI REST API.
    """

    def __init__(self, url: str) -> None:
        super().__init__(url)
        self._client_id = str(uuid.uuid4())

    # General utility:
    def get_embeddings(self) -> list[str]:
        """Returns the list of available embedding files."""
        return self.get(ComfyEndpoints.EMBEDDINGS, timeout=DEFAULT_TIMEOUT).json()

    def get_model_types(self) -> list[str]:
        """Returns the list of available model types."""
        return cast(list[str], self.get(ComfyEndpoints.MODELS, timeout=DEFAULT_TIMEOUT).json())

    def get_extensions(self) -> list[str]:
        """Returns the list of installed extension files."""
        return cast(list[str], self.get(ComfyEndpoints.EXTENSIONS, timeout=DEFAULT_TIMEOUT).json())

    def get_system_stats(self) -> comfy_type.SystemStatResponse:
        """Returns information about the system and device running Stable-Diffusion."""
        return cast(comfy_type.SystemStatResponse,
                    self.get(ComfyEndpoints.SYSTEM_STATS, timeout=DEFAULT_TIMEOUT).json())

    def get_models(self, model_type: ComfyModelType) -> list[str]:
        """Returns the list of available models, given a particular model type."""
        endpoint = f'{ComfyEndpoints.MODELS}/{model_type.value}'
        return cast(list[str], self.get(endpoint, timeout=DEFAULT_TIMEOUT).json())

    def get_sd_checkpoints(self) -> list[str]:
        """Returns the list of available Stable-Diffusion models."""
        return self.get_models(ComfyModelType.CHECKPOINT)

    def get_vae_models(self) -> list[str]:
        """Returns the list of available Stable-Diffusion VAE models."""
        return self.get_models(ComfyModelType.VAE)

    def get_controlnets(self) -> list[str]:
        """Returns the list of available ControlNet models."""
        return self.get_models(ComfyModelType.CONTROLNET)

    def get_lora_models(self) -> list[str]:
        """Returns the list of available LORA models."""
        return self.get_models(ComfyModelType.LORA)

    def get_hypernetwork_models(self) -> list[str]:
        """Returns the list of available Hypernetwork models."""
        return self.get_models(ComfyModelType.HYPERNETWORKS)

    def get_controlnet_preprocessors(self) -> list[ControlNetPreprocessor]:
        """Scans all nodes for valid preprocessor nodes, and returns the list of parameterized options."""
        preprocessors: list[ControlNetPreprocessor] = []
        node_data = self.get(ComfyEndpoints.OBJECT_INFO, timeout=DEFAULT_TIMEOUT).json()
        for node in node_data:
            node = cast(comfy_type.NodeInfoResponse, node)
            if node['category'] != comfy_type.CONTROLNET_PREPROCESSOR_CATEGORY:
                continue
            try:
                preprocessor = ControlNetPreprocessor.from_comfyui_node_def(node)
                preprocessors.append(preprocessor)
            except ValueError:
                logger.info(f'Skipping incompatible preprocessor node "{node["name"]}"')
        return preprocessors

    def upload_image(self, image: QImage, name: Optional[str] = None, subfolder: Optional[str] = None,
                     temp=False, overwrite=True) -> comfy_type.ImageFileReference:
        """Uploads an image for img2img, inpainting, ControlNet, etc."""
        body: comfy_type.ImageUploadParams = {
            'type': 'temp' if temp else 'input',
            'subfolder': INTRAPAINT_UPLOAD_SUBFOLDER
        }
        if subfolder is not None:
            body['subfolder'] = subfolder
        if overwrite:
            body['overwrite'] = '1'
        buf = QBuffer()
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        image.save(buf, 'PNG')
        buf.close()
        if name is None:
            name = f'src_image.png'
        elif not name.endswith('.png'):
            name = f'{name}.png'
        files = {comfy_type.IMAGE_UPLOAD_FILE_NAME: (name, buf.data().data(), TYPE_PNG_IMAGE)}
        res = cast(comfy_type.ImageUploadResponse, self.post(ComfyEndpoints.IMG_UPLOAD,
                                                             body=body,
                                                             body_format=MULTIPART_FORM_DATA_TYPE,
                                                             files=files,
                                                             timeout=EXTENDED_TIMEOUT).json())
        file_ref: comfy_type.ImageFileReference = {
            'filename': res['name'],
            'subfolder': '' if 'subfolder' not in res else res['subfolder'],
            'type': res['type']
        }
        return file_ref

    def upload_mask(self, mask: QImage, ref_image: comfy_type.ImageFileReference, subfolder: Optional[str] = None,
                    overwrite=True) -> comfy_type.ImageFileReference:
        """Upload an inpainting mask for a particular image.

        The ref_image parameter should contain data returned by a previous upload_image request. Mask size must match
        original image size.

        IMPORTANT: ComfyUI's use of masks is inverted from IntraPaint's usual expectations. Transparency marks the
                   areas where changes are allowed, instead of the areas where changes should be blocked. Make sure
                   to invert mask images before using them here.
        """
        buf = QBuffer()
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        mask.save(buf, 'PNG')
        buf.close()
        body: comfy_type.MaskUploadParams = {
            'original_ref': json.dumps(ref_image),
            'subfolder': INTRAPAINT_UPLOAD_SUBFOLDER
        }
        if subfolder is not None and subfolder != '':
            body['subfolder'] = subfolder
        if overwrite:
            body['overwrite'] = '1'
        mask_name = f'mask_{ref_image["filename"]}'
        files = {comfy_type.IMAGE_UPLOAD_FILE_NAME: (mask_name, buf.data().data(), TYPE_PNG_IMAGE)}
        res = cast(comfy_type.ImageUploadResponse, self.post(ComfyEndpoints.MASK_UPLOAD,
                                                             body=body,
                                                             body_format=MULTIPART_FORM_DATA_TYPE,
                                                             files=files,
                                                             timeout=EXTENDED_TIMEOUT).json())
        file_ref: comfy_type.ImageFileReference = {
            'filename': res['name'],
            'subfolder': '' if 'subfolder' not in res else res['subfolder'],
            'type': res['type']
        }
        return file_ref

    def download_images(self, image_refs: list[comfy_type.ImageFileReference]) -> list[QImage]:
        """Download a list of images from ComfyUI as ARGB QImages."""
        images: list[QImage] = []
        for image_ref in image_refs:
            try:
                image_res = self.get(ComfyEndpoints.VIEW_IMAGE, url_params=cast(dict[str, str], image_ref),
                                     timeout=EXTENDED_TIMEOUT)
                buffer = BytesIO(image_res.content)
                byte_data = buffer.getvalue()
                qimage = QImage.fromData(byte_data)
                if not qimage.isNull():
                    if qimage.format() != QImage.Format.Format_ARGB32_Premultiplied:
                        qimage = qimage.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                    images.append(qimage)
            except (IOError, ValueError, RuntimeError) as err:
                logger.error(f'Skipping image {image_ref}: {err}')
        return images

    def _build_diffusion_body(self, seed: Optional[int] = None) -> DiffusionWorkflowBuilder:
        """Apply cached parameters to begin building a ComfyUI workflow."""
        cache = Cache()
        model_name = cache.get(Cache.SD_MODEL)
        workflow_builder = DiffusionWorkflowBuilder(model_name)
        workflow_builder.batch_size = cache.get(Cache.BATCH_SIZE)
        workflow_builder.prompt = cache.get(Cache.PROMPT)
        workflow_builder.negative_prompt = cache.get(Cache.NEGATIVE_PROMPT)
        workflow_builder.steps = cache.get(Cache.SAMPLING_STEPS)
        workflow_builder.cfg_scale = cache.get(Cache.GUIDANCE_SCALE)
        workflow_builder.image_size = cache.get(Cache.GENERATION_SIZE)

        sampler = cache.get(Cache.SAMPLING_METHOD)
        if sampler in SAMPLER_OPTIONS:
            workflow_builder.sampler = sampler

        scheduler = cache.get(Cache.SCHEDULER)
        if scheduler in SCHEDULER_OPTIONS:
            workflow_builder.scheduler = scheduler

        if seed is None:
            workflow_builder.seed = int(cache.get(Cache.SEED))
        else:
            workflow_builder.seed = seed

        # Find and add LORA and Hypernetwork models:
        available_loras = cache.get(Cache.LORA_MODELS)
        available_hypernetworks = cache.get(Cache.HYPERNETWORK_MODELS)
        lora_name_map: dict[str, str] = {}
        hypernet_name_map: dict[str, str] = {}
        for model_list, model_dict in ((available_loras, lora_name_map),
                                       (available_hypernetworks, hypernet_name_map)):
            for model_option in model_list:
                if '.' in model_option:
                    model_dict[model_option[:model_option.rindex('.')]] = model_option
                model_dict[model_option] = model_option

        extension_model_pattern = r'<(lora|lyco|hypernet):([^:><]+):([^:>]+)(?::([^>]+))?>'
        for prompt, strength_multiplier in ((workflow_builder.prompt, 1.0),
                                            (workflow_builder.negative_prompt, -1.0)):
            extension_model_matches = list(re.finditer(extension_model_pattern, prompt))

            for match in extension_model_matches:
                model_type_name = match.group(1)
                model_type = ExtensionModelType.HYPERNETWORK if model_type_name == 'hypernet' \
                    else ExtensionModelType.LORA
                model_name = match.group(2)
                model_option_dict = hypernet_name_map if model_type == ExtensionModelType.HYPERNETWORK \
                    else lora_name_map
                if model_name not in model_option_dict:
                    logger.error(f'Extension model {model_name} specified, but not found')
                    continue
                model_name = model_option_dict[model_name]
                model_strength_str = match.group(3)
                clip_strength_str = match.group(4) if match.group(4) is not None else model_strength_str
                try:
                    model_strength = float(model_strength_str) * strength_multiplier
                    clip_strength = float(clip_strength_str) * strength_multiplier
                    workflow_builder.add_extension_model(model_name, model_strength, clip_strength, model_type)
                except ValueError:
                    logger.error(f'Invalid strength value "{model_strength_str}" for lora "{model_name}"')

            # remove the lora/hypernetwork syntax from the prompt now that the models are selected:
            if strength_multiplier > 0:
                workflow_builder.prompt = re.sub(extension_model_pattern, '', prompt)
            else:
                workflow_builder.negative_prompt = re.sub(extension_model_pattern, '', prompt)

        edit_mode = cache.get(Cache.EDIT_MODE)
        if edit_mode != EDIT_MODE_TXT2IMG:
            workflow_builder.denoising_strength = cache.get(Cache.DENOISING_STRENGTH)

        config_names = self.get_models(ComfyModelType.CONFIG)
        cached_config = cache.get(Cache.COMFYUI_MODEL_CONFIG)
        if cached_config in config_names:
            workflow_builder.model_config_path = cached_config
        else:  # Only use if one exists matching the model name
            if '.' in model_name:
                ext_idx = model_name.rindex('.')
                model_name = model_name[:ext_idx]
            for config_file in config_names:
                config_ext_idx = config_file.index('.')
                if config_ext_idx != -1:
                    if config_file[:config_ext_idx] == model_name:
                        workflow_builder.model_config_path = config_file
        return workflow_builder

    def get_queue_info(self) -> comfy_type.QueueInfoResponse:
        """Get info on the set of queued jobs."""
        res_body = self.get(ComfyEndpoints.QUEUE, timeout=DEFAULT_TIMEOUT).json()
        for queue_key in [comfy_type.ACTIVE_QUEUE_KEY, comfy_type.PENDING_QUEUE_KEY]:
            assert queue_key in res_body
            queue_list = res_body[queue_key]
            assert isinstance(queue_list, list)
            res_body[queue_key] = [tuple(queue_entry) for queue_entry in queue_list]
        return cast(comfy_type.QueueInfoResponse, res_body)

    def check_queue_entry(self, entry_uuid: str, task_number: int) -> AsyncTaskProgress:
        """Returns the status of a queued task, along with associated data when relevant."""
        endpoint = f'{ComfyEndpoints.HISTORY}/{entry_uuid}'
        history_response = cast(comfy_type.QueueHistoryResponse, self.get(endpoint, timeout=DEFAULT_TIMEOUT).json())
        if entry_uuid in history_response:
            entry_history = history_response[entry_uuid]
            if entry_history['status']['status_str'] == 'error':
                return {'status': AsyncTaskStatus.FAILED}
            if entry_history['status']['completed']:
                progress: AsyncTaskProgress = {
                    'status': AsyncTaskStatus.FINISHED,
                    'outputs': {'images': []}
                }
                for output_data in entry_history['outputs'].values():
                    if 'images' in output_data:
                        for reference in output_data['images']:
                            progress['outputs']['images'].append(cast(comfy_type.ImageFileReference, reference))
                return progress
        queue_info = self.get_queue_info()
        for running_task in queue_info['queue_running']:
            if running_task[1] == entry_uuid:
                return {'status': AsyncTaskStatus.ACTIVE}
        queue_index = 0
        task_found = False
        for pending_task in queue_info['queue_pending']:
            if pending_task[0] < task_number:
                queue_index += 1
            elif pending_task[0] == task_number:
                task_found = True
        if task_found:
            return {'status': AsyncTaskStatus.PENDING, 'index': queue_index}
        return {'status': AsyncTaskStatus.NOT_FOUND}

    def txt2img(self, seed: Optional[int] = None) -> comfy_type.QueueAdditionResponse:
        """Queues an async text-to-image job with the ComfyUI server.

        Most parameters are read directly from the cache, where they should have been written from UI inputs. Calling
        this method will update the LAST_SEED value in the cache.

        Parameters:
        -----------
        seed: Optional[int], default = None
            Seed to use for image generation. If None, the value in the cache is used.
        Returns
        -------
        comfy_type.QueueAdditionResponse
            Information needed to track the async task and download the resulting images once it finishes.
        """
        workflow_builder = self._build_diffusion_body(seed)
        if workflow_builder.denoising_strength != 1.0:
            workflow_builder.denoising_strength = 1.0
        prompt = workflow_builder.build_workflow().get_workflow_dict()
        body: comfy_type.QueueAdditionRequest = {'prompt': prompt, 'client_id': self._client_id}
        res = cast(comfy_type.QueueAdditionResponse, self.post(ComfyEndpoints.PROMPT, body=body,
                                                               timeout=DEFAULT_TIMEOUT).json())
        res['seed'] = workflow_builder.seed
        return res

    def img2img(self, image: QImage, seed: Optional[int] = None) -> comfy_type.QueueAdditionResponse:
        """Queues an async image-to-image job with the ComfyUI server.

        Most parameters are read directly from the cache, where they should have been written from UI inputs. Calling
        this method will update theLAST_SEED value in the cache.

        Parameters:
        -----------
        image: QImage
            The image to inpaint. It must be pre-cropped to the generation area or padded inpainting area, and
            pre-scaled to the generation size if necessary.
        mask: QImage
            The inpainting mask. This must have the same resolution as the image parameter. Note that ComfyUI uses
            the mask to select preserved pixels instead of changed pixels, so any mask taken directly from the
            selection layer must be inverted before its used with this method.
        seed: Optional[int], default = None
            Seed to use for image generation. If None, the value in the cache is used.
        Returns
        -------
        comfy_type.QueueAdditionResponse
            Information needed to track the async task and download the resulting images once it finishes.
        """
        image_reference = self.upload_image(image)
        assert image_reference is not None
        workflow_builder = self._build_diffusion_body(seed)
        workflow_builder.set_source_image_from_reference(image_reference)
        prompt = workflow_builder.build_workflow().get_workflow_dict()
        body: comfy_type.QueueAdditionRequest = {'prompt': prompt, 'client_id': self._client_id}
        res = cast(comfy_type.QueueAdditionResponse, self.post(ComfyEndpoints.PROMPT, body=body,
                                                               timeout=DEFAULT_TIMEOUT).json())
        res['seed'] = workflow_builder.seed
        return res

    def inpaint(self, image: QImage, mask: QImage, seed: Optional[int] = None) -> comfy_type.QueueAdditionResponse:
        """Queues an async inpainting job with the ComfyUI server.

        Most parameters are read directly from the cache, where they should have been written from UI inputs. Calling
        this method will update theLAST_SEED value in the cache.

        Parameters:
        -----------
        image: QImage
            The image to inpaint. It must be pre-cropped to the generation area or padded inpainting area, and
            pre-scaled to the generation size if necessary.
        mask: QImage
            The inpainting mask. This must have the same resolution as the image parameter. Note that ComfyUI uses
            the mask to select preserved pixels instead of changed pixels, so any mask taken directly from the
            selection layer must be inverted before its used with this method.

            Also note that ComfyUI doesn't do any mask blurring, so AppConfig.MASK_BLUR should be handled by the caller
            beforehand.
        seed: Optional[int], default = None
            Seed to use for image generation. If None, the value in the cache is used.
        Returns
        -------
        comfy_type.QueueAdditionResponse
            Information needed to track the async task and download the resulting images once it finishes.
        """
        image_reference = self.upload_image(image)
        mask_reference = self.upload_mask(mask, image_reference)
        workflow_builder = self._build_diffusion_body(seed)
        workflow_builder.set_source_image_from_reference(image_reference)
        workflow_builder.set_mask_from_reference(mask_reference)
        prompt = workflow_builder.build_workflow().get_workflow_dict()
        body: comfy_type.QueueAdditionRequest = {'prompt': prompt, 'client_id': self._client_id}
        res = cast(comfy_type.QueueAdditionResponse, self.post(ComfyEndpoints.PROMPT, body=body,
                                                               timeout=DEFAULT_TIMEOUT).json())
        res['seed'] = workflow_builder.seed
        return res

    def interrupt(self, task_id: Optional[str] = None) -> None:
        """Stops the active workflow, and removes a task from the queue if task_id is not None."""
        if task_id is not None:
            queue_removal_body: comfy_type.QueueDeletionRequest = {
                'delete': [task_id]
            }
            self.post(ComfyEndpoints.QUEUE, body=queue_removal_body)
        self.post(ComfyEndpoints.INTERRUPT, body=None, timeout=DEFAULT_TIMEOUT)

    @contextmanager
    def open_websocket(self) -> Generator[websocket.WebSocket, None, None]:
        """Yields an open ComfyUI websocket that automatically closes when the context exits."""
        ws = websocket.WebSocket()
        base_url = self.server_url  # http://localhost:8188
        assert '://' in base_url
        ws_url = f'ws://{base_url[base_url.index("://") + 3:]}/ws?clientId={self._client_id}'  # _client_id is uuid
        ws.connect(ws_url)
        try:
            yield ws
        finally:
            ws.close()

    @staticmethod
    def parse_percentage_from_websocket_message(websocket_text: str) -> Optional[float]:
        """Attempts to parse a percentage from a ComfyUI websocket message."""
        status: Optional[dict[str, Any]] = None
        if isinstance(websocket_text, str):
            try:
                status = json.loads(websocket_text)
            except json.decoder.JSONDecodeError:
                return None
        if status is not None and 'type' in status and 'data' in status:
            if status['type'] == 'progress':
                data = status['data']
                if 'value' in data and 'max' in data:
                    return round(data['value'] / data['max'] * 100, ndigits=4)
        return None
