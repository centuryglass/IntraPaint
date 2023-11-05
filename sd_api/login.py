from sd_api.endpoint import Endpoint

class LoginPost(Endpoint):
    def __init__(self, url):
        super().__init__(url, '/login', 'POST')
        self._format = 'x-www-form-urlencoded'

    def _createBody(self, username, password):
        return {
            'username': username,
            'password': password
        }

