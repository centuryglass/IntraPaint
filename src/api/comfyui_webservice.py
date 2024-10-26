"""
Accesses ComfyUI through its REST API, providing access to image generation and editing through stable-diffusion.
"""
import datetime
import json
import logging
from enum import StrEnum, Enum
from io import BytesIO
from typing import List, cast, Optional, TypedDict, NotRequired

import requests  # type: ignore
from PIL import Image  # type: ignore
from PySide6.QtCore import QBuffer, QSize, Qt, QPoint
from PySide6.QtGui import QImage, QPainter, QPainterPath

import src.api.comfyui_types as comfy_type
from src.api.comfyui_nodes.ksampler_node import SAMPLER_OPTIONS
from src.api.comfyui_workflows.diffusion_workflow_builder import DiffusionWorkflowBuilder
from src.api.webservice import WebService, MULTIPART_FORM_DATA_TYPE
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.image.filter.blur import BlurFilter, MODE_GAUSSIAN
from src.util.shared_constants import EDIT_MODE_TXT2IMG
from src.util.visual.image_utils import create_transparent_image

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Identifies login failures."""


UPSCALE_SCRIPT = 'ultimate sd upscale'
DEFAULT_TIMEOUT = 30
SETTINGS_UPDATE_TIMEOUT = 90
TYPE_PNG_IMAGE = 'image/png'
INTRAPAINT_UPLOAD_SUBFOLDER = 'IntraPaint'


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
    DIFFUSION_MODEL = 'diffusion_models'
    CLIP_VISION = 'clip_vision'
    STYLE_MODEL = 'style_models'
    EMBEDDING = 'embeddings'
    DIFFUSER = 'diffusers'
    VAE_APPROX = 'vae_approx'
    CONTROLNET = 'controlnet'
    GLIGEN = 'gligen'
    UPSCALING = 'upscale_models'
    CUSTOM_NODES = 'custom_nodes'
    HYPERNETWORKS = 'hypernetworks'
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

    # General utility:
    def get_embeddings(self) -> List[str]:
        """Returns the list of available embedding files."""
        return self.get(ComfyEndpoints.EMBEDDINGS).json()

    def get_model_types(self) -> List[str]:
        """Returns the list of available model types."""
        return cast(List[str], self.get(ComfyEndpoints.MODELS).json())

    def get_extensions(self) -> List[str]:
        """Returns the list of installed extension files."""
        return cast(List[str], self.get(ComfyEndpoints.EXTENSIONS).json())

    def get_system_stats(self) -> comfy_type.SystemStatResponse:
        """Returns information about the system and device running Stable-Diffusion."""
        return cast(comfy_type.SystemStatResponse, self.get(ComfyEndpoints.SYSTEM_STATS).json())

    def get_models(self, model_type: ComfyModelType) -> List[str]:
        """Returns the list of available models, given a particular model type."""
        endpoint = f'{ComfyEndpoints.MODELS}/{model_type.value}'
        return cast(List[str], self.get(endpoint).json())

    def get_sd_checkpoints(self) -> List[str]:
        """Returns the list of available Stable-Diffusion models."""
        return self.get_models(ComfyModelType.CHECKPOINT)

    def get_vae_models(self) -> List[str]:
        """Returns the list of available Stable-Diffusion VAE models."""
        return self.get_models(ComfyModelType.VAE)

    def get_controlnets(self) -> List[str]:
        """Returns the list of available ControlNet models."""
        return self.get_models(ComfyModelType.CONTROLNET)

    def get_lora_models(self) -> List[str]:
        """Returns the list of available LORA models."""
        return self.get_models(ComfyModelType.LORA)

    def upload_image(self, image: QImage, name: Optional[str] = None, subfolder: Optional[str] = None,
                     temp=True, overwrite=True) -> comfy_type.ImageFileReference:
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
                                                             files=files).json())
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
                                                             files=files).json())
        file_ref: comfy_type.ImageFileReference = {
            'filename': res['name'],
            'subfolder': '' if 'subfolder' not in res else res['subfolder'],
            'type': res['type']
        }
        return file_ref

    def download_images(self, image_refs: List[comfy_type.ImageFileReference]) -> List[QImage]:
        """Download a list of images from ComfyUI as ARGB QImages."""
        images: List[QImage] = []
        for image_ref in image_refs:
            try:
                image_res = self.get(ComfyEndpoints.VIEW_IMAGE, url_params=image_ref)
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

    def _build_diffusion_body(self) -> DiffusionWorkflowBuilder:
        """Apply cached parameters to begin building a ComfyUI workflow."""
        cache = Cache()
        model_name = cache.get(Cache.COMFYUI_SD_MODEL)
        workflow_builder = DiffusionWorkflowBuilder(model_name)
        workflow_builder.batch_size = cache.get(Cache.BATCH_SIZE)
        workflow_builder.prompt = cache.get(Cache.PROMPT)
        workflow_builder.negative_prompt = cache.get(Cache.NEGATIVE_PROMPT)
        workflow_builder.steps = cache.get(Cache.SAMPLING_STEPS)
        workflow_builder.cfg_scale = cache.get(Cache.GUIDANCE_SCALE)
        workflow_builder.image_size = cache.get(Cache.GENERATION_SIZE)
        workflow_builder.sampler = cache.get(Cache.SAMPLING_METHOD)
        workflow_builder.seed = cache.get(Cache.SEED)

        edit_mode = cache.get(Cache.EDIT_MODE)
        if edit_mode != EDIT_MODE_TXT2IMG:
            workflow_builder.denoising_strength = cache.get(Cache.DENOISING_STRENGTH)

        config_names = self.get_models(ComfyModelType.CONFIG)
        cached_config = cache.get(Cache.COMFYUI_MODEL_CONFIG)
        if cached_config in config_names:
            workflow_builder.model_config_path = cached_config
        else:  # Only use if one exists matching the model name
            ext_idx = model_name.index('.')
            if ext_idx != -1:
                model_name = model_name[:ext_idx]
            for config_file in config_names:
                config_ext_idx = config_file.index('.')
                if config_ext_idx != -1:
                    if config_file[:config_ext_idx] == model_name:
                        workflow_builder.model_config_path = config_file
        return workflow_builder

    def get_queue_info(self) -> comfy_type.QueueInfoResponse:
        """Get info on the set of queued jobs."""
        res_body = self.get(ComfyEndpoints.QUEUE).json()
        for queue_key in [comfy_type.ACTIVE_QUEUE_KEY, comfy_type.PENDING_QUEUE_KEY]:
            assert queue_key in res_body
            queue_list = res_body[queue_key]
            assert isinstance(queue_list, list)
            res_body[queue_key] = [tuple(queue_entry) for queue_entry in queue_list]
        return cast(comfy_type.QueueInfoResponse, res_body)

    def check_queue_entry(self, entry_uuid: str, task_number: int) -> AsyncTaskProgress:
        """Returns the status of a queued task, along with associated data when relevant."""
        endpoint = f'{ComfyEndpoints.HISTORY}/{entry_uuid}'
        history_response = cast (comfy_type.QueueHistoryResponse, self.get(endpoint).json())
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
                        progress['outputs']['images'] += output_data['images']
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

    def txt2img(self) -> comfy_type.QueueAdditionResponse:
        """Queues an async text-to-image job with the ComfyUI server.

        Most parameters are read directly from the cache, where they should have been written from UI inputs. Calling
        this method will update the LAST_SEED value in the cache.

        Returns
        -------
        comfy_type.QueueAdditionResponse
            Information needed to track the async task and download the resulting images once it finishes.
        """
        workflow = self._build_diffusion_body()
        if workflow.denoising_strength != 1.0:
            workflow.denoising_strength = 1.0
        prompt = workflow.build_workflow().get_workflow_dict()
        body: comfy_type.QueueAdditionRequest = {'prompt': prompt}
        return cast(comfy_type.QueueAdditionResponse, self.post(ComfyEndpoints.PROMPT, body=body).json())

    def img2img(self, image: QImage) -> comfy_type.QueueAdditionResponse:
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
        Returns
        -------
        comfy_type.QueueAdditionResponse
            Information needed to track the async task and download the resulting images once it finishes.
        """
        image_reference = self.upload_image(image, temp=False)
        workflow_builder = self._build_diffusion_body()
        workflow_builder.source_image = image_reference
        Cache().set(Cache.LAST_SEED, workflow_builder.seed)

        prompt = workflow_builder.build_workflow().get_workflow_dict()
        body: comfy_type.QueueAdditionRequest = {'prompt': prompt}
        return cast(comfy_type.QueueAdditionResponse, self.post(ComfyEndpoints.PROMPT, body=body).json())

    def inpaint(self, image: QImage, mask: QImage) -> comfy_type.QueueAdditionResponse:
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
        Returns
        -------
        comfy_type.QueueAdditionResponse
            Information needed to track the async task and download the resulting images once it finishes.
        """
        image_reference = self.upload_image(image, overwrite=True)
        mask_reference = self.upload_mask(mask, image_reference)
        workflow = self._build_diffusion_body()
        workflow.source_image = image_reference
        workflow.source_mask = mask_reference

        prompt = workflow.build_workflow().get_workflow_dict()
        body: comfy_type.QueueAdditionRequest = {'prompt': prompt}
        return cast(comfy_type.QueueAdditionResponse, self.post(ComfyEndpoints.PROMPT, body=body).json())

    def test_latest(self, prompt: str, num: int):
        """Temporary test method. TODO: remove after UI implementation."""
        # Manually set a bunch of stuff the UI or generator will need to handle later:
        Cache().set(Cache.PROMPT, prompt)
        Cache().set(Cache.BATCH_SIZE, num)
        Cache().update_options(Cache.SAMPLING_METHOD, SAMPLER_OPTIONS)
        Cache().set(Cache.SAMPLING_METHOD, 'euler_ancestral')
        Cache().set(Cache.COMFYUI_SD_MODEL, 'pirsusArtstation_v10.safetensors')
        Cache().set(Cache.GUIDANCE_SCALE, 8.0)
        Cache().set(Cache.DENOISING_STRENGTH, 0.8)
        Cache().set(Cache.GENERATION_SIZE, QSize(1024, 1024))

        # Create and print queued task:
        image = QImage('./examples/model_example_photon.png')
        mask = create_transparent_image(image.size())
        painter = QPainter(mask)
        painter.setPen(Qt.GlobalColor.black)
        path = QPainterPath()
        path.addEllipse(QPoint(300, 300), 200, 100)
        painter.fillPath(path, Qt.GlobalColor.black)
        painter.end()
        mask.invertPixels(QImage.InvertMode.InvertRgba)
        mask = BlurFilter.blur(mask, MODE_GAUSSIAN, AppConfig().get(AppConfig.MASK_BLUR))

        queue_item = self.inpaint(image, mask)
        print(f'Added to queue as {queue_item["prompt_id"]}, number {queue_item["number"]}')

        # Continually check status until it's done. Real implementation will need to use a delay and operate outside
        # the UI thread, of course.
        is_finished = False
        status = None
        last_status = None
        while not is_finished:
            status = self.check_queue_entry(queue_item['prompt_id'], queue_item['number'])
            if status['status'] != last_status:
                print(f'Status: {status}')
                last_status = status['status']
            is_finished = status['status'] == AsyncTaskStatus.FINISHED

        # Download images using the output data from the last status response, save to cwd for inspection:
        if status is not None and 'outputs' in status and 'images' in status['outputs']:
            images = status['outputs']['images']
            print(f'response: {len(images)} image references.')
            qimages = self.download_images(images)
            for i, image in enumerate(qimages):
                image.save(f'test_{prompt}_{i}.png')