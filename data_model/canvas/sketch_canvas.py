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
    """Provides a Canvas implementation for directly drawing within edited image sections."""

    def __init__(self, config, image_data):
        """Initialize with config values and optional arbitrary initial image data.

        Parameters
        ----------
        config: data_model.Config
            Used for setting initial size if no initial image data is provided.
        image: QImage or PIL Image or QPixmap or QSize or str, optional
        """
        super().__init__(config, image_data)
        self._has_sketch = False
        config.connect(self, 'sketch_brush_size', self.set_brush_size)
        self.set_brush_size(config.get('sketch_brush_size'))
        self.shading = False
        self._shading_pixmap = QGraphicsPixmapItem()
        self._set_empty_shading_pixmap()


    def has_sketch(self):
        """Returns whether the canvas contains non-empty image data."""
        return self._has_sketch


    def add_to_scene(self, scene, z_value = None):
        """Adds the canvas to a QGraphicsScene.

        Parameters
        ----------
        scene : QGraphicsScene
            Scene that will display the canvas content.
        z_value : int
            Level within the scene where canvas content is drawn, higher levels appear above lower ones.
        """
        super().add_to_scene(scene, z_value)
        self._shading_pixmap.setZValue(self.zValue())
        scene.addItem(self._shading_pixmap)


    def set_image(self, image_data):
        """Loads an image into the canvas, overwriting existing canvas content.

        Parameters
        ----------
        image_data : QImage or QPixmap or QSize or PIL Image or str
            An image, image size, or image path. If necessary, the canvas will be resized to match the image size.
            If image_data is a QSize, the canvas will be cleared.
        """
        super().set_image(image_data)
        self._has_sketch = image_data is not None and not isinstance(image_data, QSize)


    def start_stroke(self):
        """Signals the start of a brush stroke, to be called once whenever user input starts or resumes."""
        super().start_stroke()
        if self._config.get("pressure_opacity"):
            self.shading = True


    def end_stroke(self):
        """Signals the end of a brush stroke, to be called once whenever user input stops or pauses."""
        super().end_stroke()
        self._apply_shading()


    def draw_point(self, point, color, size_multiplier=None, size_override=None):
        """Draws a single point on the canvas.

        Parameters
        ----------
        point : QPoint
            Position where the point should be drawn.
        color : QColor
            Current color selected for drawing.
        size_multiplier : float, optional
            Multiplier applied to brush size when calculating drawn point diameter.
        size_override : int, optional
            Optional value that should override brush_size for this operation only.
        """
        if self.shading:
            pixmap = QPixmap(self.size())
            pixmap.swap(self._shading_pixmap.pixmap())
            self._base_draw(pixmap, point, color, QPainter.CompositionMode.CompositionMode_Source,
                    size_multiplier, size_override)
            self._shading_pixmap.setPixmap(pixmap)
        else:
            super().draw_point(point, color, size_multiplier, size_override)
        self._has_sketch = True


    def draw_line(self, line, color, size_multiplier=None, size_override=None):
        """Draws a line on the canvas.

        Parameters
        ----------
        line : QLine
            Position where the line should be drawn.
        color : QColor
            Current color selected for drawing.
        size_multiplier : float, optional
            Multiplier applied to brush size when calculating drawn line width.
        size_override : int, optional
            Optional value that should override brush_size for this operation only.
        """
        self._has_sketch = True
        if self.shading:
            pixmap = QPixmap(self.size())
            pixmap.swap(self._shading_pixmap.pixmap())
            self._base_draw(pixmap, line, color, QPainter.CompositionMode.CompositionMode_Source,
                    size_multiplier, size_override)
            self._shading_pixmap.setPixmap(pixmap)
        else:
            super().draw_line(line, color, size_multiplier, size_override)


    def start_shading(self):
        """Sets the next drawing stroke to use variable opacity."""
        self.shading = True


    def get_qimage(self):
        """Returns the canvas image content as QImage."""
        self._apply_shading()
        return super().get_pil_image()


    def get_pil_image(self):
        """Returns the canvas image content as PIL Image."""
        self._apply_shading()
        return super().get_pil_image()


    def resize(self, size):
        """Updates the canvas size, scaling any image content to match.

        Parameters
        ----------
        size : QSize
            New canvas size in pixels.
        """
        super().resize(size)
        self._shading_pixmap.setPixmap(self._shading_pixmap.pixmap().scaled(size))


    def fill(self, color):
        """Fills the canvas with a single QColor."""
        super().fill(color)
        self._has_sketch = True
        self.update()


    def clear(self):
        """Replaces all canvas image contents with transparency."""
        super().clear()
        self._set_empty_shading_pixmap()
        self._has_sketch = False
        self.update()


    def setVisible(self, visible):
        """Shows or hides the canvas."""
        super().setVisible(visible)
        self._shading_pixmap.setVisible(visible)


    def setOpacity(self, opacity):
        """Changes the opacity used when drawing the masked area."""
        super().setOpacity(opacity)
        self._shading_pixmap.setOpacity(opacity)


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
