from sd_api.endpoint import Endpoint

class ControlnetVersionGet(Endpoint):
    def __init__(self, url):
        super().__init__(url, '/controlnet/version', 'GET')

