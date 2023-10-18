from sd_api.endpoint import Endpoint
from startup.utils import imageToBase64, loadImageFromBase64

class Img2ImgPost(Endpoint):
    def __init__(self, url):
        super().__init__(url, '/sdapi/v1/img2img', 'POST')

    def _createBody(self, config, image, mask=None):
        body =  {
            'prompt': config.get('prompt'),
            'seed': config.get('seed'),
            'batch_size': config.get('batchSize'),
            'n_iter': config.get('batchCount'),
            'init_images': [ imageToBase64(image, includePrefix=True) ],
            'denoising_strength': config.get('denoisingStrength'),
            'steps': config.get('samplingSteps'),
            'cfg_scale': config.get('cfgScale'),
            'width': image.width,
            'height': image.height,
            'restore_faces': config.get('restoreFaces'),
            'tiling': config.get('tiling'),
            'negative_prompt': config.get('negativePrompt'),
            'override_settings': {},
            'sampler_index': config.get('samplingMethod'),
            'alwayson_scripts': {}
        }
        if mask is not None:
            mask = mask.convert('L').point(lambda p: 0 if p < 1 else 255).convert('RGB')
            body['mask'] = imageToBase64(mask, includePrefix=True)
            body['mask_blur'] = config.get('maskBlur')
            body['inpainting_fill'] = config.getOptionIndex('maskedContent')
            body['inpainting_mask_invert'] = config.getOptionIndex('inpaintMasked')
            body['inpaint_full_res'] = config.get('inpaintFullRes')
            body['inpaint_full_res_padding'] = config.get('inpaintFullResPadding')
        if config.get('controlnetInpainting'):
            body['alwayson_scripts']['controlNet'] = {
                "args": [
                    {
                        "module": "inpaint_global_harmonious",
                        "model": "control_v11p_sd15_inpaint [ebff9138]",
                        "threshold_a": config.get('controlnetDownsampleRate')
                    }
                ]
            }
        return body
