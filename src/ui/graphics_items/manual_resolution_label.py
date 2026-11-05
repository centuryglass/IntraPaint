"""A label on the generation area's top edge that shows the resolution while the resolution rule is Manual.

Under the Manual rule the resolution stops following the generation area, and the rule is saved between sessions, so
the label keeps that state in view where generation happens. `ImageViewer` owns it and decides when it shows.
"""
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QApplication, QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from src.ui.graphics_items.transform_handle import HANDLE_SIZE
from src.ui.ink_style import caution_color

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.graphics_items.manual_resolution_label'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


MANUAL_RESOLUTION_LABEL = _tr('Manual resolution: {width} x {height}')

PADDING_X = 6.0
PADDING_Y = 2.0
CORNER_RADIUS = 3.0
# Gap between the label and the area's top edge, in screen pixels:
EDGE_GAP = 4.0
# The label starts this far right of the area's left edge, clear of the corner resize handle:
LEFT_INSET = HANDLE_SIZE + EDGE_GAP


class ManualResolutionLabel(QGraphicsItem):
    """Shows "Manual resolution: W x H" at a fixed screen size next to the generation area's top left corner.

    The label sits above the area's top edge, or just inside it when the space above is out of view. It accepts no
    mouse buttons, so it never takes clicks from the tools.
    """

    def __init__(self, parent: Optional[QGraphicsItem] = None) -> None:
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setZValue(1)
        self._text = ''
        self._font = QFont()
        self._rect = QRectF()
        self._inside = False

    @property
    def text(self) -> str:
        """Returns the label text."""
        return self._text

    def set_resolution(self, width: int, height: int) -> None:
        """Sets the resolution the label shows."""
        text = MANUAL_RESOLUTION_LABEL.format(width=width, height=height)
        if text == self._text:
            return
        self.prepareGeometryChange()
        self._text = text
        metrics = QFontMetricsF(self._font)
        self._rect = QRectF(0.0, 0.0, metrics.horizontalAdvance(text) + PADDING_X * 2,
                            metrics.height() + PADDING_Y * 2)
        self._place_rect()

    @property
    def inside(self) -> bool:
        """Returns whether the label sits inside the area's top edge instead of above it."""
        return self._inside

    def place(self, area_top_left: QPointF, visible_scene_top: float, scene_scale: float) -> None:
        """Anchors the label to the area's top left corner, above the edge if that stays within the visible scene.

        Parameters
        ----------
        area_top_left: QPointF
            The generation area's top left corner, in scene coordinates.
        visible_scene_top: float
            The scene y-coordinate of the view's top edge.
        scene_scale: float
            View pixels per scene pixel.
        """
        self.setPos(area_top_left)
        height_above = (self._rect.height() + EDGE_GAP) / scene_scale if scene_scale > 0 else 0.0
        inside = area_top_left.y() - height_above < visible_scene_top
        if inside != self._inside:
            self.prepareGeometryChange()
            self._inside = inside
            self._place_rect()

    def _place_rect(self) -> None:
        top = EDGE_GAP if self._inside else -(self._rect.height() + EDGE_GAP)
        self._rect.moveTopLeft(QPointF(LEFT_INSET, top))

    def boundingRect(self) -> QRectF:
        """Returns the label's bounds in screen pixels around its position, including the border."""
        return self._rect.adjusted(-1.0, -1.0, 1.0, 1.0)

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draws the text in the caution color over a window-colored rounded rectangle."""
        assert painter is not None
        if self._text == '':
            return
        palette = QApplication.palette()
        background = palette.color(QPalette.ColorRole.Window)
        text_color = caution_color()
        if text_color is None:
            text_color = palette.color(QPalette.ColorRole.WindowText)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self._rect, CORNER_RADIUS, CORNER_RADIUS)
        painter.fillPath(path, background)
        painter.setPen(QPen(QColor(text_color), 1.0))
        painter.drawPath(path)
        painter.setFont(self._font)
        painter.drawText(self._rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.restore()
