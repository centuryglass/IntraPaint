import requests

class Endpoint():
    def __init__(self, url, endpoint, method):
        self._address = f"{url}{endpoint}"
        if not method in ["GET", "POST"]:
            raise Exception(f"unsupported HTTP method {method} provided")
        self._method = method

    def send(self, *args, **kwargs):
        if 'timeout' not in kwargs:
            kwargs['timeout'] = None
        if self._method == 'GET':
            return requests.get(self._address, timeout=kwargs['timeout'])
        if self._method == 'POST':
            body = self._createBody(*args)
            return requests.post(self._address, timeout=kwargs['timeout'], json=body)


    def _createBody(self, *args):
        raise Exception("POST endpoint subclass created without _createBody implementation")

