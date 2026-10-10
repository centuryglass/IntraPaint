"""Offline stand-in for the Stable Diffusion HTTP backends, for tests that pin the generators' request payloads.

`FakeSdBackend` patches `get` and `post` on both `src.api`'s `WebService` and `sd_backend_client`'s, so every WebUI and
ComfyUI request gets a canned response and none reaches the network. It records each POST, and `snapshot_requests`
turns those records into JSON that stays stable across runs: image data becomes a size, format and pixel-hash
placeholder, and per-session ids become fixed strings.

A request with no route fails the test. Generators catch and wrap most exceptions, so the failure can surface as a
RuntimeError naming the unrouted endpoint.
"""
import base64
import hashlib
import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from unittest import mock

import numpy as np
from PySide6.QtCore import QBuffer, QByteArray
from PySide6.QtGui import QImage
from sd_backend_client.api import webservice as library_webservice

from src.api.webservice import WebService
from src.util.visual.image_utils import BASE_64_PREFIX

# Raw base64 PNG data starts with the encoded PNG signature.
BASE_64_PNG_START = 'iVBORw0KGgo'
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

# The base classes whose HTTP methods are patched. `sd_backend_client` exports no base class, so this reaches past its
# public API.
_WEBSERVICE_CLASSES = (WebService, library_webservice.WebService)


class FakeResponse:
    """The subset of `requests.Response` that the API clients read."""

    def __init__(self, body: Any = None, content: Optional[bytes] = None, status_code: int = 200,
                 url: str = '') -> None:
        self._body = body
        self.url = url
        self.content = content if content is not None else json.dumps(body).encode('utf-8')
        self.status_code = status_code

    @property
    def ok(self) -> bool:
        """Whether the status code is below 400, as in `requests.Response.ok`."""
        return self.status_code < 400

    @property
    def text(self) -> str:
        """The response content as text."""
        return self.content.decode('utf-8', errors='replace')

    def json(self) -> Any:
        """Returns the canned response body."""
        return self._body


# A route takes the bound request arguments and returns a response, or a body to wrap in a FakeResponse.
Route = Callable[[dict[str, Any]], Any]


@dataclass
class RecordedRequest:
    """One request sent to the fake backend, with the arguments it was sent with."""
    method: str
    endpoint: str
    arguments: dict[str, Any] = field(default_factory=dict)
    # Default values of the arguments the sending method accepts:
    defaults: dict[str, Any] = field(default_factory=dict)


class FakeSdBackend:
    """Patches the WebService HTTP methods to serve canned responses, recording every request.

    Routes are looked up by method and endpoint. An endpoint ending in '/' matches any endpoint with that prefix,
    after exact matches are tried. Use it as a context manager, or call `start` and register `stop` as cleanup.
    """

    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], Route] = {}
        self.requests: list[RecordedRequest] = []
        self._patches = [mock.patch.object(webservice_class, method_name, autospec=True,
                                           side_effect=self._handler(method_name.upper(),
                                                                     getattr(webservice_class, method_name)))
                         for webservice_class in _WEBSERVICE_CLASSES for method_name in ('get', 'post')]

    def route(self, method: str, endpoint: str, handler: Route | Any) -> None:
        """Serves `handler` for requests to an endpoint. A non-callable handler is returned as the response body."""
        if callable(handler):
            self._routes[(method, endpoint)] = handler
        else:
            self._routes[(method, endpoint)] = lambda _args, body=handler: body

    def start(self) -> None:
        """Starts intercepting requests."""
        for patch in self._patches:
            patch.start()

    def stop(self) -> None:
        """Stops intercepting requests."""
        for patch in self._patches:
            patch.stop()

    def __enter__(self) -> 'FakeSdBackend':
        self.start()
        return self

    def __exit__(self, *_exc_info) -> None:
        self.stop()

    def posts(self) -> list[RecordedRequest]:
        """Returns the recorded POST requests, in the order they were sent."""
        return [request for request in self.requests if request.method == 'POST']

    def _handler(self, method: str, function: Callable[..., Any]) -> Callable[..., FakeResponse]:
        signature = inspect.signature(function)
        defaults = {name: parameter.default for name, parameter in signature.parameters.items()}

        def _handle_request(*args, **kwargs) -> FakeResponse:
            return self._handle(method, signature.bind(*args, **kwargs), defaults)
        return _handle_request

    def _handle(self, method: str, bound: inspect.BoundArguments, defaults: dict[str, Any]) -> FakeResponse:
        bound.apply_defaults()
        arguments = dict(bound.arguments)
        del arguments['self']
        endpoint = arguments.pop('endpoint')
        self.requests.append(RecordedRequest(method, endpoint, arguments, defaults))
        handler = self._routes.get((method, endpoint))
        if handler is None:
            prefixes = [key for key in self._routes if key[0] == method and key[1].endswith('/')
                        and endpoint.startswith(key[1])]
            if len(prefixes) == 0:
                raise AssertionError(f'FakeSdBackend: no route for {method} {endpoint}')
            handler = self._routes[max(prefixes, key=lambda key: len(key[1]))]
        response = handler(arguments)
        if isinstance(response, FakeResponse):
            return response
        return FakeResponse(response)


