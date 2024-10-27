"""
Basic interface for classes used to access HTTP web services. 

Provides basic session management, auth access, and functions for making GET and POST requests.
"""
from typing import Optional, Dict, Tuple, Any
import secrets
import requests


JSON_DATA_TYPE = 'application/json'
MULTIPART_FORM_DATA_TYPE = 'multipart/form-data'


class WebService:
    """
    WebService establishes a connection to a URL, handles basic auth, and provides convenience methods for GET and
    POST requests.
    """

    def __init__(self, url: str):
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

    @property
    def server_url(self) -> str:
        """Returns the server URL."""
        return self._server_url

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
            endpoint: str,
            timeout: Optional[int] = None,
            url_params: Optional[dict[str, str]] = None,
            headers: Optional[dict[str, str]] = None,
            fail_on_auth_error: bool = False,
            throw_on_failure: bool = True) -> requests.Response:
        """Sends an HTTP GET request to the webservice

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
        Response
            The response returned by the webservice.
        """
        return self._send(endpoint, 'GET', None, None, timeout, url_params, headers, None,
                          fail_on_auth_error, throw_on_failure)

    def post(self,
             endpoint: str,
             body: Any,
             body_format: str = 'application/json',
             timeout: Optional[int] = None,
             url_params: Optional[dict[str, str]] = None,
             headers: Optional[dict[str, str]] = None,
             files: Optional[Dict[str, Tuple[str, bytes, str]]] = None,
             fail_on_auth_error: bool = False,
             throw_on_failure: bool = True) -> requests.Response:
        """Sends an HTTP POST request to the webservice

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
        url_params : Dict[str, str], optional
            Any URL parameters to send with the request.
        headers : Dict[str, str], optional
            Any headers that should be explicitly set on the request.
        files: Dict[str, Tuple[str, bytes, str]], optional
            Files that should be sent with form data, to be used with body type 'multipart/form-data'. Tuple format is
            (filename, file_bytes, file_type_str).
        fail_on_auth_error : bool, default=false
            Whether 401: unauthorized responses should raise a RuntimeError
        throw_on_failure : bool, default=true
            Whether other responses with failure statuses should raise a RuntimeError

        Returns
        -------
        Response
            The response returned by the webservice.
        """
        if body is None:
            body_format = None
        return self._send(endpoint, 'POST', body, body_format, timeout, url_params, headers, files,
                          fail_on_auth_error, throw_on_failure)

    def _send(self,
              endpoint: str,
              method: str,
              body,
              body_format: Optional[str] = JSON_DATA_TYPE,
              timeout: Optional[int] = None,
              url_params: Optional[Dict[str, str]] = None,
              headers: Optional[Dict[str, str]] = None,
              files: Optional[Dict[str, Tuple[str, bytes, str]]] = None,
              fail_on_auth_error: bool = False,
              throw_on_failure: bool = True) -> requests.Response:
        address = self._build_address(endpoint, url_params)
        if headers is None:
            headers = {}
        if method == 'GET':
            res = self._session.get(address, timeout=timeout, headers=headers)
        elif method == 'POST':
            if body_format == JSON_DATA_TYPE:
                res = self._session.post(address, timeout=timeout, headers=headers, json=body)
            elif body_format == MULTIPART_FORM_DATA_TYPE and files is not None:
                res = self._session.post(address, timeout=timeout, headers=headers, files=files, data=body)
            else:
                res = self._session.post(address, timeout=timeout, headers=headers, data=body)
        else:
            raise ValueError(f'HTTP method {method} not supported')
        if res.status_code == 401:
            if fail_on_auth_error and throw_on_failure:
                raise RuntimeError(f'HTTP method {method} failed with status 401: unauthorized')
            if not fail_on_auth_error:
                self._handle_auth_error()
                return self._send(endpoint,
                                  method,
                                  body,
                                  body_format,
                                  timeout,
                                  url_params,
                                  headers,
                                  files,
                                  fail_on_auth_error,
                                  throw_on_failure)
        elif res.status_code != 200 and throw_on_failure:
            raise RuntimeError(f'{res.status_code}: {res.text}')
        return res

    def disconnect(self) -> None:
        """Close the session and clear auth.  Do not use the webservice after calling this."""
        self._session.close()
        self._auth = None

    def _handle_auth_error(self):
        raise NotImplementedError('Authentication is not implemented')

    def _build_address(self, endpoint: str, url_params: Optional[dict[str, str]] = None) -> str:
        address = f'{self._server_url}{endpoint}'
        if url_params is not None:
            for key, value in url_params.items():
                address = address + ('?' if ('?' not in address) else '&') + key + '=' + value
        return address
