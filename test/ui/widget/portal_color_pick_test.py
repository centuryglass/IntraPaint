"""Tests the portal-based screen color pick used on native Wayland."""
from unittest.mock import patch

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor

from src.ui.widget.color_picker import screen_color
from src.ui.widget.color_picker.color_picker_header import ColorPickerHeader
from src.ui.widget.color_picker.portal_color_pick import parse_portal_response
from test.base_test_case import IntraPaintTestCase
from test.ui.widget.color_picker_test_utils import SignalRecorder

HEADER = ('signal time=1.5 sender=:1.2 -> destination=:1.9 serial=7 '
          'path=/org/freedesktop/portal/desktop/request/1_9/tok; interface=org.freedesktop.portal.Request; '
          'member=Response\n')
SUCCESS = HEADER + """   uint32 0
   array [
      dict entry(
         string "color"
         variant             struct {
               double 1
               double 0.5
               double 0
            }
      )
   ]
"""
CANCELLED = HEADER + """   uint32 1
   array [
   ]
"""


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


class ParsePortalResponseTest(IntraPaintTestCase):
    """Tests parsing of `dbus-monitor` output."""

    def test_success_returns_color(self) -> None:
        """A successful response yields its color."""
        self.assertEqual(parse_portal_response(SUCCESS, 'tok'), (0, QColor.fromRgbF(1.0, 0.5, 0.0)))

    def test_cancel_has_no_color(self) -> None:
        """A cancelled pick has code 1 and no color."""
        self.assertEqual(parse_portal_response(CANCELLED, 'tok'), (1, None))

    def test_partial_output_waits(self) -> None:
        """Output that stops before the color is complete gives None."""
        self.assertIsNone(parse_portal_response(SUCCESS[:SUCCESS.index('double 0.5')], 'tok'))
        self.assertIsNone(parse_portal_response(HEADER, 'tok'))

    def test_other_requests_are_ignored(self) -> None:
        """Responses to other tokens and unrelated output give None."""
        self.assertIsNone(parse_portal_response(SUCCESS, 'other'))
        self.assertIsNone(parse_portal_response('signal time=1 path=/a/b; member=NameOwnerChanged\n', 'tok'))

    def test_next_message_is_not_read(self) -> None:
        """Doubles from a later message are not mistaken for the color."""
        text = CANCELLED + 'signal time=2 path=/x; interface=a; member=B\n   double 1\n   double 1\n   double 1\n'
        self.assertEqual(parse_portal_response(text, 'tok'), (1, None))


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