def image_to_png_bytes(image: QImage) -> bytes:
    """Encodes an image as PNG data."""
    image_bytes = QByteArray()
    buffer = QBuffer(image_bytes)
    image.save(buffer, 'PNG')  # type: ignore
    return image_bytes.data()


def image_to_base64_png(image: QImage) -> str:
    """Encodes an image as base64 PNG data, without a data URL prefix."""
    return base64.b64encode(image_to_png_bytes(image)).decode('utf-8')


def describe_image(image: QImage) -> str:
    """Returns a placeholder naming an image's size, format and a hash of its pixels.

    The hash covers the alpha channel and the color of fully opaque pixels, read from the decoded image, so PNG
    encoder settings don't affect it. Color under partial alpha is left out: it passes through premultiplied
    conversions whose rounding depends on the CPU features Qt selects at runtime, so it varies between machines.
    """
    if image.isNull():
        return '<invalid image>'
    argb_image = image.convertToFormat(QImage.Format.Format_ARGB32)
    line_bytes = np.frombuffer(argb_image.constBits(), dtype=np.uint8).reshape((argb_image.height(),
                                                                              argb_image.bytesPerLine()))
    pixels = line_bytes[:, :argb_image.width() * 4].reshape((argb_image.height(), argb_image.width(), 4))
    alpha = pixels[:, :, 3]
    opaque_colors = np.where((alpha == 255)[:, :, np.newaxis], pixels[:, :, :3], 0)
    pixel_hash = hashlib.sha256()
    pixel_hash.update(np.ascontiguousarray(alpha).tobytes())
    pixel_hash.update(np.ascontiguousarray(opaque_colors).tobytes())
    return f'<image {image.width()}x{image.height()} {image.format().name} {pixel_hash.hexdigest()[:16]}>'


def _describe_encoded_image(data: bytes) -> str:
    return describe_image(QImage.fromData(data))


def scrub_value(value: Any, replacements: dict[str, str]) -> Any:
    """Returns a JSON-compatible copy of a request value, with image data and session-specific strings replaced.

    `replacements` maps exact string values to the placeholders that replace them.
    """
    if isinstance(value, dict):
        return {str(key): scrub_value(item, replacements) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub_value(item, replacements) for item in value]
    if isinstance(value, (bytes, bytearray)):
        if bytes(value).startswith(PNG_SIGNATURE):
            return _describe_encoded_image(bytes(value))
        return f'<{len(value)} bytes>'
    if isinstance(value, str):
        if value in replacements:
            return replacements[value]
        if value.startswith(BASE_64_PREFIX):
            return _describe_encoded_image(base64.b64decode(value[len(BASE_64_PREFIX):]))
        if value.startswith(BASE_64_PNG_START):
            return _describe_encoded_image(base64.b64decode(value))
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return repr(value)


def snapshot_requests(requests: list[RecordedRequest], replacements: Optional[dict[str, str]] = None
                      ) -> list[dict[str, Any]]:
    """Converts recorded requests to stable JSON-compatible data for comparing with a committed snapshot.

    Each entry keeps the method, the endpoint and every argument that differs from the sending method's default, so a
    snapshot shows timeouts and body formats along with the request body.
    """
    replacements = {} if replacements is None else replacements
    snapshot: list[dict[str, Any]] = []
    for request in requests:
        entry: dict[str, Any] = {'method': request.method, 'endpoint': request.endpoint}
        for name, value in request.arguments.items():
            if value != request.defaults[name]:
                entry[name] = scrub_value(value, replacements)
        snapshot.append(entry)
    return snapshot
