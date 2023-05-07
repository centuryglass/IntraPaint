from sd_api.endpoint import Endpoint
from startup.utils import imageToBase64

class InterrogatePost(Endpoint):
    def __init__(self, url):
        super().__init__(url, '/sdapi/v1/interrogate', 'POST')

    def _createBody(self, config, image):
        return {
            'model': config.get('interrogateModel'),
            'image': imageToBase64(image, includePrefix=True)
        }
