from sd_api.endpoint import Endpoint

class LoginCheckGet(Endpoint):
    def __init__(self, url):
        super().__init__(url, '/login_check', 'GET')

