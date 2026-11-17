"""Shows another view's visible region within a scene: everything outside it dims, and it gets an accent outline.

The outline is a cosmetic pen in the view's palette `Highlight` color, which InkStyle sets to its accent, so it keeps
the same screen width at any scale and follows theme changes.
"""
from typing import Optional
from weakref import ref

from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView, QStyleOptionGraphicsItem, QWidget

# The dimming drawn over everything outside the highlighted region:
DIM_COLOR = QColor(13, 14, 16, 115)
OUTLINE_WIDTH = 1.5
# How far past the view's visible area the dimming reaches, so panning never shows an undimmed edge:
_BOUNDS_MARGIN = 9999


class ViewportHighlight(QGraphicsItem):
    """Dims a scene outside a region and outlines the region, as seen through one view."""

    def __init__(self, scene: QGraphicsScene, view: QGraphicsView, parent: Optional[QGraphicsItem] = None) -> None:
        super().__init__(parent)
        self._region = QRectF()
        # Held weakly, since the view holds its scene's items:
        self._view_ref = ref(view)
        scene.addItem(self)

    @property
    def _view(self) -> QGraphicsView:
        view = self._view_ref()
        assert view is not None, 'A viewport highlight outlived its view'
        return view

    @property
    def region(self) -> QRectF:
        """Returns the highlighted region in scene coordinates."""
        return QRectF(self._region)

    @region.setter
    def region(self, region: QRectF) -> None:
        """Changes the highlighted region, in scene coordinates."""
        self.prepareGeometryChange()
        self._region = QRectF(region)
        self.update()

    def boundingRect(self) -> QRectF:  # pylint: disable=invalid-name
        """Returns the view's visible scene area with a wide margin, since the dimming covers everything outside the
        region."""
        visible = self._view.mapToScene(QRect(QPoint(), self._view.size())).boundingRect()
        return visible.adjusted(-_BOUNDS_MARGIN, -_BOUNDS_MARGIN, _BOUNDS_MARGIN, _BOUNDS_MARGIN)

    def paint(self, painter: Optional[QPainter], _option: Optional[QStyleOptionGraphicsItem],
              _widget: Optional[QWidget] = None) -> None:
        """Dims the area outside the region, then outlines the region."""
        assert painter is not None
        dimmed = QPainterPath()
        dimmed.addRect(self.boundingRect())
        if not self._region.isEmpty():
            inside = QPainterPath()
            inside.addRect(self._region)
            dimmed = dimmed.subtracted(inside)
        painter.fillPath(dimmed, DIM_COLOR)
        if self._region.isEmpty():
            return
        pen = QPen(self._view.palette().color(QPalette.ColorRole.Highlight), OUTLINE_WIDTH)
        pen.setCosmetic(True)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self._region)
