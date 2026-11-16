"""Tests the portal-based screen color pick used on native Wayland, without a bus or compositor."""
import threading
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from jeepney import HeaderFields, MessageType

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor

from src.ui.widget.color_picker import portal_color_pick, screen_color
from src.ui.widget.color_picker.color_picker_header import ColorPickerHeader
from src.ui.widget.color_picker.portal_color_pick import (PortalColorPicker, decode_response, request_color,
                                                          request_path)
from test.base_test_case import IntraPaintTestCase
from test.ui.widget.color_picker_test_utils import SignalRecorder


class FakePortalPicker(QObject):
    """Stands in for PortalColorPicker without running any process."""

    picked = Signal(QColor)
    cancelled = Signal()
    failed = Signal(str)
    instances: list['FakePortalPicker'] = []

    def __init__(self) -> None:
        super().__init__()
        self.started = False
        self.canceled_quietly = False
        FakePortalPicker.instances.append(self)

    def start(self) -> None:
        """Records the start."""
        self.started = True

    def cancel(self) -> None:
        """Records the quiet cancel."""
        self.canceled_quietly = True


class FakeConnection:
    """A jeepney connection that answers a request with a prepared signal body."""

    unique_name = ':1.42'

    def __init__(self, body: tuple) -> None:
        self.body = body
        self.rules: list = []
        self.calls: list = []
        self.closed = False

    @contextmanager
    def filter(self, rule):
        """Records the filter rule."""
        self.rules.append(rule)
        yield 'queue'

    def send_and_get_reply(self, message):
        """Records the method call."""
        self.calls.append(message)
        return SimpleNamespace(header=SimpleNamespace(message_type=MessageType.method_return), body=('/handle',))

    def recv_until_filtered(self, queue, timeout=None):
        """Returns the prepared response."""
        return SimpleNamespace(body=self.body)

    def close(self) -> None:
        """Records the close."""
        self.closed = True


class RequestColorTest(IntraPaintTestCase):
    """Tests the portal request and response decoding."""

    def test_request_path(self) -> None:
        """The request path comes from the bus name and token."""
        self.assertEqual(request_path(':1.42', 'tok'), '/org/freedesktop/portal/desktop/request/1_42/tok')

    def test_decode_success(self) -> None:
        """A successful response yields its color."""
        body = (0, {'color': ('(ddd)', (1.0, 0.5, 0.0))})
        self.assertEqual(decode_response(body), (0, QColor.fromRgbF(1.0, 0.5, 0.0)))

    def test_decode_cancel(self) -> None:
        """A cancelled pick has code 1 and no color."""
        self.assertEqual(decode_response((1, {})), (1, None))

    def test_request_sends_pick_color_and_listens_on_request_path(self) -> None:
        """The call names PickColor with the handle token, and the filter matches the predicted request path."""
        connection = FakeConnection((0, {'color': ('(ddd)', (0.0, 0.0, 1.0))}))
        code, color = request_color(connection, 'tok', threading.Event())
        self.assertEqual((code, color), (0, QColor.fromRgbF(0.0, 0.0, 1.0)))
        call = connection.calls[0]
        self.assertEqual(call.header.fields[HeaderFields.member], 'PickColor')
        self.assertEqual(call.body, ('', {'handle_token': ('s', 'tok')}))
        self.assertEqual(connection.rules[0].header_fields['path'], request_path(':1.42', 'tok'))

    def test_stop_ends_wait(self) -> None:
        """A set stop event ends the wait as a cancel."""
        stop = threading.Event()
        stop.set()
        self.assertEqual(request_color(FakeConnection(()), 'tok', stop), (1, None))


class PortalColorPickerTest(IntraPaintTestCase):
    """Tests the picker's thread hand-off."""

    def _run(self, **patches) -> list:
        events: list = []
        picker = PortalColorPicker()
        picker.picked.connect(lambda color: events.append(('picked', color.name())))
        picker.cancelled.connect(lambda: events.append(('cancelled',)))
        picker.failed.connect(lambda reason: events.append(('failed', reason)))
        stop = threading.Event()
        picker._stop = stop  # pylint: disable=protected-access
        with patch.object(portal_color_pick, 'run_on_main_thread', lambda fn: fn()):
            with patch.object(portal_color_pick, 'open_connection', patches['open']):
                picker._run(stop)  # pylint: disable=protected-access
        return events

    def test_picked(self) -> None:
        """A successful pick emits its color and closes the connection."""
        connection = FakeConnection((0, {'color': ('(ddd)', (0.0, 1.0, 0.0))}))
        self.assertEqual(self._run(open=lambda: connection), [('picked', '#00ff00')])
        self.assertTrue(connection.closed)

    def test_cancelled(self) -> None:
        """A cancelled pick emits cancelled."""
        self.assertEqual(self._run(open=lambda: FakeConnection((1, {}))), [('cancelled',)])

    def test_failure_reports_reason(self) -> None:
        """A connection error emits failed with its message."""
        def fail():
            raise FileNotFoundError('no bus')
        self.assertEqual(self._run(open=fail), [('failed', 'no bus')])


class ScreenColorPortalTest(IntraPaintTestCase):
    """Tests how the screen color widget uses the portal picker when on native Wayland."""

    def setUp(self) -> None:
        super().setUp()
        FakePortalPicker.instances = []
        patches = [patch.object(screen_color, 'is_native_wayland', return_value=True),
                   patch.object(screen_color, 'PortalColorPicker', FakePortalPicker)]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.header = ColorPickerHeader()
        self.picked = SignalRecorder(self.header.screen_color_picked)

    def test_no_live_preview(self) -> None:
        """Wayland picking reports no live preview and explains the system picker."""
        self.assertFalse(self.header.live_preview)
        self.header.start_screen_color_picking()
        self.assertTrue(self.header.color_picking_active)
        self.assertTrue(FakePortalPicker.instances[0].started)
        self.assertFalse(self.header.picking_label.isHidden())

    def test_pick_emits_color_and_stops(self) -> None:
        """A portal result is emitted once and ends picking."""
        self.header.start_screen_color_picking()
        FakePortalPicker.instances[0].picked.emit(QColor('#102030'))
        self.assertEqual(self.picked.colors, [QColor('#102030')])
        self.assertFalse(self.header.color_picking_active)
        self.assertTrue(self.header.picking_label.isHidden())

    def test_cancel_stops_without_color(self) -> None:
        """Cancelling the system picker ends picking without a color."""
        self.header.start_screen_color_picking()
        FakePortalPicker.instances[0].cancelled.emit()
        self.assertEqual(self.picked.colors, [])
        self.assertFalse(self.header.color_picking_active)

    def test_failure_is_shown(self) -> None:
        """A failed request ends picking and shows the reason."""
        self.header.start_screen_color_picking()
        FakePortalPicker.instances[0].failed.emit('no portal')
        self.assertFalse(self.header.color_picking_active)
        self.assertFalse(self.header.picking_label.isHidden())
        self.assertIn('no portal', self.header.picking_label.text())
