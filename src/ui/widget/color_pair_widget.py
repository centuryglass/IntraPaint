"""Shows the foreground and background colors as overlapping swatches, with swap and reset controls.

The foreground swatch sits at the top left over the background swatch at the bottom right. The swap control fills the
top right corner and the reset control the bottom left. Clicking a swatch opens `ColorDialog` on that color. All color
changes go through `src.controller.color_controller`.
"""
from enum import Enum
from typing import Optional

from PySide6.QtCore import Qt, QRect, QSize, QPoint, QEvent, QPointF
from PySide6.QtGui import QPainter, QPaintEvent, QMouseEvent, QColor, QPen, QPainterPath, QHelpEvent, QPalette
from PySide6.QtWidgets import QWidget, QApplication, QToolTip, QSizePolicy

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller import color_controller
from src.ui.modal.color_dialog import ColorDialog
from src.util.visual.image_utils import tile_pattern_fill

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.color_pair_widget'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


FOREGROUND_TOOLTIP = _tr('Foreground color: click to change')
BACKGROUND_TOOLTIP = _tr('Background color: click to change')
SWAP_TOOLTIP = _tr('Swap foreground and background colors')
RESET_TOOLTIP = _tr('Reset to a black foreground and a white background')
SHORTCUT_TOOLTIP_FORMAT = '{tooltip} ({shortcut})'

DEFAULT_SIZE = 48
SWATCH_FRACTION = 0.65
CHECKER_TILE_SIZE = 4
CONTROL_MARGIN_FRACTION = 0.15


class ColorPairRegion(Enum):
    """Clickable parts of a ColorPairWidget."""
    FOREGROUND = 0
    BACKGROUND = 1
    SWAP = 2
    RESET = 3


