"""Covers a scene region with diagonal hatching drawn at a fixed screen size, to mark it as excluded.

Each stripe is a dark line beside a light line, so at least one of them contrasts with any solid color underneath. The
lines are partly transparent and the gaps between stripes are clear, so the content below stays recognizable. The
pattern is drawn in device space, so its density doesn't change with zoom, and its origin is the scene origin, so it
moves with the content when panning.
"""
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPixmap, QTransform
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

# Horizontal and vertical distance between stripes, in logical screen pixels:
HATCH_PERIOD = 8
# Width of each of a stripe's two lines, in logical screen pixels:
HATCH_LINE_WIDTH = 1
HATCH_DARK_COLOR = QColor(0, 0, 0)
HATCH_LIGHT_COLOR = QColor(255, 255, 255)
HATCH_OPACITY = 0.6


def hatch_tile(device_pixel_ratio: float) -> QPixmap:
    """Returns one tile of the hatching pattern, at `HATCH_PERIOD` logical pixels for the given device pixel ratio.

    Pixels are dark where (x + y) modulo the tile size is below the line width, and light for the next line width, so
    the stripes run at 45 degrees and the tile repeats without seams.
    """
    line_width = max(1, round(HATCH_LINE_WIDTH * device_pixel_ratio))
    size = max(line_width * 2, round(HATCH_PERIOD * device_pixel_ratio))
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    dark = QColor(HATCH_DARK_COLOR)
    dark.setAlphaF(HATCH_OPACITY)
    light = QColor(HATCH_LIGHT_COLOR)
    light.setAlphaF(HATCH_OPACITY)
    for y in range(size):
        for x in range(size):
            stripe_offset = (x + y) % size
            if stripe_offset < line_width:
                image.setPixelColor(x, y, dark)
            elif stripe_offset < line_width * 2:
                image.setPixelColor(x, y, light)
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(size / HATCH_PERIOD)
    return pixmap


class HatchedRegion(QGraphicsItem):
    """Draws the hatching pattern over a scene-space region."""

    def __init__(self, parent: Optional[QGraphicsItem] = None) -> None:
        super().__init__(parent)
        self._region = QPainterPath()
        self._brushes: dict[float, QBrush] = {}
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    @property
    def region(self) -> QPainterPath:
        """Returns the hatched region in scene coordinates."""
        return QPainterPath(self._region)

    @region.setter
    def region(self, region: QPainterPath) -> None:
        """Changes the hatched region, in scene coordinates."""
        self.prepareGeometryChange()
        self._region = QPainterPath(region)
        self.update()

    def boundingRect(self) -> QRectF:  # pylint: disable=invalid-name  # Qt override
        """Returns the region's bounds."""
        return self._region.boundingRect()

    def shape(self) -> QPainterPath:
        """Returns the hatched region."""
        return QPainterPath(self._region)

    def _brush(self, device_pixel_ratio: float) -> QBrush:
        brush = self._brushes.get(device_pixel_ratio)
        if brush is None:
            brush = QBrush(hatch_tile(device_pixel_ratio))
            self._brushes[device_pixel_ratio] = brush
        return brush

    def paint(self,
              painter: Optional[QPainter],
              _option: Optional[QStyleOptionGraphicsItem],
              _widget: Optional[QWidget] = None) -> None:
        """Fills the region with the hatching pattern in device space, anchored to the scene origin."""
        assert painter is not None
        if self._region.isEmpty():
            return
        device = painter.device()
        device_pixel_ratio = 1.0 if device is None else device.devicePixelRatioF()
        world_transform = painter.worldTransform()
        device_region = world_transform.map(self._region)
        origin = world_transform.map(QPointF())
        brush = QBrush(self._brush(device_pixel_ratio))
        brush.setTransform(QTransform.fromTranslate(origin.x(), origin.y()))
        painter.save()
        painter.resetTransform()
        painter.fillPath(device_region, brush)
        painter.restore()
