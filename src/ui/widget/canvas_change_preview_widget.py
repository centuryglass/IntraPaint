"""Shows a preview of how the image will look after the ImageStack canvas is resized."""
from typing import Optional

from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QTransform, QResizeEvent, QPaintEvent, QPainter, QPen, Qt, QPainterPath, QBrush
from PySide6.QtWidgets import QWidget

from src.config.cache import Cache
from src.image.layers.image_stack import ImageStack
from src.image.layers.image_stack_utils import image_stack_outline_path
from src.util.visual.geometry_utils import get_scaled_placement, get_rect_transformation
from src.util.visual.image_utils import get_transparency_tile_pixmap


class CanvasChangePreviewWidget(QWidget):
    """Shows a preview of how the image will look after the ImageStack canvas is resized."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__()
        self._image_preview = image_stack.qimage(crop_to_image=False)
        self._merged_layer_bounds = image_stack.merged_layer_bounds
        self._image_bounds = image_stack.bounds
        self._new_bounds = QRect(self._image_bounds)
        self._layer_mask = image_stack_outline_path(image_stack)
        self._cropping_layers = Cache().get(Cache.CANVAS_RESIZE_CROP_LAYERS)

        def _update_crop_layers(should_crop: bool) -> None:
            self._cropping_layers = should_crop
            self.update()
        Cache().connect(self, Cache.CANVAS_RESIZE_CROP_LAYERS, _update_crop_layers)

        self._paint_transform = QTransform()
        self._transparency_background = get_transparency_tile_pixmap(QSize(320, 320))

    def _update_preview_transform(self) -> None:
        content_bounds = self._merged_layer_bounds.united(self._new_bounds)
        paint_bounds = get_scaled_placement(self.size(), content_bounds.size())
        transform = get_rect_transformation(content_bounds, paint_bounds)
        if transform != self._paint_transform:
            self._paint_transform = transform
            self.update()

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Recalculate paint transformation on widget size update."""
        self._update_preview_transform()

    def set_new_bounds(self, bounds: QRect) -> None:
        """Update the preview with the potential new image bounds."""
        if bounds == self._new_bounds:
            return
        self._new_bounds = QRect(bounds)
        self._update_preview_transform()
        self.update()

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draw image with proposed changes to brush bounds."""
        painter = QPainter(self)
        line_pen = QPen(Qt.GlobalColor.black, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap,
                        Qt.PenJoinStyle.MiterJoin)
        line_pen.setCosmetic(True)
        painter.setPen(line_pen)

        painter.setTransform(self._paint_transform)
        painter.drawTiledPixmap(self._new_bounds, self._transparency_background)

        painter.drawImage(self._merged_layer_bounds, self._image_preview)

        image_bounds_path = QPainterPath()
        image_bounds_path.addRect(self._new_bounds)
        excluded_content = self._layer_mask.subtracted(image_bounds_path)

        excluded_image_brush = QBrush(Qt.BrushStyle.Dense3Pattern)
        excluded_image_brush.setColor(Qt.GlobalColor.red if self._cropping_layers else Qt.GlobalColor.black)
        painter.fillPath(excluded_content, excluded_image_brush)
        painter.drawRect(self._new_bounds)
        painter.end()
