"""
Accesses ComfyUI through its REST API, providing access to image generation and editing through stable-diffusion.
"""
import json
import logging
import os
import uuid
from contextlib import contextmanager
from copy import deepcopy
from enum import StrEnum, Enum
from io import BytesIO
from json import JSONDecodeError
from typing import cast, Optional, TypedDict, NotRequired, Any, Generator

import websocket
from PySide6.QtCore import QBuffer
from PySide6.QtGui import QImage

import src.api.comfyui.comfyui_types as comfyui_types
from src.api.comfyui.controlnet_comfyui_utils import get_all_preprocessors, \
    diffusion_workflow_builder_with_cache_applied
from src.api.comfyui.diffusion_workflow_builder import DiffusionWorkflowBuilder
from src.api.comfyui.nodes.ksampler_node import KSAMPLER_NAME
from src.api.comfyui.preprocessor_preview_workflow_builder import PreprocessorPreviewWorkflowBuilder
from src.api.controlnet.controlnet_category_builder import ControlNetCategoryBuilder
from src.api.controlnet.controlnet_constants import CONTROLNET_REUSE_IMAGE_CODE
from src.api.controlnet.controlnet_preprocessor import ControlNetPreprocessor
from src.api.controlnet.controlnet_unit import ControlNetUnit
from src.api.webservice import WebService, MULTIPART_FORM_DATA_TYPE
from src.api.webui.controlnet_webui_constants import ControlTypeDef
from src.config.cache import Cache

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Identifies login failures."""


UPSCALE_SCRIPT = 'ultimate sd upscale'
DEFAULT_TIMEOUT = 30
EXTENDED_TIMEOUT = 90
TYPE_PNG_IMAGE = 'image/png'
INTRAPAINT_UPLOAD_SUBFOLDER = 'IntraPaint'
LORA_EXTENSION = '.safetensors'

# Keys used when extracting data from the KSampler node definition:
SAMPLER_OPTION_KEY = 'sampler_name'
SCHEDULER_OPTION_KEY = 'scheduler'


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
       list will change, and we're going to need to reference them to do things like load LoRA options."""
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
    outputs: NotRequired[comfyui_types.PromptExecOutputs]  # Only used if status is FINISHED


