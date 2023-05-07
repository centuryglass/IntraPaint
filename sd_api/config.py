from sd_api.endpoint import Endpoint

class ConfigGet(Endpoint):
    def __init__(self, url):
        super().__init__(url, '/config', 'GET')

