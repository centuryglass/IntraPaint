"""Picks a screen color through the XDG Desktop Portal, for native Wayland sessions.

Wayland compositors don't let clients read arbitrary screen pixels, so `QScreen.grabWindow` returns nothing there.
The portal's `org.freedesktop.portal.Screenshot.PickColor` method has the compositor show its own eyedropper and
return one color, with no live preview.

PySide6's QtDBus can't read the reply's `(ddd)` color struct (reading it aborts inside libdbus), so the request goes
through the `gdbus` tool and the reply is parsed from `dbus-monitor` output. The portal sends the Response signal only
to the requesting connection, which is why a monitor that can see other connections' traffic is needed. Both tools
ship with the `dbus` and `glib` packages on desktop Linux.
"""
import re
import shutil
from typing import Optional

from PySide6.QtCore import QObject, QProcess, Signal
from PySide6.QtGui import QColor, QGuiApplication

PORTAL_SERVICE = 'org.freedesktop.portal.Desktop'
PORTAL_PATH = '/org/freedesktop/portal/desktop'
PICK_COLOR_METHOD = 'org.freedesktop.portal.Screenshot.PickColor'
RESPONSE_SIGNAL = 'org.freedesktop.portal.Request.Response'
GDBUS = 'gdbus'

RESPONSE_SUCCESS = 0
MONITOR = 'dbus-monitor'
MONITOR_RULE = "type='signal',interface='org.freedesktop.portal.Request',member='Response'"
_CODE_PATTERN = re.compile(r'^\s*u?int32 (\d+)\s*$', re.MULTILINE)
_DOUBLE_PATTERN = re.compile(r'^\s*double (\S+)\s*$', re.MULTILINE)
_RESULTS_END_PATTERN = re.compile(r'^\s*\]\s*$', re.MULTILINE)


def is_native_wayland() -> bool:
    """Returns whether Qt is running on its native Wayland platform plugin, not XWayland."""
    return QGuiApplication.platformName().startswith('wayland')


def portal_picking_available() -> bool:
    """Returns whether the tools used to reach the portal are installed."""
    return shutil.which(GDBUS) is not None and shutil.which(MONITOR) is not None


def parse_portal_response(output: str, token: str) -> Optional[tuple[int, Optional[QColor]]]:
    """Parses accumulated `dbus-monitor` output for the Response signal of the request created with `token`.

    Returns `None` until the whole response has arrived. Otherwise returns the portal's response code (0 for success,
    1 if the user cancelled, 2 for any other failure) and the picked color, if there is one.
    """
    header = re.search(rf'^signal .*path=\S+/{re.escape(token)};.*member=Response$', output, re.MULTILINE)
    if header is None:
        return None
    body = output[header.end():]
    next_message = re.search(r'^(signal|method call|method return|error) ', body, re.MULTILINE)
    if next_message is not None:
        body = body[:next_message.start()]
    code_match = _CODE_PATTERN.search(body)
    if code_match is None:
        return None
    code = int(code_match.group(1))
    if code != RESPONSE_SUCCESS:
        return code, None
    values = _DOUBLE_PATTERN.findall(body)
    if len(values) >= 3:
        try:
            red, green, blue = (max(0.0, min(1.0, float(value))) for value in values[:3])
        except ValueError:
            return code, None
        return code, QColor.fromRgbF(red, green, blue)
    return (code, None) if _RESULTS_END_PATTERN.search(body) else None


class PortalColorPicker(QObject):
    """Runs one portal color pick. Exactly one of `picked`, `cancelled` or `failed` fires per `start`."""

    picked = Signal(QColor)
    cancelled = Signal()
    failed = Signal(str)

    _token_counter = 0

    def __init__(self) -> None:
        super().__init__()
        PortalColorPicker._token_counter += 1
        self._token = f'intrapaint_pick_{PortalColorPicker._token_counter}'
        self._monitor: Optional[QProcess] = None
        self._call: Optional[QProcess] = None
        self._buffer = ''
        self._running = False

    def __del__(self) -> None:
        try:
            self._stop_processes()
        except RuntimeError:
            pass

    def start(self) -> None:
        """Asks the compositor to show its color picker."""
        if self._running:
            return
        self._running = True
        self._buffer = ''
        self._monitor = QProcess(self)
        self._monitor.readyReadStandardOutput.connect(self._read_monitor)
        self._monitor.errorOccurred.connect(self._process_error)
        self._monitor.start(MONITOR, ['--session', MONITOR_RULE])
        self._call = QProcess(self)
        self._call.errorOccurred.connect(self._process_error)
        self._call.finished.connect(self._call_finished)
        self._call.start(GDBUS, ['call', '--session', '--dest', PORTAL_SERVICE, '--object-path', PORTAL_PATH,
                                 '--method', PICK_COLOR_METHOD, '', f"{{'handle_token': <'{self._token}'>}}"])

    def cancel(self) -> None:
        """Abandons a pick in progress without emitting any signal."""
        self._stop_processes()

    def _stop_processes(self) -> None:
        self._running = False
        for process in (self._monitor, self._call):
            if process is not None:
                process.blockSignals(True)
                process.kill()
                process.deleteLater()
        self._monitor = None
        self._call = None

    def _read_monitor(self) -> None:
        if self._monitor is None:
            return
        self._buffer += bytes(self._monitor.readAllStandardOutput().data()).decode('utf-8', errors='replace')
        parsed = parse_portal_response(self._buffer, self._token)
        if parsed is None:
            return
        code, color = parsed
        self._stop_processes()
        if code == RESPONSE_SUCCESS and color is not None:
            self.picked.emit(color)
        elif code == RESPONSE_SUCCESS:
            self.failed.emit('The portal returned no color.')
        else:
            self.cancelled.emit()

    def _call_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if not self._running or exit_code == 0 or self._call is None:
            return
        message = bytes(self._call.readAllStandardError().data()).decode('utf-8', errors='replace').strip()
        self._stop_processes()
        self.failed.emit(message or 'The portal request failed.')

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if not self._running:
            return
        self._stop_processes()
        self.failed.emit(f'Could not run the portal tools: {error.name}')
