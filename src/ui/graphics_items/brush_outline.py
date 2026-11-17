"""Circle that shows a brush's footprint in the image scene."""
from typing import Optional

from PySide6.QtCore import QRectF, Qt, QPointF
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QStyleOptionGraphicsItem, QWidget

from src.ui.brush_crosshair import CORE_COLOR, HALO_COLOR, HALO_WIDTH

# Above image content and the other scene overlays:
BRUSH_OUTLINE_Z_LEVEL = 9999

# Dash and gap lengths of a dashed outline, in multiples of its 1px line width:
DASH_PATTERN = [4.0, 4.0]


class BrushOutline(QGraphicsItem):
    """Circle that shows a brush's footprint in the image scene.

    The circle is centred on the item's position, with a diameter in scene pixels. It draws a 1px dark line over a
    light halo matching the brush crosshair's, both at a fixed on-screen width at every zoom level. A dashed outline
    draws the dark line as dashes over a solid halo.
    """

    def __init__(self, scene: QGraphicsScene, dashed: bool = False) -> None:
        super().__init__()
        self._dashed = dashed
        self._diameter = 0.0
        self._view_scale = 1.0
        self.setZValue(BRUSH_OUTLINE_Z_LEVEL)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setVisible(False)
        scene.addItem(self)

    @property
    def diameter(self) -> float:
        """Returns the outline's diameter in scene pixels."""
        return self._diameter

    def set_size(self, diameter: float, view_scale: float) -> None:
        """Sets the diameter in scene pixels, and the view scale that sets the line width in scene pixels."""
        if diameter == self._diameter and view_scale == self._view_scale:
            return
        self.prepareGeometryChange()
        self._diameter = diameter
        self._view_scale = view_scale

    def boundingRect(self) -> QRectF:  # pylint: disable=invalid-name  # Qt override
        """Covers the circle and its halo."""
        radius = self._diameter / 2 + (HALO_WIDTH + 1) / self._view_scale
        return QRectF(-radius, -radius, radius * 2, radius * 2)

    def paint(self, painter: Optional[QPainter], unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draws the halo, then the line over it."""
        assert painter is not None
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        radius = self._diameter / 2
        for color, width in ((HALO_COLOR, 1 + 2 * HALO_WIDTH), (CORE_COLOR, 1)):
            pen = QPen(color, width)
            pen.setCosmetic(True)
            if self._dashed and color == CORE_COLOR:
                pen.setDashPattern(DASH_PATTERN)
            painter.setPen(pen)
            painter.drawEllipse(QPointF(), radius, radius)
        painter.restore()
