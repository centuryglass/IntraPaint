"""Manages an edited image composed of multiple layers."""
import re
from typing import Optional
from PyQt5.QtGui import QPainter, QPixmap, QImage, QColor
from PyQt5.QtCore import Qt, QObject, QSize, QPoint, QRect, pyqtSignal
from PIL import Image
from src.image.image_layer import ImageLayer
from src.image.mask_layer import MaskLayer
from src.util.image_utils import qimage_to_pil_image, pil_image_to_qimage
from src.util.validation import assert_type, assert_types, assert_valid_index
from src.util.cached_data import CachedData
from src.config.application_config import AppConfig
from src.undo_stack import commit_action, last_action


class LayerStack(QObject):
    """Manages an edited image composed of multiple layers."""
    visible_content_changed = pyqtSignal()
    selection_bounds_changed = pyqtSignal(QRect, QRect)
    size_changed = pyqtSignal(QSize)
    layer_added = pyqtSignal(ImageLayer, int)
    layer_removed = pyqtSignal(ImageLayer)
    active_layer_changed = pyqtSignal(int)

    def __init__(self,
                 image_size: QSize,
                 selection_size: QSize,
                 min_selection_size: QSize,
                 max_selection_size: QSize,
                 config: AppConfig):
        """Initializes the layer stack with an empty initial layer."""
        super().__init__()
        self._size = image_size
        self._min_selection_size = min_selection_size
        self._max_selection_size = max_selection_size
        self._selection = QRect(0, 0, selection_size.width(), selection_size.height())
        self._config = config
        self._copy_buffer: Optional[QImage] = None
        self.selection = self._selection

        self._image_cache_saved = CachedData(None)
        self._pixmap_cache_saved = CachedData(None)
        self._image_cache_full = CachedData(None)
        self._pixmap_cache_full = CachedData(None)
        self._layers = []
        self._active_layer: Optional[int] = None

        # Create mask layer:
        self._mask_layer = MaskLayer(image_size, config, self.selection_bounds_changed)
        self._mask_layer.update_selection(self._selection)

        def handle_mask_layer_update():
            """Refresh appropriate caches and send on signals if the mask layer changes."""
            if self._mask_layer.visible:
                self._image_cache_full.invalidate()
                self._pixmap_cache_full.invalidate()
                self.visible_content_changed.emit()

        self._mask_layer.content_changed.connect(handle_mask_layer_update)

        def handle_mask_layer_visibility_change():
            """Refresh appropriate caches and send on signals if the mask layer is shown or hidden."""
            self._image_cache_full.invalidate()
            self._pixmap_cache_full.invalidate()
            self.visible_content_changed.emit()
        self._mask_layer.content_changed.connect(handle_mask_layer_visibility_change)

    @property
    def active_layer(self) -> Optional[int]:
        """Returns the index of the layer currently selected for editing."""
        return self._active_layer

    @active_layer.setter
    def active_layer(self, new_active_layer: Optional[int]) -> None:
        """Updates the index of the layer currently selected for editing."""
        if new_active_layer is not None:
            assert_valid_index(new_active_layer, self._layers)
        self._active_layer = new_active_layer
        self.active_layer_changed.emit(new_active_layer if new_active_layer is not None else -1)

    @property
    def mask_layer(self) -> MaskLayer:
        """Returns the unique MaskLayer used for highlighting image regions."""
        return self._mask_layer

    def get_layer_index(self, layer: ImageLayer) -> Optional[int]:
        """Returns a layer's index in the stack, or None if it isn't found."""
        try:
            return self._layers.index(layer)
        except ValueError:
            return None

    @property
    def has_image(self) -> bool:
        """Returns whether any image layers are present."""
        return len(self._layers) > 0

    @property
    def size(self) -> QSize:
        """Gets the size of the edited image."""
        return QSize(self._size.width(), self._size.height())

    @size.setter
    def size(self, new_size) -> None:
        """Updates the full image size, scaling the mask layer."""
        assert_type(new_size, QSize)
        if new_size == self._size:
            return
        self._set_size(new_size)
        if self.has_image:
            self._invalidate_all_cached()
        # Re-apply bounds to make sure they still fit:
        if not QRect(QPoint(0, 0), new_size).contains(self._selection):
            self.selection = self._selection
        self.size_changed.emit(self.size)
        self._mask_layer.size = self.size
        self.visible_content_changed.emit()

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
        # Reset selection to make sure it's still in bounds:
        if not QRect(QPoint(0, 0), self.size).contains(self._selection):
            self.selection = self._selection
        if size_changed:
            self.size_changed.emit(self.size)
        for layer in [self._mask_layer, *self._layers]:
            layer.resize_canvas(self.size, x_offset, y_offset)
        if self.has_image:
            self._invalidate_all_cached()
            self.visible_content_changed.emit()

    def create_layer(self,
                     layer_name: Optional[str] = None,
                     image_data: Optional[Image.Image | QImage | QPixmap] = None,
                     saved: bool = True,
                     index: Optional[int] = None) -> None:
        """
        Creates a new image layer and adds it to the stack.

        
        - After the layer is created, the 'layer_added' signal is triggered.
        - If no layer was active, the new layer becomes active and the 'active_layer_changed' signal is triggered.
        - If the new layer is visible, the 'visible_content_changed' signal is triggered.

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
            layer = ImageLayer(self.size, layer_name, saved)
        else:
            layer = ImageLayer(image_data, layer_name, saved)

        def handle_layer_update():
            """Pass on layer update signals."""
            if layer.visible and layer in self._layers:
                if not layer.saved:
                    self._image_cache_full.invalidate()
                    self._pixmap_cache_full.invalidate()
                else:
                    self._invalidate_all_cached()
                self.visible_content_changed.emit()

        def handle_layer_visibility_change():
            """Invalidate caches and signal size change when layer visibility changes."""
            if layer in self._layers:
                self._invalidate_all_cached(not layer.saved)
                self.visible_content_changed.emit()

        last_active = self.active_layer

        def add_layer():
            """Add the layer to the stack and connect update signals."""
            self._layers.insert(index, layer)
            layer.content_changed.connect(handle_layer_update)
            layer.visibility_changed.connect(handle_layer_visibility_change)
            self.layer_added.emit(layer, index)
            if last_active is None:
                self.active_layer = index
            if layer.visible and image_data is not None:
                self._invalidate_all_cached(not layer.saved)
                self.visible_content_changed.emit()

        def undo_add_layer():
            """Disconnect update signals and remove the layer from the stack."""
            layer.content_changed.disconnect(handle_layer_update)
            layer.visibility_changed.connect(handle_layer_visibility_change)
            self._layers.remove(layer)
            if last_active is None:
                self.active_layer = None
            self.layer_removed.emit(layer)
            if layer.visible and image_data is not None:
                self._invalidate_all_cached(not layer.saved)
                self.visible_content_changed.emit()
        commit_action(add_layer, undo_add_layer)

    def copy_layer(self, index: int) -> None:
        """Copies a layer, inserting the copy below the original."""
        assert_valid_index(index, self._layers)
        layer = self._layers[index]
        self.create_layer(layer.name + ' copy', layer.qimage.copy(), layer.saved, index + 1)
        self._layers[index + 1].visible = layer.visible

    def remove_layer(self, index: int) -> None:
        """Removes an image layer.

        - If the removed index was invalid, throw an assertion error and exit.
        - If the removed layer was active, the previous layer becomes active, or no layer will become active if
          that was the last layer.
        - The 'layer_removed' signal is triggered.
        - If the active layer was after the removed layer, the 'active_layer_changed' signal is triggered with
          the adjusted index.
        - If the removed layer was visible, the 'visible_content_changed' signal is triggered.
        """
        assert_valid_index(index, self._layers)
        last_active_layer = self.active_layer
        next_active_layer = last_active_layer
        layer = self._layers[index]

        # If the removed layer is active, the layer before it becomes active:
        if last_active_layer == index:
            if self.count == 1:
                next_active_layer = None
            elif index == (self.count - 1):
                next_active_layer = (index - 1)
        elif last_active_layer is not None and last_active_layer > index:
            next_active_layer = last_active_layer - 1

        def remove() -> None:
            """Remove the layer, update active index if necessary, send appropriate signals."""
            if next_active_layer is None or next_active_layer <= index:
                self.active_layer = next_active_layer
            self._layers.pop(index)
            self.layer_removed.emit(layer)
            if next_active_layer is not None and next_active_layer > index:
                self.active_layer = next_active_layer
            else:
                self.active_layer = self.active_layer
            if layer.visible:
                self._invalidate_all_cached(not layer.saved)
                self.visible_content_changed.emit()

        def undo_remove() -> None:
            """Restore the removed layer."""
            self._layers.insert(index, layer)
            if layer.visible:
                self._invalidate_all_cached(not layer.saved)
                self.visible_content_changed.emit()
            self.layer_added.emit(layer, index)
            self.active_layer = last_active_layer
        commit_action(remove, undo_remove)

    def move_layer(self, index: int, offset: int) -> None:
        """Moves a layer up or down in the stack.

        - Layer offset is checked against layer bounds. If the layer cannot move by the given offset, the function
          will exit without doing anything.
        - The layer will first be removed, triggering all the usual signals you would get from remove_layer.
        - The layer is then inserted at the new index, triggering all the usual signals you would get from add_layer.
        - Both operations will be combined in the undo stack into a single operation.
        Parameters
        ----------
            index: int
                The index of the layer to move.
            offset: int
                The amount the index should change.
        """
        assert_valid_index(index, self._layers)
        insert_index = index + offset
        if not 0 <= insert_index <= self.count - 1:
            return

        def move(last_index, next_index):
            """Remove and replace the layer, adjusting active index as necessary."""
            active_index = self.active_layer
            layer = self._layers.pop(last_index)
            self.layer_removed.emit(layer)
            self._layers.insert(next_index, layer)
            self.layer_added.emit(layer, next_index)
            if active_index == last_index:
                self.active_layer = next_index
            elif last_index < active_index <= next_index:
                self.active_layer = active_index - 1
            elif last_index > active_index >= next_index:
                self.active_layer = active_index + 1
        commit_action(lambda i=index: move(i, insert_index), lambda i=index: move(insert_index, i))
    
    def merge_layer_down(self, index: int) -> None:
        """Merges a layer with the one beneath it on the stack.

        - If this layer is on the bottom of the stack, the function will fail silently.
        - This will trigger the 'layer_removed' signal first as the top layer is removed.
        - If the top and bottom layers don't have the same visibility, the 'visible_content_changed' signal is emitted.
        - If the active layer index was greater than or equal to the index of the removed layer, the active layer
          index will be decreased by one.
        """
        assert_valid_index(index, self._layers)
        if index == self.count - 1:
            return
        top_layer = self._layers[index]
        base_layer = self._layers[index + 1]
        active_index = self.active_layer

        base_pos = base_layer.position
        base_size = base_layer.size
        last_layer_image = base_layer.qimage.copy()
        merged_bounds = QRect(base_layer.position, base_layer.size).united(QRect(top_layer.position, top_layer.size))
        merged_image = QImage(merged_bounds.size(), QImage.Format.Format_ARGB32_Premultiplied)
        merged_image.fill(Qt.transparent)
        painter = QPainter(merged_image)
        painter.drawImage(QRect(base_pos - merged_bounds.topLeft(), base_size), last_layer_image)
        painter.drawImage(QRect(top_layer.position - merged_bounds.topLeft(), top_layer.size), top_layer.qimage)

        def do_merge() -> None:
            """Combine the two layers, adjust active index as needed."""
            self._layers.pop(index)
            self.layer_removed.emit(top_layer)
            if active_index > index:
                self.active_layer = active_index - 1
            else:
                self.active_layer = active_index
            base_layer.qimage = merged_image
            base_layer.set_position(merged_bounds.topLeft(), False)
            if top_layer.visible != base_layer.visible:
                self.visible_content_changed.emit()

        def undo_merge() -> None:
            """Revert the base layer to its previous state and re-insert the top layer."""
            base_layer.qimage = last_layer_image
            base_layer.set_position(base_pos, False)
            self._layers.insert(index, top_layer)
            self.layer_added.emit(top_layer, index)
            if self.active_layer >= index:
                self.active_layer = active_index + 1
            else:
                self.active_layer = active_index
            if top_layer.visible != base_layer.visible:
                self.visible_content_changed.emit()
        commit_action(do_merge, undo_merge)

    def copy_masked(self, index: int, use_buffer=True) -> QImage:
        """Returns the image content within a layer that's covered by the mask, optionally saving it in the copy
           buffer."""
        assert_valid_index(index, self._layers)
        inpaint_mask = self.mask_layer.qimage
        layer = self._layers[index]
        image = layer.qimage.copy()
        painter = QPainter(image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(QRect(-layer.position.x(), -layer.position.y(), image.width(), image.height()), inpaint_mask)
        painter.end()
        if use_buffer:
            self._copy_buffer = image
        return image

    def cut_masked(self, index: int, use_buffer=True) -> None:
        """Replaces all masked image content in a layer with transparency, optionally saving it in the copy
           buffer."""
        assert_valid_index(index, self._layers)
        layer = self._layers[index]
        source_content = layer.qimage.copy()
        inpaint_mask = self.mask_layer.qimage.copy()
        if use_buffer:
            self._copy_buffer = self.copy_masked(index)

        def make_cut() -> None:
            """Paint the mask on the image with the DestinationOut mode to replace masked with transparency…"""
            with layer.borrow_image() as layer_image:
                painter = QPainter(layer_image)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
                painter.drawImage(QRect(-layer.position.x(), -layer.position.y(), layer_image.width(),
                                        layer_image.height()), inpaint_mask)

        def undo_cut() -> None:
            """Restore the original image content."""
            with layer.borrow_image() as layer_image:
                painter = QPainter(layer_image)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                painter.drawImage(QRect(0, 0, layer_image.width(), layer_image.height()), source_content)
        commit_action(make_cut, undo_cut)

    def paste(self) -> None:
        """If the copy buffer contains image data, paste it into a new layer."""
        if self._copy_buffer is not None:
            insert_index = 0 if self.active_layer is None else self.active_layer
            self.create_layer("Paste layer", self._copy_buffer, index=insert_index)

    @property
    def count(self) -> int:
        """Returns the number of layers"""
        return len(self._layers)

    def get_layer(self, index: int) -> ImageLayer:
        """Returns a layer from the stack"""
        assert_valid_index(index, self._layers)
        return self._layers[index]

    def qimage(self, saved_only: bool = True) -> QImage:
        """Returns combined visible layer content as a QImage object, optionally including unsaved layers."""
        cache = self._image_cache_saved if saved_only else self._image_cache_full
        if cache.valid:
            return cache.data
        image = QImage(self.size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        for layer in [*reversed(self._layers), self._mask_layer]:
            if not layer.visible or (saved_only and not layer.saved):
                continue
            layer_image = layer.qimage
            if layer_image is not None:
                painter.drawImage(layer.position, layer_image)
        painter.end()
        cache.data = image
        return image

    def pixmap(self, saved_only: bool = True) -> QPixmap:
        """Returns combined visible layer content as a QPixmap, optionally including unsaved layers."""
        cache = self._pixmap_cache_saved if saved_only else self._pixmap_cache_full
        if cache.valid:
            return cache.data
        image = self.qimage(saved_only)
        pixmap = QPixmap.fromImage(image)
        cache.data = pixmap
        return pixmap

    def pil_image(self, saved_only: bool = True) -> Image.Image:
        """Returns combined visible layer content as a PIL Image object, optionally including unsaved layers."""
        return qimage_to_pil_image(self.qimage(saved_only))

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
    def selection(self, bounds_rect: QRect) -> None:
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

            def update_fn(prev_bounds: QRect, next_bounds: QRect) -> None:
                """Apply an arbitrary selection change."""
                if self._selection != next_bounds:
                    self._selection = next_bounds
                    self.selection_bounds_changed.emit(next_bounds, prev_bounds)
                    if next_bounds.size() != prev_bounds.size():
                        self._config.set(AppConfig.EDIT_SIZE, self._selection.size())

            action_type = 'layer_stack.selection'
            with last_action() as prev_action:
                if prev_action is not None and prev_action.type == action_type:
                    last_bounds = prev_action.action_data['prev_bounds']
                    prev_action.redo = lambda: update_fn(last_bounds, bounds_rect)
                    prev_action.undo = lambda: update_fn(bounds_rect, last_bounds)
                    prev_action.redo()
                    return

            commit_action(lambda: update_fn(last_bounds, bounds_rect),
                          lambda: update_fn(bounds_rect, last_bounds),
                          action_type, {'prev_bounds': last_bounds})

    def cropped_qimage_content(self, bounds_rect: QRect) -> QImage:
        """Returns the contents of a bounding QRect as a QImage."""
        assert_type(bounds_rect, QRect)
        image = self.qimage(saved_only=True)
        return image.copy(bounds_rect)

    def cropped_pixmap_content(self, bounds_rect: QRect) -> QPixmap:
        """Returns the contents of a bounding QRect as a QPixmap."""
        return QPixmap.fromImage(self.cropped_qimage_content(bounds_rect))

    def cropped_pil_image_content(self, bounds_rect: QRect) -> Image.Image:
        """Returns the contents of a bounding QRect as a PIL Image."""
        return qimage_to_pil_image(self.cropped_qimage_content(bounds_rect))

    def pixmap_selection_content(self) -> QPixmap:
        """Returns the contents of the selection area as a QPixmap."""
        return self.cropped_pixmap_content(self.selection)

    def qimage_selection_content(self) -> QImage:
        """Returns the contents of the selection area as a QImage."""
        return self.cropped_qimage_content(self.selection)

    def pil_image_selection_content(self) -> Image.Image:
        """Returns the contents of the selection area as a PIL Image."""
        return qimage_to_pil_image(self.cropped_qimage_content(self.selection))

    def set_selection_content(self,
                              image_data: Image.Image | QImage | QPixmap,
                              layer_index: Optional[int] = None,
                              composition_mode: QPainter.CompositionMode = QPainter.CompositionMode_Source):
        """Updates selection content within a layer.
        Parameters
        ----------
        image_data: PIL Image or QImage or QPixmap
            Image data to draw into the selection. If the size of the image doesn't match the size of the
            bounds_rect, it will be scaled to fit.
        layer_index: int, default = None
            Layer where image data will be inserted. If none is specified, the active layer is used.
        composition_mode: QPainter.CompositionMode, default=Source
            Mode used to insert image content. Default behavior is for the new image content to completely replace the
            old content.
        """
        if layer_index is None:
            layer_index = self.active_layer
        assert_valid_index(layer_index, self._layers)
        self._layers[layer_index].insert_image_content(image_data, self.selection, composition_mode)

    def set_image(self, image_data: Image.Image | QImage | QPixmap, layer_index: int = 0):
        """
        Loads a new image to be edited.

        Parameters
        ----------
        image_data: PIL Image or QImage or QPixmap
            Layer stack size will be adjusted to match image data size.
        layer_index: int, default=0
            index of the layer where the image data will be loaded.
        """
        assert_valid_index(layer_index, self._layers, allow_end=True)
        assert_type(image_data, (QImage, QPixmap, Image.Image))
        if layer_index == len(self._layers):
            self.create_layer()
        if isinstance(image_data, QPixmap):
            self.size = image_data.size()
            self._layers[layer_index].pixmap = image_data
        elif isinstance(image_data, QImage):
            self.size = image_data.size()
            self._layers[layer_index].qimage = image_data
        else:  # PIL Image
            self.size = QSize(image_data.width, image_data.height)
            self._layers[layer_index].qimage = pil_image_to_qimage(image_data)

    def get_color_at_point(self, image_point: QPoint) -> QColor:
        """Gets the combined color of visible saved layers at a single point, or QColor(0, 0, 0) if out of bounds."""
        if not (0 <= image_point.x() < self.size.width()) or not (0 <= image_point.y() < self.size.height()):
            return QColor(0, 0, 0)
        return self.qimage(True).pixelColor(image_point)

    def _set_size(self, new_size: QSize) -> None:
        """Update the size without replacing the size object."""
        self._size.setWidth(new_size.width())
        self._size.setHeight(new_size.height())
        self.selection = self._selection

    def _has_unsaved(self) -> bool:
        """Returns whether any layers are present that should not be saved."""
        return any(layer.saved is False for layer in self._layers)

    def _invalidate_all_cached(self, full_caches_only=False) -> None:
        """Mark all image/pixmap caches as invalid."""
        if not full_caches_only:
            self._image_cache_saved.invalidate()
            self._pixmap_cache_saved.invalidate()
        self._image_cache_full.invalidate()
        self._pixmap_cache_full.invalidate()

