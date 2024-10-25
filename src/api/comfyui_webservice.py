"""
Accesses ComfyUI through its REST API, providing access to image generation and editing through stable-diffusion.
"""
import json
import logging
from enum import StrEnum
from typing import List, cast, Optional

import requests  # type: ignore
from PIL import Image  # type: ignore
from PySide6.QtCore import QBuffer
from PySide6.QtGui import QImage

import src.api.comfyui_types as comfy_type
from src.api.webservice import WebService, MULTIPART_FORM_DATA_TYPE

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

    def upload_image(self, image: QImage, name: str, temp=True, subfolder: Optional[str] = None,
                     overwrite=False) -> comfy_type.ImageUploadResponse:
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
        if not name.endswith('.png'):
            name = f'{name}.png'
        files = {comfy_type.IMAGE_UPLOAD_FILE_NAME: (name, buf.data().data(), TYPE_PNG_IMAGE)}
        return cast(comfy_type.ImageUploadResponse, self.post(ComfyEndpoints.IMG_UPLOAD,
                                                              body=body,
                                                              body_format=MULTIPART_FORM_DATA_TYPE,
                                                              files=files).json())

    def upload_mask(self, mask: QImage, ref_image: comfy_type.MaskRefObject) -> comfy_type.ImageUploadResponse:
        """Upload an inpainting mask for a particular image.

        The ref_image parameter should contain data returned by a previous upload_image request. Mask size must match
        original image size.
        """

        buf = QBuffer()
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        mask.save(buf, 'PNG')
        buf.close()
        body: comfy_type.MaskUploadParams = {
            'original_ref': json.dumps(ref_image)
        }
        mask_name = f'mask_{ref_image["filename"]}'
        files = {comfy_type.IMAGE_UPLOAD_FILE_NAME: (mask_name, buf.data().data(), TYPE_PNG_IMAGE)}
        return cast(comfy_type.ImageUploadResponse, self.post(ComfyEndpoints.MASK_UPLOAD,
                                                              body=body,
                                                              body_format=MULTIPART_FORM_DATA_TYPE,
                                                              files=files).json())
