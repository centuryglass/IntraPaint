"""
Accesses the A1111/stable-diffusion-webui through its REST API, providing access to image generation and editing
through stable-diffusion.
"""
import json
import logging
from copy import deepcopy
from typing import Optional, Any, cast, TypedDict

import requests  # type: ignore
from PIL import Image  # type: ignore
from PySide6.QtCore import QByteArray
from PySide6.QtGui import QImage
from requests import Response

from src.api.controlnet.controlnet_category_builder import ControlNetCategoryBuilder
from src.api.controlnet.controlnet_preprocessor import ControlNetPreprocessor
from src.api.webservice import WebService
from src.api.webui.controlnet_webui_constants import (ControlNetModelResponse, ControlNetModuleResponse,
                                                      ControlTypeDef, ControlTypeResponse, CONTROLNET_SCRIPT_KEY)
from src.api.webui.controlnet_webui_utils import get_all_preprocessors
from src.api.webui.diffusion_request_body import DiffusionRequestBody
from src.api.webui.request_formats import UpscalingRequestBody
from src.api.webui.response_formats import GenerationInfoData, ProgressResponseBody, Img2ImgResponse, \
    InterrogateResponse, PromptStyleData, SamplerInfo, UpscalerInfo, ModelInfo, VaeInfo, LoraInfo
