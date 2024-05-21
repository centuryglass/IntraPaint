"""Manages an edited image layer."""
from PyQt5.QtGui import QImage, QPainter, QPixmap
from PyQt5.QtCore import Qt, QObject, QRect, QPoint, QSize, pyqtSignal
from PIL import Image
from util.image_utils import qimage_to_pil_image, pil_image_to_qimage
from util.validation import assert_type, assert_types


class ImageLayer(QObject):
    """Represents an edited image layer."""

    pixmap_changed = pyqtSignal(QPixmap)
    visibility_changed = pyqtSignal(bool)
    content_changed = pyqtSignal()

    def __init__(
            self,
            image_data: Image.Image | QImage | QPixmap | QSize,
            name: str,
            saved: bool = True):
        """
        Initializes an image based on config values and optional image data.

        Parameters
        ----------
        image_data: PIL Image or QImage or QPixmap or QSize
            Initial image data, or size of initial transparent image to create.
        name: str
            Name string to assign to this layer.
        saved: bool, default=True
            Whether this layer's data should be included when saving image data.
        """
        super().__init__()
        self._name = str(name)
        self._saved = bool(saved)
        self._visible = True
        self._pixmap = None
        self.set_image(image_data)

    @property
    def pixmap(self) -> QPixmap:
        """Returns the layer's pixmap content."""
        return self._pixmap

    @pixmap.setter
    def pixmap(self, new_pixmap: QPixmap):
        """Replaces the layer's pixmap content."""
        assert_type(new_pixmap, QPixmap)
        if new_pixmap != self._pixmap:
            self._pixmap = new_pixmap
            self.pixmap_changed.emit(new_pixmap)
            self.content_changed.emit()

    @property
    def visible(self) -> bool:
        """Returns whether this layer is marked as visible."""
        return self._visible

    @visible.setter
    def visible(self, visible: bool):
        """Sets whether this layer is marked as visible."""
        if self._visible != bool(visible):
            self._visible = bool(visible)
            self.visibility_changed.emit(self._visible)

    @property
    def name(self) -> str:
        """Returns the layer's name string."""
        return self._name

    @name.setter
    def name(self, new_name: str):
        """Updates the layer's name string."""
        assert_type(new_name, str)
        self._name = new_name

    @property
    def saved(self) -> bool:
        """Returns whether layer content is included when saving image data.  Non-visible layers are never saved."""
        return self._saved and self.visible

    @saved.setter
    def saved(self, saved: bool):
        """Sets whether this layer is saved when visible and image data is saved."""
        self._saved = saved

    def qimage(self) -> QImage:
        """Returns the image currently being edited as a QImage object"""
        return self.pixmap.toImage()

    def pil_image(self) -> Image.Image:
        """Returns the image currently being edited as a PIL Image object"""
        return qimage_to_pil_image(self.qimage())

    def set_image(self, image_data: Image.Image | QImage | QPixmap | QSize):
        """
        Loads a new image to be edited.

        Parameters
        ----------
        image_data: PIL Image or QImage or QPixmap or QSize
            If image_data is a QSize, a transparent image will be created with the given size.
        """
        assert_type(image_data, (QImage, Image.Image, QPixmap, QSize))
        if isinstance(image_data, QPixmap):
            self.pixmap = image_data
        if isinstance(image_data, QImage):
            self.pixmap = QPixmap.fromImage(image_data)
        elif isinstance(image_data, Image.Image):
            self.pixmap = QPixmap.fromImage(pil_image_to_qimage(image_data))
        elif isinstance(image_data, QSize):
            pixmap = QPixmap(image_data)
            pixmap.fill(Qt.transparent)
            self.pixmap = pixmap

    def scale(self, scaled_size: QSize):
        """Scales the layer image content to a new resolution size."""
        assert_type(scaled_size, QSize)
        if scaled_size == self.size:
            return
        scaled = self.pixmap.scaled(scaled_size)
        self.pixmap = scaled

    def resize_canvas(self, new_size: QSize, x_offset: int, y_offset: int):
        """
        Changes the layer size without scaling existing image content.

        Parameters
        ----------
        new_size: QSize
            New layer size in pixels.
        x_offset: int
            X offset where existing image content will be placed in the adjusted layer
        y_offset: int
            Y offset where existing image content will be placed in the adjusted layer
        """
        assert_type(new_size, QSize)
        assert_types((x_offset, y_offset), int)
        if new_size == self.size and x_offset == 0 and y_offset == 0:
            return
        new_pixmap = QPixmap(new_size)
        new_pixmap.fill(Qt.transparent)
        painter = QPainter(new_pixmap)
        painter.drawPixmap(x_offset, y_offset, self.pixmap)
        painter.end()
        self.pixmap = new_pixmap
        self.content_changed.emit()

    @property
    def size(self) -> QSize:
        """Returns the edited image size in pixels as a QSize object."""
        return self.pixmap.size()

    @property
    def width(self) -> int:
        """Returns the edited image width in pixels."""
        return self.size.width()

    @property
    def height(self) -> int:
        """Returns the edited image height in pixels."""
        return self.size.height()

    def cropped_pixmap_content(self, bounds_rect: QRect) -> QPixmap:
        """Returns the contents of a bounding QRect as a QPixmap object."""
        assert_type(bounds_rect, QRect)
        try:
            self._validate_bounds(bounds_rect)
        except:
            return self.pixmap()
        return self.pixmap.copy(bounds_rect)

    def insert_image_content(
            self,
            image_data: Image.Image | QImage | QPixmap,
            bounds_rect: QRect):
        """
        Replaces the contents of an area within the image with new image content.

        Parameters
        ----------
        image_data: PIL Image or QImage or QPixmap
            Image data to draw into the selection. If the size of the image doesn't match the size of the
            bounds_rect, it will be scaled to fit.
        bounds_rect: QRect
            Area where image data will be inserted. This must be within the edited image bounds.
        """
        assert_type(image_data, (QImage, QPixmap, Image.Image))
        assert_type(bounds_rect, QRect)

        try:
            self._validate_bounds(bounds_rect)
        except:
            return
        pixmap = QPixmap(self.pixmap.size())
        pixmap.swap(self.pixmap)
        painter = QPainter(pixmap)
        if isinstance(image_data, QPixmap):
            painter.drawPixmap(bounds_rect, image_data)
        elif isinstance(image_data, (Image.Image, QImage)):
            qimage = image_data if isinstance(image_data, QImage) else pil_image_to_qimage(image_data)
            painter.drawImage(bounds_rect, qimage)
        self.pixmap = pixmap

    def clear(self):
        """Replaces all image content with transparency."""
        self.pixmap.fill(Qt.transparent)
        self.content_changed.emit()

    def _validate_bounds(self, bounds_rect: QRect):
        assert_type(bounds_rect, QRect)
        layer_bounds = QRect(QPoint(0, 0), self.size)
        if not layer_bounds.contains(bounds_rect):
            raise ValueError(f'{bounds_rect} not within {layer_bounds}')
