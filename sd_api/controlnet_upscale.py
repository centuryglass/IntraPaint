from sd_api.img2img import Img2ImgPost
from startup.utils import imageToBase64, loadImageFromBase64

class ControlnetUpscalePost(Img2ImgPost):
    """A limited ControlNet Img2Img class that just does tiled upscaling."""
    def __init__(self, url):
        super().__init__(url)

    def _createBody(self, config, image, width, height):
        body =  super()._createBody(config, image)
        # Change options to appropriate values for upscaling:
        body['width']=width
        body['height']=height
        body['batch_size'] = 1
        body['n_iter'] = 1
        # Set upscale and controlnet options:
        body['alwayson_scripts']['controlNet'] = {
            "args": [
                {
                    "module": "tile_resample",
                    "model": "control_v11f1e_sd15_tile [a371b31b]",
                    "threshold_a": config.get('controlnetDownsampleRate')
                }
            ]
        }
        upscaler = config.get('upscaleMethod')
        if upscaler != "None":
            body['script_name'] = 'ultimate sd upscale'
            body['script_args'] = [
                None, # not used
                config.get('maxEditSize').width(), #tile width
                config.get('maxEditSize').height(), #tile height
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
        return body
