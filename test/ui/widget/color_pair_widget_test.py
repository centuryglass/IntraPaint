"""Tests ColorPairWidget."""
from unittest.mock import patch

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QDrag, QDragMoveEvent, QDropEvent, QPalette
from PySide6 import QtTest

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.ui.widget.color_pair_widget import ColorPairWidget, ColorPairRegion
from test.base_test_case import IntraPaintTestCase
from test.ui.widget.color_picker_test_utils import press, move, release

DIALOG_PATH = 'src.ui.widget.color_pair_widget.ColorDialog.show_color_dialog'

FOREGROUND = '#ff112233'
BACKGROUND = '#80445566'


class ColorPairWidgetTest(IntraPaintTestCase):
    """Tests ColorPairWidget."""

    def setUp(self) -> None:
        super().setUp()
        Cache().set(Cache.LAST_BRUSH_COLOR, FOREGROUND)
        Cache().set(Cache.BACKGROUND_COLOR, BACKGROUND)
        self.widget = ColorPairWidget()

    def _click(self, region: ColorPairRegion) -> None:
        bounds = {
            ColorPairRegion.FOREGROUND: self.widget.foreground_bounds(),
            ColorPairRegion.BACKGROUND: self.widget.background_bounds(),
            ColorPairRegion.SWAP: self.widget.swap_bounds(),
            ColorPairRegion.RESET: self.widget.reset_bounds(),
        }[region]
        point = bounds.center()
        if region == ColorPairRegion.BACKGROUND:
            point = bounds.bottomRight() - QPoint(2, 2)  # Outside the foreground swatch, which covers the overlap.
        self.assertEqual(self.widget.region_at(point), region)
        QtTest.QTest.mouseClick(self.widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)

    def _background_point(self) -> QPoint:
        """A point on the background swatch, outside the foreground swatch that covers the overlap."""
        return self.widget.background_bounds().bottomRight() - QPoint(2, 2)

    def _color_mime_data(self, color: str) -> QMimeData:
        mime_data = QMimeData()
        mime_data.setColorData(QColor(color))
        return mime_data

    def _drop(self, color: str, point: QPoint) -> bool:
        """Drops a color at a point, returning whether the widget accepted it."""
        # The event doesn't own its mime data, so it has to outlive the event.
        mime_data = self._color_mime_data(color)
        event = QDropEvent(QPointF(point), Qt.DropAction.CopyAction, mime_data, Qt.MouseButton.LeftButton,
                           Qt.KeyboardModifier.NoModifier)
        self.widget.dropEvent(event)
        return event.isAccepted()

    def _drag_from(self, point: QPoint) -> list[QColor]:
        """Drags from a point, returning the colors the drags carried."""
        dragged: list[QColor] = []

        def _exec(drag: QDrag, *_args) -> Qt.DropAction:
            dragged.append(QColor(drag.mimeData().colorData()))
            return Qt.DropAction.CopyAction

        with patch.object(QDrag, 'exec', _exec), patch(DIALOG_PATH) as show_dialog:
            press(self.widget, QPointF(point))
            move(self.widget, QPointF(point + QPoint(20, 0)))
            release(self.widget, QPointF(point))
            show_dialog.assert_not_called()
        return dragged

    def test_drag_swatches_carry_their_colors(self) -> None:
        """Dragging either swatch carries its color and doesn't open the dialog; the controls don't drag."""
        self.assertEqual(self._drag_from(self.widget.foreground_bounds().center()), [QColor(FOREGROUND)])
        self.assertEqual(self._drag_from(self._background_point()), [QColor(BACKGROUND)])
        self.assertEqual(self._drag_from(self.widget.swap_bounds().center()), [])

    def test_drop_sets_swatch_color_and_records_it(self) -> None:
        """Dropping a color on a swatch sets that color and records it as a recent color."""
        Cache().set(Cache.RECENT_COLORS, [])
        self.assertTrue(self._drop('#ffabcdef', self.widget.foreground_bounds().center()))
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#ffabcdef')
        self._drop('#fffedcba', self._background_point())
        self.assertEqual(Cache().get(Cache.BACKGROUND_COLOR), '#fffedcba')
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), ['#fffedcba', '#ffabcdef'])

    def test_drop_on_controls_is_ignored(self) -> None:
        """A color dropped on the swap or reset control changes nothing."""
        for point in (self.widget.swap_bounds().center(), self.widget.reset_bounds().center()):
            self.assertFalse(self._drop('#ffabcdef', point))
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), FOREGROUND)
        self.assertEqual(Cache().get(Cache.BACKGROUND_COLOR), BACKGROUND)

    def test_drag_over_swatch_highlights_it(self) -> None:
        """A color dragged over a swatch outlines it in the highlight color until the drop."""
        point = self.widget.foreground_bounds().center()
        mime_data = self._color_mime_data('#ffabcdef')
        event = QDragMoveEvent(point, Qt.DropAction.CopyAction, mime_data, Qt.MouseButton.LeftButton,
                               Qt.KeyboardModifier.NoModifier)
        self.widget.dragMoveEvent(event)
        self.assertTrue(event.isAccepted())
        highlight = self.widget.palette().color(QPalette.ColorRole.Highlight)
        image = self.widget.grab().toImage()
        self.assertEqual(image.pixelColor(self.widget.foreground_bounds().topLeft() + QPoint(1, 5)).rgb(),
                         highlight.rgb())
        self._drop('#ffabcdef', point)
        image = self.widget.grab().toImage()
        self.assertNotEqual(image.pixelColor(self.widget.foreground_bounds().topLeft() + QPoint(1, 5)).rgb(),
                            highlight.rgb())

    def test_regions(self) -> None:
        """The foreground swatch covers the overlap, and the corners hold the swap and reset controls."""
        overlap = self.widget.foreground_bounds().intersected(self.widget.background_bounds())
        self.assertFalse(overlap.isEmpty())
        self.assertEqual(self.widget.region_at(overlap.center()), ColorPairRegion.FOREGROUND)
        self.assertEqual(self.widget.region_at(QPoint(self.widget.width() - 2, 1)), ColorPairRegion.SWAP)
        self.assertEqual(self.widget.region_at(QPoint(1, self.widget.height() - 2)), ColorPairRegion.RESET)

    def test_foreground_click_opens_dialog_and_writes_foreground(self) -> None:
        """Clicking the foreground swatch opens the dialog on the foreground and saves the choice as foreground."""
        with patch(DIALOG_PATH, return_value=QColor('#ff0000ff')) as dialog:
            self._click(ColorPairRegion.FOREGROUND)
        dialog.assert_called_once()
        self.assertEqual(dialog.call_args.args[0], QColor(FOREGROUND))
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#ff0000ff')
        self.assertEqual(Cache().get(Cache.BACKGROUND_COLOR), BACKGROUND)
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), ['#ff0000ff'])

    def test_background_click_opens_dialog_and_writes_background(self) -> None:
        """Clicking the background swatch opens the dialog on the background and saves the choice as background."""
        with patch(DIALOG_PATH, return_value=QColor('#ff00ff00')) as dialog:
            self._click(ColorPairRegion.BACKGROUND)
        dialog.assert_called_once()
        self.assertEqual(dialog.call_args.args[0], QColor(BACKGROUND))
        self.assertEqual(Cache().get(Cache.BACKGROUND_COLOR), '#ff00ff00')
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), FOREGROUND)

    def test_cancelled_dialog_changes_nothing(self) -> None:
        """Cancelling the dialog leaves both colors and the recent colors unchanged."""
        with patch(DIALOG_PATH, return_value=None):
            self._click(ColorPairRegion.FOREGROUND)
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), FOREGROUND)
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), [])

    def test_swap_click(self) -> None:
        """Clicking the swap control exchanges the colors."""
        self._click(ColorPairRegion.SWAP)
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), BACKGROUND)
        self.assertEqual(Cache().get(Cache.BACKGROUND_COLOR), FOREGROUND)

    def test_reset_click(self) -> None:
        """Clicking the reset control restores black and white."""
        self._click(ColorPairRegion.RESET)
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#ff000000')
        self.assertEqual(Cache().get(Cache.BACKGROUND_COLOR), '#ffffffff')

    def test_control_tooltips_name_shortcuts(self) -> None:
        """The swap and reset tooltips name their configured shortcuts."""
        self.assertIn(KeyConfig().get(KeyConfig.SWAP_COLORS_SHORTCUT),
                      ColorPairWidget.region_tooltip(ColorPairRegion.SWAP))
        self.assertIn(KeyConfig().get(KeyConfig.RESET_COLORS_SHORTCUT),
                      ColorPairWidget.region_tooltip(ColorPairRegion.RESET))

    def test_paints_both_colors(self) -> None:
        """The rendered widget shows the foreground and background colors."""
        Cache().set(Cache.BACKGROUND_COLOR, '#ff445566')
        image = self.widget.grab().toImage()
        self.assertEqual(image.pixelColor(self.widget.foreground_bounds().center()), QColor(FOREGROUND))
        self.assertEqual(image.pixelColor(self.widget.background_bounds().bottomRight() - QPoint(3, 3)),
                         QColor('#ff445566'))
