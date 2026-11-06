"""Fixed-size crosshair that marks a point in the image scene."""
import math
from typing import Optional

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QStyleOptionGraphicsItem, QWidget

from src.ui.brush_crosshair import CROSSHAIR_SIZE, CrosshairVariant, crosshair_pixmap
from src.ui.graphics_items.brush_outline import BRUSH_OUTLINE_Z_LEVEL


class CrosshairItem(QGraphicsItem):
    """Crosshair centred on the item's position, drawn at the same on-screen size at every zoom level.

    It draws the same pattern as the brush cursor's crosshair for the variant, pixel-doubled on high-density screens.
    """

    def __init__(self, scene: QGraphicsScene, variant: CrosshairVariant) -> None:
        super().__init__()
        self._variant = variant
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setZValue(BRUSH_OUTLINE_Z_LEVEL + 1)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setVisible(False)
        scene.addItem(self)

    @property
    def variant(self) -> CrosshairVariant:
        """Returns the crosshair design the item draws."""
        return self._variant

    @variant.setter
    def variant(self, variant: CrosshairVariant) -> None:
        if variant != self._variant:
            self._variant = variant
            self.update()

    def boundingRect(self) -> QRectF:  # pylint: disable=invalid-name  # Qt override
        """Covers the crosshair, in device-independent pixels around the item's position, with a pixel of slack for
        snapping to the screen pixel grid."""
        half_size = CROSSHAIR_SIZE / 2 + 1
        return QRectF(-half_size, -half_size, half_size * 2, half_size * 2)

    def paint(self, painter: Optional[QPainter], unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draws the crosshair pixmap with its centre pixel on the screen pixel under the item's position.

        The paint device's pixel ratio chooses the pixmap's pixel scale.
        """
        assert painter is not None
        pixmap = crosshair_pixmap(self._variant, painter.device().devicePixelRatioF())
        origin = painter.worldTransform().map(QPointF())
        center = CROSSHAIR_SIZE // 2
        painter.resetTransform()
        painter.drawPixmap(QPoint(math.floor(origin.x()) - center, math.floor(origin.y()) - center), pixmap)