class ColorPairWidget(QWidget):
    """Shows the foreground and background colors as overlapping swatches, with swap and reset controls."""

    def __init__(self, parent: Optional[QWidget] = None, size: int = DEFAULT_SIZE) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._pressed_region: Optional[ColorPairRegion] = None
        cache = Cache()
        for key in (Cache.LAST_BRUSH_COLOR, Cache.BACKGROUND_COLOR):
            cache.connect(self, key, self._color_changed)

    def sizeHint(self) -> QSize:
        """The widget is a fixed square."""
        return self.size()

    def foreground_bounds(self) -> QRect:
        """Returns the foreground swatch bounds, in widget coordinates."""
        swatch_size = self._swatch_size()
        return QRect(0, 0, swatch_size, swatch_size)

    def background_bounds(self) -> QRect:
        """Returns the background swatch bounds, in widget coordinates."""
        swatch_size = self._swatch_size()
        return QRect(self.width() - swatch_size, self.height() - swatch_size, swatch_size, swatch_size)

    def swap_bounds(self) -> QRect:
        """Returns the swap control bounds: the top right corner outside the foreground swatch."""
        swatch_size = self._swatch_size()
        return QRect(swatch_size, 0, self.width() - swatch_size, self.height() - swatch_size)

    def reset_bounds(self) -> QRect:
        """Returns the reset control bounds: the bottom left corner outside the foreground swatch."""
        swatch_size = self._swatch_size()
        return QRect(0, swatch_size, self.width() - swatch_size, self.height() - swatch_size)

    def region_at(self, point: QPoint) -> Optional[ColorPairRegion]:
        """Returns the clickable region under a point, or None. The foreground swatch covers the background swatch."""
        if self.foreground_bounds().contains(point):
            return ColorPairRegion.FOREGROUND
        if self.background_bounds().contains(point):
            return ColorPairRegion.BACKGROUND
        if self.swap_bounds().contains(point):
            return ColorPairRegion.SWAP
        if self.reset_bounds().contains(point):
            return ColorPairRegion.RESET
        return None

    def select_foreground(self) -> None:
        """Opens the color dialog on the foreground color, and applies the selection."""
        selection = ColorDialog.show_color_dialog(color_controller.foreground())
        if selection is not None:
            color_controller.set_foreground(selection)

    def select_background(self) -> None:
        """Opens the color dialog on the background color, and applies the selection."""
        selection = ColorDialog.show_color_dialog(color_controller.background())
        if selection is not None:
            color_controller.set_background(selection)

    def activate_region(self, region: ColorPairRegion) -> None:
        """Runs the action for a clicked region."""
        if region == ColorPairRegion.FOREGROUND:
            self.select_foreground()
        elif region == ColorPairRegion.BACKGROUND:
            self.select_background()
        elif region == ColorPairRegion.SWAP:
            color_controller.swap()
        else:
            color_controller.reset()

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Track the pressed region, so a release over the same region activates it."""
        assert event is not None
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed_region = self.region_at(event.position().toPoint())
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Activate the pressed region if the release is still over it."""
        assert event is not None
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        pressed_region = self._pressed_region
        self._pressed_region = None
        if pressed_region is not None and self.region_at(event.position().toPoint()) == pressed_region:
            self.activate_region(pressed_region)

    def event(self, event: Optional[QEvent]) -> bool:
        """Show a tooltip for the region under the cursor."""
        if event is not None and event.type() == QEvent.Type.ToolTip:
            assert isinstance(event, QHelpEvent)
            region = self.region_at(event.pos())
            if region is None:
                QToolTip.hideText()
                event.ignore()
            else:
                QToolTip.showText(event.globalPos(), self.region_tooltip(region), self)
            return True
        return super().event(event)

    @staticmethod
    def region_tooltip(region: ColorPairRegion) -> str:
        """Returns a region's tooltip, naming its keyboard shortcut if it has one."""
        if region == ColorPairRegion.FOREGROUND:
            return FOREGROUND_TOOLTIP
        if region == ColorPairRegion.BACKGROUND:
            return BACKGROUND_TOOLTIP
        if region == ColorPairRegion.SWAP:
            tooltip, shortcut_key = SWAP_TOOLTIP, KeyConfig.SWAP_COLORS_SHORTCUT
        else:
            tooltip, shortcut_key = RESET_TOOLTIP, KeyConfig.RESET_COLORS_SHORTCUT
        shortcut = KeyConfig().get(shortcut_key)
        if not shortcut:
            return tooltip
        return SHORTCUT_TOOLTIP_FORMAT.format(tooltip=tooltip, shortcut=shortcut)

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draw the background swatch, the foreground swatch over it, and the swap and reset controls."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        line_color = self.palette().color(QPalette.ColorRole.WindowText)
        self._draw_swatch(painter, self.background_bounds(), color_controller.background(), line_color)
        self._draw_swatch(painter, self.foreground_bounds(), color_controller.foreground(), line_color)
        self._draw_swap_icon(painter, self.swap_bounds(), line_color)
        self._draw_reset_icon(painter, self.reset_bounds(), line_color)
        painter.end()

    def _swatch_size(self) -> int:
        return round(min(self.width(), self.height()) * SWATCH_FRACTION)

    def _color_changed(self, _: str) -> None:
        self.update()

    @staticmethod
    def _draw_swatch(painter: QPainter, bounds: QRect, color: QColor, line_color: QColor) -> None:
        inner = bounds.adjusted(1, 1, -1, -1)
        if color.alpha() < 255:
            tile_pattern_fill(painter, inner, CHECKER_TILE_SIZE, Qt.GlobalColor.lightGray, Qt.GlobalColor.darkGray)
        painter.fillRect(inner, color)
        painter.setPen(QPen(line_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(bounds.adjusted(0, 0, -1, -1))

    @staticmethod
    def _control_bounds(bounds: QRect) -> QRect:
        margin = max(1, round(min(bounds.width(), bounds.height()) * CONTROL_MARGIN_FRACTION))
        return bounds.adjusted(margin, margin, -margin, -margin)

    @staticmethod
    def _draw_swap_icon(painter: QPainter, bounds: QRect, line_color: QColor) -> None:
        """Draws a curved arrow from the top left to the bottom right of the bounds, with a head at each end."""
        icon_bounds = ColorPairWidget._control_bounds(bounds)
        if icon_bounds.width() < 4 or icon_bounds.height() < 4:
            return
        start = QPointF(icon_bounds.left(), icon_bounds.top() + 0.5)
        end = QPointF(icon_bounds.right() + 0.5, icon_bounds.bottom())
        path = QPainterPath(start)
        path.quadTo(QPointF(end.x(), start.y()), end)
        head = max(2.0, icon_bounds.width() / 3)
        path.moveTo(start.x() + head, start.y() - head)
        path.lineTo(start)
        path.lineTo(start.x() + head, start.y() + head)
        path.moveTo(end.x() - head, end.y() - head)
        path.lineTo(end)
        path.lineTo(end.x() + head, end.y() - head)
        painter.setPen(QPen(line_color, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    @staticmethod
    def _draw_reset_icon(painter: QPainter, bounds: QRect, line_color: QColor) -> None:
        """Draws a small black swatch over a small white swatch."""
        icon_bounds = ColorPairWidget._control_bounds(bounds)
        if icon_bounds.width() < 4 or icon_bounds.height() < 4:
            return
        mini_size = round(min(icon_bounds.width(), icon_bounds.height()) * 0.7)
        white_bounds = QRect(icon_bounds.right() - mini_size + 1, icon_bounds.bottom() - mini_size + 1,
                             mini_size, mini_size)
        black_bounds = QRect(icon_bounds.left(), icon_bounds.top(), mini_size, mini_size)
        painter.setPen(QPen(line_color, 1))
        for mini_bounds, color in ((white_bounds, Qt.GlobalColor.white), (black_bounds, Qt.GlobalColor.black)):
            painter.setBrush(color)
            painter.drawRect(mini_bounds.adjusted(0, 0, -1, -1))
