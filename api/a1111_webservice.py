"""
Accesses the A1111/stable-diffusion-webui through its REST API, providing access to image generation and editing
through stable-diffusion.
"""
import json
import os
import io
import sys
from PIL import Image
from api.webservice import WebService
from startup.utils import image_to_base64, load_image_from_base64

class A1111Webservice(WebService):
    """
    A1111Webservice provides access to the a1111/stable-diffusion-webui through the REST API.
    """

    # General utility:
    def login_check(self):
        """Calls the login check endpoint, returning a status 401 response if a login is required."""
        return self.get('/login_check')


    def set_config(self, config_updates):
        """
        Updates the stable-diffusion-webui configuration.

        Parameters
        ----------
        config_updates: dict
            Maps settings that should change to their updated values. Use the get_settings method's response body
            to check available options.
        """
        return self.post('/sdapi/v1/options', config_updates, timeout=30).json()


    def refresh_checkpoints(self):
        """Requests an updated list of available stable-diffusion models.

        Returns
        -------
        response
            HTTP response with the list of updated stable-diffusion models.
        """
        return self.post('/sdapi/v1/refresh-checkpoints')


    def refresh_vae(self):
        """Requests an updated list of available stable-diffusion VAE models.

        VAE models handle the conversion between images and the latent image space. Different VAE models can be used
        to adjust performance and final image quality.


        Returns
        -------
        response
            HTTP response with the list of updated stable-diffusion VAE models.
        """
        return self.post('/sdapi/v1/refresh-vae')


    def refresh_loras(self):
        """Requests an updated list of available stable-diffusion LORA models.

        LORA models augment existing stable-diffusion models, usually to provide support for new concepts, characters,
        or art styles.

        Returns
        -------
        response
            HTTP response with the list of updated stable-diffusion LORA models.
        """
        return self.post('/sdapi/v1/refresh-loras')


    def progress_check(self):
        """Checks the progress of an ongoing image operation.

        Returns
        -------
        dict
            An HTTP response body with 'current_image', 'progress', and 'eta_relative' properties
        """
        return self.get('/sdapi/v1/progress').json()


    # Image manipulation:
    def img2img(self, image, config, mask=None, width=None, height=None, overrides=None, scripts=None):
        """Starts a request to alter an image section using selected parameters.

        Parameters
        ----------
        image : PIL Image
            Image to alter, usually contents of the EditedImage selection.
        config : Config
            data_model.Config object holding image generation parameters.
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
        body['init_images'] = [ image_to_base64(image, include_prefix=True) ]
        body['denoising_strength'] = config.get('denoising_strength')
        body['width'] = image.width if width is None else width
        body['height'] = image.height if height is None else height
        if mask is not None:
            body['mask'] = image_to_base64(mask, include_prefix=True)
            body['mask_blur'] = config.get('mask_blur')
            body['inpainting_fill'] = config.get_option_index('masked_content')
            body['inpainting_mask_invert'] = 0 #Don't invert
            body['inpaint_full_res'] = config.get('inpaint_full_res')
            body['inpaint_full_res_padding'] = config.get('inpaint_full_res_padding')
        if overrides is not None:
            for key in overrides:
                body[key] = overrides[key]
        res = self.post('/sdapi/v1/img2img', body)
        return self._handle_image_response(res)


    def txt2img(self, config, width, height, scripts=None, image=None):
        """Starts a request to generate new images using selected parameters.

        Parameters
        ----------
        config : Config
            data_model.Config object holding image generation parameters.
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
        #scripts = {
        #    'cfg rescale extension': {
        #        'args': [
        #            0.7,  #CFG Rescale
        #            True, #Auto color fix
        #            1.0,  #Fix strength
        #            False #Keep original
        #        ]
        #    }
        #}
        body = self._get_base_diffusion_body(config, image, scripts)
        body['width'] = width
        body['height'] = height
        res = self.post('/sdapi/v1/txt2img', body)
        return self._handle_image_response(res)


    def upscale(self, image, width, height, config):
        """Starts a request to upscale an image.

        Parameters
        ----------
        image : PIL Image
            Image to upscale, usually the entire image loaded in EditedImage.
        width : int
            New image width in pixels requested.
        height : int
            New image height in pixels requested.
        config : Config
            data_model.Config object holding additional upscaling parameters.
        Returns
        -------
        list of PIL Images
            All images returned in the API response
        dict or None
            Any additional information sent back with the generated images.
        """
        if config.get('controlnet_upscaling'):
            scripts = {
                'controlNet': {
                    'args': [{
                        "module": "tile_resample",
                        "model": config.get('controlnet_tile_model'),
                        "threshold_a": config.get('controlnet_downsample_rate')
                    }]
                }
            }
            overrides = {
                'width': width,
                'height': height,
                'batch_size': 1,
                'n_iter': 1
            }
            upscaler = config.get('upscale_method')
            if upscaler != "None":
                overrides['script_name'] = 'ultimate sd upscale'
                overrides['script_args'] = [
                    None, # not used
                    config.get('edit_size').width(), #tile width
                    config.get('edit_size').height(), #tile height
                    8, # mask_blur
                    32, # padding
                    64, # seams_fix_width
                    0.35, # seams_fix_denoise
                    32, # seams_fix_padding
                    config.get_options('upscale_method').index(upscaler), # upscaler_index
                    False, # save_upscaled_image a.k.a Upscaled
                    0, # redraw_mode (linear)
                    False, # save_seams_fix_image a.k.a Seams fix
                    8, # seams_fix_mask_blur
                    0, # seams_fix_type (none)
                    1, # target_size_type (use below)
                    width, # custom_width
                    height, # custom_height
                    None # custom_scale (ignored)
                ]
            return self.img2img(image, config, width=width, height=height, overrides=overrides, scripts=scripts)
        # otherwise, normal upscaling without controlNet:
        body = {
            'resize_mode': 1,
            'upscaling_resize_w': width,
            'upscaling_resize_h': height,
            'upscaler_1': config.get('upscale_method'),
            'image': image_to_base64(image, include_prefix=True)
        }
        res = self.post('/sdapi/v1/extra-single-image', body)
        return self._handle_image_response(res)


    def interrogate(self, config, image):
        """Requests text describing an image.

        Parameters
        ----------
        config : Config
            data_model.Config object defining which image captioning model should be used.
        image : PIL Image
            The image to describe.
        Returns
        -------
        str
            A brief description of the image.
        """
        body = {
            'model': config.get('interrogate_model'),
            'image': image_to_base64(image, include_prefix=True)
        }
        res = self.post('/sdapi/v1/interrogate', body)
        return res.json()['caption']


    def interrupt(self):
        """
        Attempts to interrupt an ongoing image operation, returning a dict from the response body indicating the
        result.
        """
        res = self.post('/sdapi/v1/interrupt')
        return res.json()


    def _get_base_diffusion_body(self, config, image = None, scripts = None):
        body = {
            'prompt': config.get('prompt'),
            'seed': config.get('seed'),
            'batch_size': config.get('batch_size'),
            'n_iter': config.get('batch_count'),
            'steps': config.get('sampling_steps'),
            'cfg_scale': config.get('guidance_scale'),
            'restore_faces': config.get('restore_faces'),
            'tiling': config.get('tiling'),
            'negative_prompt': config.get('negative_prompt'),
            'override_settings': {},
            'sampler_index': config.get('sampling_method'),
            'alwayson_scripts': {}
        }
        controlnet = dict(config.get("controlnet_args_0"))
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
            if scripts is None:
                scripts = {}
            if 'controlNet' not in scripts:
                scripts['controlNet'] = { 'args': [] }
            scripts['controlNet']['args'].append(controlnet)
        if scripts is not None:
            body['alwayson_scripts'] = scripts
        return body


    def _handle_image_response(self, res):
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
                        image = image['data']
                    else:
                        file_path = image['name']
                        res = self.get(f"/file={file_path}")
                        res.raise_for_status()
                        buffer = io.BytesIO()
                        buffer.write(res.content)
                        buffer.seek(0)
                        images.append(Image.open(buffer))
                elif isinstance(image, str):
                    images.append(load_image_from_base64(image))
        #print(f"A1111 webservice returned {len(images)} images")
        return images, info


    # Load misc. service info:
    def get_config(self):
        """Returns a dict containing the stable-diffusion-webui's current configuration.
        """
        return self.get('/sdapi/v1/options', timeout=30).json()


    def get_styles(self):
        """Returns a list of image generation style objects saved by the stable-diffusion-webui.
        Returns
        -------
        list of dict
            Styles will have 'name', 'prompt', and 'negative_prompt' keys.
        """
        res_body = self.get('/sdapi/v1/prompt-styles').json()
        return [json.dumps(s) for s in res_body]


    def get_scripts(self):
        """Returns available scripts installed to the stable-diffusion-webui.
        Returns
        -------
        dict
            Response will have 'txt2img' and 'img2img' keys, each holding a list of scripts avaliable for that mode.
        """
        return self.get('/sdapi/v1/scripts').json()


    def get_script_info(self):
        """Returns information on expected script parameters
        Returns
        -------
        list of dict
            Objects defining all parameters required by each script.
        """
        return self.get('/sdapi/v1/script-info').json()


    def _get_name_list(self, endpoint):
        res_body = self.get(endpoint, timeout=30).json()
        return [obj['name'] for obj in res_body]


    def get_samplers(self):
        """Returns the list of image sampler algorithms available for image generation."""
        return self._get_name_list('/sdapi/v1/samplers')


    def get_upscalers(self):
        """Returns the list of image upscalers available."""
        return self._get_name_list('/sdapi/v1/upscalers')


    def get_latent_upscale_modes(self):
        """Returns the list of stable-diffusion enhanced upscaling modes."""
        return self._get_name_list('/sdapi/v1/latent-upscale-modes')


    def get_hypernetworks(self):
        """Returns the list of hypernetworks available.

        Hypernetworks are a simpler form of model for augmenting full stable-diffusion models. Each hypernetwork
        introduces a single style or concept.
        """
        return self._get_name_list('/sdapi/v1/hypernetworks')


    def get_models(self):
        """Returns the list of available stable-diffusion models cached by the webui.

        If available models may have changed, instead consider using the slower refresh_checkpoints method.
        """
        return self.get('/sdapi/v1/sd-models', timeout=30).json()


    def get_vae(self):
        """Returns the list of available stable-diffusion VAE models cached by the webui.

        If available models may have changed, instead consider using the slower refresh_vae method.
        """
        return self.get('/sdapi/v1/sd-vae', timeout=30).json()


    def get_controlnet_version(self):
        """
        Returns the installed version of the stable-diffusion ControlNet extension, or raises if the exception is not
        installed.
        """
        return self.get('/controlnet/version', timeout=30).json()['version']


    def get_controlnet_models(self):
        """Returns the list of models available to the stable-diffusion ControlNet extension.
        """
        return self.get('/controlnet/model_list', timeout=30).json()


    def get_controlnet_modules(self):
        """Returns the list of modules available to the stable-diffusion ControlNet extension.
        """
        return self.get('/controlnet/module_list', timeout=30).json()


    def get_controlnet_control_types(self):
        """Returns the list of control types available to the stable-diffusion ControlNet extension.
        """
        return self.get('/controlnet/control_types', timeout=30).json()['control_types']


    def get_controlnet_settings(self):
        """Returns the current settings applied to the stable-diffusion ControlNet extension.
        """
        return self.get('/controlnet/settings', timeout=30).json()


    def get_loras(self):
        """Returns the list of available stable-diffusion LORA models cached by the webui.

        If available models may have changed, instead consider using the slower refresh_loras method.
        """
        return self.get('/sdapi/v1/loras', timeout=30).json()


    def _login(self, username, password):
        body = { 'username': username, 'password': password }
        return self.post('/login', body, 'x-www-form-urlencoded', timeout=30, throw_on_failure=False)


    def _handle_auth_error(self):
        from ui.modal.login_modal import LoginModal
        login_modal = LoginModal(self._login)
        auth = None
        while auth is None:
            try:
                auth = login_modal.show_login_modal()
            except RuntimeError:
                auth = None
            if login_modal.get_login_response() is None:
                print("Login aborted, exiting")
                sys.exit()
        self.set_auth(auth)
