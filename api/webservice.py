"""
Basic interface for classes used to access HTTP web services. 

Provides basic session management, auth access, and functions for making GET and POST requests.
"""
import secrets
import requests


class WebService():
    """
    WebService establishes a connection to a URL, handles basic auth, and provides convenience methods for GET and
    POST requests.
    """

    def __init__(self, url):
        """__init__.

        Parameters
        ----------
        url : str
            Base URL of the webservice.
        """
        self._server_url = url
        self._session = requests.Session()
        self._auth = None
        self._session_hash = secrets.token_hex(5)


    def set_auth(self, auth):
        """Set session authentication.

        Parameters
        ----------
        auth : (str, str)
            A (username, password) pair, or any other auth format supported by the requests library and the particular
            webservice being targeted.
        """
        self._session.auth = auth


    def get(self,
            endpoint,
            timeout=None,
            url_params=None,
            headers=None,
            fail_on_auth_error=False,
            throw_on_failure=True):
        """Sends a HTTP GET request to the webservice

        Parameters
        ----------
        endpoint : str
            String appended to the end of the service's base URL.
        timeout : int, optional
            Request timeout period in seconds.
        url_params : dict, optional
            Any URL parameters to send with the request.
        headers : dict, optional
            Any headers that should be explicitly set on the request.
        fail_on_auth_error : bool, default=false
            Whether 401: unauthorized responses should raise a RuntimeError
        throw_on_failure : bool, default=true
            Whether other responses with failure statuses should raise a RuntimeError

        Returns
        -------
        request.response
            The response returned by the webservice.
        """
        return self._send(endpoint, 'GET', None, None, timeout, url_params, headers, fail_on_auth_error,
                throw_on_failure)


    def post(self,
            endpoint,
            body,
            body_format='application/json',
            timeout=None,
            url_params=None,
            headers=None,
            fail_on_auth_error=False,
            throw_on_failure=True):
        """Sends a HTTP POST request to the webservice

        Parameters
        ----------
        endpoint : str
            String appended to the end of the service's base URL.
        body: any
            Data to send to the webservice. Any format supported by the request library is accepted, but it should
            be one that's valid for the body_format parameter used.
        body_format: str, default='application/json'
            Request content format to use.
        timeout : int, optional
            Request timeout period in seconds.
        url_params : dict, optional
            Any URL parameters to send with the request.
        headers : dict, optional
            Any headers that should be explicitly set on the request.
        fail_on_auth_error : bool, default=false
            Whether 401: unauthorized responses should raise a RuntimeError
        throw_on_failure : bool, default=true
            Whether other responses with failure statuses should raise a RuntimeError

        Returns
        -------
        request.response
            The response returned by the webservice.
        """
        return self._send(endpoint, 'POST', body, body_format, timeout, url_params, headers, fail_on_auth_error,
                throw_on_failure)


    def _send(self,
            endpoint,
            method,
            body,
            body_format='application/json',
            timeout=None,
            url_params=None,
            headers=None,
            fail_on_auth_error=False,
            throw_on_failure=True):
        address = self._build_address(endpoint, url_params)
        res = None
        if headers is None:
            headers = {}
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