from src.api.webui.script_info_types import ScriptRequestData, ScriptResponseData, ScriptInfo
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.ui.modal.login_modal import LoginModal
from src.util.visual.image_utils import image_to_base64, qimage_from_base64

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Identifies login failures."""


class ImageResponse(TypedDict):
    """Defines image generation response format."""
    images: list[QImage]
    info: Optional[GenerationInfoData]


UPSCALE_SCRIPT = 'ultimate sd upscale'
DEFAULT_TIMEOUT = 30
SETTINGS_UPDATE_TIMEOUT = 90


class A1111Webservice(WebService):
    """
    A1111Webservice provides access to the a1111/stable-diffusion-webui through the REST API.
    """

    # noinspection SpellCheckingInspection
    class Endpoints:
        """REST API endpoint constants."""
        OPTIONS = '/sdapi/v1/options'
        REFRESH_CKPT = '/sdapi/v1/refresh-checkpoints'
        REFRESH_VAE = '/sdapi/v1/refresh-vae'
        REFRESH_LORA = '/sdapi/v1/refresh-loras'
        PROGRESS = '/sdapi/v1/progress'
        IMG2IMG = '/sdapi/v1/img2img'
        TXT2IMG = '/sdapi/v1/txt2img'
        UPSCALE = '/sdapi/v1/extra-single-image'
        INTERROGATE = '/sdapi/v1/interrogate'
        INTERRUPT = '/sdapi/v1/interrupt'
        STYLES = '/sdapi/v1/prompt-styles'
        SCRIPTS = '/sdapi/v1/scripts'
        SCRIPT_INFO = '/sdapi/v1/script-info'
        SAMPLERS = '/sdapi/v1/samplers'
        UPSCALERS = '/sdapi/v1/upscalers'
        LATENT_UPSCALE_MODES = '/sdapi/v1/latent-upscale-modes'
        HYPERNETWORKS = '/sdapi/v1/hypernetworks'
        SD_MODELS = '/sdapi/v1/sd-models'
        VAE_MODELS = '/sdapi/v1/sd-vae'
        LORA_MODELS = '/sdapi/v1/loras'
        CONTROLNET_VERSION = '/controlnet/version'
        CONTROLNET_MODELS = '/controlnet/model_list'
        CONTROLNET_MODULES = '/controlnet/module_list'
        CONTROLNET_CONTROL_TYPES = '/controlnet/control_types'
        CONTROLNET_SETTINGS = '/controlnet/settings'
        CONTROLNET_PREVIEW = '/controlnet/detect'
        LOGIN = '/login'
        EXTRA_NW_DATA = '/sd_extra_networks/metadata'
        EXTRA_NW_THUMB = '/sd_extra_networks/thumb'
        EXTRA_NW_CARD = '/sd_extra_networks/card'

    class ForgeEndpoints:
        """REST API endpoint constants (Forge WebUI alternates)"""
        SD_MODULES = '/sdapi/v1/sd-modules'

    def __init__(self, url: str) -> None:
        super().__init__(url)
        self._preprocessor_cache: Optional[list[ControlNetPreprocessor]] = None

    # General utility:
    def login_check(self):
        """Calls the login check endpoint, returning a status 401 response if a login is required."""
        return self.get('/login_check')

    def set_config(self, config_updates: dict) -> None:
        """
        Updates the stable-diffusion-webui configuration.

        Parameters
        ----------
        config_updates: dict
            Maps settings that should change to their updated values. Use the get_settings method's response body
            to check available options.
        """
        self.post(A1111Webservice.Endpoints.OPTIONS, config_updates, timeout=SETTINGS_UPDATE_TIMEOUT).json()

    def refresh_checkpoints(self) -> requests.Response:
        """Requests an updated list of available stable-diffusion models.

        Returns
        -------
        response
            HTTP response with the list of updated stable-diffusion models.
        """
        return self.post(A1111Webservice.Endpoints.REFRESH_CKPT, body={})

    def refresh_vae(self) -> requests.Response:
        """Requests an updated list of available stable-diffusion VAE models.

        VAE models handle the conversion between images and the latent image space. Different VAE models can be used
        to adjust performance and final image quality.


        Returns
        -------
        response
            HTTP response with the list of updated stable-diffusion VAE models.
        """
        return self.post(A1111Webservice.Endpoints.REFRESH_VAE, body={})

    def refresh_loras(self) -> requests.Response:
        """Requests an updated list of available stable-diffusion LoRA models.

        LoRA models augment existing stable-diffusion models, usually to provide support for new concepts, characters,
        or art styles.

        Returns
        -------
        response
            HTTP response with the list of updated stable-diffusion LoRA models.
        """
        return self.post(A1111Webservice.Endpoints.REFRESH_LORA, body={})

    def progress_check(self) -> ProgressResponseBody:
        """Checks the progress of an ongoing image operation."""
        return cast(ProgressResponseBody, self.get(A1111Webservice.Endpoints.PROGRESS, timeout=DEFAULT_TIMEOUT).json())

    # Image manipulation:
    def img2img(self, image: QImage, mask: Optional[QImage] = None,
                request_body: Optional[DiffusionRequestBody] = None) -> ImageResponse:
        """Sends a request to alter an image section using selected parameters.

        Parameters
        ----------
        image: QImage
            Source image to transform. If request_body is not None, and it already has an image, this parameter is
            ignored.
        mask: Optional[QImage] = None
            Optional inpainting mask.  This will also be ignored if request_body is not None, and it already has a mask.
        request_body : Optional[DiffusionRequestBody] = None
            Optional initial request body to use. If None, a new one will be constructed from cache/config parameters.
        Returns
        -------
        ImageResponse
            All generated images, plus accompanying image generation data if available.
        """
        if request_body is None:
            request_body = DiffusionRequestBody()
            request_body.load_data(image, mask)
        else:
            if request_body.init_images is None:
                request_body.init_images = [image_to_base64(image, True)]
            elif len(request_body.init_images) == 0:
                request_body.init_images.append(image_to_base64(image, True))
            if request_body.mask is None and mask is not None:
                request_body.mask = image_to_base64(mask, True)
        res = self.post(A1111Webservice.Endpoints.IMG2IMG, request_body.to_dict())
        return self._handle_image_response(res)

    def txt2img(self, request_body: Optional[DiffusionRequestBody] = None,
                control_image: Optional[QImage] = None) -> ImageResponse:
        """Sends a request to generate new images using selected parameter.

        Parameters
        ----------
        request_body : Optional[DiffusionRequestBody] = None
            Optional initial request body to use. If None, a new one will be constructed from cache/config parameters.
        control_image: Optional[QImage]
            Optional image to use for ControlNet. If request_body is already defined, this will instead be ignored.
        Returns
        -------
        ImageResponse
            All generated images, plus accompanying image generation data if available.
        """
        if request_body is None:
            request_body = DiffusionRequestBody()
            request_body.load_data(image=control_image)
        res = self.post(A1111Webservice.Endpoints.TXT2IMG, request_body.to_dict())
        return self._handle_image_response(res)

    def controlnet_preprocessor_preview(self, image: QImage, mask: Optional[QImage],
                                        preprocessor: ControlNetPreprocessor) -> QImage:
        """Gets a preview image for a ControlNet preprocessor.

        TODO:
        """
        input_images: list[str] = [image_to_base64(image, True)]
        if mask is not None:
            input_images.append(image_to_base64(mask, True))
        body: dict[str, int | float | str | list[str]] = {
            'controlnet_module': preprocessor.name,
            'controlnet_input_images': input_images
        }
        for param in preprocessor.parameters:
            body[param.key] = param.value
        res = self.post(A1111Webservice.Endpoints.CONTROLNET_PREVIEW, body)
        return self._handle_image_response(res)['images'][0]

    def upscale(self,
                image: QImage,
                width: int,
                height: int) -> ImageResponse:
        """Sends a request to upscale an image.

        Parameters
        ----------
        image : QImage
            Source image to upscale, usually the entire image loaded in EditedImage.
        width : int
            New image width in pixels requested.
        height : int
            New image height in pixels requested.
        Returns
        -------
        ImageResponse
            The generated image, plus accompanying image generation data if available.
        """
        config = AppConfig()
        cache = Cache()
        if cache.get(Cache.CONTROLNET_UPSCALING):
            request_body = DiffusionRequestBody()
            request_body.load_data()
            if request_body.alwayson_scripts is None:
                request_body.alwayson_scripts = {}
            controlnet_script_data: ScriptRequestData = {'args': [
                {
                    'module': 'tile_resample',
                    'model': config.get(AppConfig.CONTROLNET_TILE_MODEL),
                    'threshold_a': cache.get(Cache.CONTROLNET_DOWNSAMPLE_RATE)
                }
            ]}
            request_body.alwayson_scripts[CONTROLNET_SCRIPT_KEY] = controlnet_script_data
            request_body.width = width
            request_body.height = height
            request_body.batch_size = 1
            request_body.n_iter = 1
            request_body.add_init_image(image)
            script_list = cache.get(Cache.SCRIPTS_IMG2IMG)
            if UPSCALE_SCRIPT in script_list:
                upscaler = cache.get(Cache.UPSCALE_METHOD)

                upscale_options = [upscaler['name'] for upscaler in self.get_upscalers()]
                if upscaler not in upscale_options:
                    upscaler = upscale_options[0]
                request_body.script_name = UPSCALE_SCRIPT
                request_body.script_args = [
                    None,  # not used
                    cache.get(Cache.GENERATION_SIZE).width(),  # tile width
                    cache.get(Cache.GENERATION_SIZE).height(),  # tile height
                    8,  # mask_blur
                    32,  # padding
                    64,  # seams_fix_width
                    0.35,  # seams_fix_denoise
                    32,  # seams_fix_padding
                    upscale_options.index(upscaler),  # upscaler_index
                    False,  # save_upscaled_image a.k.a Upscaled
                    0,  # redraw_mode (linear)
                    False,  # save_seams_fix_image a.k.a Seams fix
                    8,  # seams_fix_mask_blur
                    0,  # seams_fix_type (none)
                    1,  # target_size_type (use below)
                    width,  # custom_width
                    height,  # custom_height
                    None  # custom_scale (ignored)
                ]
            return self.img2img(image, None, request_body)
        # otherwise, normal upscaling without controlNet:
        body: UpscalingRequestBody = {
            'resize_mode': 1,
            'upscaling_resize_w': width,
            'upscaling_resize_h': height,
            'upscaler_1': cache.get(Cache.UPSCALE_METHOD),
            'image': image_to_base64(image, include_prefix=True)
        }
        res = self.post(A1111Webservice.Endpoints.UPSCALE, body)
        return self._handle_image_response(res)

    def interrogate(self, image: QImage | Image.Image) -> str:
        """Requests text describing an image.

        Parameters
        ----------
        image : PIL Image
            The image to describe.
        Returns
        -------
        str
            A brief description of the image.
        """
        body = {
            'model': AppConfig().get(AppConfig.INTERROGATE_MODEL),
            'image': image_to_base64(image, include_prefix=True)
        }
        res = self.post(A1111Webservice.Endpoints.INTERROGATE, body, timeout=60).json()
        if isinstance(res, dict):
            res = cast(InterrogateResponse, res)
            return res['caption']
        assert isinstance(res, str)
        return res

    def interrupt(self) -> dict:
        """
        Attempts to interrupt an ongoing image operation, returning a dict from the response body indicating the
        result.
        """
        res = self.post(A1111Webservice.Endpoints.INTERRUPT, body={})
        return res.json()

    @staticmethod
    def _handle_image_response(res: Response) -> ImageResponse:
        if res.status_code != 200:
            raise RuntimeError(res.json())
        res_body = cast(Img2ImgResponse, res.json())
        info = res_body['info'] if 'info' in res_body else None
        images = []
        if 'images' in res_body:
            for image in res_body['images']:
                images.append(qimage_from_base64(image))
        if isinstance(info, str):
            try:
                info_data: Optional[GenerationInfoData] = cast(GenerationInfoData, json.loads(info))
            except json.JSONDecodeError:
                logger.error(f'Image response info not valid JSON, got {info}')
                info_data = None
        else:
            info_data = cast(GenerationInfoData, info)
        image_response: ImageResponse = {
            'images': images,
            'info': info_data
        }
        return image_response

    # Load misc. service info:
    def get_config(self) -> dict[str, Any]:
        """Returns a dict containing the current Stable-Diffusion-WebUI configuration."""
        return self.get('/sdapi/v1/options', timeout=DEFAULT_TIMEOUT).json()

    def get_styles(self) -> list[PromptStyleData]:
        """Returns a list of image generation style objects saved by the Stable-Diffusion-WebUI."""
        res_body = self.get(A1111Webservice.Endpoints.STYLES).json()
        all_styles: list[PromptStyleData] = []
        for serialized_style in res_body:
            all_styles.append(cast(PromptStyleData, json.dumps(serialized_style)))
        return all_styles

    def get_scripts(self) -> ScriptResponseData:
        """Returns available scripts installed to the stable-diffusion-webui.
        Returns
        -------
        dict
            Response will have 'txt2img' and 'img2img' keys, each holding a list of scripts available for that mode.
        """
        return cast(ScriptResponseData, self.get(A1111Webservice.Endpoints.SCRIPTS).json())

    def get_script_info(self) -> list[ScriptInfo]:
        """Returns information on expected script parameters
        Returns
        -------
        list of dict
            Objects defining all parameters required by each script.
        """
        return cast(list[ScriptInfo], self.get(A1111Webservice.Endpoints.SCRIPT_INFO).json())

    def _get_name_list(self, endpoint: str) -> list[str]:
        res_body = self.get(endpoint, timeout=30).json()
        return [obj['name'] for obj in res_body]

    def get_samplers(self) -> list[SamplerInfo]:
        """Returns the list of image sampler algorithms available for image generation."""
        return cast(list[SamplerInfo], self.get(A1111Webservice.Endpoints.SAMPLERS, timeout=DEFAULT_TIMEOUT).json())

    def get_upscalers(self) -> list[UpscalerInfo]:
        """Returns the list of image upscalers available."""
        return cast(list[UpscalerInfo], self.get(A1111Webservice.Endpoints.UPSCALERS, timeout=DEFAULT_TIMEOUT).json())

    def get_latent_upscale_modes(self) -> list[str]:
        """Returns the list of stable-diffusion enhanced upscaling modes."""
        return self._get_name_list(A1111Webservice.Endpoints.LATENT_UPSCALE_MODES)

    def get_hypernetworks(self) -> list[str]:
        """Returns the list of hypernetworks available.

        Hypernetworks are a simpler form of model for augmenting full stable-diffusion models. Each hypernetwork
        introduces a single style or concept.
        """
        return self._get_name_list(A1111Webservice.Endpoints.HYPERNETWORKS)

    def get_models(self) -> list[ModelInfo]:
        """Returns the list of available stable-diffusion models cached by the webui.

        If available models may have changed, instead consider using the slower refresh_checkpoints method.
        """
        return cast(list[ModelInfo], self.get(A1111Webservice.Endpoints.SD_MODELS, timeout=DEFAULT_TIMEOUT).json())

    def get_vae(self) -> list[VaeInfo]:
        """Returns the list of available stable-diffusion VAE models cached by the webui.

        If available models may have changed, instead consider using the slower refresh_vae method.
        """
        try:
            vae_models = self.get(A1111Webservice.Endpoints.VAE_MODELS, timeout=DEFAULT_TIMEOUT).json()
        except RuntimeError:
            vae_models = self.get(A1111Webservice.ForgeEndpoints.SD_MODULES, timeout=DEFAULT_TIMEOUT).json()
        return cast(list[VaeInfo], vae_models)

    def get_controlnet_version(self) -> int:
        """
        Returns the installed version of the stable-diffusion ControlNet extension, or raises if the exception is not
        installed.
        """
        return self.get(A1111Webservice.Endpoints.CONTROLNET_VERSION, timeout=DEFAULT_TIMEOUT).json()['version']

    def get_controlnet_models(self) -> ControlNetModelResponse:
        """Returns a dict defining the models available to the stable-diffusion ControlNet extension."""
        return cast(ControlNetModelResponse,
                    self.get(A1111Webservice.Endpoints.CONTROLNET_MODELS, timeout=DEFAULT_TIMEOUT).json())

    def get_controlnet_modules(self) -> ControlNetModuleResponse:
        """Returns a dict defining the modules available to the stable-diffusion ControlNet extension."""
        return cast(ControlNetModuleResponse,
                    self.get(A1111Webservice.Endpoints.CONTROLNET_MODULES, timeout=DEFAULT_TIMEOUT).json())

    def get_controlnet_control_types(self) -> ControlTypeResponse:
        """Returns a dict defining the control types available to the stable-diffusion ControlNet extension."""
        return cast(ControlTypeResponse, self.get(A1111Webservice.Endpoints.CONTROLNET_CONTROL_TYPES,
                                                  timeout=DEFAULT_TIMEOUT).json())

    def get_controlnet_settings(self) -> dict[str, Any]:
        """Returns the current settings applied to the stable-diffusion ControlNet extension."""
        return self.get(A1111Webservice.Endpoints.CONTROLNET_SETTINGS, timeout=DEFAULT_TIMEOUT).json()

    def get_controlnet_preprocessors(self, update_cache=False) -> list[ControlNetPreprocessor]:
        """Queries the API for ControlNet preprocessor modules, and parameterizes and returns all options."""
        if update_cache or self._preprocessor_cache is None:
            modules = cast(ControlNetModuleResponse, self.get_controlnet_modules())
            module_names = modules['module_list']
            module_details = None if 'module_details' not in modules else modules['module_details']
            self._preprocessor_cache = get_all_preprocessors(module_names, module_details)
        return deepcopy(self._preprocessor_cache)

    def get_controlnet_type_categories(self) -> dict[str, ControlTypeDef]:
        """Gets the set of valid ControlNet proeprocessor/model categories, taking into account available options and
           API category definitions if possible."""
        modules = cast(ControlNetModuleResponse, self.get_controlnet_modules())
        models = self.get_controlnet_models()
        try:
            control_type_defs: Optional[dict[str, str]] = cast(dict[str, str], self.get_controlnet_control_types())
        except (KeyError, RuntimeError):
            control_type_defs = None
        preprocessor_names = modules['module_list']
        model_names = models['model_list']
        control_type_builder = ControlNetCategoryBuilder(preprocessor_names, model_names, control_type_defs)
        return control_type_builder.get_control_types()

    def get_loras(self) -> list[LoraInfo]:
        """Returns the list of available stable-diffusion LoRA models cached by the webui.

        If available models may have changed, instead consider using the slower refresh_loras method.
        """
        return cast(list[LoraInfo], self.get(A1111Webservice.Endpoints.LORA_MODELS, timeout=DEFAULT_TIMEOUT).json())

    def get_thumbnail(self, file_path: str) -> Optional[QImage]:
        """Attempts to load one of the extra model thumbnails given a path parameter."""
        try:
            res = self.get(A1111Webservice.Endpoints.EXTRA_NW_THUMB, timeout=DEFAULT_TIMEOUT,
                           url_params={'filename': file_path})
            if not res.ok:
                return None
            image_bytes = QByteArray(res.content)
            image = QImage.fromData(image_bytes)
            return image
        except (RuntimeError, IOError) as err:
            logger.error(f'Failed to load thumbnail "{file_path}": {err}')
            return None

    def login(self, username: str, password: str) -> requests.Response:
        """Attempt to log in with a username and password."""
        body = {'username': username, 'password': password}
        return self.post(A1111Webservice.Endpoints.LOGIN, body, 'x-www-form-urlencoded',
                         timeout=DEFAULT_TIMEOUT,
                         throw_on_failure=False)

    def _handle_auth_error(self):
        login_modal = LoginModal(self.login)
        auth = None
        while auth is None:
            try:
                auth = login_modal.show_login_modal()
            except RuntimeError:
                auth = None
            if login_modal.get_login_response() is None:
                logger.info('Login aborted')
                raise AuthError()
        self.set_auth(auth)
