"""
Provides a Canvas implementation for directly drawing within edited image sections. Allows painting in full color
with drawing tablet support. Used as a fallback implementation on systems that can't use the superior brushlib_canvas
module.
"""
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPainter, QPixmap
from PyQt5.QtWidgets import QGraphicsPixmapItem
from data_model.canvas.pixmap_canvas import PixmapCanvas

class SketchCanvas(PixmapCanvas):
    def __init__(self, config, image_data):
        super().__init__(config, image_data)
        self._has_sketch = False
        config.connect(self, 'sketchBrushSize', lambda size: self.set_brush_size(size))
        self.set_brush_size(config.get('sketchBrushSize'))
        self.shading = False
        self._shading_pixmap = QGraphicsPixmapItem()
        self._set_empty_shading_pixmap()

    def add_to_scene(self, scene, z_value = None):
        super().add_to_scene(scene, z_value)
        self._shading_pixmap.setZValue(self.zValue())
        scene.addItem(self._shading_pixmap)

    def set_image(self, image_data):
        super().set_image(image_data)
        self._has_sketch = image_data is not None and not isinstance(image_data, QSize)

    def start_stroke(self):
        super().start_stroke()
        if self._config.get("pressureOpacity"):
            self.shading = True

    def end_stroke(self):
        super().end_stroke()
        self._apply_shading()

    def draw_line(self, line, color, size_multiplier=None, size_override=None):
        self._has_sketch = True
        if self.shading:
            pixmap = QPixmap(self.size())
            pixmap.swap(self._shading_pixmap.pixmap())
            self._base_draw(pixmap, line, color, QPainter.CompositionMode.CompositionMode_Source,
                    size_multiplier, size_override)
            self._shading_pixmap.setPixmap(pixmap)
        else:
            super().draw_line(line, color, size_multiplier, size_override)

    def draw_point(self, point, color, size_multiplier=None, size_override=None):
        if self.shading:
            pixmap = QPixmap(self.size())
            pixmap.swap(self._shading_pixmap.pixmap())
            self._base_draw(pixmap, point, color, QPainter.CompositionMode.CompositionMode_Source,
                    size_multiplier, size_override)
            self._shading_pixmap.setPixmap(pixmap)
        else:
            super().draw_point(point, color, size_multiplier, size_override)
        self._has_sketch = True


    def start_shading(self):
        self.shading = True

    def _set_empty_shading_pixmap(self):
        blank_pixmap = QPixmap(self.size())
        blank_pixmap.fill(Qt.transparent)
        self._shading_pixmap.setPixmap(blank_pixmap)

    def _apply_shading(self):
        if self.shading:
            pixmap = QPixmap(self.size())
            pixmap.swap(self.pixmap())
            painter = QPainter(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.drawPixmap(0, 0, self.width(), self.height(), self._shading_pixmap.pixmap())
            painter.end()
            self.setPixmap(pixmap)
            self._set_empty_shading_pixmap()
            self.shading = False

    def get_pil_image(self):
        self._apply_shading()
        return super().get_pil_image()

    def resize(self, size):
        super().resize(size)
        self._shading_pixmap.setPixmap(self._shading_pixmap.pixmap().scaled(size))

    def clear(self):
        super().clear()
        self._set_empty_shading_pixmap()
        self._has_sketch = False
        self.update()

    def fill(self, color):
        super().fill(color)
        self._has_sketch = True
        self.update()

    def setVisible(self, visible):
        super().setVisible(visible)
        self._shading_pixmap.setVisible(visible)

    def setOpacity(self, opacity):
        super().setOpacity(opacity)
        self._shading_pixmap.setOpacity(opacity)
