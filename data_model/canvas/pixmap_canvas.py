"""
Provides a generic Canvas implementation based on QPixmap and QGraphicsPixmapItem.
"""
from typing import Optional
from PyQt5.QtGui import QPainter, QPixmap, QPen, QImage, QColor
from PyQt5.QtCore import Qt, QLine, QSize, QPoint
from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsScene
from PIL import Image
from data_model.canvas.canvas import Canvas
from data_model.config import Config
from ui.image_utils import pil_image_to_qimage
from util.validation import assert_type

class PixmapCanvas(Canvas, QGraphicsPixmapItem):
    """
    Provides a generic Canvas implementation based on QPixmap and QGraphicsPixmapItem.
    """

    def __init__(self,
            config: Config,
            image: Optional[QImage | Image.Image | QPixmap | QSize | str]):
        """Initialize with config values and optional arbitrary initial image data.

        Parameters
        ----------
        config: data_model.Config
            Used for setting initial size if no initial image data is provided.
        image: QImage or PIL Image or QPixmap or QSize or str, optional
        """
        super(PixmapCanvas, self).__init__(config, image)
        self._config = config
        self._brush_size = 1
        self._drawing = False
        self._image = None


    def add_to_scene(self, scene: QGraphicsScene, z_value: Optional[int] = None):
        """Adds the canvas to a QGraphicsScene. This must only ever be called once.

        Parameters
        ----------
        scene : QGraphicsScene
            Scene that will display the canvas content.
        z_value : int
            Level within the scene where canvas content is drawn, higher levels appear above lower ones.
        """
        if z_value is None:
            z_value = 0
            for item in scene.items():
                z_value = max(z_value, item.zValue() + 1, self.zValue())
        self.setZValue(z_value)
        scene.addItem(self)


    def set_image(self, image_data: QImage | Image.Image | QPixmap | QSize | str):
        """Loads an image into the canvas, overwriting existing canvas content.

        Parameters
        ----------
        image_data : QImage or QPixmap or QSize or PIL Image or str
            An image, image size, or image path. If necessary, the canvas will be resized to match the image size.
            If image_data is a QSize, the canvas will be cleared.
        """
        self._image = None
        assert_type(image_data, (QImage, Image.Image, QPixmap, QSize, str))
        if isinstance(image_data, QSize): # Blank initial image:
            pixmap = QPixmap(image_data)
            pixmap.fill(Qt.transparent)
            self.setPixmap(pixmap)
        elif isinstance(image_data, str): # Load from image path:
            self.setPixmap(QPixmap(image_data, "RGBA"))
        elif isinstance(image_data, Image.Image):
            self.setPixmap(QPixmap.fromImage(pil_image_to_qimage(image_data)))
        elif isinstance(image_data, QImage):
            self._image = image_data
            self.setPixmap(QPixmap.fromImage(image_data))


    def size(self) -> QSize:
        """Returns the canvas size in pixels as QSize."""
        return self.pixmap().size()


    def width(self) -> int:
        """Returns the canvas width in pixels as int."""
        return self.pixmap().width()


    def height(self) -> int:
        """Returns the canvas height in pixels as int."""
        return self.pixmap().height()


    def get_qimage(self) -> QImage:
        """Returns the canvas image content as QImage."""
        if self._image is None:
            self._image = self.pixmap().toImage()
        return self._image


    def get_color_at_point(self, point: QPoint) -> QColor:
        """Returns canvas image color at QPoint pixel coordinates, or QColor(0,0,0) if point is outside of bounds."""
        if self.get_qimage().rect().contains(point):
            return self.get_qimage().pixelColor(point)
        return QColor(0, 0, 0, 0)


    def resize(self, size: QSize):
        """Updates the canvas size, scaling any image content to match.

        Parameters
        ----------
        size : QSize
            New canvas size in pixels.
        """
        assert_type(size, QSize)
        if size != self.size():
            self.setPixmap(self.pixmap().scaled(size))
            self._handle_changes()


    def start_stroke(self):
        """Signals the start of a brush stroke, to be called once whenever user input starts or resumes."""
        super().start_stroke()
        if self._drawing:
            self.end_stroke()
        self._drawing = True


    def end_stroke(self):
        """Signals the end of a brush stroke, to be called once whenever user input stops or pauses."""
        if self._drawing:
            self._drawing = False


    def draw_point(self,
            point: QPoint,
            color: QColor,
            size_multiplier: Optional[float] = 1.0,
            size_override: Optional[int] = None):
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
        if not self._drawing:
            self.start_stroke()
        self._draw(point, color, QPainter.CompositionMode.CompositionMode_SourceOver, size_multiplier, size_override)


    def draw_line(self,
            line: QLine,
            color: QColor,
            size_multiplier: Optional[float] = 1.0,
            size_override: Optional[int] = None):
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
        if not self._drawing:
            self.start_stroke()
        self._draw(line, color, QPainter.CompositionMode.CompositionMode_SourceOver, size_multiplier, size_override)


    def erase_point(self,
            point: QPoint,
            size_multiplier: Optional[float] = 1.0,
            size_override: Optional[int] = None):
        """Erases a single point on the canvas.

        Parameters
        ----------
        point : QPoint
            Position where the point should be eraseed.
        size_multiplier : float, optional
            Multiplier applied to brush size when calculating erased point diameter.
        size_override : int, optional
            Optional value that should override brush_size for this operation only.
        """
        if not self._drawing:
            self.start_stroke()
        self._draw(point, Qt.transparent, QPainter.CompositionMode.CompositionMode_Clear, size_multiplier,
                size_override)


    def erase_line(self,
            line: QLine,
            size_multiplier: Optional[float] = 1.0,
            size_override: Optional[int] = None):
        """Erases a line on the canvas.

        Parameters
        ----------
        line : QLine
            Position where the line should be erased.
        size_multiplier : float, optional
            Multiplier applied to brush size when calculating drawn line width.
        size_override : int, optional
            Optional value that should override brush_size for this operation only.
        """
        if not self._drawing:
            self.start_stroke()
        self._draw(line, Qt.transparent, QPainter.CompositionMode.CompositionMode_Clear, size_multiplier, size_override)


    def fill(self, color: QColor):
        """Fills the canvas with a single QColor."""
        super().fill(color)
        if not self.enabled():
            print("not enabled for fill")
            return
        if self._drawing:
            self.end_stroke()
        pixmap = QPixmap(self.size())
        pixmap.swap(self.pixmap())
        pixmap.fill(color)
        self.setPixmap(pixmap)
        self._handle_changes()
        self.update()


    def clear(self):
        """Replaces all canvas image contents with transparency."""
        super().clear()
        if self._drawing:
            self.end_stroke()
        self.fill(Qt.transparent)


    def _handle_changes(self):
        self._image = None


    def _base_draw(self,
            pixmap: QPixmap,
            pos: QPoint | QLine,
            color: QColor,
            composition_mode: QPainter.CompositionMode,
            size_multiplier: Optional[float] = 1.0,
            size_override: Optional[int] = None):
        painter = QPainter(pixmap)
        painter.setCompositionMode(composition_mode)
        size = int(self._brush_size * size_multiplier) if size_override is None else int(size_override)
        painter.setPen(QPen(color, size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if isinstance(pos, QLine):
            painter.drawLine(pos)
        else: # Should be QPoint
            painter.drawPoint(pos)
        painter.end()


    def _draw(self,
            pos: QPoint | QLine,
            color: QColor,
            composition_mode: QPainter.CompositionMode,
            size_multiplier: Optional[float] = 1.0,
            size_override: Optional[int] = None):
        if size_multiplier is None:
            size_multiplier=1.0
        if not self.enabled():
            return
        pixmap = QPixmap(self.size())
        pixmap.swap(self.pixmap())
        self._base_draw(pixmap, pos, color, composition_mode, size_multiplier, size_override)
        self.setPixmap(pixmap)
        self._handle_changes()
