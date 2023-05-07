from sd_api.endpoint import Endpoint

class OptionsGet(Endpoint):
    def __init__(self, url):
        super().__init__(url, '/sdapi/v1/options', 'GET')

class OptionsPost(Endpoint):
    def __init__(self, url):
        super().__init__(url, '/sdapi/v1/options', 'POST')
    def _createBody(self, *args):
        raise Exception("POST endpoint subclass created without _createBody implementation")
