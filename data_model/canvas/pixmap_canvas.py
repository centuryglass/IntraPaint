from PyQt5.QtGui import QPainter, QPixmap, QPen, QImage, QColor
from PyQt5.QtCore import Qt, QLine, QSize
from PyQt5.QtWidgets import QGraphicsPixmapItem
from PIL import Image
from data_model.canvas.canvas import Canvas
from ui.image_utils import pil_image_to_qimage, qimage_to_pil_image

class PixmapCanvas(Canvas, QGraphicsPixmapItem):
    def __init__(self, config, image):
        super(PixmapCanvas, self).__init__(config, image)
        self._config = config
        self._brush_size = 1
        self._drawing = False
        self._image = None

    def add_to_scene(self, scene, z_value = None):
        if z_value is None:
            z_value = 0
            for item in scene.items():
                z_value = max(z_value, item.zValue() + 1, self.zValue())
        self.setZValue(z_value)
        scene.addItem(self)

    def set_image(self, image_data):
        self._image = None
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
        else:
            raise TypeError(f"Invalid image param {image_data}")

    def size(self):
        return self.pixmap().size()

    def width(self):
        return self.pixmap().width()

    def height(self):
        return self.pixmap().height()

    def get_qimage(self):
        if self._image is None:
            self._image = self.pixmap().toImage()
        return self._image

    def get_pil_image(self):
        return qimage_to_pil_image(self.get_qimage())

    def get_color_at_point(self, point):
        if self.get_qimage().rect().contains(point):
            return self.get_qimage().pixelColor(point)
        return QColor(0, 0, 0, 0)

    def resize(self, size):
        if not isinstance(size, QSize):
            raise TypeError(f"Invalid resize param {size}")
        if size != self.size():
            self.setPixmap(self.pixmap().scaled(size))
            self._handle_changes()

    def start_stroke(self):
        super().start_stroke()
        if self._drawing:
            self.end_stroke()
        self._drawing = True

    def end_stroke(self):
        if self._drawing:
            self._drawing = False

    def _base_draw(self, pixmap, pos, color, composition_mode, size_multiplier=1.0, size_override = None):
        painter = QPainter(pixmap)
        painter.setCompositionMode(composition_mode)
        size = int(self._brush_size * size_multiplier) if size_override is None else int(size_override)
        painter.setPen(QPen(color, size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if isinstance(pos, QLine):
            painter.drawLine(pos)
        else: # Should be QPoint
            painter.drawPoint(pos)
        painter.end()

    def _draw(self, pos, color, composition_mode, size_multiplier=1.0, size_override = None):
        if size_multiplier is None:
            size_multiplier=1.0
        if not self.enabled():
            return
        pixmap = QPixmap(self.size())
        pixmap.swap(self.pixmap())
        self._base_draw(pixmap, pos, color, composition_mode, size_multiplier, size_override)
        self.setPixmap(pixmap)
        self._handle_changes()

    def draw_point(self, point, color, size_multiplier = 1.0, size_override = None):
        if not self._drawing:
            self.start_stroke()
        self._draw(point, color, QPainter.CompositionMode.CompositionMode_SourceOver, size_multiplier, size_override)

    def draw_line(self, line, color, size_multiplier = 1.0, size_override = None):
        if not self._drawing:
            self.start_stroke()
        self._draw(line, color, QPainter.CompositionMode.CompositionMode_SourceOver, size_multiplier, size_override)

    def erase_point(self, point, color, size_multiplier = 1.0, size_override = None):
        if not self._drawing:
            self.start_stroke()
        self._draw(point, color, QPainter.CompositionMode.CompositionMode_Clear, size_multiplier, size_override)

    def erase_line(self, line, color, size_multiplier = 1.0, size_override = None):
        if not self._drawing:
            self.start_stroke()
        self._draw(line, color, QPainter.CompositionMode.CompositionMode_Clear, size_multiplier, size_override)

    def fill(self, color):
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
        super().clear()
        if self._drawing:
            self.end_stroke()
        self.fill(Qt.transparent)

    def _handle_changes(self):
        self._image = None
