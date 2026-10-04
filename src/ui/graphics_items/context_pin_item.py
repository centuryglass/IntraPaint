"""Push-pin marker drawn over a context pin."""
from functools import lru_cache
from typing import Optional

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QSize
from PySide6.QtGui import QPainter, QImage, QImageReader
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from src.util.shared_constants import PROJECT_DIR

MARKER_PATH = f'{PROJECT_DIR}/resources/icons/context_pin.svg'

# Marker size in screen pixels, unaffected by the view scale. The SVG's viewBox is MARKER_VIEWBOX_SIZE units square,
# and its needle tip at MARKER_ANCHOR marks the pinned pixel. Changing the SVG's geometry means updating
# MARKER_ANCHOR and MARKER_VIEWBOX_BOUNDS to match.
MARKER_SIZE = 32
MARKER_VIEWBOX_SIZE = 36.0
MARKER_ANCHOR = QPointF(18.0, 34.0)
MARKER_VIEWBOX_BOUNDS = QRectF(7.0, 4.0, 22.0, 31.0)  # Drawn content, including the white outline.
# Rendered at a multiple of MARKER_SIZE, so the marker stays sharp on high-DPI screens:
MARKER_RENDER_SCALE = 3


def _viewbox_to_screen(viewbox_rect: QRectF) -> QRectF:
    scale = MARKER_SIZE / MARKER_VIEWBOX_SIZE
    return QRectF((viewbox_rect.x() - MARKER_ANCHOR.x()) * scale, (viewbox_rect.y() - MARKER_ANCHOR.y()) * scale,
                  viewbox_rect.width() * scale, viewbox_rect.height() * scale)


def marker_screen_bounds() -> QRectF:
    """Returns the drawn marker's bounds in screen pixels, relative to the center of the pinned pixel."""
    return _viewbox_to_screen(MARKER_VIEWBOX_BOUNDS)


@lru_cache(maxsize=1)
def _get_marker_image() -> QImage:
    reader = QImageReader(MARKER_PATH)
    render_size = MARKER_SIZE * MARKER_RENDER_SCALE
    reader.setScaledSize(QSize(render_size, render_size))
    image = reader.read()
    assert not image.isNull(), f'failed to load {MARKER_PATH}: {reader.errorString()}'
    return image


class ContextPinItem(QGraphicsItem):
    """Draws a fixed-size push-pin with its needle tip on the center of one image pixel, at every view scale."""

    def __init__(self, pin: QPoint) -> None:
        super().__init__()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setPos(QPointF(pin) + QPointF(0.5, 0.5))

    def boundingRect(self) -> QRectF:
        """Returns the full marker image bounds in screen pixels around the pin."""
        return _viewbox_to_screen(QRectF(0.0, 0.0, MARKER_VIEWBOX_SIZE, MARKER_VIEWBOX_SIZE))

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draws the marker image."""
        assert painter is not None
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(self.boundingRect(), _get_marker_image())
        painter.restore()
