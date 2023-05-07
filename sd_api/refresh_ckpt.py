from sd_api.endpoint import Endpoint

class RefreshCheckpointsPost(Endpoint):
    def __init__(self, url):
        super().__init__(url, '/sdapi/v1/refresh-checkpoints', 'POST')

    def _createBody(self, *args):
        raise Exception("POST endpoint subclass created without _createBody implementation")


