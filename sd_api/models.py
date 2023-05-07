from sd_api.endpoint import Endpoint

class ModelsGet(Endpoint):
    def __init__(self, url):
        super().__init__(url, '/sdapi/v1/sd-models', 'GET')

