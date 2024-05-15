"""
Provides a Canvas implementation using the libmypaint/brushlib library, used for directly drawing within edited image
sections. Allows painting in full color with drawing tablet support, using .myb brush files.

To function correctly, this Canvas requires the pre-packaged brushlib.so library, which is currently only built for
x86_64 Linux machines. Other systems will need to use the older sketch_canvas module instead.
"""
import math
from PyQt5.QtGui import QPainter, QImage
from PyQt5.QtCore import Qt, QLine, QSize
from PIL import Image
from brushlib import MPBrushLib as brushlib
from data_model.canvas.canvas import Canvas
from data_model.config import Config
from ui.image_utils import pil_image_to_qimage



class BrushlibCanvas(Canvas):
    """BrushlibCanvas provides an image editing layer that uses the MyPaint brush engine."""

    RADIUS_LOG = brushlib.BrushSetting.MYPAINT_BRUSH_SETTING_RADIUS_LOGARITHMIC
    ERASER = brushlib.BrushSetting.MYPAINT_BRUSH_SETTING_ERASER

    def __init__(self, config, image):
        """Initialize with config values and optional arbitrary initial image data.

        Parameters
        ----------
        config: data_model.Config
            Used for setting initial size if no initial image data is provided.
        image: QImage or PIL Image or QPixmap or QSize or str, optional
        """
        super().__init__(config, image)
        self._visible = True
        config.connect(self, Config.SKETCH_BRUSH_SIZE, self.set_brush_size)
        self.set_brush_size(config.get(Config.SKETCH_BRUSH_SIZE))
        self._size = config.get(Config.EDIT_SIZE)
        brushlib.set_surface_size(config.get(Config.EDIT_SIZE))
        self._drawing = False
        self._scene = None
        self._scale = 1.0
        self._has_sketch = False
        self._saved_brush_size = None
        self._saved_image = None
        brushlib.load_brush(config.get(Config.MYPAINT_BRUSH))


    def has_sketch(self):
        """Returns whether the canvas contains non-empty image data."""
        return self._has_sketch


    def set_brush(self, brush_path):
        """Loads a MyPaint brush file.

        Parameters
        ----------
        brush_path : str
            Path to a valid MyPaint brush file. These files contain JSON data in the format specified by MyPaint and
            usually have the .myb extension.
        """
        brushlib.load_brush(brush_path, True)
        self.set_brush_size(self.brush_size())


    def set_brush_size(self, size):
        """Sets the base brush size.

        Parameters
        ----------
        size : int
            Base brush blot diameter in pixels.
        """
        super().set_brush_size(size)
        size_log_radius = math.log(size / 2)
        brushlib.set_brush_value(BrushlibCanvas.RADIUS_LOG, size_log_radius)


    def add_to_scene(self, scene, z_value=None):
        """Adds the canvas to a QGraphicsScene. This must only ever be called once.

        Parameters
        ----------
        scene : QGraphicsScene
            Scene that will display the canvas content.
        z_value : int
            Level within the scene where canvas content is drawn, higher levels appear above lower ones.
        """
        self._scene = scene
        brushlib.add_to_scene(scene, z_value)


    def set_image(self, image_data):
        """Loads an image into the canvas, overwriting existing canvas content.

        Parameters
        ----------
        image_data : QImage or QSize or PIL Image or str
            An image, image size, or image path. If necessary, the canvas will be resized to match the image size.
            If image_data is a QSize, the canvas will be cleared.
        """
        brushlib.clear_surface()
        if isinstance(image_data, QSize):
            if self.size() != image_data:
                brushlib.set_surface_size(image_data)
        elif isinstance(image_data, str):
            image = QImage(image_data)
            if self.size() != image.size():
                brushlib.set_surface_size(image.size())
            brushlib.load_image(image)
        elif isinstance(image_data, Image.Image):
            image = pil_image_to_qimage(image_data)
            if self.size() != image.size():
                brushlib.set_surface_size(image.size())
            brushlib.load_image(image)
        elif isinstance(image_data, QImage):
            if self.size() != image_data.size():
                brushlib.set_surface_size(image_data.size())
            brushlib.load_image(image_data)
        else:
            raise TypeError(f'Invalid image param {image_data}')


    def size(self):
        """Returns the canvas size in pixels as a QSize."""
        return brushlib.surface_size()


    def width(self):
        """Returns the canvas width in pixels as an int."""
        return self._size.width()


    def height(self):
        """Returns the canvas height in pixels as an int."""
        return self._size.height()


    def get_qimage(self):
        """Returns all canvas image content as a QImage."""
        image = brushlib.render_image()
        if image.size() != self.size():
            image = image.scaled(self.size())
        return image


    def resize(self, size):
        """Updates the canvas size, scaling any image content to match.

        Parameters
        ----------
        size : QSize
            New canvas size in pixels.
        """
        self._size = size
        size = QSize(int(size.width() * self._scale), int(size.height() * self._scale))
        if size != brushlib.surface_size():
            image = self.get_qimage().scaled(size)
            self.set_image(image)


    def start_stroke(self):
        """Signals the start of a brush stroke, to be called once whenever user input starts or resumes."""
        if not self._visible:
            return
        super().start_stroke()
        brushlib.start_stroke()
        self._drawing = True


    def end_stroke(self):
        """Signals the end of a brush stroke, to be called once whenever user input stops or pauses."""
        if not self._visible:
            return
        brushlib.end_stroke()
        self._drawing = False
        if self._saved_brush_size is not None:
            self.set_brush_size(self._saved_brush_size)
            self._saved_brush_size = None


    def draw_point(self, point, color, size_multiplier, size_override = None):
        """Draws a single point on the canvas.

        Parameters
        ----------
        point : QPoint
            Position where the point should be drawn.
        color : QColor
            Current color selected for drawing.
        size_multiplier : float, optional
            Tablet pen pressure value. This may or may not actually affect size, it depends on the brush.
        size_override : int, optional
            Optional value that should override brush_size for this operation only.
        """
        if not self._visible:
            return
        brushlib.set_brush_value(BrushlibCanvas.ERASER, 0.0)
        self._draw(point, color, size_multiplier, size_override)


    def draw_line(self, line, color, size_multiplier, size_override = None):
        """Draws a line on the canvas.

        Parameters
        ----------
        line : QLine
            Position where the line should be drawn.
        color : QColor
            Current color selected for drawing.
        size_multiplier : float, optional
            Tablet pen pressure value. This may or may not actually affect size, it depends on the brush.
        size_override : int, optional
            Optional value that should override brush_size for this operation only.
        """
        if not self._visible:
            return
        brushlib.set_brush_value(BrushlibCanvas.ERASER, 0.0)
        self._draw(line, color, size_multiplier, size_override)


    def erase_point(self, point, size_multiplier, size_override = None):
        """Erases a single point on the canvas.

        Parameters
        ----------
        point : QPoint
            Position where the point should be erased.
        size_multiplier : float, optional
            Tablet pen pressure value. This may or may not actually affect size, it depends on the brush.
        size_override : int, optional
            Optional value that should override brush_size for this operation only.
        """
        if not self._visible:
            return
        brushlib.set_brush_value(BrushlibCanvas.ERASER, 1.0)
        self._draw(point, Qt.black, size_multiplier, size_override)


    def erase_line(self, line, size_multiplier, size_override = None):
        """Erases a line on the canvas.

        Parameters
        ----------
        line : QLine
            Position where the line should be erased.
        size_multiplier : float, optional
            Tablet pen pressure value. This may or may not actually affect size, it depends on the brush.
        size_override : int, optional
            Optional value that should override brush_size for this operation only.
        """
        if not self._visible:
            return
        brushlib.set_brush_value(BrushlibCanvas.ERASER, 1.0)
        self._draw(line, Qt.black, size_multiplier, size_override)


    def fill(self, color):
        """Fills the canvas with a single QColor."""
        if not self._visible:
            return
        super().fill(color)
        self._has_sketch = True
        size = self.size()
        image = QImage(size, QImage.Format_ARGB32)
        painter = QPainter(image)
        painter.fillRect(0, 0, size.width(), size.height(), color)
        painter.end()
        brushlib.load_image(image)


    def clear(self):
        """Replaces all canvas image contents with transparency."""
        super().clear()
        self._has_sketch = False
        brushlib.clear_surface()


    def setVisible(self, visible):
        """Shows or hides the canvas."""
        if visible == self._visible:
            return
        self._visible = visible
        if self._visible:
            if self._saved_image is not None:
                self.set_image(self._saved_image)
                self._saved_image = None
        else:
            self._saved_image = self.get_qimage()
            self.clear()


    def _draw(self, pos, color, size_multiplier, size_override = None):
        if not self._visible:
            return
        if size_override is not None:
            if self._saved_brush_size is None:
                self._saved_brush_size = self.brush_size()
            self.set_brush_size(size_override)
        self._has_sketch = True
        brushlib.set_brush_color(color)
        if not self._drawing:
            self.start_stroke()
            if isinstance(pos, QLine):
                if size_multiplier is None:
                    brushlib.basic_stroke_to(float(pos.x1()), float(pos.y1()))
                else:
                    brushlib.stroke_to(float(pos.x1()), float(pos.y1()), size_multiplier, 0.0, 0.0)
        if isinstance(pos, QLine):
            if size_multiplier is None:
                brushlib.basic_stroke_to(float(pos.x2()), float(pos.y2()))
            else:
                brushlib.stroke_to(float(pos.x2()), float(pos.y2()), size_multiplier, 0.0, 0.0)
        else: #QPoint
            if size_multiplier is None:
                brushlib.basic_stroke_to(float(pos.x()), float(pos.y()))
            else:
                brushlib.stroke_to(float(pos.x()), float(pos.y()), size_multiplier, 0.0, 0.0)
