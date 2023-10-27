from sd_api.endpoint import Endpoint

class UpscalersGet(Endpoint):
    def __init__(self, url):
        super().__init__(url, '/sdapi/v1/upscalers', 'GET')

