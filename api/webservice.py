from PyQt5.QtCore import QObject, pyqtSignal
import requests, secrets

class WebService():
    def __init__(self, url):
        self._server_url = url
        self._session = requests.Session()
        self._auth = None
        self._session_hash = secrets.token_hex(5)

    def _buildAddress(self, endpoint, urlParams=None):
        address = f"{self._server_url}{endpoint}"
        if urlParams is not None:
            for key, value in kwargs['urlParams'].items():
                address = address + ('?' if ('?' not in address) else '&') + key + '=' + value
        return address

    def _setAuth(self, auth):
        self._session.auth = auth

    def _send(self,
            endpoint,
            method,
            body,
            bodyFormat='application/json',
            timeout=None,
            urlParams=None,
            headers={},
            failOnAuthError=False,
            throwOnFailure=True):
        address = self._buildAddress(endpoint, urlParams)
        res = None
        if method == 'GET':
            res = self._session.get(address, timeout=timeout, headers=headers)
        elif method == 'POST':
            if bodyFormat == 'application/json':
                res = self._session.post(address, timeout=timeout, headers=headers, json=body)
            else:
                res = self._session.post(address, timeout=timeout, headers=headers, data=body)
        else:
            raise Exception(f"HTTP method {method} not implemented")
        if res.status_code == 401:
            if failOnAuthError and throwOnFailure:
                raise Exception(f"HTTP method {method} failed with status 401: unauthorized")
            elif not failOnAuthError:
                self._handleAuthError()
                return self._send(endpoint,
                        method,
                        body,
                        bodyFormat,
                        timeout,
                        urlParams,
                        headers,
                        failOnAuthError,
                        throwOnFailure)
        elif res.status_code != 200 and throwOnFailure:
            raise Exception(f"{res.status_code}: {res.text}")
        return res

    def _get(self,
            endpoint,
            timeout=None,
            urlParams=None,
            headers={},
            failOnAuthError=False,
            throwOnFailure=True):
        return self._send(endpoint, 'GET', None, None, timeout, urlParams, headers, failOnAuthError, throwOnFailure)

    def _post(self,
            endpoint,
            body,
            bodyFormat='application/json',
            timeout=None,
            urlParams=None,
            headers={},
            failOnAuthError=False,
            throwOnFailure=True):
        return self._send(endpoint, 'POST', body, bodyFormat, timeout, urlParams, headers, failOnAuthError, throwOnFailure)

    def _handleAuthError(self):
        raise Exception("Authentication is not implemented")
