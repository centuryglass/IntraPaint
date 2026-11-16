"""Picks a screen color through the XDG Desktop Portal, for native Wayland sessions.

Wayland compositors don't let clients read arbitrary screen pixels, so `QScreen.grabWindow` returns nothing there.
The portal's `org.freedesktop.portal.Screenshot.PickColor` method has the compositor show its own eyedropper and
return one color, with no live preview.

The request runs on a worker thread over `jeepney`, a pure-Python D-Bus client. The
worker never touches Qt: results return through `run_on_main_thread`.
"""
import threading
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QGuiApplication

from src.util.main_thread import run_on_main_thread

PORTAL_SERVICE = 'org.freedesktop.portal.Desktop'
PORTAL_PATH = '/org/freedesktop/portal/desktop'
SCREENSHOT_INTERFACE = 'org.freedesktop.portal.Screenshot'
REQUEST_INTERFACE = 'org.freedesktop.portal.Request'
REQUEST_PATH_PREFIX = '/org/freedesktop/portal/desktop/request'

RESPONSE_SUCCESS = 0
POLL_SECONDS = 0.2


def is_native_wayland() -> bool:
    """Returns whether Qt is running on its native Wayland platform plugin, not XWayland."""
    return QGuiApplication.platformName().startswith('wayland')


def request_path(unique_name: str, token: str) -> str:
    """Returns the object path the portal uses for a request made by `unique_name` with `token`.

    The portal derives it from the caller's bus name (`:1.42` becomes `1_42`) and the request's `handle_token`.
    """
    bus_id = unique_name.lstrip(':').replace('.', '_')
    return f'{REQUEST_PATH_PREFIX}/{bus_id}/{token}'


def decode_response(body: tuple) -> tuple[int, Optional[QColor]]:
    """Decodes a Response signal body of `(code, results)` into the response code and the picked color.

    The code is 0 on success, 1 if the user cancelled and 2 for any other failure. The color is `None` unless the
    response carries one.
    """
    code = int(body[0])
    color = None
    results = body[1] if len(body) > 1 else {}
    if code == RESPONSE_SUCCESS and 'color' in results:
        value = results['color']
        red, green, blue = (max(0.0, min(1.0, float(channel))) for channel in value[1][:3])
        color = QColor.fromRgbF(red, green, blue)
    return code, color


def open_connection() -> Any:
    """Opens a blocking connection to the session bus. Raises if jeepney is missing or no bus is reachable."""
    from jeepney.io.blocking import open_dbus_connection  # pylint: disable=import-outside-toplevel
    return open_dbus_connection(bus='SESSION')


def request_color(connection: Any, token: str, stop: threading.Event) -> tuple[int, Optional[QColor]]:
    """Asks the portal for a color on `connection` and blocks until it answers or `stop` is set.

    Returns the portal's response code and color, or `(1, None)` if stopped. Raises on D-Bus errors.
    """
    from jeepney import DBusAddress, MatchRule, new_method_call  # pylint: disable=import-outside-toplevel
    from jeepney.wrappers import unwrap_msg  # pylint: disable=import-outside-toplevel
    rule = MatchRule(type='signal', interface=REQUEST_INTERFACE, member='Response',
                     path=request_path(connection.unique_name, token))
    address = DBusAddress(PORTAL_PATH, bus_name=PORTAL_SERVICE, interface=SCREENSHOT_INTERFACE)
    call = new_method_call(address, 'PickColor', 'sa{sv}', ('', {'handle_token': ('s', token)}))
    with connection.filter(rule) as responses:
        unwrap_msg(connection.send_and_get_reply(call))
        while not stop.is_set():
            try:
                message = connection.recv_until_filtered(responses, timeout=POLL_SECONDS)
            except TimeoutError:
                continue
            return decode_response(message.body)
    return 1, None


class PortalColorPicker(QObject):
    """Runs one portal color pick. Exactly one of `picked`, `cancelled` or `failed` fires per `start`.

    Created and used on the GUI thread.
    """

    picked = Signal(QColor)
    cancelled = Signal()
    failed = Signal(str)

    _token_counter = 0

    def __init__(self) -> None:
        super().__init__()
        PortalColorPicker._token_counter += 1
        self._token = f'intrapaint_pick_{PortalColorPicker._token_counter}'
        self._stop: Optional[threading.Event] = None

    def start(self) -> None:
        """Asks the compositor to show its color picker."""
        if self._stop is not None:
            return
        stop = threading.Event()
        self._stop = stop
        threading.Thread(target=self._run, args=(stop,), daemon=True, name='portal-color-pick').start()

    def cancel(self) -> None:
        """Abandons a pick in progress without emitting any signal."""
        if self._stop is not None:
            self._stop.set()
            self._stop = None

    def _run(self, stop: threading.Event) -> None:
        """Worker thread body: no Qt calls except scheduling the result."""
        try:
            connection = open_connection()
            try:
                code, color = request_color(connection, self._token, stop)
            finally:
                connection.close()
        except Exception as err:  # pylint: disable=broad-exception-caught
            reason = str(err) or type(err).__name__
            run_on_main_thread(lambda: self._finish(stop, None, None, reason))
            return
        run_on_main_thread(lambda: self._finish(stop, code, color, ''))

    def _finish(self, stop: threading.Event, code: Optional[int], color: Optional[QColor], reason: str) -> None:
        """Main thread: reports the outcome unless the request was cancelled or restarted meanwhile."""
        if stop.is_set() or self._stop is not stop:
            return
        self._stop = None
        if code is None:
            self.failed.emit(reason)
        elif code == RESPONSE_SUCCESS and color is not None:
            self.picked.emit(color)
        elif code == RESPONSE_SUCCESS:
            self.failed.emit('The portal returned no color.')
        else:
            self.cancelled.emit()
