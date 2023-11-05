import requests

class Endpoint():
    def __init__(self, url, endpoint, method):
        self._server_url = url
        self._address = f"{url}{endpoint}"
        if not method in ["GET", "POST"]:
            raise Exception(f"unsupported HTTP method {method} provided")
        self._method = method
        self._format = 'application/json'

    def send(self, session, *args, **kwargs):
        if session is None:
            session = requests
        if 'timeout' not in kwargs:
            kwargs['timeout'] = None
        address = self._address
        if 'urlParams' in kwargs:
            for key, value in kwargs['urlParams'].items():
                address = address + ('?' if address == self._address else '&') + key + '=' + value
        headers = {}

        res = None
        if self._method == 'GET':
            res = session.get(address, timeout=kwargs['timeout'])
        if self._method == 'POST':
            body = self._createBody(*args)
            if self._format == 'application/json':
                res = session.post(address, timeout=kwargs['timeout'], headers=headers, json=body)
            else:
                res = session.post(address, timeout=kwargs['timeout'], headers=headers, data=body)
        if res is not None and res.status_code == 401 and session != requests:
            from ui.modal.login_modal import LoginModal
            loginModal = LoginModal(self._server_url, session)
            loginModal.showLoginModal()
            return self.send(session, *args, **kwargs)
        return res


    def _createBody(self, *args):
        raise Exception("POST endpoint subclass created without _createBody implementation")

