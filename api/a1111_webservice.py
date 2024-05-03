"""
Accesses the A1111/stable-diffusion-webui through its REST API, providing access to image generation and editing
through stable-diffusion.
"""
from api.webservice import WebService
from startup.utils import image_to_base64, load_image_from_base64
import json, requests, os

class A1111Webservice(WebService):
    def __init__(self, url):
        super().__init__(url)

    def _login(self, username, password):
        body = { 'username': username, 'password': password }
        try:
            return self.post('/login', body, 'x-www-form-urlencoded', timeout=30, throw_on_failure=False)
        except requests.Response as err_response:
            return err_response

    def _handle_auth_error(self):
        from ui.modal.login_modal import LoginModal
        login_modal = LoginModal(lambda user, pw: self._login(user, pw))
        auth = None
        while auth == None:
            try:
                auth = login_modal.show_login_modal()
            except:
                auth = None
            if login_modal._res is False:
                print("Login aborted, exiting")
                exit()
        self.set_auth(auth)

    # General utility:
    def login_check(self):
        return self.get('/login_check')

    def set_config(self, configUpdates):
        return self.post('/sdapi/v1/options', configUpdates, timeout=30).json()

    def refresh_checkpoints(self):
        return self.post('/sdapi/v1/refresh-checkpoints')

    def refresh_vae(self):
        return self.post('/sdapi/v1/refresh-vae')

    def refresh_loras(self):
        return self.post('/sdapi/v1/refresh-loras')

    def progress_check(self):
        return self.get('/sdapi/v1/progress').json()

    # Image manipulation:
    def img2img(self, image, config, mask=None, width=None, height=None, overrides=None, scripts=None):
        body = self._get_base_diffusion_body(config, image, scripts)
        body['init_images'] = [ image_to_base64(image, include_prefix=True) ]
        body['denoising_strength'] = config.get('denoisingStrength')
        body['width'] = image.width if width is None else width
        body['height'] = image.height if height is None else height
        if mask is not None:
            body['mask'] = image_to_base64(mask, include_prefix=True)
            body['mask_blur'] = config.get('maskBlur')
            body['inpainting_fill'] = config.get_option_index('maskedContent')
            body['inpainting_mask_invert'] = config.get_option_index('inpaintMasked')
            body['inpaint_full_res'] = config.get('inpaintFullRes')
            body['inpaint_full_res_padding'] = config.get('inpaintFullResPadding')
        if overrides is not None:
            for key in overrides:
                body[key] = overrides[key]
        res = self.post('/sdapi/v1/img2img', body)
        return self._handle_image_response(res)

    def txt2img(self, config, width, height, scripts=None, image=None):
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
        if config.get('controlnetUpscaling'):
            scripts = {
                'controlNet': {
                    'args': [{
                        "module": "tile_resample",
                        "model": "control_v11f1e_sd15_tile [a371b31b]",
                        "threshold_a": config.get('controlnetDownsampleRate')
                    }]
                }
            }
            overrides = {
                'width': width,
                'height': height,
                'batch_size': 1,
                'n_iter': 1
            }
            upscaler = config.get('upscaleMethod')
            if upscaler != "None":
                overrides['script_name'] = 'ultimate sd upscale'
                overrides['script_args'] = [
                    None, # not used
                    config.get('editSize').width(), #tile width
                    config.get('editSize').height(), #tile height
                    8, # mask_blur
                    32, # padding
                    64, # seams_fix_width
                    0.35, # seams_fix_denoise
                    32, # seams_fix_padding
                    config.getOptions('upscaleMethod').index(upscaler), # upscaler_index
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
        else:
            body = {
                'resize_mode': 1,
                'upscaling_resize_w': width,
                'upscaling_resize_h': height,
                'upscaler_1': config.get('upscaleMethod'),
                'image': image_to_base64(image, include_prefix=True)
            }
            res = self.post('/sdapi/v1/extra-single-image', body)
            return self._handle_image_response(res)

    def interrogate(self, config, image):
        body = {
            'model': config.get('interrogateModel'),
            'image': image_to_base64(image, include_prefix=True)
        }
        res = self.post('/sdapi/v1/interrogate', body)
        return res.json()['caption']

    def interrupt(self):
        res = self.post('/sdapi/v1/interrupt')
        return res.json()

    def _get_base_diffusion_body(self, config, image = None, scripts = None):
        body = {
            'prompt': config.get('prompt'),
            'seed': config.get('seed'),
            'batch_size': config.get('batchSize'),
            'n_iter': config.get('batchCount'),
            'steps': config.get('samplingSteps'),
            'cfg_scale': config.get('cfgScale'),
            'restore_faces': config.get('restoreFaces'),
            'tiling': config.get('tiling'),
            'negative_prompt': config.get('negativePrompt'),
            'override_settings': {},
            'sampler_index': config.get('samplingMethod'),
            'alwayson_scripts': {}
        }
        controlnet = dict(config.get("controlnetArgs"))
        if len(controlnet) > 0:
            if 'image' in controlnet:
                if controlnet['image'] == 'SELECTION' and image is not None:
                    controlnet['image'] = image_to_base64(image, include_prefix=True)
                elif os.path.exists(controlnet['image']):
                    try: 
                        controlnet['image'] = image_to_base64(controlnet['image'], include_prefix=True)
                    except Exception as err:
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
                        filePath = image['name']
                        res = self.get(f"/file={filePath}")
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
        return self.get('/sdapi/v1/options', timeout=30).json()

    def get_styles(self):
        resBody = self.get('/sdapi/v1/prompt-styles').json()
        return list(map(lambda s: json.dumps(s), resBody))

    def get_scripts(self):
        return self.get('/sdapi/v1/scripts').json()

    def get_script_info(self):
        return self.get('/sdapi/v1/script-info').json()

    def _get_name_list(self, endpoint):
        resBody = self.get(endpoint, timeout=30).json()
        return list(map(lambda obj: obj['name'], resBody))

    def get_samplers(self):
        return self._get_name_list('/sdapi/v1/samplers')

    def get_upscalers(self):
        return self._get_name_list('/sdapi/v1/upscalers')

    def get_latent_upscale_modes(self):
        return self._get_name_list('/sdapi/v1/latent-upscale-modes')

    def get_hypernetworks(self):
        return self._get_name_list('/sdapi/v1/hypernetworks')

    def get_models(self):
        return self.get('/sdapi/v1/sd-models', timeout=30).json()

    def get_vae(self):
        return self.get('/sdapi/v1/sd-vae', timeout=30).json()

    def get_controlnet_version(self):
        return self.get('/controlnet/version', timeout=30).json()['version']

    def get_controlnet_models(self):
        return self.get('/controlnet/model_list', timeout=30).json()

    def get_controlnet_modules(self):
        return self.get('/controlnet/module_list', timeout=30).json()

    def get_controlnet_control_types(self):
        return self.get('/controlnet/control_types', timeout=30).json()['control_types']

    def get_controlnet_settings(self):
        return self.get('/controlnet/settings', timeout=30).json()

    def get_loras(self):
        return self.get('/sdapi/v1/loras', timeout=30).json()

    def get_scripts(self):
        return self.get('/sdapi/v1/scripts', timeout=30).json()

    def get_script_info(self):
        return self.get('/sdapi/v1/script-info', timeout=30).json()
