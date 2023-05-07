from sd_api.endpoint import Endpoint

class EmbeddingsGet(Endpoint):
    def __init__(self, url):
        super().__init__(url, '/sdapi/v1/embeddings', 'GET')

