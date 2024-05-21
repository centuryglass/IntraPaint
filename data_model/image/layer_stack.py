"""Manages an edited image composed of multiple layers."""
import re
from typing import Optional
from PyQt5.QtGui import QPainter, QPixmap, QImage
from PyQt5.QtCore import Qt, QObject, QSize, QPoint, QRect, pyqtSignal
from PIL import Image
from data_model.image.image_layer import ImageLayer
from util.image_utils import qimage_to_pil_image
from util.validation import assert_type, assert_types, assert_valid_index


class LayerStack(QObject):
    """Manages an edited image composed of multiple layers."""
    visible_content_changed = pyqtSignal()
    selection_bounds_changed = pyqtSignal(QRect, QRect)
    size_changed = pyqtSignal(QSize)
    layer_added = pyqtSignal(ImageLayer, int)
    layer_removed = pyqtSignal(ImageLayer)

    def __init__(self,
                 image_size: QSize,
                 selection_size: QSize,
                 min_selection_size: QSize,
                 max_selection_size: QSize):
        """Initializes the layer stack with an empty initial layer."""
        super().__init__()
        self._size = image_size
        self._min_selection_size = min_selection_size
        self._max_selection_size = max_selection_size
        self._selection = QRect(0, 0, selection_size.width(), selection_size.height())
        self._layers = []

    @property
    def has_image(self) -> bool:
        """Returns whether any image layers are present."""
        return len(self._layers) > 0

    @property
    def size(self) -> QSize:
        """Gets the size of the edited image."""
        return QSize(self._size.width(), self._size.height())

    @property
    def width(self) -> int:
        """Gets the width of the edited image."""
        return self._size.width()

    @property
    def height(self) -> int:
        """Gets the height of the edited image."""
        return self._size.height()

    @property
    def min_selection_size(self) -> QSize:
        """Gets the minimum size allowed for the selected editing region."""
        return self._min_selection_size

    @min_selection_size.setter
    def min_selection_size(self, new_min: QSize):
        """Sets the minimum size allowed for the selected editing region."""
        assert_type(new_min, QSize)
        self._min_selection_size = new_min
        if new_min.width() > self._selection.width() or new_min.height() > self._selection.height():
            self.selection = self._selection

    @property
    def max_selection_size(self) -> QSize:
        """Gets the maximum size allowed for the selected editing region."""
        return self._max_selection_size

    @max_selection_size.setter
    def max_selection_size(self, new_max: QSize):
        """Sets the maximum size allowed for the selected editing region."""
        assert_type(new_max, QSize)
        self._max_selection_size = new_max
        if new_max.width() < self._selection.width() or new_max.height() < self._selection.height():
            self.selection = self._selection

    def scale(self, new_size: QSize):
        """Scales all layer image content to a new resolution size."""
        assert_type(new_size, QSize)
        if new_size == self._size:
            return
        self._set_size(new_size)
        # Re-apply bounds to make sure they still fit:
        if not QRect(QPoint(0, 0), new_size).contains(self._selection):
            self.selection = self._selection
        self.size_changed.emit(self.size)
        for layer in self._layers:
            layer.scale(self.size)
        self.visible_content_changed.emit()


    def resize_canvas(self, new_size: QSize, x_offset: int, y_offset: int):
        """
        Changes all layer sizes without scaling existing image content.

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
        size_changed = self._size != new_size
        self._set_size(new_size)
        self.selection = self._selection.translated(x_offset, y_offset)
        if not QRect(QPoint(0, 0), self.size).contains(self._selection):
            self.selection = self._selection
        if size_changed:
            self.size_changed.emit(self.size)
        for layer in self._layers:
            layer.resize_canvas(self.size, x_offset, y_offset)
        self.visible_content_changed.emit()

    def create_layer(self,
                     layer_name: Optional[str] = None,
                     image_data: Optional[Image.Image | QImage | QPixmap] = None,
                     saved: bool = True,
                     index: Optional[int] = None):
        """
        Creates a new image layer and adds it to the stack.

        Parameters
        ----------
        layer_name: str or None, default=None
            Layer name string. If None, a placeholder name will be assigned.
        image_data: QImage or PIL Image or QPixmap or  None, default=None
            Initial layer image data. If None, the initial image will be transparent and size will match layer stack
            size.
        saved: bool, default=True
            Sets whether the new layer is included when saving image data
        index: int or None, default = None
            Index where the layer will be inserted into the stack. If None, it will be inserted at the top/last index.
        """
        if layer_name is None:
            default_name_pattern = r'^layer (\d+)'
            max_missing_layer = 0
            for layer in self._layers:
                match = re.match(default_name_pattern, layer.name)
                if match:
                    max_missing_layer = max(max_missing_layer, int(match.group(1)) + 1)
            layer_name = f'layer {max_missing_layer}'
        assert_type(layer_name, str)
        if index is None:
            index = len(self._layers)
        assert_valid_index(index, self._layers, allow_end=True)
        assert_type(image_data, (QImage, Image.Image, QPixmap, type(None)))
        if image_data is None:
            image_data = self.size
        layer = ImageLayer(image_data, layer_name, saved)
        self._layers.insert(index, layer)

        def handle_layer_update():
            """Pass on layer update signals."""
            if layer.visible and layer in self._layers:
                self.visible_content_changed.emit()

        layer.content_changed.connect(handle_layer_update)
        if not isinstance(layer, QSize):
            self.visible_content_changed.emit()
        self.layer_added.emit(layer, index)

    def pop_layer(self, index: int) -> ImageLayer:
        """Removes and returns an image layer."""
        assert_valid_index(index, self._layers)
        if len(self._layers) == 1:
            raise RuntimeError('Cannot remove final layer')
        removed_layer = self._layers.pop(index)
        if removed_layer.visible:
            self.visible_content_changed.emit()
        self.layer_removed.emit(removed_layer)
        return removed_layer

    def set_layer_visibility(self, index: int, visible: bool):
        """Shows or hides an image layer."""
        assert_valid_index(index, self._layers)
        self._layers[index].visible = bool(visible)
        self.visible_content_changed.emit()

    def count(self) -> int:
        """Returns the number of layers"""
        return len(self._layers)

    def get_layer(self, index: int) -> ImageLayer:
        """Returns a layer from the stack"""
        assert_valid_index(index, self._layers)
        return self._layers[index]

    def pixmap(self, saved_only: bool = True) -> QPixmap:
        """Returns combined visible layer content as a QPixmap, optionally including unsaved layers."""
        pixmap = QPixmap(self.size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        for layer in reversed(self._layers):
            if not layer.visible or (saved_only and not layer.saved):
                continue
            painter.drawPixmap(0, 0, layer.pixmap)
        painter.end()
        return pixmap

    def qimage(self, saved_only: bool = True) -> QImage:
        """Returns combined visible layer content as a QImage object, optionally including unsaved layers."""
        return self.pixmap(saved_only).toImage()

    def pil_image(self, saved_only: bool = True) -> Image.Image:
        """Returns combined visible layer content as a PIL Image object, optionally including unsaved layers."""
        return qimage_to_pil_image(self.pixmap(saved_only).toImage())

    def get_max_selection_size(self) -> QSize:
        """
        Returns the largest area that can be selected within the image, based on image size and self.max_selection_size
        """
        max_size = self.max_selection_size
        return QSize(min(max_size.width(), self.width), min(max_size.height(), self.height))

    @property
    def selection(self) -> QRect:
        """Returns the bounds of the area selected for editing within the image."""
        return QRect(self._selection.topLeft(), self._selection.size())

    @selection.setter
    def selection(self, bounds_rect: QRect):
        """
        Updates the bounds of the selected area within the image. If `bounds_rect` exceeds the maximum selection size
        or doesn't fit fully within the image bounds, the closest valid region will be selected.
        """
        assert_type(bounds_rect, QRect)
        initial_bounds = bounds_rect
        bounds_rect = QRect(initial_bounds.topLeft(), initial_bounds.size())
        # Make sure that the selection fits within allowed size limits:
        min_size = self.min_selection_size
        max_size = self.get_max_selection_size()
        if bounds_rect.width() > self.width:
            bounds_rect.setWidth(self.width)
        if bounds_rect.width() > max_size.width():
            bounds_rect.setWidth(max_size.width())
        if bounds_rect.width() < min_size.width():
            bounds_rect.setWidth(min_size.width())
        if bounds_rect.height() > self.height:
            bounds_rect.setHeight(self.height)
        if bounds_rect.height() > max_size.height():
            bounds_rect.setHeight(max_size.height())
        if bounds_rect.height() < min_size.height():
            bounds_rect.setHeight(min_size.height())

        # make sure the selection is within the image bounds:
        if bounds_rect.left() > (self.width - bounds_rect.width()):
            bounds_rect.moveLeft(self.width - bounds_rect.width())
        if bounds_rect.left() < 0:
            bounds_rect.moveLeft(0)
        if bounds_rect.top() > (self.height - bounds_rect.height()):
            bounds_rect.moveTop(self.height - bounds_rect.height())
        if bounds_rect.top() < 0:
            bounds_rect.moveTop(0)
        if bounds_rect != self._selection:
            last_bounds = self._selection
            self._selection = bounds_rect
            self.selection_bounds_changed.emit(self.selection, last_bounds)

    def cropped_pixmap_content(self, bounds_rect: QRect) -> QPixmap:
        """Returns the contents of a bounding QRect as a QPixmap."""
        assert_type(bounds_rect, QRect)
        pixmap = QPixmap(bounds_rect.size())
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        for layer in reversed(self._layers):
            if not layer.visible or not layer.saved:
                continue
            painter.drawPixmap(0, 0, layer.cropped_pixmap_content(bounds_rect))
        painter.end()
        return pixmap

    def cropped_qimage_content(self, bounds_rect: QRect) -> QImage:
        """Returns the contents of a bounding QRect as a QImage."""
        return self.cropped_pixmap_content(bounds_rect).toImage()

    def cropped_pil_image_content(self, bounds_rect: QRect) -> Image.Image:
        """Returns the contents of a bounding QRect as a PIL Image."""
        return qimage_to_pil_image(self.cropped_pixmap_content(bounds_rect).toImage())

    def pixmap_selection_content(self) -> QPixmap:
        """Returns the contents of the selection area as a QPixmap."""
        return self.cropped_pixmap_content(self.selection)

    def qimage_selection_content(self) -> QImage:
        """Returns the contents of the selection area as a QImage."""
        return self.cropped_qimage_content(self.selection)

    def pil_image_selection_content(self) -> Image.Image:
        """Returns the contents of the selection area as a PIL Image."""
        return qimage_to_pil_image(self.cropped_qimage_content(self.selection))

    def set_selection_content(self, image_data: Image.Image | QImage | QPixmap, layer_index: int = 0):
        """Updates selection content within a layer.
        Parameters
        ----------
        image_data: PIL Image or QImage or QPixmap
            Image data to draw into the selection. If the size of the image doesn't match the size of the
            bounds_rect, it will be scaled to fit.
        layer_index: int, default = 0
            Layer where image data will be inserted. If none are specified, the base layer is used.
        """
        assert_valid_index(layer_index, self._layers)
        self._layers[layer_index].insert_image_content(image_data, self.selection)

    def set_image(self, image_data: Image.Image | QImage | QPixmap | QSize, layer_index: int = 0):
        """
        Loads a new image to be edited.

        Parameters
        ----------
        image_data: PIL Image or QImage or QPixmap or QSize
            If image_data is a QSize, a transparent image will be created with the given size. Layer stack size will be
            adjusted to match image data size.
        layer_index: int, default=0
            index of the layer where the image data will be loaded.
        """
        assert_valid_index(layer_index, self._layers, allow_end=True)
        assert_type(image_data, (QImage, QPixmap, Image.Image, QSize))
        image_size = self.size
        if isinstance(image_data, (QImage, QPixmap)):
            image_size = image_data.size()
        elif isinstance(image_data, Image.Image):
            image_size = QSize(image_data.width, image_data.height)
        elif isinstance(image_data, QSize):
            image_size = image_data
        if image_size != self.size:
            self.scale(image_size)
        if layer_index == len(self._layers):
            self.create_layer()
        self._layers[layer_index].set_image(image_data)

    def _set_size(self, new_size: QSize) -> None:
        """Update the size without replacing the size object."""
        self._size.setWidth(new_size.width())
        self._size.setHeight(new_size.height())