class ComfyUiWebservice(WebService):
    """
    ComfyUiWebservice provides access to Stable-Diffusion through the ComfyUI REST API.
    """

    def __init__(self, url: str) -> None:
        super().__init__(url)
        self._preprocessor_cache: Optional[list[ControlNetPreprocessor]] = None
        self._ksampler_info: Optional[comfyui_types.NodeInfoResponse] = None
        self._client_id = str(uuid.uuid4())

    # General utility:

    def get_sampler_names(self) -> list[str]:
        """Gets the list of sampling method names from KSampler node info."""
        if self._ksampler_info is None:
            info_endpoint = f'{ComfyEndpoints.OBJECT_INFO}/{KSAMPLER_NAME}'
            self._ksampler_info = cast(comfyui_types.NodeInfoResponse, self.get(info_endpoint).json()[KSAMPLER_NAME])
        required_inputs = self._ksampler_info['input']['required']
        assert SAMPLER_OPTION_KEY in required_inputs and isinstance(required_inputs[SAMPLER_OPTION_KEY], list)
        return cast(list[str], required_inputs[SAMPLER_OPTION_KEY][0])

    def get_scheduler_names(self) -> list[str]:
        """Gets the list of sampling scheduler names from KSampler node info."""
        if self._ksampler_info is None:
            info_endpoint = f'{ComfyEndpoints.OBJECT_INFO}/{KSAMPLER_NAME}'
            self._ksampler_info = cast(comfyui_types.NodeInfoResponse, self.get(info_endpoint).json())
        required_inputs = self._ksampler_info['input']['required']
        assert SCHEDULER_OPTION_KEY in required_inputs and isinstance(required_inputs[SCHEDULER_OPTION_KEY], list)
        return cast(list[str], required_inputs[SCHEDULER_OPTION_KEY][0])

    def get_embeddings(self) -> list[str]:
        """Returns the list of available embedding files."""
        return self.get(ComfyEndpoints.EMBEDDINGS, timeout=DEFAULT_TIMEOUT).json()

    def get_model_types(self) -> list[str]:
        """Returns the list of available model types."""
        return cast(list[str], self.get(ComfyEndpoints.MODELS, timeout=DEFAULT_TIMEOUT).json())

    def get_extensions(self) -> list[str]:
        """Returns the list of installed extension files."""
        return cast(list[str], self.get(ComfyEndpoints.EXTENSIONS, timeout=DEFAULT_TIMEOUT).json())

    def get_system_stats(self) -> comfyui_types.SystemStatResponse:
        """Returns information about the system and device running Stable-Diffusion."""
        return cast(comfyui_types.SystemStatResponse,
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
        """Returns the list of available LoRA models."""
        return self.get_models(ComfyModelType.LORA)

    def get_hypernetwork_models(self) -> list[str]:
        """Returns the list of available Hypernetwork models."""
        return self.get_models(ComfyModelType.HYPERNETWORKS)

    def get_controlnet_preprocessors(self, update_cache=False) -> list[ControlNetPreprocessor]:
        """Scans all nodes for valid preprocessor nodes, and returns the list of parameterized options."""
        if update_cache or self._preprocessor_cache is None:
            node_data = cast(dict[str, comfyui_types.NodeInfoResponse],
                             self.get(ComfyEndpoints.OBJECT_INFO, timeout=DEFAULT_TIMEOUT).json())
            self._preprocessor_cache = get_all_preprocessors(node_data)
        return deepcopy(self._preprocessor_cache)

    def get_controlnet_type_categories(self, preprocessors: Optional[list[ControlNetPreprocessor]] = None
                                       ) -> dict[str, ControlTypeDef]:
        """Gets the set of valid ControlNet proeprocessor/model categories, taking into account available options and
           API category definitions if possible."""
        if preprocessors is None:
            preprocessors = self.get_controlnet_preprocessors()
        preprocessor_names = [module.name for module in preprocessors]
        preprocessor_categories: dict[str, str] = {}
        for module in preprocessors:
            preprocessor_categories[module.name] = module.category_name
        model_names = self.get_controlnets()
        control_type_builder = ControlNetCategoryBuilder(preprocessor_names, model_names, preprocessor_categories,
                                                         None)
        return control_type_builder.get_control_types()

    def upload_image(self, image: QImage, name: Optional[str] = None, subfolder: Optional[str] = None,
                     temp=False, overwrite=True) -> comfyui_types.ImageFileReference:
        """Uploads an image for img2img, inpainting, ControlNet, etc."""
        body: comfyui_types.ImageUploadParams = {
            'type': 'temp' if temp else 'input',
            'subfolder': INTRAPAINT_UPLOAD_SUBFOLDER
        }
        if subfolder is not None:
            body['subfolder'] = subfolder
        if overwrite:
            body['overwrite'] = '1'
        buf = QBuffer()
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        image.save(buf, 'PNG')  # type: ignore
        buf.close()
        if name is None:
            name = 'src_image.png'
        elif not name.endswith('.png'):
            name = f'{name}.png'
        files = {comfyui_types.IMAGE_UPLOAD_FILE_NAME: (name, buf.data().data(), TYPE_PNG_IMAGE)}
        res = cast(comfyui_types.ImageUploadResponse, self.post(ComfyEndpoints.IMG_UPLOAD,
                                                                body=body,
                                                                body_format=MULTIPART_FORM_DATA_TYPE,
                                                                files=files,
                                                                timeout=EXTENDED_TIMEOUT).json())
        file_ref: comfyui_types.ImageFileReference = {
            'filename': res['name'],
            'subfolder': '' if 'subfolder' not in res else res['subfolder'],
            'type': res['type']
        }
        return file_ref

    def upload_mask(self, mask: QImage, ref_image: comfyui_types.ImageFileReference, subfolder: Optional[str] = None,
                    overwrite=True) -> comfyui_types.ImageFileReference:
        """Upload an inpainting mask for a particular image.

        The ref_image parameter should contain data returned by a previous upload_image request. Mask size must match
        original image size.

        IMPORTANT: ComfyUI's use of masks is inverted from IntraPaint's usual expectations. Transparency marks the
                   areas where changes are allowed, instead of the areas where changes should be blocked. Make sure
                   to invert mask images before using them here.
        """
        buf = QBuffer()
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        mask.save(buf, 'PNG')  # type: ignore
        buf.close()
        body: comfyui_types.MaskUploadParams = {
            'original_ref': json.dumps(ref_image),
            'subfolder': INTRAPAINT_UPLOAD_SUBFOLDER
        }
        if subfolder is not None and subfolder != '':
            body['subfolder'] = subfolder
        if overwrite:
            body['overwrite'] = '1'
        mask_name = f'mask_{ref_image["filename"]}'
        files = {comfyui_types.IMAGE_UPLOAD_FILE_NAME: (mask_name, buf.data().data(), TYPE_PNG_IMAGE)}
        res = cast(comfyui_types.ImageUploadResponse, self.post(ComfyEndpoints.MASK_UPLOAD,
                                                                body=body,
                                                                body_format=MULTIPART_FORM_DATA_TYPE,
                                                                files=files,
                                                                timeout=EXTENDED_TIMEOUT).json())
        file_ref: comfyui_types.ImageFileReference = {
            'filename': res['name'],
            'subfolder': '' if 'subfolder' not in res else res['subfolder'],
            'type': res['type']
        }
        return file_ref

    def download_images(self, image_refs: list[comfyui_types.ImageFileReference]) -> list[QImage]:
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
        workflow_builder = diffusion_workflow_builder_with_cache_applied(seed)
        config_names = self.get_models(ComfyModelType.CONFIG)
        if workflow_builder.model_config_path not in config_names:
            # Check available config, and if one matches the stable diffusion model name, use that one:
            workflow_builder.model_config_path = None
            model_name = workflow_builder.sd_model
            if '.' in model_name:
                ext_idx = model_name.rindex('.')
                model_name = model_name[:ext_idx]
            for config_file in config_names:
                config_ext_idx = config_file.index('.')
                if config_ext_idx != -1:
                    if config_file[:config_ext_idx] == model_name:
                        workflow_builder.model_config_path = config_file
        return workflow_builder

    def _prepare_controlnet_data(self, workflow_builder: DiffusionWorkflowBuilder,
                                 gen_area_control_image: QImage | comfyui_types.ImageFileReference,
                                 image_references: dict[str, comfyui_types.ImageFileReference]) -> None:
        """Loads ControlNet units from the cache into a workflow builder.

        Parameters:
        ----------
        workflow_builder: DiffusionWorkflowBuilder
            Workflow builder object where any active ControlNet units will be defined as ComfyUI nodes.
        gen_area_control_image: QImage | comfy_type.ImageFileREference
            Image generation area content to upload or include if a ControlNet unit uses the "generation area as
            control" option. Only used if that option is set and the image isn't already found in image_references
            under the CONTROLNET_REUSE_IMAGE_CODE key.
        image_references: dict[str, comfy_type.ImageFileReference]
            Maps image strings as they appear in cached ControlNet unit data to previously uploaded image
            references. If any new images are uploaded, their references will be added here.

        """
        cache = Cache()
        if (isinstance(gen_area_control_image, dict)
                and CONTROLNET_REUSE_IMAGE_CODE not in image_references):
            image_references[CONTROLNET_REUSE_IMAGE_CODE] = cast(comfyui_types.ImageFileReference,
                                                                 gen_area_control_image)
        for control_unit_key in (Cache.CONTROLNET_ARGS_0_COMFYUI, Cache.CONTROLNET_ARGS_1_COMFYUI,
                                 Cache.CONTROLNET_ARGS_2_COMFYUI):
            try:
                control_unit = ControlNetUnit.deserialize(cache.get(control_unit_key))
            except (KeyError, ValueError, RuntimeError, JSONDecodeError) as err:
                logger.error(f'skipping invalid controlnet unit "{control_unit_key}": {err}')
                continue
            if not control_unit.enabled:
                continue
            model_name = control_unit.model.full_model_name
            preprocessor = control_unit.preprocessor

            control_image_str = control_unit.image_string
            assert control_image_str is not None
            if control_image_str in image_references:
                control_image_ref = image_references[control_image_str]
            else:
                image_to_upload: Optional[QImage] = None
                if control_image_str == CONTROLNET_REUSE_IMAGE_CODE and isinstance(gen_area_control_image, QImage):
                    image_to_upload = gen_area_control_image
                elif os.path.isfile(control_image_str):
                    image_to_upload = QImage(control_image_str)
                if image_to_upload is None or image_to_upload.isNull():
                    logger.error(f'Skipping "{control_unit_key}": failed to load image {control_image_str}')
                    continue
                try:
                    control_image_ref = self.upload_image(image_to_upload, control_unit_key)
                except (KeyError, RuntimeError) as err:
                    logger.error(f'Skipping "{model_name}" ControlNet, uploading image "{control_image_str}"'
                                 f' failed: {err}')
                    continue
                image_references[control_image_str] = control_image_ref
            workflow_builder.add_controlnet_unit(model_name, preprocessor, control_image_ref,
                                                 float(control_unit.control_strength.value),
                                                 float(control_unit.control_start.value),
                                                 float(control_unit.control_end.value))

    def get_queue_info(self) -> comfyui_types.QueueInfoResponse:
        """Get info on the set of queued jobs."""
        res_body = self.get(ComfyEndpoints.QUEUE, timeout=DEFAULT_TIMEOUT).json()
        for queue_key in [comfyui_types.ACTIVE_QUEUE_KEY, comfyui_types.PENDING_QUEUE_KEY]:
            assert queue_key in res_body
            queue_list = res_body[queue_key]
            assert isinstance(queue_list, list)
            res_body[queue_key] = [tuple(queue_entry) for queue_entry in queue_list]
        return cast(comfyui_types.QueueInfoResponse, res_body)

    def check_queue_entry(self, entry_uuid: str, task_number: int) -> AsyncTaskProgress:
        """Returns the status of a queued task, along with associated data when relevant."""
        endpoint = f'{ComfyEndpoints.HISTORY}/{entry_uuid}'
        history_response = cast(comfyui_types.QueueHistoryResponse, self.get(endpoint, timeout=DEFAULT_TIMEOUT).json())
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
                            progress['outputs']['images'].append(cast(comfyui_types.ImageFileReference, reference))
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

    def txt2img(self,
                control_image: QImage | comfyui_types.ImageFileReference,
                control_image_refs: dict[str, comfyui_types.ImageFileReference],
                seed: Optional[int] = None) -> comfyui_types.QueueAdditionResponse:
        """Queues an async text-to-image job with the ComfyUI server.

        Most parameters are read directly from the cache, where they should have been written from UI inputs. Calling
        this method will update the LAST_SEED value in the cache.

        Parameters:
        -----------
        control_image_refs: dict[str, comfy_type.ImageFileReference]
            Dictionary tracking already uploaded images that can be reused for ControlNet. Keys use the same format
            as cached ControlNet units:  CONTROLNET_REUSE_IMAGE_CODE for the image generation area content, full file
            paths for all other images.
        control_image: Optional[QImage] = None
            Optional image generation area content, only used if ControlNet is enabled and set to use existing image
            data, and the image isn't already uploaded and tracked in control_image_refs.
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
        self._prepare_controlnet_data(workflow_builder, control_image, control_image_refs)
        prompt = workflow_builder.build_workflow().get_workflow_dict()
        body: comfyui_types.QueueAdditionRequest = {'prompt': prompt, 'client_id': self._client_id}
        res = cast(comfyui_types.QueueAdditionResponse, self.post(ComfyEndpoints.PROMPT, body=body,
                                                                  timeout=DEFAULT_TIMEOUT).json())

        res['seed'] = workflow_builder.seed
        res['uploaded_images'] = control_image_refs
        return res

    def img2img(self, image: QImage | comfyui_types.ImageFileReference,
                control_image_refs: dict[str, comfyui_types.ImageFileReference],
                seed: Optional[int] = None) -> comfyui_types.QueueAdditionResponse:
        """Queues an async image-to-image job with the ComfyUI server.

        Most parameters are read directly from the cache, where they should have been written from UI inputs. Calling
        this method will update theLAST_SEED value in the cache.

        Parameters:
        -----------
        image: QImage | comfy_type.ImageFileReference
            The image to edit. It must be pre-cropped to the generation area or padded inpainting area, and
            pre-scaled to the generation size if necessary.
        control_image_refs: dict[str, comfy_type.ImageFileReference]
            Dictionary tracking already uploaded images that can be reused for ControlNet. Keys use the same format
            as cached ControlNet units:  CONTROLNET_REUSE_IMAGE_CODE for the image generation area content, full file
            paths for all other images.
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
        if CONTROLNET_REUSE_IMAGE_CODE in control_image_refs:
            image_reference = control_image_refs[CONTROLNET_REUSE_IMAGE_CODE]
        else:
            if isinstance(image, dict):
                image_reference = cast(comfyui_types.ImageFileReference, image)
            else:
                image_reference = self.upload_image(image)
            control_image_refs[CONTROLNET_REUSE_IMAGE_CODE] = image_reference
        assert image_reference is not None
        workflow_builder = self._build_diffusion_body(seed)
        workflow_builder.set_source_image_from_reference(image_reference)
        self._prepare_controlnet_data(workflow_builder, image_reference, control_image_refs)
        prompt = workflow_builder.build_workflow().get_workflow_dict()
        body: comfyui_types.QueueAdditionRequest = {'prompt': prompt, 'client_id': self._client_id}
        res = cast(comfyui_types.QueueAdditionResponse, self.post(ComfyEndpoints.PROMPT, body=body,
                                                                  timeout=DEFAULT_TIMEOUT).json())
        res['seed'] = workflow_builder.seed
        res['uploaded_images'] = control_image_refs
        return res

    def inpaint(self, image: QImage | comfyui_types.ImageFileReference,
                mask: QImage | comfyui_types.ImageFileReference,
                control_image_refs: dict[str, comfyui_types.ImageFileReference],
                seed: Optional[int] = None) -> comfyui_types.QueueAdditionResponse:
        """Queues an async inpainting job with the ComfyUI server.

        Most parameters are read directly from the cache, where they should have been written from UI inputs. Calling
        this method will update theLAST_SEED value in the cache.

        Parameters:
        -----------
        image: QImage | comfy_type.ImageFileReference
            The image to inpaint. It must be pre-cropped to the generation area or padded inpainting area, and
            pre-scaled to the generation size if necessary.
        mask: QImage | comfy_type.ImageFileReference
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
        if CONTROLNET_REUSE_IMAGE_CODE in control_image_refs:
            image_reference = control_image_refs[CONTROLNET_REUSE_IMAGE_CODE]
        else:
            if isinstance(image, dict):
                image_reference = cast(comfyui_types.ImageFileReference, image)
            else:
                image_reference = self.upload_image(image)
            control_image_refs[CONTROLNET_REUSE_IMAGE_CODE] = image_reference
        if isinstance(mask, dict):
            mask_reference = cast(comfyui_types.ImageFileReference, mask)
        else:
            mask_reference = self.upload_mask(mask, image_reference)
        workflow_builder = self._build_diffusion_body(seed)
        workflow_builder.set_source_image_from_reference(image_reference)
        workflow_builder.set_mask_from_reference(mask_reference)
        self._prepare_controlnet_data(workflow_builder, image_reference, control_image_refs)
        prompt = workflow_builder.build_workflow().get_workflow_dict()
        body: comfyui_types.QueueAdditionRequest = {'prompt': prompt, 'client_id': self._client_id}
        res = cast(comfyui_types.QueueAdditionResponse, self.post(ComfyEndpoints.PROMPT, body=body,
                                                                  timeout=DEFAULT_TIMEOUT).json())
        res['seed'] = workflow_builder.seed
        res['uploaded_images'] = control_image_refs
        res['uploaded_mask'] = mask_reference
        return res

    def controlnet_preprocessor_preview(self, image: QImage, mask: QImage,
                                        preprocessor: ControlNetPreprocessor) -> comfyui_types.QueueAdditionResponse:
        """Runs a minimal workflow to load a ControlNet preprocessor preview."""
        image_reference = self.upload_image(image) if preprocessor.has_image_input else None
        if image_reference is not None and preprocessor.has_mask_input:
            mask_reference = self.upload_mask(mask, image_reference)
        else:
            mask_reference = None
        workflow_builder = PreprocessorPreviewWorkflowBuilder(preprocessor)
        workflow = workflow_builder.build_workflow(image_reference, mask_reference)
        prompt = workflow.get_workflow_dict()
        body: comfyui_types.QueueAdditionRequest = {'prompt': prompt, 'client_id': self._client_id}
        return cast(comfyui_types.QueueAdditionResponse, self.post(ComfyEndpoints.PROMPT, body=body,
                                                                   timeout=DEFAULT_TIMEOUT).json())

    def interrupt(self, task_id: Optional[str] = None) -> None:
        """Stops the active workflow, and removes a task from the queue if task_id is not None."""
        if task_id is not None:
            queue_removal_body: comfyui_types.QueueDeletionRequest = {
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
