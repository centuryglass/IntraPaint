from sd_api.endpoint import Endpoint
from startup.utils import imageToBase64

class ExtrasPost(Endpoint):
    def __init__(self, url):
        super().__init__(url, '/sdapi/v1/extra-single-image', 'POST')

    def _createBody(self, image, width, height):
        """Only supports upscaling with SwinIR for now"""
        return {
            'resize_mode': 1,
            'upscaling_resize_w': width,
            'upscaling_resize_h': height,
            'upscaler_1': 'SwinIR_4x',
            'image': imageToBase64(image, includePrefix=True)
        }

