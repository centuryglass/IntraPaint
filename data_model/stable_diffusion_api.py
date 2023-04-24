from startup.utils import imageToBase64, loadImageFromBase64

API_ENDPOINT_BASE = '/sdapi/v1'
API_ENDPOINTS = {
    'LOGIN_CHECK': '/login_check',
    'LOGIN': '/login',
    'CONFIG': '/config',
    'TXT2IMG': f'{API_ENDPOINT_BASE}/txt2img',
    'IMG2IMG': f'{API_ENDPOINT_BASE}/img2img',
    'EXTRAS': f'{API_ENDPOINT_BASE}/extra-single-image',
    'PROGRESS': f'{API_ENDPOINT_BASE}/progress',
    'STYLES': f'{API_ENDPOINT_BASE}/prompt-styles',
    'INTERROGATE': f'{API_ENDPOINT_BASE}/interrogate',
    'OPTIONS': f'{API_ENDPOINT_BASE}/options',
}

def getTxt2ImgBody(config, width, height):
    return {
        'prompt': config.get('prompt'),
        'seed': config.get('seed'),
        'batch_size': config.get('batchSize'),
        'n_iter': config.get('batchCount'),
        'steps': config.get('samplingSteps'),
        'cfg_scale': config.get('cfgScale'),
        'width': width,
        'height': height,
        'restore_faces': config.get('restoreFaces'),
        'tiling': config.get('tiling'),
        'negative_prompt': config.get('negativePrompt'),
        'override_settings': {},
        'sampler_index': config.get('samplingMethod')
    }

def getImg2ImgBody(config, image, mask=None):
    body = getTxt2ImgBody(config, image.width, image.height)
    body['init_images'] = [ imageToBase64(image, includePrefix=True) ]
    body['denoising_strength'] = config.get('denoisingStrength')
    if mask is not None:
        mask = mask.convert('L').point(lambda p: 0 if p < 1 else 255).convert('RGB')
        body['mask'] = imageToBase64(mask, includePrefix=True)
        body['mask_blur'] = config.get('maskBlur')
        body['inpainting_fill'] = config.getOptionIndex('maskedContent')
        body['inpainting_mask_invert'] = config.getOptionIndex('inpaintMasked')
        body['inpaint_full_res'] = False
    return body

def getInterrogateBody(config, image):
    return {
        'model': config.get('interrogateModel'),
        'image': imageToBase64(image, includePrefix=True)
    }

def getUpscaleBody(image, width, height):
    return {
        'resize_mode': 1,
        'upscaling_resize_w': width,
        'upscaling_resize_h': height,
        'upscaler_1': 'SwinIR_4x',
        'image': imageToBase64(image, includePrefix=True)
    }
