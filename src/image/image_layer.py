"""Manages an edited image layer."""
from sys import version_info
if version_info[1] >= 11:
    from typing import Self, Optional
else:
    from typing import Optional
    from typing_extensions import Self
from collections.abc import Generator
from contextlib import contextmanager
from PyQt5.QtGui import QImage, QPainter, QPixmap
from PyQt5.QtCore import Qt, QObject, QRect, QPoint, QSize, pyqtSignal
from PIL import Image
from src.util.image_utils import qimage_to_pil_image, pil_image_to_qimage
from src.util.validation import assert_type, assert_types
from src.util.cached_data import CachedData


class ImageLayer(QObject):
    """Represents an edited image layer."""

    visibility_changed = pyqtSignal(bool)
    content_changed = pyqtSignal()
    opacity_changed = pyqtSignal(float)

    def __init__(
            self,
            image_data: Image.Image | QImage | QPixmap | QSize,
            name: str,
            saved: bool = True):
        """
        Initializes a new layer with image data.

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
        self._image = None
        self._opacity = 1.0
        self._pixmap = CachedData(None)
        if isinstance(image_data, QPixmap):
            self.pixmap = image_data
        elif isinstance(image_data, Image.Image):
            self.pil_image = image_data
        elif isinstance(image_data, QImage):
            self.q_image = image_data
        elif isinstance(image_data, QSize):
            q_image = QImage(image_data, QImage.Format.Format_ARGB32_Premultiplied)
            q_image.fill(Qt.transparent)
            self.q_image = q_image
        else:
            raise TypeError(f'Invalid layer image data: {image_data}')

    def copy(self) -> Self:
        """Creates a copy of this layer."""
        layer = ImageLayer(self._image.copy(), self.name + ' copy', self.saved)
        layer.opacity = self.opacity
        return layer

    @property
    def opacity(self) -> float:
        """Returns the layer opacity."""
        return self._opacity  # TODO: apply when saving

    @opacity.setter
    def opacity(self, new_opacity) -> None:
        """Updates the layer opacity."""
        self._opacity = new_opacity
        self.opacity_changed.emit(new_opacity)

    @contextmanager
    def borrow_image(self) -> Generator[Optional[QImage], None, None]:
        """Provides direct access to the image for editing, automatically marking it as changed when complete."""
        try:
            yield self._image
        finally:
            self._pixmap.invalidate()
            self.content_changed.emit()

    def refresh_pixmap(self) -> None:
        """Regenerate the image pixmap cache and notify self.content_changed subscribers."""
        self._pixmap.data = self._generate_pixmap(self._image)
        self.content_changed.emit()

    @property
    def q_image(self) -> QImage:
        """Returns the image currently being edited as a QImage object"""
        return self._image

    @q_image.setter
    def q_image(self, new_image: QImage) -> None:
        """Replaces the layer's QImage content."""
        if new_image.format() != QImage.Format_ARGB32_Premultiplied:
            self._image = new_image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        else:
            self._image = new_image
        self._pixmap.invalidate()
        self.content_changed.emit()

    @property
    def pixmap(self) -> QPixmap:
        """Returns the layer's pixmap content."""
        if not self._pixmap.valid:
            self._pixmap.data = self._generate_pixmap(self._image)
        return self._pixmap.data

    @pixmap.setter
    def pixmap(self, new_pixmap: QPixmap):
        """Replaces the layer's pixmap content."""
        assert_type(new_pixmap, QPixmap)
        if new_pixmap != self._pixmap:
            self._pixmap.data = new_pixmap
            self._image = new_pixmap.toImage()
            self.content_changed.emit()

    @property
    def pil_image(self) -> Image.Image:
        """Returns the image currently being edited as a PIL Image object"""
        return qimage_to_pil_image(self.q_image)

    @pil_image.setter
    def pil_image(self, new_image: Image.Image) -> None:
        """Replaces the layer's image content with PIL Image data."""
        self.q_image = pil_image_to_qimage(new_image)

    @property
    def size(self) -> QSize:
        """Returns the layer size in pixels as a QSize object."""
        return QSize(0, 0) if self._image is None else self._image.size()

    @size.setter
    def size(self, new_size: QSize) -> None:
        """Updates the layer size. Scales existing content, or creates with transparency if not initialized."""
        if self._image is None:
            self._image = QImage(new_size, QImage.Format.Format_ARGB32_Premultiplied)
            self._image.fill(Qt.transparent)
        elif new_size != self.size:
            self._image = self._image.scaled(new_size)
        else:
            return
        self._pixmap.invalidate()
        self.content_changed.emit()

    @property
    def width(self) -> int:
        """Returns the edited image width in pixels."""
        return self.size.width()

    @property
    def height(self) -> int:
        """Returns the edited image height in pixels."""
        return self.size.height()

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
        new_image = QImage(new_size)
        new_image.fill(Qt.transparent)
        painter = QPainter(new_image)
        painter.drawImage(x_offset, y_offset, self._image)
        painter.end()
        self._image = new_image
        self._pixmap.invalidate()
        self.content_changed.emit()

    def cropped_image_content(self, bounds_rect: QRect) -> QImage:
        """Returns the contents of a bounding QRect as a QImage object."""
        assert_type(bounds_rect, QRect)
        try:
            self._validate_bounds(bounds_rect)
        except ValueError:
            return self._image.copy()
        return self._image.copy(bounds_rect)

    def insert_image_content(
            self,
            image_data: Image.Image | QImage | QPixmap,
            bounds_rect: QRect,
            composition_mode: QPainter.CompositionMode=QPainter.CompositionMode.CompositionMode_Source):
        """
        Replaces the contents of an area within the image with new image content.

        Parameters
        ----------
        image_data: PIL Image or QImage or QPixmap
            Image data to draw into the selection. If the size of the image doesn't match the size of the
            bounds_rect, it will be scaled to fit.
        bounds_rect: QRect
            Area where image data will be inserted. This must be within the edited image bounds.
        composition_mode: QPainter.CompositionMode, default=Source
            Mode used to insert image content. Default behavior is for the new image content to completely replace the
            old content.
        """
        assert_type(image_data, (QImage, QPixmap, Image.Image))
        assert_type(bounds_rect, QRect)
        try:
            self._validate_bounds(bounds_rect)
        except ValueError:
            return
        with self.borrow_image() as layer_image:
            painter = QPainter(layer_image)
            painter.setCompositionMode(composition_mode)
            if isinstance(image_data, QPixmap):
                painter.drawPixmap(bounds_rect, image_data)
            elif isinstance(image_data, (Image.Image, QImage)):
                qimage = image_data if isinstance(image_data, QImage) else pil_image_to_qimage(image_data)
                painter.drawImage(bounds_rect, qimage)

    def clear(self):
        """Replaces all image content with transparency."""
        self._image.fill(Qt.transparent)
        self._pixmap.invalidate()
        self.content_changed.emit()

    def _validate_bounds(self, bounds_rect: QRect):
        assert_type(bounds_rect, QRect)
        layer_bounds = QRect(QPoint(0, 0), self.size)
        if not layer_bounds.contains(bounds_rect):
            raise ValueError(f'{bounds_rect} not within {layer_bounds}')

    def _generate_pixmap(self, image: QImage) -> QPixmap:
        """Generate and return a new pixmap for the layer's image data."""
        return QPixmap.fromImage(image)
