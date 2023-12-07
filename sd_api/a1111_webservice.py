from sd_api.webservice import WebService
from startup.utils import imageToBase64, loadImageFromBase64
import json, requests

class A1111Webservice(WebService):
    def __init__(self, url):
        super().__init__(url)

    def _login(self, username, password):
        body = { 'username': username, 'password': password }
        try:
            return self._post('/login', body, 'x-www-form-urlencoded', timeout=30, throwOnFailure=False)
        except requests.Response as errResponse:
            return errResponse

    def _handleAuthError(self):
        from ui.modal.login_modal import LoginModal
        loginModal = LoginModal(lambda user, pw: self._login(user, pw))
        auth = None
        while auth == None:
            try:
                auth = loginModal.showLoginModal()
            except:
                auth = None
            if loginModal._res is False:
                print("Login aborted, exiting")
                exit()
        self._setAuth(auth)

    # General utility:
    def loginCheck(self):
        return self._get('/login_check')

    def setConfig(self, configUpdates):
        return self._post('/sdapi/v1/options', configUpdates, timeout=30).json()

    def refreshCheckpoints(self):
        return self._post('/sdapi/v1/refresh-checkpoints')

    def refreshVAE(self):
        return self._post('/sdapi/v1/refresh-vae')

    def refreshLoras(self):
        return self._post('/sdapi/v1/refresh-loras')

    def progressCheck(self):
        return self._get('/sdapi/v1/progress').json()

    # Image manipulation:
    def img2img(self, image, config, mask=None, width=None, height=None, overrides=None, scripts=None):
        body = self._getBaseDiffusionBody(config, scripts)
        body['init_images'] = [ imageToBase64(image, includePrefix=True) ]
        body['denoising_strength'] = config.get('denoisingStrength')
        body['width'] = image.width if width is None else width
        body['height'] = image.height if height is None else height
        if mask is not None:
            body['mask'] = imageToBase64(mask, includePrefix=True)
            body['mask_blur'] = config.get('maskBlur')
            body['inpainting_fill'] = config.getOptionIndex('maskedContent')
            body['inpainting_mask_invert'] = config.getOptionIndex('inpaintMasked')
            body['inpaint_full_res'] = config.get('inpaintFullRes')
            body['inpaint_full_res_padding'] = config.get('inpaintFullResPadding')
        if overrides is not None:
            for key in overrides:
                body[key] = overrides[key]
        res = self._post('/sdapi/v1/img2img', body)
        return self._handleImageResponse(res)

    def txt2img(self, config, width, height, scripts=None):
        body = self._getBaseDiffusionBody(config, scripts)
        body['width'] = width
        body['height'] = height
        res = self._post('/sdapi/v1/txt2img', body)
        return self._handleImageResponse(res)

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
                'image': imageToBase64(image, includePrefix=True)
            }
            res = self._post('/sdapi/v1/extra-single-image', body)
            return self._handleImageResponse(res)

    def interrogate(self, config, image):
        body = {
            'model': config.get('interrogateModel'),
            'image': imageToBase64(image, includePrefix=True)
        }
        res = self._post('/sdapi/v1/interrogate', body)
        return res.json()['caption']

    def interrupt(self):
        res = self._post('/sdapi/v1/interrupt')
        return res.json()

    def _getBaseDiffusionBody(self, config, scripts = None):
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
        if scripts is not None:
            body['alwayson_scripts'] = scripts
        return body

    def _handleImageResponse(self, res):
        if res.status_code != 200:
            return res
        resBody = res.json()
        info = resBody['info'] if 'info' in resBody else None
        images = []
        if 'image' in resBody:
            images.append(loadImageFromBase64(resBody['image']))
        if 'images' in resBody:
            for image in resBody['images']:
                if isinstance(image, dict):
                    if not image['is_file'] and image['data'] is not None:
                        image = image['data']
                    else:
                        filePath = image['name']
                        res = self._get(f"/file={filePath}")
                        res.raise_for_status()
                        buffer = io.BytesIO()
                        buffer.write(res.content)
                        buffer.seek(0)
                        images.append(Image.open(buffer))
                elif isinstance(image, str):
                    images.append(loadImageFromBase64(image))
        #print(f"A1111 webservice returned {len(images)} images")
        return images, info

    # Load misc. service info:
    def getConfig(self):
        return self._get('/sdapi/v1/options', timeout=30).json()

    def getStyles(self):
        resBody = self._get('/sdapi/v1/prompt-styles').json()
        return list(map(lambda s: json.dumps(s), resBody))

    def getScripts(self):
        return self._get('/sdapi/v1/scripts').json()

    def getScriptInfo(self):
        return self._get('/sdapi/v1/script-info').json()

    def _getNameList(self, endpoint):
        resBody = self._get(endpoint, timeout=30).json()
        return list(map(lambda obj: obj['name'], resBody))

    def getSamplers(self):
        return self._getNameList('/sdapi/v1/samplers')

    def getUpscalers(self):
        return self._getNameList('/sdapi/v1/upscalers')

    def getLatentUpscaleModes(self):
        return self._getNameList('/sdapi/v1/latent-upscale-modes')

    def getHypernetworks(self):
        return self._getNameList('/sdapi/v1/hypernetworks')

    def getModels(self):
        return self._get('/sdapi/v1/sd-models', timeout=30).json()

    def getVAE(self):
        return self._get('/sdapi/v1/sd-vae', timeout=30).json()

    def getControlnetVersion(self):
        return self._get('/controlnet/version', timeout=30).json()['version']

    def getControlnetModels(self):
        return self._get('/controlnet/model_list', timeout=30).json()

    def getControlnetModules(self):
        return self._get('/controlnet/module_list', timeout=30).json()

    def getControlnetControlTypes(self):
        return self._get('/controlnet/control_types', timeout=30).json()

    def getControlnetSettings(self):
        return self._get('/controlnet/settings', timeout=30).json()

    def getLoras(self):
        return self._get('/sdapi/v1/loras', timeout=30).json()

    def getScripts(self):
        return self._get('/sdapi/v1/scripts', timeout=30).json()

    def getScriptInfo(self):
        return self._get('/sdapi/v1/script-info', timeout=30).json()
