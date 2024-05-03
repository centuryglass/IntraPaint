"""
Basic interface for classes used to access HTTP web services. 

Provides basic session management, auth access, and functions for making GET and POST requests.
"""
import requests
import secrets
from PyQt5.QtCore import QObject, pyqtSignal


class WebService():
    def __init__(self, url):
        self._server_url = url
        self._session = requests.Session()
        self._auth = None
        self._session_hash = secrets.token_hex(5)


    def set_auth(self, auth):
        self._session.auth = auth


    def get(self,
            endpoint,
            timeout=None,
            url_params=None,
            headers={},
            fail_on_auth_error=False,
            throw_on_failure=True):
        return self._send(endpoint, 'GET', None, None, timeout, url_params, headers, fail_on_auth_error,
                throw_on_failure)


    def post(self,
            endpoint,
            body,
            body_format='application/json',
            timeout=None,
            url_params=None,
            headers={},
            fail_on_auth_error=False,
            throw_on_failure=True):
        return self._send(endpoint, 'POST', body, body_format, timeout, url_params, headers, fail_on_auth_error,
                throw_on_failure)


    def _send(self,
            endpoint,
            method,
            body,
            body_format='application/json',
            timeout=None,
            url_params=None,
            headers={},
            fail_on_auth_error=False,
            throw_on_failure=True):
        address = self._build_address(endpoint, url_params)
        res = None
        if method == 'GET':
            res = self._session.get(address, timeout=timeout, headers=headers)
        elif method == 'POST':
            if body_format == 'application/json':
                res = self._session.post(address, timeout=timeout, headers=headers, json=body)
            else:
                res = self._session.post(address, timeout=timeout, headers=headers, data=body)
        else:
            raise NotImplementedError(f"HTTP method {method} not implemented")
        if res.status_code == 401:
            if fail_on_auth_error and throw_on_failure:
                raise RuntimeError(f"HTTP method {method} failed with status 401: unauthorized")
            if not fail_on_auth_error:
                self._handle_auth_error()
                return self._send(endpoint,
                        method,
                        body,
                        body_format,
                        timeout,
                        url_params,
                        headers,
                        fail_on_auth_error,
                        throw_on_failure)
        elif res.status_code != 200 and throw_on_failure:
            raise RuntimeError(f"{res.status_code}: {res.text}")
        return res


    def _handle_auth_error(self):
        raise NotImplementedError("Authentication is not implemented")


    def _build_address(self, endpoint, url_params=None):
        address = f"{self._server_url}{endpoint}"
        if url_params is not None:
            for key, value in url_params.items():
                address = address + ('?' if ('?' not in address) else '&') + key + '=' + value
        return address
