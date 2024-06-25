"""Manages an edited image composed of multiple layers."""
import json
import os.path
import re
import shutil
import tempfile
from typing import Optional, Tuple, Dict, Any, List

from PIL import Image
from PyQt5.QtCore import Qt, QObject, QSize, QPoint, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QPixmap, QImage, QColor

from src.config.application_config import AppConfig
from src.image.image_layer import ImageLayer
from src.image.selection_layer import SelectionLayer
from src.undo_stack import commit_action, last_action
from src.util.cached_data import CachedData
from src.util.image_utils import qimage_to_pil_image
from src.util.shared_constants import COMPOSITION_MODES
from src.util.validation import assert_type, assert_types, assert_valid_index

LAYER_DATA_FILE_EMBEDDED = 'data.json'

SELECTION_LAYER_FILE_EMBEDDED = 'selection.png'


class LayerStack(QObject):
    """Manages an edited image composed of multiple layers."""
    visible_content_changed = pyqtSignal()
    generation_area_bounds_changed = pyqtSignal(QRect)
    size_changed = pyqtSignal(QSize)
    layer_added = pyqtSignal(ImageLayer, int)
    layer_removed = pyqtSignal(ImageLayer)
    active_layer_changed = pyqtSignal(int, int)  # emits id, index

    def __init__(self,
                 image_size: QSize,
                 generation_area_size: QSize,
                 min_generation_area_size: QSize,
                 max_generation_area_size: QSize):
        """Initializes the layer stack with an empty initial layer."""
        super().__init__()
        self._size = image_size
        self._min_generation_area_size = min_generation_area_size
        self._max_generation_area_size = max_generation_area_size
        self._generation_area = QRect(0, 0, generation_area_size.width(), generation_area_size.height())
        self._copy_buffer: Optional[QImage] = None
        self.generation_area = self._generation_area

        self._image_cache_saved = CachedData(None)
        self._pixmap_cache_saved = CachedData(None)
        self._image_cache_full = CachedData(None)
        self._pixmap_cache_full = CachedData(None)
        self._layers: List[ImageLayer] = []
        self._active_layer_id: Optional[int] = None

        # Create selection layer:
        self._selection_layer = SelectionLayer(image_size, self.generation_area_bounds_changed)
        self._selection_layer.update_generation_area(self._generation_area)

        def handle_selection_layer_update():
            """Refresh appropriate caches and send on signals if the selection layer changes."""
            if self._selection_layer.visible:
                self._image_cache_full.invalidate()
                self._pixmap_cache_full.invalidate()
                self.visible_content_changed.emit()

        self._selection_layer.content_changed.connect(handle_selection_layer_update)

        def handle_selection_layer_visibility_change():
            """Refresh appropriate caches and send on signals if the selection layer is shown or hidden."""
            self._image_cache_full.invalidate()
            self._pixmap_cache_full.invalidate()
            self.visible_content_changed.emit()

        self._selection_layer.content_changed.connect(handle_selection_layer_visibility_change)

    # PROPERTY DEFINITIONS:

    @property
    def count(self) -> int:
        """Returns the number of layers"""
        return len(self._layers)

    @property
    def active_layer(self) -> Optional[ImageLayer]:
        """Returns the active layer object, or None if the layer stack is empty."""
        return None if self._active_layer_id is None else self.get_layer_by_id(self._active_layer_id)

    @active_layer.setter
    def active_layer(self, new_active_layer: Optional[ImageLayer | int]) -> None:
        """Updates the active layer when given a new layer or layer id."""
        last_id = self._active_layer_id
        last_idx = None if last_id is None else self.get_layer_index(last_id)
        if new_active_layer is None:
            new_id = None
            layer = None
        elif isinstance(new_active_layer, ImageLayer):
            new_id = new_active_layer.id
            layer = new_active_layer
        elif isinstance(new_active_layer, int):
            new_id = new_active_layer
            layer = self.get_layer_by_id(new_id)
        else:
            raise TypeError(f'Invalid active layer parameter {new_active_layer}, expected ImageLayer or int ID.')
        if layer is not None:
            assert layer in self._layers, f'Tried to set removed or invalid layer {layer.name} as active'
        new_idx = None if layer is None else self.get_layer_index(layer)
        if last_id == new_id and last_idx == new_idx:
            return
        self._active_layer_id = new_id
        self.active_layer_changed.emit(new_id, new_idx)

    @property
    def active_layer_id(self) -> Optional[int]:
        """Returns the unique integer ID of the active layer, or None if no layer is active."""
        return self._active_layer_id

    @property
    def active_layer_index(self) -> Optional[int]:
        """Returns the index of the layer currently selected for editing."""
        if self._active_layer_id is None:
            return None
        for i in range(self.count):
            if self._layers[i].id == self.active_layer_id:
                return i
        layer_ids = [layer.id for layer in self._layers]
        raise RuntimeError(f'active_layer_index: layer with ID {self.active_layer_id} '
                           f'not found in {self.count} layers, actual IDs = {layer_ids}')

    @property
    def selection_layer(self) -> SelectionLayer:
        """Returns the unique SelectionLayer used for highlighting image regions."""
        return self._selection_layer

    @property
    def has_image(self) -> bool:
        """Returns whether any image layers are present."""
        return len(self._layers) > 0

    @property
    def geometry(self) -> QRect:
        """Gets image geometry as a QRect. Image position will always be 0,0, so this is mostly a convenience function
           for assorted rectangle calculations."""
        return QRect(QPoint(0, 0), self._size)

    @property
    def merged_layer_geometry(self) -> QRect:
        """Gets the bounding box containing all image layers."""
        bounds = self.geometry
        for layer in self._layers:
            bounds = bounds.united(layer.geometry)
        return bounds

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
        if not QRect(QPoint(0, 0), new_size).contains(self._generation_area):
            self._set_generation_area_internal(self._generation_area)
        self.size_changed.emit(self.size)
        self._selection_layer.size = self.size
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
    def min_generation_area_size(self) -> QSize:
        """Gets the minimum size allowed for the selected editing region."""
        return self._min_generation_area_size

    @min_generation_area_size.setter
    def min_generation_area_size(self, new_min: QSize):
        """Sets the minimum size allowed for the selected editing region."""
        assert_type(new_min, QSize)
        self._min_generation_area_size = new_min
        if new_min.width() > self._generation_area.width() or new_min.height() > self._generation_area.height():
            self._set_generation_area_internal(self._generation_area)

    @property
    def max_generation_area_size(self) -> QSize:
        """Gets the maximum size allowed for the selected editing region."""
        return self._max_generation_area_size

    @max_generation_area_size.setter
    def max_generation_area_size(self, new_max: QSize):
        """Sets the maximum size allowed for the selected editing region."""
        assert_type(new_max, QSize)
        self._max_generation_area_size = new_max
        if new_max.width() < self._generation_area.width() or new_max.height() < self._generation_area.height():
            self._set_generation_area_internal(self._generation_area)

    @property
    def generation_area(self) -> QRect:
        """Returns the bounds of the area selected for editing within the image."""
        return QRect(self._generation_area.topLeft(), self._generation_area.size())

    @generation_area.setter
    def generation_area(self, bounds_rect: QRect) -> None:
        """
        Updates the bounds of the image generation area within the image. If `bounds_rect` exceeds the maximum  size
        or doesn't fit fully within the image bounds, the closest valid region will be selected.
        """
        assert_type(bounds_rect, QRect)
        bounds_rect = self._get_closest_valid_generation_area(bounds_rect)
        if bounds_rect != self._generation_area:
            last_bounds = self._generation_area

            def update_fn(prev_bounds: QRect, next_bounds: QRect) -> None:
                """Apply an arbitrary image generation area change."""
                if self._generation_area != next_bounds:
                    self._generation_area = next_bounds
                    self.generation_area_bounds_changed.emit(next_bounds)
                    if next_bounds.size() != prev_bounds.size():
                        AppConfig.instance().set(AppConfig.EDIT_SIZE, QSize(self._generation_area.size()))

            action_type = 'layer_stack.generation_area'
            with last_action() as prev_action:
                if prev_action is not None and prev_action.type == action_type and prev_action.action_data is not None:
                    last_bounds = prev_action.action_data['prev_bounds']
                    prev_action.redo = lambda: update_fn(last_bounds, bounds_rect)
                    prev_action.undo = lambda: update_fn(bounds_rect, last_bounds)
                    prev_action.redo()
                    return

            commit_action(lambda: update_fn(last_bounds, bounds_rect),
                          lambda: update_fn(bounds_rect, last_bounds),
                          action_type, {'prev_bounds': last_bounds})

    # IMAGE ACCESS / MANIPULATION FUNCTIONS:

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
        self.generation_area = self._generation_area.translated(x_offset, y_offset)
        # Reset image generation area to make sure it's still in bounds:
        if not QRect(QPoint(0, 0), self.size).contains(self._generation_area):
            self.generation_area = self._generation_area
        if size_changed:
            self.size_changed.emit(self.size)
        for layer in [self._selection_layer, *self._layers]:
            layer.resize_canvas(self.size, x_offset, y_offset)
        if self.has_image:
            self._invalidate_all_cached()
            self.visible_content_changed.emit()

    def qimage(self, saved_only: bool = True) -> QImage:
        """Returns combined visible layer content as a QImage object, optionally including unsaved layers."""
        cache = self._image_cache_saved if saved_only else self._image_cache_full
        if cache.valid:
            return cache.data
        image = QImage(self.size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        for layer in [*reversed(self._layers), self._selection_layer]:
            if not layer.visible or (saved_only and not layer.saved):
                continue
            layer_image = layer.qimage
            if layer_image is not None:
                painter.setOpacity(layer.opacity)
                painter.setCompositionMode(layer.composition_mode)
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

    def get_max_generation_area_size(self) -> QSize:
        """
        Returns the largest area that can be selected within the image, based on image size and self.max_generation_area_size
        """
        max_size = self.max_generation_area_size
        return QSize(min(max_size.width(), self.width), min(max_size.height(), self.height))

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

    def pixmap_generation_area_content(self) -> QPixmap:
        """Returns the contents of the image generation area as a QPixmap."""
        return self.cropped_pixmap_content(self.generation_area)

    def qimage_generation_area_content(self) -> QImage:
        """Returns the contents of the image generation area as a QImage."""
        return self.cropped_qimage_content(self.generation_area)

    def pil_image_generation_area_content(self) -> Image.Image:
        """Returns the contents of the image generation area as a PIL Image."""
        return qimage_to_pil_image(self.cropped_qimage_content(self.generation_area))

    def get_color_at_point(self, image_point: QPoint) -> QColor:
        """Gets the combined color of visible saved layers at a single point, or QColor(0, 0, 0) if out of bounds."""
        if not 0 <= image_point.x() < self.size.width() or not 0 <= image_point.y() < self.size.height():
            return QColor(0, 0, 0)
        return self.qimage(True).pixelColor(image_point)

    # LAYER ACCESS / MANIPULATION FUNCTIONS:

    def get_layer_by_index(self, index: int) -> ImageLayer:
        """Returns a layer from the stack"""
        assert_valid_index(index, self._layers)
        return self._layers[index]

    def get_layer_by_id(self, layer_id: Optional[int]) -> Optional[ImageLayer]:
        """Returns a layer from the stack, or None if no matching layer was found."""
        if layer_id is None:
            return None
        for layer in self._layers:
            if layer.id == layer_id:
                return layer
        return None

    def get_layer_index(self, layer: ImageLayer | int) -> Optional[int]:
        """Returns a layer's index in the stack, or None if it isn't found."""
        if isinstance(layer, ImageLayer):
            try:
                return self._layers.index(layer)
            except (KeyError, ValueError):
                return None
        elif isinstance(layer, int):
            for i in range(self.count):
                if self._layers[i].id == layer:
                    return i
        return None

    def create_layer(self,
                     layer_name: Optional[str] = None,
                     image_data: Optional[Image.Image | QImage | QPixmap] = None,
                     saved: bool = True,
                     layer_index: Optional[int] = None) -> None:
        """
        Creates a new image layer and adds it to the stack.

        - After the layer is created, the 'layer_added' signal is triggered.
        - If no layer was active, the new layer becomes active and the 'active_layer_index_changed' signal is triggered.
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
        layer_index: int or None, default = None
            Index where the layer will be inserted into the stack. If None, it will be inserted above the active layer.
        """
        if layer_index is None:
            active_index = self.active_layer_index
            layer_index = len(self._layers) if active_index is None else active_index
        assert_valid_index(layer_index, self._layers, allow_end=True)
        layer = self._create_layer_internal(layer_name, image_data, saved)

        def _create_new(new_layer=layer, i=layer_index) -> None:
            self._insert_layer_internal(new_layer, i, True)

        def _remove_new(new_layer=layer):
            self._remove_layer_internal(new_layer, True)

        commit_action(_create_new, _remove_new)

    def copy_layer(self, layer: Optional[ImageLayer | int] = None) -> None:
        """Copies a layer, inserting the copy below the original.
        Parameters
        ----------
            layer: ImageLayer | int | None, default=None
                The layer object to copy, or its id. If None, the active layer will be used, and the method will fail
                silently if no layer is active.
        """
        layer, layer_index = self._layer_values_from_layer_or_id_or_active(layer)
        assert layer is not None and layer_index is not None
        assert_valid_index(layer_index, self._layers)
        self.create_layer(layer.name + ' copy', layer.qimage, layer.saved, layer_index + 1)
        self._layers[layer_index + 1].visible = layer.visible

    def remove_layer(self, layer: Optional[ImageLayer | int] = None) -> None:
        """Removes an image layer.

        - If the removed layer_index was invalid, throw an assertion error and exit.
        - If the removed layer was active, the previous layer becomes active, or no layer will become active if
          that was the last layer.
        - The 'layer_removed' signal is triggered.
        - If the active layer was after the removed layer, the 'active_layer_index_changed' signal is triggered with
          the adjusted layer_index.
        - If the removed layer was visible, the 'visible_content_changed' signal is triggered.

        Parameters
        ----------
            layer: ImageLayer | int | None, default=None
                The layer object to copy, or its id. If None, the active layer will be used, and the method will fail
                silently if no layer is active.
        """
        removed_layer, removed_layer_index = self._layer_values_from_layer_or_id_or_active(layer)
        if removed_layer is None:
            return

        def _remove(img_layer=removed_layer):
            self._remove_layer_internal(img_layer)

        def _undo_remove(img_layer=removed_layer, idx=removed_layer_index):
            self._insert_layer_internal(img_layer, idx)

        commit_action(_remove, _undo_remove)

    def offset_active_selection(self, offset: int) -> None:
        """Picks a new active layer relative to the index of the previous active layer. Does nothing if no layer is
           inactive or the new index would be out of bounds."""
        if self.active_layer_index is None:
            return
        new_index = self.active_layer_index + offset
        if not 0 <= new_index < self.count:
            return
        self.active_layer = self.get_layer_by_index(new_index)

    def move_layer(self, offset: int, layer: Optional[ImageLayer | int] = None) -> None:
        """Moves a layer up or down in the stack.

        - Layer offset is checked against layer bounds. If the layer cannot move by the given offset, the function
          will exit without doing anything.
        - The layer will first be removed, triggering all the usual signals you would get from remove_layer.
        - The layer is then inserted at the new layer_index, triggering all the usual signals you would get from
           add_layer.
        - Both operations will be combined in the undo stack into a single operation.

        Parameters
        ----------
            offset: int
                The amount the layer index should change.
            layer: ImageLayer | int | None, default=None
                The layer object to copy, or its id. If None, the active layer will be used, and the method will fail
                silently if no layer is active.
        """
        moved_layer, moved_layer_index = self._layer_values_from_layer_or_id_or_active(layer)
        assert moved_layer is not None and moved_layer_index is not None
        assert_valid_index(moved_layer_index, self._layers)
        insert_index = moved_layer_index + offset
        if not 0 <= insert_index <= self.count - 1:
            return

        def _move(last_index, new_index):
            moving_layer = self._layers[last_index]
            is_active = moving_layer.id == self._active_layer_id
            self._remove_layer_internal(moving_layer)
            self._insert_layer_internal(moving_layer, new_index)
            if is_active:
                self._active_layer_id = moving_layer.id
                self.active_layer_changed.emit(moving_layer.id, new_index)

        def _make_move(from_idx=moved_layer_index, to_idx=insert_index):
            _move(from_idx, to_idx)

        def _move_back(to_idx=moved_layer_index, from_idx=insert_index):
            _move(from_idx, to_idx)

        commit_action(_make_move, _move_back)

    def merge_layer_down(self, layer: Optional[ImageLayer | int] = None) -> None:
        """Merges a layer with the one beneath it on the stack.

        - If this layer is on the bottom of the stack, the function will fail silently.
        - This will trigger the 'layer_removed' signal first as the top layer is removed.
        - If the top and bottom layers don't have the same visibility, the 'visible_content_changed' signal is emitted.
        - If the active layer layer_index was greater than or equal to the layer_index of the removed layer, the active
          layer index will be decreased by one.

        Parameters
        ----------
            layer: ImageLayer | int | None, default=None
                The layer object to copy, or its id. If None, the active layer will be used, and the method will fail
                silently if no layer is active.
        """
        top_layer, top_layer_index = self._layer_values_from_layer_or_id_or_active(layer)
        assert top_layer is not None and top_layer_index is not None
        if top_layer_index == self.count - 1:
            return
        base_layer, base_layer_index = self._layer_values_from_layer_or_id_or_active(self._layers[top_layer_index + 1])
        assert base_layer is not None and base_layer_index is not None

        base_pos = base_layer.position
        base_size = base_layer.size
        base_layer_image = base_layer.qimage
        merged_bounds = QRect(base_layer.position, base_layer.size).united(QRect(top_layer.position, top_layer.size))
        merged_image = QImage(merged_bounds.size(), QImage.Format.Format_ARGB32_Premultiplied)
        merged_image.fill(Qt.transparent)
        painter = QPainter(merged_image)
        painter.drawImage(QRect(base_pos - merged_bounds.topLeft(), base_size), base_layer_image)
        painter.drawImage(QRect(top_layer.position - merged_bounds.topLeft(), top_layer.size), top_layer.qimage)

        def _do_merge() -> None:
            self._remove_layer_internal(top_layer, True)
            base_layer.qimage = merged_image
            base_layer.set_position(merged_bounds.topLeft(), False)
            if top_layer.visible != base_layer.visible:
                self.visible_content_changed.emit()

        def _undo_merge() -> None:
            base_layer.qimage = base_layer_image
            base_layer.set_position(base_pos, False)
            self._insert_layer_internal(top_layer, True)

        commit_action(_do_merge, _undo_merge)

    def layer_to_image_size(self, layer: Optional[ImageLayer | int] = None) -> None:
        """Resizes a layer to match the image size. Out-of-bounds content is cropped, new content is transparent.

        Parameters
        ----------
            layer: ImageLayer | int | None, default=None
                The layer object to copy, or its id. If None, the active layer will be used, and the method will fail
                silently if no layer is active.
        """
        layer, _ = self._layer_values_from_layer_or_id_or_active(layer)
        if layer is None:
            return
        layer_bounds = QRect(layer.position, layer.size)
        image_bounds = QRect(0, 0, self.width, self.height)
        if layer_bounds == image_bounds:
            return
        layer_position = layer_bounds.topLeft()
        layer_image = layer.qimage
        resized_image = QImage(self.size, QImage.Format.Format_ARGB32_Premultiplied)
        resized_image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(resized_image)
        painter.drawImage(layer_bounds, layer_image)
        painter.end()

        def _resize() -> None:
            layer.qimage = resized_image
            layer.set_position(QPoint(0, 0), False)
            if layer.visible and not image_bounds.contains(layer_bounds):
                self.visible_content_changed.emit()

        def _undo_resize() -> None:
            layer.qimage = layer_image
            layer.set_position(layer_position, False)
            if layer.visible and not image_bounds.contains(layer_bounds):
                self.visible_content_changed.emit()

        commit_action(_resize, _undo_resize)

    def copy_selected(self, layer: Optional[ImageLayer | int] = None) -> Optional[QImage]:
        """Returns the image content within a layer that's covered by the mask, saving it in the copy buffer.

        Parameters
        ----------
            layer: ImageLayer | int | None, default=None
                The layer object to copy, or its id. If None, the active layer will be used, and the method will fail
                silently if no layer is active.
        """
        layer, _ = self._layer_values_from_layer_or_id_or_active(layer)
        if layer is None:
            return None
        selection_mask = self.selection_layer.qimage
        image = layer.cropped_image_content(QRect(-layer.position.x(), -layer.position.y(), self.width, self.height))
        painter = QPainter(image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(QRect(0, 0, image.width(), image.height()), selection_mask)
        painter.end()
        self._copy_buffer = image
        return image

    def cut_selected(self, layer: Optional[ImageLayer | int] = None) -> None:
        """Replaces all masked image content in a layer with transparency, saving it in the copy buffer."""
        layer, _ = self._layer_values_from_layer_or_id_or_active(layer)
        if layer is None:
            return
        source_content = layer.qimage
        selection_mask = self.selection_layer.qimage.copy()
        self._copy_buffer = self.copy_selected(layer)

        def _make_cut() -> None:
            with layer.borrow_image() as layer_image:
                assert layer_image is not None
                painter = QPainter(layer_image)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
                painter.drawImage(QRect(-layer.position.x(), -layer.position.y(), layer_image.width(),
                                        layer_image.height()), selection_mask)

        def _undo_cut() -> None:
            with layer.borrow_image() as layer_image:
                assert layer_image is not None
                painter = QPainter(layer_image)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                painter.drawImage(QRect(0, 0, layer_image.width(), layer_image.height()), source_content)

        commit_action(_make_cut, _undo_cut)

    def paste(self) -> None:
        """If the copy buffer contains image data, paste it into a new layer."""
        if self._copy_buffer is not None:
            insert_index = 0 if self.active_layer_index is None else self.active_layer_index
            self.create_layer('Paste layer', self._copy_buffer.copy(), layer_index=insert_index)
            self.active_layer = self._layers[insert_index]

    def set_generation_area_content(self,
                                    image_data: Image.Image | QImage | QPixmap,
                                    layer: Optional[ImageLayer | int] = None,
                                    composition_mode: QPainter.CompositionMode = QPainter.CompositionMode_Source):
        """Updates image generation area content within a layer.
        Parameters
        ----------
        image_data: PIL Image or QImage or QPixmap
            Image data to draw into the image generation area. If the size of the image doesn't match the size of the
            bounds_rect, it will be scaled to fit.
        layer: ImageLayer | int | None, default=None
            The layer object to copy, or its id. If None, the active layer will be used
        composition_mode: QPainter.CompositionMode, default=Source
            Mode used to insert image content. Default behavior is for the new image content to completely replace the
            old content.
        """
        insert_layer, _ = self._layer_values_from_layer_or_id_or_active(layer)
        if insert_layer is None:
            raise RuntimeError(f'set_selection_content: No layer specified, and no layer is active, layer={layer}')
        insert_layer.insert_image_content(image_data, self.generation_area, composition_mode)

    def save_layer_stack_file(self, file_path: str, metadata: Optional[Dict[str, Any]]) -> None:
        """Save layers and image metadata to a file that can be opened for future editing."""
        size = self.size
        data: Dict[str, Any] = {'metadata': metadata, 'size': f'{size.width()}x{size.height()}', 'files': []}
        # Create temporary directory tmpdir
        tmpdir = tempfile.mkdtemp()
        self.selection_layer.qimage.save(os.path.join(tmpdir, SELECTION_LAYER_FILE_EMBEDDED))
        for layer in self._layers:
            index = self._layers.index(layer)
            layer.qimage.save(os.path.join(tmpdir, f'{index}.png'))
            composition_mode = ''
            for mode_name, mode_type in COMPOSITION_MODES.items():
                if mode_type == layer.composition_mode:
                    composition_mode = mode_name
                    break
            data['files'].append({
                'name': layer.name,
                'pos': f'{layer.position.x()},{layer.position.y()}',
                'visible': layer.visible,
                'opacity': layer.opacity,
                'mode': composition_mode
            })
        json_path = os.path.join(tmpdir, LAYER_DATA_FILE_EMBEDDED)
        with open(json_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
        shutil.make_archive(file_path, 'zip', tmpdir)
        shutil.move(f'{file_path}.zip', file_path)
        shutil.rmtree(tmpdir)

    def load_layer_stack_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Load layers and image metadata from a file, returning the metadata."""
        tmpdir = tempfile.mkdtemp()
        shutil.unpack_archive(file_path, tmpdir, format='zip')
        old_mask_image = self.selection_layer.qimage
        old_layers = self._layers.copy()
        new_layers = []
        old_size = self.size
        with open(os.path.join(tmpdir, LAYER_DATA_FILE_EMBEDDED)) as json_file:
            data = json.load(json_file)
        w, h = (int(substr) for substr in data['size'].split('x'))
        new_size = QSize(w, h)
        new_mask_image = QImage(os.path.join(tmpdir, SELECTION_LAYER_FILE_EMBEDDED))
        for i, file_data in enumerate(data['files']):
            image = QImage(os.path.join(tmpdir, f'{i}.png'))
            name = None
            if 'name' in file_data:
                name = file_data['name']
            layer = self._create_layer_internal(name, image)
            if 'pos' in file_data:
                x, y = (int(substr) for substr in file_data['pos'].split(','))
                layer.position = QPoint(x, y)
            if 'visible' in file_data:
                layer.visible = file_data['visible']
            if 'opacity' in file_data:
                layer.opacity = file_data['opacity']
            if 'mode' in file_data:
                mode_name = file_data['mode']
                if mode_name in COMPOSITION_MODES:
                    layer.composition_mode = COMPOSITION_MODES[mode_name]
            new_layers.append(layer)
        shutil.rmtree(tmpdir)

        def _load():
            for old_layer in old_layers:
                self._remove_layer_internal(old_layer)
            self._set_size(new_size)
            self.selection_layer.qimage = new_mask_image
            for new_layer in new_layers:
                self._insert_layer_internal(new_layer, self.count)

        def _undo_load():
            for new_layer in new_layers:
                self._remove_layer_internal(new_layer)
            self._set_size(old_size)
            self.selection_layer.qimage = old_mask_image
            for old_layer in old_layers:
                self._insert_layer_internal(old_layer, self.count)

        commit_action(_load, _undo_load)
        metadata = data['metadata']
        return metadata

    def set_image(self, image_data: Image.Image | QImage | QPixmap):
        """
        Loads a new image to be edited. This clears all layers, updates the image size, and inserts the image as a new
        active layer.

        Parameters
        ----------
        image_data: PIL Image or QImage or QPixmap
            Layer stack size will be adjusted to match image data size.
        """
        old_layers = self._layers.copy()
        old_size = self.size
        selection_image = self.selection_layer.qimage.copy()
        new_layer = self._create_layer_internal(None, image_data)
        new_size = new_layer.size
        gen_area = QRect(self._generation_area)
        new_gen_area = gen_area.intersected(new_layer.geometry)

        def _load():
            self.selection_layer.clear()
            for layer in reversed(old_layers):
                self._remove_layer_internal(layer, True)
            self.size = new_size
            self._insert_layer_internal(new_layer, self.count)
            self._set_generation_area_internal(new_gen_area)

        def _undo_load():
            assert self.count == 1, f'Unexpected layer count {self.count} when reversing image load!'
            self._remove_layer_internal(new_layer)
            self.size = old_size
            for layer in old_layers:
                self._insert_layer_internal(layer, self.count)
            self.selection_layer.qimage = selection_image
            self._set_generation_area_internal(gen_area)

        commit_action(_load, _undo_load)

    # INTERNAL:

    def _set_size(self, new_size: QSize) -> None:
        """Update the size without replacing the size object."""
        self._size.setWidth(new_size.width())
        self._size.setHeight(new_size.height())
        self._set_generation_area_internal(self._generation_area)
        self.selection_layer.size = new_size

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

    def _layer_values_from_layer_or_id_or_active(self, layer: Optional[ImageLayer | int]) -> Tuple[Optional[ImageLayer],
    Optional[int]]:
        """Returns layer, layer_id, layer_index, given a layer, id, or None. If None, use the active layer."""
        if layer is None:
            if self._active_layer_id is None:
                return None, None
            layer = self.active_layer
        elif isinstance(layer, int):
            layer = self.get_layer_by_id(layer)
        elif not isinstance(layer, ImageLayer):
            raise TypeError(f'Invalid layer parameter {layer}, expected ImageLayer or int ID')
        layer_index = None if layer is None else self.get_layer_index(layer)
        return layer, layer_index

    def _layer_content_change_slot(self, layer: ImageLayer, _=None) -> None:
        if layer.visible and layer in self._layers:
            if not layer.saved:
                self._image_cache_full.invalidate()
                self._pixmap_cache_full.invalidate()
            else:
                self._invalidate_all_cached()
            self.visible_content_changed.emit()

    def _layer_visibility_change_slot(self, layer: ImageLayer, _) -> None:
        if layer in self._layers:
            self._invalidate_all_cached(not layer.saved)
            self.visible_content_changed.emit()

    def _create_layer_internal(self, layer_name: Optional[str] = None,
                               image_data: Optional[Image.Image | QImage | QPixmap] = None,
                               saved: bool = True) -> ImageLayer:
        """Returns a new layer object given valid data. This emits no signals, connects no signal handlers, and does
           not add the layer to the stack."""
        if layer_name is None:
            default_name_pattern = r'^layer (\d+)'
            max_missing_layer = 0
            for layer in self._layers:
                match = re.match(default_name_pattern, layer.name)
                if match:
                    max_missing_layer = max(max_missing_layer, int(match.group(1)) + 1)
            layer_name = f'layer {max_missing_layer}'
        assert_type(layer_name, str)
        assert_type(image_data, (QImage, Image.Image, QPixmap, type(None)))
        if image_data is None:
            layer = ImageLayer(self.size, layer_name, saved)
        else:
            layer = ImageLayer(image_data, layer_name, saved)
        return layer

    def _insert_layer_internal(self, layer: ImageLayer, index: int, connect_signals=True, empty_image=False) -> None:
        """Insert a layer into the stack, optionally connect layer signals, and emit all required layer stack signals.
           This does not alter the undo history."""
        if index is None:
            index = len(self._layers)
        assert layer not in self._layers, f'layer {layer.name} is already in the layer stack.'
        assert_valid_index(index, self._layers, allow_end=True)
        if connect_signals:
            layer.content_changed.connect(self._layer_content_change_slot)
            layer.opacity_changed.connect(self._layer_content_change_slot)
            layer.composition_mode_changed.connect(self._layer_content_change_slot)
            layer.visibility_changed.connect(self._layer_visibility_change_slot)
        self._layers.insert(index, layer)
        self.layer_added.emit(layer, index)
        active_id = self.active_layer_id
        active_index = self.active_layer_index
        if active_index is None or active_id is None:
            self._active_layer_id = layer.id
            self.active_layer_changed.emit(layer.id, index)
        elif active_index >= index:
            self.active_layer_changed.emit(active_id, active_index)
        if layer.visible and not empty_image:
            self._invalidate_all_cached(not layer.saved)
            self.visible_content_changed.emit()

    def _remove_layer_internal(self, layer: ImageLayer, disconnect_signals=True) -> None:
        """Removes a layer from the stack, optionally disconnect layer signals, and emit all required layer stack
           signals. This does not alter the undo history."""
        assert layer in self._layers, f'layer {layer.name} is not in the stack.'
        if disconnect_signals:
            layer.content_changed.disconnect(self._layer_content_change_slot)
            layer.opacity_changed.disconnect(self._layer_content_change_slot)
            layer.composition_mode_changed.disconnect(self._layer_content_change_slot)
            layer.visibility_changed.disconnect(self._layer_visibility_change_slot)

        active_layer = self.active_layer
        active_layer_index = self.active_layer_index
        assert active_layer is not None and active_layer_index is not None

        next_active_layer: Optional[ImageLayer] = active_layer
        next_active_layer_index: Optional[int] = self.active_layer_index
        index = self.get_layer_index(layer)
        assert index is not None and next_active_layer_index is not None

        if active_layer == layer:  # index stays the same, but active layer changes
            if active_layer_index < self.count - 1:  # Switch to layer below if possible
                next_active_layer = self._layers[next_active_layer_index + 1]
            elif active_layer_index > 0:  # Otherwise switch to layer above
                next_active_layer = self._layers[next_active_layer_index - 1]
            else:  # Removing last layer
                next_active_layer = None
                next_active_layer_index = None
        elif index < active_layer_index:  # Index changes, active layer is the same:
            next_active_layer_index -= 1

        if next_active_layer is None or next_active_layer != self.active_layer:
            self._active_layer_id = None if next_active_layer is None else next_active_layer.id
            self.active_layer_changed.emit(self._active_layer_id, self.active_layer_index)
        self._layers.pop(index)
        self.layer_removed.emit(layer)
        if next_active_layer_index is not None and next_active_layer_index != active_layer_index:
            self.active_layer_changed.emit(self._active_layer_id, next_active_layer_index)
        if layer.visible:
            self._invalidate_all_cached(not layer.saved)
            self.visible_content_changed.emit()

    def _get_closest_valid_generation_area(self, bounds_rect: QRect) -> QRect:
        assert_type(bounds_rect, QRect)
        initial_bounds = bounds_rect
        bounds_rect = QRect(initial_bounds.topLeft(), initial_bounds.size())
        # Make sure that the image generation area fits within allowed size limits:
        min_size = self.min_generation_area_size
        max_size = self.get_max_generation_area_size()
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

        # make sure the image generation area is within the image bounds:
        if bounds_rect.left() > (self.width - bounds_rect.width()):
            bounds_rect.moveLeft(self.width - bounds_rect.width())
        if bounds_rect.left() < 0:
            bounds_rect.moveLeft(0)
        if bounds_rect.top() > (self.height - bounds_rect.height()):
            bounds_rect.moveTop(self.height - bounds_rect.height())
        if bounds_rect.top() < 0:
            bounds_rect.moveTop(0)
        return bounds_rect

    def _set_generation_area_internal(self, bounds_rect: QRect) -> None:
        """Updates the image generation area, adjusting as needed based on image bounds, and sending the selection_changed signal
           if any changes happened. Does not update undo history."""
        assert_type(bounds_rect, QRect)
        bounds_rect = self._get_closest_valid_generation_area(bounds_rect)
        if bounds_rect != self._generation_area:
            last_bounds = self._generation_area
            self._generation_area = bounds_rect
            if bounds_rect.size() != last_bounds.size():
                AppConfig.instance().set(AppConfig.EDIT_SIZE, QSize(bounds_rect.size()))
            self.generation_area_bounds_changed.emit(bounds_rect)
