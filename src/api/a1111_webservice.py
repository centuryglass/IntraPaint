"""
Accesses the A1111/stable-diffusion-webui through its REST API, providing access to image generation and editing
through stable-diffusion.
"""
from typing import Optional, List, Dict, Any
import json
import os
import io
import sys
import requests
from PIL import Image
from requests import Response

from src.api.webservice import WebService
from src.util.image_utils import load_image_from_base64, image_to_base64
from src.config.application_config import AppConfig
from src.ui.modal.login_modal import LoginModal


class A1111Webservice(WebService):
    """
    A1111Webservice provides access to the a1111/stable-diffusion-webui through the REST API.
    """

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
        LOGIN = '/login'

    class ImgParams:
        """Image generation body key constants."""
        INIT_IMAGES = 'init_images'
        DENOISING = 'denoising_strength'
        WIDTH = 'width'
        HEIGHT = 'height'
        MASK = 'mask'
        MASK_BLUR = 'mask_blur'
        MASK_INVERT = 'inpainting_mask_invert'
        INPAINT_FILL = 'inpainting_fill'
        INPAINT_FULL_RES = 'inpaint_full_res'
        INPAINT_FULL_RES_PADDING = 'inpaint_full_res_padding'
        PROMPT = 'prompt'
        NEGATIVE = 'negative_prompt'
        SEED = 'seed'
        BATCH_SIZE = 'batch_size'
        BATCH_COUNT = 'n_iter'
        STEPS = 'steps'
        CFG_SCALE = 'cfg_scale'
        RESTORE_FACES = 'restore_faces'
        TILING = 'tiling'
        OVERRIDE_SETTINGS = 'override_settings'
        SAMPLER_IDX = 'sampler_index'
        ALWAYS_ON_SCRIPTS = 'alwayson_scripts'

    # General utility:
    def login_check(self):
        """Calls the login check endpoint, returning a status 401 response if a login is required."""
        return self.get('/login_check')

    def set_config(self, config_updates: dict) -> requests.Response:
        """
        Updates the stable-diffusion-webui configuration.

        Parameters
        ----------
        config_updates: dict
            Maps settings that should change to their updated values. Use the get_settings method's response body
            to check available options.
        """
        return self.post(A1111Webservice.Endpoints.OPTIONS, config_updates, timeout=30).json()

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
        """Requests an updated list of available stable-diffusion LORA models.

        LORA models augment existing stable-diffusion models, usually to provide support for new concepts, characters,
        or art styles.

        Returns
        -------
        response
            HTTP response with the list of updated stable-diffusion LORA models.
        """
        return self.post(A1111Webservice.Endpoints.REFRESH_LORA, body={})

    def progress_check(self) -> dict:
        """Checks the progress of an ongoing image operation.

        Returns
        -------
        dict
            An HTTP response body with 'current_image', 'progress', and 'eta_relative' properties
        """
        return self.get(A1111Webservice.Endpoints.PROGRESS).json()

    # Image manipulation:
    def img2img(self,
                image: Image.Image,
                config: AppConfig,
                mask: Optional[Image.Image] = None,
                width: Optional[int] = None,
                height: Optional[int] = None,
                overrides: Optional[dict] = None,
                scripts: Optional[Dict[str, Any]] = None) -> Response | tuple[List[Image.Image], Dict[str, Any] | None]:
        """Starts a request to alter an image section using selected parameters.

        Parameters
        ----------
        image : PIL Image
            Source image, usually contents of the EditedImage selection.
        config : AppConfig
            Object holding image generation parameters.
        mask : PIL Image, optional
            A 1-bit image mask that's the same size as the image parameter, used to mark which areas should be altered.
            If not provided, the entire image will be altered.
        width : int, optional
            Generated image width requested, in pixels. If not provided, width of the image parameter is used.
        height : int, optional
            Generated image height requested, in pixels. If not provided, height of the image parameter is used.
        overrides : dict, optional
            A dict of request body parameters that should override parameters derived from the config.
        scripts : list, optional
            Array of parameters to add to the request that will trigger stable-diffusion-webui scripts or extensions.
        Returns
        -------
        list of PIL Images
            All images returned in the API response
        dict or None
            Any additional information sent back with the generated images.
        """
        body = self._get_base_diffusion_body(config, image, scripts)
        body[A1111Webservice.ImgParams.INIT_IMAGES] = [image_to_base64(image, include_prefix=True)]
        body[A1111Webservice.ImgParams.DENOISING] = config.get(AppConfig.DENOISING_STRENGTH)
        body[A1111Webservice.ImgParams.WIDTH] = image.width if width is None else width
        body[A1111Webservice.ImgParams.HEIGHT] = image.height if height is None else height
        if mask is not None:
            body[A1111Webservice.ImgParams.MASK] = image_to_base64(mask, include_prefix=True)
            body[A1111Webservice.ImgParams.MASK_BLUR] = config.get(AppConfig.MASK_BLUR)
            body[A1111Webservice.ImgParams.INPAINT_FILL] = config.get_option_index(AppConfig.MASKED_CONTENT)
            body[A1111Webservice.ImgParams.MASK_INVERT] = 0  # Don't invert
            body[A1111Webservice.ImgParams.INPAINT_FULL_RES] = config.get(AppConfig.INPAINT_FULL_RES)
            body[A1111Webservice.ImgParams.INPAINT_FULL_RES_PADDING] = config.get(AppConfig.INPAINT_FULL_RES_PADDING)
        if overrides is not None:
            for key in overrides:
                body[key] = overrides[key]
        res = self.post(A1111Webservice.Endpoints.IMG2IMG, body)
        return self._handle_image_response(res)

    def txt2img(self,
                config: AppConfig,
                width: Optional[int] = None,
                height: Optional[int] = None,
                scripts: Optional[Dict[str, Any]] = None,
                image: Optional[Image.Image] = None) -> Response | tuple[List[Image.Image], Dict[str, Any] | None]:
        """Starts a request to generate new images using selected parameters.

        Parameters
        ----------
        config : AppConfig
            Object holding image generation parameters.
        width : int, optional
            Generated image width requested, in pixels.
        height : int, optional
            Generated image height requested, in pixels.
        scripts : list, optional
            Array of parameters to add to the request that will trigger stable-diffusion-webui scripts or extensions.
        image: PIL Image, optional
            If scripts use an image to augment image generation, it should be provided through this parameter.
        Returns
        -------
        list of PIL Images
            All images returned in the API response
        dict or None
            Any additional information sent back with the generated images.
        """
        body = self._get_base_diffusion_body(config, image, scripts)
        body[A1111Webservice.ImgParams.WIDTH] = width
        body[A1111Webservice.ImgParams.HEIGHT] = height
        res = self.post(A1111Webservice.Endpoints.TXT2IMG, body)
        return self._handle_image_response(res)

    def upscale(self,
                image: Image.Image,
                width: int,
                height: int,
                config: AppConfig) -> Response | tuple[List[Image.Image], Dict[str, Any] | None]:
        """Starts a request to upscale an image.

        Parameters
        ----------
        image : PIL Image
            Source image to upscale, usually the entire image loaded in EditedImage.
        width : int
            New image width in pixels requested.
        height : int
            New image height in pixels requested.
        config : AppConfig
            Object holding additional upscaling parameters.
        Returns
        -------
        list of PIL Images
            All images returned in the API response
        dict or None
            Any additional information sent back with the generated images.
        """
        if config.get(AppConfig.CONTROLNET_UPSCALING):
            scripts = {
                'controlNet': {
                    'args': [{
                        'module': 'tile_resample',
                        'model': config.get(AppConfig.CONTROLNET_TILE_MODEL),
                        'threshold_a': config.get(AppConfig.CONTROLNET_DOWNSAMPLE_RATE)
                    }]
                }
            }
            overrides = {
                'width': width,
                'height': height,
                'batch_size': 1,
                'n_iter': 1
            }
            upscaler = config.get(AppConfig.UPSCALE_METHOD)
            if upscaler != 'None':
                overrides['script_name'] = 'ultimate sd upscale'
                overrides['script_args'] = [
                    None,  # not used
                    config.get(AppConfig.GENERATION_SIZE).width(),  # tile width
                    config.get(AppConfig.GENERATION_SIZE).height(),  # tile height
                    8,  # mask_blur
                    32,  # padding
                    64,  # seams_fix_width
                    0.35,  # seams_fix_denoise
                    32,  # seams_fix_padding
                    config.get_options(AppConfig.UPSCALE_METHOD).index(upscaler),  # upscaler_index
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
            return self.img2img(image, config, width=width, height=height, overrides=overrides, scripts=scripts)
        # otherwise, normal upscaling without controlNet:
        body = {
            'resize_mode': 1,
            'upscaling_resize_w': width,
            'upscaling_resize_h': height,
            'upscaler_1': config.get(AppConfig.UPSCALE_METHOD),
            'image': image_to_base64(image, include_prefix=True)
        }
        res = self.post(A1111Webservice.Endpoints.UPSCALE, body)
        return self._handle_image_response(res)

    def interrogate(self, config: AppConfig, image: Image.Image) -> str:
        """Requests text describing an image.

        Parameters
        ----------
        config : AppConfig
            Object defining which image captioning model should be used.
        image : PIL Image
            The image to describe.
        Returns
        -------
        str
            A brief description of the image.
        """
        body = {
            'model': config.get(AppConfig.INTERROGATE_MODEL),
            'image': image_to_base64(image, include_prefix=True)
        }
        res = self.post(A1111Webservice.Endpoints.INTERROGATE, body)
        return res.json()['caption']

    def interrupt(self) -> dict:
        """
        Attempts to interrupt an ongoing image operation, returning a dict from the response body indicating the
        result.
        """
        res = self.post(A1111Webservice.Endpoints.INTERRUPT, body={})
        return res.json()

    @staticmethod
    def _get_base_diffusion_body(config: AppConfig,
                                 image: Optional[Image.Image] = None,
                                 scripts: Optional[dict] = None) -> dict:
        body = {
            A1111Webservice.ImgParams.PROMPT: config.get(AppConfig.PROMPT),
            A1111Webservice.ImgParams.SEED: config.get(AppConfig.SEED),
            A1111Webservice.ImgParams.BATCH_SIZE: config.get(AppConfig.BATCH_SIZE),
            A1111Webservice.ImgParams.BATCH_COUNT: config.get(AppConfig.BATCH_COUNT),
            A1111Webservice.ImgParams.STEPS: config.get(AppConfig.SAMPLING_STEPS),
            A1111Webservice.ImgParams.CFG_SCALE: config.get(AppConfig.GUIDANCE_SCALE),
            A1111Webservice.ImgParams.RESTORE_FACES: config.get(AppConfig.RESTORE_FACES),
            A1111Webservice.ImgParams.TILING: config.get(AppConfig.TILING),
            A1111Webservice.ImgParams.NEGATIVE: config.get(AppConfig.NEGATIVE_PROMPT),
            A1111Webservice.ImgParams.OVERRIDE_SETTINGS: {},
            A1111Webservice.ImgParams.SAMPLER_IDX: config.get(AppConfig.SAMPLING_METHOD),
            A1111Webservice.ImgParams.ALWAYS_ON_SCRIPTS: {}
        }
        controlnet = dict(config.get(AppConfig.CONTROLNET_ARGS_0))
        if len(controlnet) > 0 and 'model' in controlnet:
            if 'image' in controlnet:
                if controlnet['image'] == 'SELECTION' and image is not None:
                    controlnet['image'] = image_to_base64(image, include_prefix=True)
                elif os.path.exists(controlnet['image']):
                    try:
                        controlnet['image'] = image_to_base64(controlnet['image'], include_prefix=True)
                    except (IOError, KeyError) as err:
                        print(f"Error loading controlnet image {controlnet['image']}: {err}")
                        del controlnet['image']
                else:
                    del controlnet['image']
                empty_keys = [k for k in controlnet.keys() if controlnet[k] is None]
                for empty_key in empty_keys:
                    del controlnet[empty_key]
            if scripts is None:
                scripts = {}
            if 'controlNet' not in scripts:
                scripts['controlNet'] = {'args': []}
            scripts['controlNet']['args'].append(controlnet)
        if scripts is not None:
            body['alwayson_scripts'] = scripts
        return body

    def _handle_image_response(self, res: Response) -> Response | tuple[List[Image.Image], Dict[str, Any] | None]:
        if res.status_code != 200:
            return res
        res_body = res.json()
        info = res_body['info'] if 'info' in res_body else None
        images = []
        if 'image' in res_body:
            images.append(load_image_from_base64(res_body['image']))
        if 'images' in res_body:
            for image in res_body['images']:
                if isinstance(image, dict):
                    if not image['is_file'] and image['data'] is not None:
                        images.append(image['data'])
                    else:
                        file_path = image['name']
                        res = self.get(f'/file={file_path}')
                        res.raise_for_status()
                        buffer = io.BytesIO()
                        buffer.write(res.content)
                        buffer.seek(0)
                        images.append(Image.open(buffer))
                elif isinstance(image, str):
                    images.append(load_image_from_base64(image))
        return images, info

    # Load misc. service info:
    def get_config(self) -> dict:
        """Returns a dict containing the current Stable-Diffusion-WebUI configuration."""
        return self.get('/sdapi/v1/options', timeout=30).json()

    def get_styles(self) -> list:
        """Returns a list of image generation style objects saved by the Stable-Diffusion-WebUI.
        Returns
        -------
        list of dict
            Styles will have 'name', 'prompt', and 'negative_prompt' keys.
        """
        res_body = self.get(A1111Webservice.Endpoints.STYLES).json()
        return [json.dumps(s) for s in res_body]

    def get_scripts(self) -> dict:
        """Returns available scripts installed to the stable-diffusion-webui.
        Returns
        -------
        dict
            Response will have 'txt2img' and 'img2img' keys, each holding a list of scripts available for that mode.
        """
        return self.get(A1111Webservice.Endpoints.SCRIPTS).json()

    def get_script_info(self) -> list[dict]:
        """Returns information on expected script parameters
        Returns
        -------
        list of dict
            Objects defining all parameters required by each script.
        """
        return self.get(A1111Webservice.Endpoints.SCRIPT_INFO).json()

    def _get_name_list(self, endpoint: str) -> list[str]:
        res_body = self.get(endpoint, timeout=30).json()
        return [obj['name'] for obj in res_body]

    def get_samplers(self) -> list[str]:
        """Returns the list of image sampler algorithms available for image generation."""
        return self._get_name_list(A1111Webservice.Endpoints.SAMPLERS)

    def get_upscalers(self) -> list[str]:
        """Returns the list of image upscalers available."""
        return self._get_name_list(A1111Webservice.Endpoints.UPSCALERS)

    def get_latent_upscale_modes(self) -> list[str]:
        """Returns the list of stable-diffusion enhanced upscaling modes."""
        return self._get_name_list(A1111Webservice.Endpoints.LATENT_UPSCALE_MODES)

    def get_hypernetworks(self) -> list[str]:
        """Returns the list of hypernetworks available.

        Hypernetworks are a simpler form of model for augmenting full stable-diffusion models. Each hypernetwork
        introduces a single style or concept.
        """
        return self._get_name_list(A1111Webservice.Endpoints.HYPERNETWORKS)

    def get_models(self) -> list[dict]:
        """Returns the list of available stable-diffusion models cached by the webui.

        If available models may have changed, instead consider using the slower refresh_checkpoints method.
        """
        return self.get(A1111Webservice.Endpoints.SD_MODELS, timeout=30).json()

    def get_vae(self) -> list[dict]:
        """Returns the list of available stable-diffusion VAE models cached by the webui.

        If available models may have changed, instead consider using the slower refresh_vae method.
        """
        return self.get(A1111Webservice.Endpoints.VAE_MODELS, timeout=30).json()

    def get_controlnet_version(self) -> int:
        """
        Returns the installed version of the stable-diffusion ControlNet extension, or raises if the exception is not
        installed.
        """
        return self.get(A1111Webservice.Endpoints.CONTROLNET_VERSION, timeout=30).json()['version']

    def get_controlnet_models(self) -> dict:
        """Returns a dict defining the models available to the stable-diffusion ControlNet extension."""
        return self.get(A1111Webservice.Endpoints.CONTROLNET_MODELS, timeout=30).json()

    def get_controlnet_modules(self) -> dict:
        """Returns a dict defining the modules available to the stable-diffusion ControlNet extension."""
        return self.get(A1111Webservice.Endpoints.CONTROLNET_MODULES, timeout=30).json()

    def get_controlnet_control_types(self) -> dict:
        """Returns a dict defining the control types available to the stable-diffusion ControlNet extension."""
        return self.get(A1111Webservice.Endpoints.CONTROLNET_CONTROL_TYPES, timeout=30).json()['control_types']

    def get_controlnet_settings(self) -> dict:
        """Returns the current settings applied to the stable-diffusion ControlNet extension."""
        return self.get(A1111Webservice.Endpoints.CONTROLNET_SETTINGS, timeout=30).json()

    def get_loras(self) -> list:
        """Returns the list of available stable-diffusion LORA models cached by the webui.

        If available models may have changed, instead consider using the slower refresh_loras method.
        """
        return self.get(A1111Webservice.Endpoints.LORA_MODELS, timeout=30).json()

    def login(self, username: str, password: str) -> requests.Response:
        """Attempt to log in with a username and password."""
        body = {'username': username, 'password': password}
        return self.post(A1111Webservice.Endpoints.LOGIN, body, 'x-www-form-urlencoded', timeout=30,
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
                print('Login aborted, exiting')
                sys.exit()
        self.set_auth(auth)