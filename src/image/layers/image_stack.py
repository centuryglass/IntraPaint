"""Manages an edited image composed of multiple layers."""
import re
import os
from typing import Optional, Tuple, Dict, Any, cast, List

from PIL import Image
from PyQt5.QtCore import Qt, QObject, QSize, QPoint, QRect, pyqtSignal, QRectF
from PyQt5.QtGui import QPainter, QPixmap, QImage, QColor, QTransform, QPolygonF

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.image.layers.image_layer import ImageLayer
from src.image.layers.layer import Layer
from src.image.layers.layer_stack import LayerStack
from src.image.layers.selection_layer import SelectionLayer
from src.undo_stack import commit_action, last_action, _UndoAction
from src.util.application_state import AppStateTracker, APP_STATE_NO_IMAGE, APP_STATE_EDITING
from src.util.cached_data import CachedData
from src.util.image_utils import qimage_to_pil_image
from src.util.validation import assert_type

LAYER_DATA_FILE_EMBEDDED = 'data.json'

SELECTION_LAYER_FILE_EMBEDDED = 'selection.png'


class ImageStack(QObject):
    """Manages an edited image composed of multiple layers."""
    generation_area_bounds_changed = pyqtSignal(QRect)
    content_changed = pyqtSignal()
    size_changed = pyqtSignal(QSize)
    layer_added = pyqtSignal(Layer)
    layer_removed = pyqtSignal(Layer)
    active_layer_changed = pyqtSignal(Layer)

    def __init__(self,
                 image_size: QSize,
                 generation_area_size: QSize,
                 min_generation_area_size: QSize,
                 max_generation_area_size: QSize) -> None:
        """Initializes the image stack with an empty initial layer."""
        super().__init__()
        self._size = image_size
        self._min_generation_area_size = min_generation_area_size
        self._max_generation_area_size = max_generation_area_size
        self._generation_area = QRect(0, 0, generation_area_size.width(), generation_area_size.height())
        self._copy_buffer: Optional[QImage] = None
        self._copy_buffer_transform: Optional[QTransform] = None
        self.generation_area = self._generation_area
        self._active_layer_id: Optional[int] = None
        self._image = CachedData(None)

        self._layer_stack = LayerStack('new image')

        # Create selection layer:
        self._selection_layer = SelectionLayer(image_size, self.generation_area_bounds_changed)
        self._selection_layer.update_generation_area(self._generation_area)

        # Layer stack update handling:
        def _set_name(name: str) -> None:
            self._layer_stack.set_name(os.path.basename(name))
        Cache().connect(self._layer_stack, Cache.LAST_FILE_PATH, _set_name)
        self._connect_layer(self._layer_stack)

        # noinspection PyUnusedLocal
        def _content_change(*args):
            selection_bounds = self._selection_layer.full_image_bounds
            content_bounds = self._layer_stack.full_image_bounds.united(self.bounds).united(selection_bounds)
            if not selection_bounds.contains(content_bounds):
                offset = content_bounds.topLeft() - selection_bounds.topLeft()
                self._selection_layer.resize_canvas(content_bounds.size(), offset.x(), offset.y(), False)
                assert self._selection_layer.full_image_bounds.contains(selection_bounds), f'expected {content_bounds}, got {self._selection_layer.full_image_bounds}'
            self._image.invalidate()
            self.content_changed.emit()
        self._layer_stack.content_changed.connect(_content_change)
        self._layer_stack.transform_changed.connect(_content_change)
        self._layer_stack.visibility_changed.connect(_content_change)
        self._layer_stack.opacity_changed.connect(_content_change)
        self._layer_stack.composition_mode_changed.connect(_content_change)

        # Selection update handling:

        def handle_selection_layer_update():
            """Refresh appropriate caches and send on signals if the selection layer changes."""
            if self._selection_layer.visible:
                self.content_changed.emit()

        self._selection_layer.content_changed.connect(handle_selection_layer_update)

        def handle_selection_layer_visibility_change():
            """Refresh appropriate caches and send on signals if the selection layer is shown or hidden."""
            self.content_changed.emit()

        self._selection_layer.content_changed.connect(handle_selection_layer_visibility_change)

    # PROPERTY DEFINITIONS:

    @property
    def count(self) -> int:
        """Returns the number of layers"""
        return self._layer_stack.count

    @property
    def active_layer(self) -> Optional[ImageLayer]:
        """Returns the active layer object, or None if the image stack is empty."""
        return None if self._active_layer_id is None else self._layer_stack.get_layer_by_id(self._active_layer_id)

    @active_layer.setter
    def active_layer(self, new_active_layer: Optional[Layer]) -> None:
        """Updates the active layer."""
        last_active = self.active_layer
        parent_iter = new_active_layer
        while parent_iter.parent is not None:
            parent_iter = parent_iter.parent
        assert parent_iter == self._layer_stack, (f'active layer {new_active_layer.name}:{new_active_layer.id} not '
                                                  'found in layer stack.')
        if last_active == new_active_layer:
            return

        def _set_active(layer):
            self._active_layer_id = None if layer is None else layer.id
            self.active_layer_changed.emit(layer)

        commit_action(lambda layer=new_active_layer: _set_active(layer), lambda layer=last_active: _set_active(layer),
                      'ImageStack.active_layer')

    @property
    def active_layer_id(self) -> Optional[int]:
        """Returns the unique integer ID of the active layer, or None if no layer is active."""
        return self._active_layer_id

    @property
    def top_level_layers(self) -> List[Layer]:
        """Returns the list of all child layers at the top level."""
        return self._layer_stack.child_layers

    @property
    def layers(self):
        """Returns the list of all layers, including nested layers."""
        return [self._layer_stack, *self._layer_stack.recursive_child_layers]

    @property
    def image_layers(self) -> list[ImageLayer]:
        """Returns the list of all child image layers, including nested layers"""
        return [layer for layer in self.layers if isinstance(layer, ImageLayer)]

    @property
    def selection_layer(self) -> SelectionLayer:
        """Returns the unique SelectionLayer used for highlighting image regions."""
        return self._selection_layer

    @property
    def has_image(self) -> bool:
        """Returns whether any image layers are present."""
        return self._layer_stack.has_image

    @property
    def bounds(self) -> QRect:
        """Gets image geometry as a QRect. Image position will always be 0,0, so this is mostly a convenience function
           for assorted rectangle calculations."""
        return QRect(QPoint(0, 0), self._size)

    @property
    def merged_layer_bounds(self) -> QRect:
        """Gets the bounding box containing all image layers."""
        return self._layer_stack.full_image_bounds

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
        self._size = QSize(new_size)
        # Re-apply bounds to make sure they still fit:
        if not QRect(QPoint(0, 0), new_size).contains(self._generation_area):
            self._set_generation_area_internal(self._generation_area)
        self.size_changed.emit(self.size)
        self._selection_layer.set_size(new_size, False)
        self.content_changed.emit()

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
                        AppConfig().set(AppConfig.EDIT_SIZE, QSize(self._generation_area.size()))

            action_type = 'ImageStack.generation_area'
            prev_action: Optional[_UndoAction]
            with last_action() as prev_action:
                if prev_action is not None and prev_action.type == action_type and prev_action.action_data is not None:
                    last_bounds = prev_action.action_data['prev_bounds']
                    prev_action.redo = lambda: update_fn(last_bounds, bounds_rect)
                    prev_action.undo = lambda: update_fn(bounds_rect, last_bounds)
                    prev_action.redo()
                    return

            commit_action(lambda: update_fn(last_bounds, bounds_rect), lambda: update_fn(bounds_rect, last_bounds),
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
        print('TODO: re-think resize_canvas method')

    def qimage(self, crop_to_image: bool = True) -> QImage:
        """Returns combined visible layer content as a QImage object, optionally including unsaved layers."""
        if not self._layer_stack.visible:
            size = self.size if crop_to_image else self._layer_stack.transformed_bounds.size()
            image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.transparent)
            return image
        image, translation = self._layer_stack.transformed_image()
        if crop_to_image:
            image = image.copy(QRect(QPoint(int(-translation.dx()), int(-translation.dy())), self.size))
        return image

    def pixmap(self) -> QPixmap:
        """Returns combined visible layer content as a QPixmap, optionally including unsaved layers."""
        return self._layer_stack.pixmap

    def pil_image(self) -> Image.Image:
        """Returns combined visible layer content as a PIL Image object, optionally including unsaved layers."""
        return qimage_to_pil_image(self.qimage())

    def get_max_generation_area_size(self) -> QSize:
        """
        Returns the largest area that can be selected within the image, based on image size and
         self.max_generation_area_size
        """
        max_size = self.max_generation_area_size
        return QSize(min(max_size.width(), self.width), min(max_size.height(), self.height))

    def cropped_qimage_content(self, bounds_rect: QRect) -> QImage:
        """Returns the contents of a bounding QRect as a QImage."""
        assert_type(bounds_rect, QRect)
        return self.qimage().copy(bounds_rect)

    def qimage_generation_area_content(self) -> QImage:
        """Returns the contents of the image generation area as a QImage."""
        return self.cropped_qimage_content(self.generation_area)

    def pil_image_generation_area_content(self) -> Image.Image:
        """Returns the contents of the image generation area as a PIL Image."""
        img = qimage_to_pil_image(self.cropped_qimage_content(self.generation_area))
        return img

    def get_color_at_point(self, image_point: QPoint) -> QColor:
        """Gets the combined color of visible saved layers at a single point, or QColor(0, 0, 0) if out of bounds."""
        layer_bounds = self._layer_stack.full_image_bounds
        adjusted_point = image_point - layer_bounds.topLeft()
        if not layer_bounds.contains(adjusted_point):
            return QColor(0, 0, 0)
        return self.qimage().pixelColor(adjusted_point)

    # LAYER ACCESS / MANIPULATION FUNCTIONS:

    def get_layer_by_id(self, layer_id: Optional[int]) -> Optional[ImageLayer]:
        """Returns a layer from the stack, or None if no matching layer was found."""
        return self._layer_stack.get_layer_by_id(layer_id)

    def create_layer(self,
                     layer_name: Optional[str] = None,
                     image_data: Optional[Image.Image | QImage | QPixmap] = None,
                     layer_parent: Optional[LayerStack] = None,
                     layer_index: Optional[int] = None,
                     transform: Optional[QTransform] = None) -> ImageLayer:
        """
        Creates a new image layer and adds it to the stack.

        - After the layer is created, the 'layer_added' signal is triggered.
        - If no layer was active, the new layer becomes active and the 'active_layer_index_changed' signal is triggered.
        - If the new layer is visible, the 'content_changed' signal is triggered.

        Parameters
        ----------
        layer_name: str or None, default=None
            Layer name string. If None, a placeholder name will be assigned.
        image_data: QImage or PIL Image or QPixmap or  None, default=None
            Initial layer image data. If None, the initial image will be transparent and size will match image stack
            size.
        layer_parent: optional LayerStack, default = None:
            Layer group where the layer will be inserted. If None, the main layer stack will be used.
        layer_index: int or None, default = None
            Index where the layer will be inserted into the stack. If None, it will be inserted above the active layer,
            or at the last index if the active layer isn't in the same group.
        transform: QTransform | None, default = None
            Optional initial transform to apply to the new layer.
        """
        if layer_index is None and layer_parent is None:
            active_layer = self.active_layer
            if active_layer is not None:
                layer_parent = cast(LayerStack, active_layer.parent)
                layer_index = layer_parent.get_layer_index(active_layer)
        if layer_parent is None:
            layer_parent = self._layer_stack
        if layer_index is None:
            layer_index = layer_parent.count
        if image_data is None:
            image_data = QImage(self.size, QImage.Format.Format_ARGB32_Premultiplied)
            image_data.fill(Qt.transparent)
        layer = self._create_layer_internal(layer_name, image_data)
        if transform is not None:
            layer.transform = transform

        def _create_new(parent=layer_parent, new_layer=layer, i=layer_index) -> None:
            self._insert_layer_internal(new_layer, parent, i, True)

        def _remove_new(parent=layer_parent, new_layer=layer):
            self._remove_layer_internal(new_layer, True)

        commit_action(_create_new, _remove_new, 'ImageStack.create_layer')
        return layer

    def copy_layer(self, layer: Optional[Layer] = None) -> None:
        """Copies a layer, inserting the copy below the original.
        Parameters
        ----------
            layer: Layer | None, default=None
                The layer object to copy, or its id. If None, the active layer will be used.
        """
        if layer == self._layer_stack:
            return
        if layer is None:
            layer = self.active_layer
        assert layer is not None and layer.parent is not None and layer.parent.contains(layer)
        layer_parent = cast(LayerStack, layer.parent)
        layer_index = layer_parent.get_layer_index(layer)
        assert layer_index is not None
        layer_copy = layer.copy()
        layer_copy.set_name(layer.name + ' copy')

        def _add_copy(parent=layer_parent, new_layer=layer_copy, idx=layer_index):
            self._insert_layer_internal(new_layer, parent, idx, True)

        def _remove_copy(new_layer=layer_copy):
            self._remove_layer_internal(new_layer, True)

        commit_action(_add_copy, _remove_copy, 'ImageStack.copy_layer')

    def remove_layer(self, layer: Optional[Layer] = None) -> None:
        """Removes an image layer from somewhere within the stack.
        Parameters
        ----------
            layer: Layer | None, default=None
                The layer object to remove. If None, the active layer will be used.
        """
        if layer == self._layer_stack:
            return
        if layer is None:
            layer = self.active_layer
        assert layer is not None and layer.parent is not None and layer.parent.contains(layer)
        layer_parent = cast(LayerStack, layer.parent)
        layer_index = layer_parent.get_layer_index(layer)
        last_active_id = self._active_layer_id

        def _remove(removed=layer):
            self._remove_layer_internal(layer)

        def _undo_remove(parent=layer_parent, restored=layer, idx=layer_index, active_id=last_active_id):
            self._insert_layer_internal(restored, parent, idx)
            if active_id != self._active_layer_id:
                self._active_layer_id = active_id
                active = self._layer_stack.get_layer_by_id(active_id)
                self.active_layer_changed.emit(active)

        commit_action(_remove, _undo_remove, 'ImageStack.remove_layer')

    def offset_active_selection(self, offset: int) -> None:
        """Picks a new active layer relative to the index of the previous active layer. Does nothing if no layer is
           active."""
        active_layer = self.active_layer
        if active_layer is None:
            return
        parent, index = self._find_offset_index(active_layer, offset, False)
        new_active_layer = parent.get_layer_by_index(index)
        self.active_layer = new_active_layer

    def move_layer(self, offset: int, layer: Optional[Layer] = None) -> None:
        """Moves a layer up or down in the stack.

        - The layer will first be removed, triggering all the usual signals you would get from remove_layer.
        - The layer is then inserted at the new layer_index, triggering all the usual signals you would get from
           add_layer.
        - Layer offset is applied as if the entire layer stack is flattened, so this might move the layer into or out
          of a nested group.
        - Both operations will be combined in the undo stack into a single operation.

        Parameters
        ----------
            offset: int
                The amount the layer index should change.
            layer: ImageLayer | None, default=None
                The layer object to copy. If None, the active layer will be used, and the method will fail
                silently if no layer is active.
        """
        if layer == self._layer_stack:
            return
        if layer is None:
            layer = self.active_layer
            if layer is None:
                return
        assert layer is not None and layer.parent is not None and layer.parent.contains(layer)
        layer_parent = cast(LayerStack, layer.parent)
        layer_index = layer_parent.get_layer_index(layer)
        new_parent, new_index = self._find_offset_index(layer, offset, True)
        if layer_index == new_index and layer_parent == new_parent:
            return
        if layer_parent == new_parent and new_index > layer_index:
            new_index -= 1

        def _move(moving=layer, parent=new_parent, idx=new_index):
            self._remove_layer_internal(moving)
            self._insert_layer_internal(moving, parent, idx)

        def _move_back(moving=layer, parent=layer_parent, idx=layer_index):
            self._remove_layer_internal(moving)
            self._insert_layer_internal(moving, parent, idx)

        commit_action(_move, _move_back, 'ImageStack.move_layer')

    def merge_layer_down(self, layer: Optional[Layer] = None) -> None:
        """Merges a layer with the one beneath it on the stack.

        - If this layer is on the bottom of the stack, the function will fail silently.
        - This will trigger the 'layer_removed' signal first as the top layer is removed.
        - If the top and bottom layers don't have the same visibility, the 'content_changed' signal is emitted.
        - If the active layer layer_index was greater than or equal to the layer_index of the removed layer, the active
          layer index will be decreased by one.

        Parameters
        ----------
            layer: Layer | None, default=None
                The layer object to merge down. If None, the active layer will be used, and the method will fail
                silently if no layer is active.
        """
        if layer == self._layer_stack:
            return
        if layer is None:
            layer = self.active_layer
            if layer is None:
                return
        assert layer is not None and layer.parent is not None and layer.parent.contains(layer)
        if not isinstance(layer, ImageLayer):
            return
        top_layer = cast(ImageLayer, layer)
        layer_parent = cast(LayerStack, top_layer.parent)
        layer_index = layer_parent.get_layer_index(top_layer)
        if layer_index == layer_parent.count - 1:
            return
        base_layer = layer_parent.get_layer_by_index(layer_index + 1)
        if not isinstance(base_layer, ImageLayer):
            return
        base_layer = cast(ImageLayer, base_layer)
        base_layer_state = base_layer.save_state()
        is_active_layer = bool(top_layer.id == self.active_layer_id)

        base_bounds = base_layer.transformed_bounds
        top_bounds = top_layer.transformed_bounds
        merged_bounds = base_bounds.united(top_bounds)
        merged_image = QImage(merged_bounds.size(), QImage.Format.Format_ARGB32_Premultiplied)
        offset = -merged_bounds.topLeft()
        merged_image.fill(Qt.transparent)
        painter = QPainter(merged_image)

        base_paint_transform = base_layer.transform
        base_paint_transform.translate(base_bounds.x() + offset.x(), base_bounds.y() + offset.y())
        painter.setTransform(base_paint_transform, False)
        painter.drawImage(QRect(QPoint(), base_layer.size), base_layer.image)

        top_paint_transform = top_layer.transform
        top_paint_transform.translate(top_bounds.x() + offset.x(), top_bounds.y() + offset.y())
        painter.setTransform(top_paint_transform)
        painter.drawImage(QRect(top_bounds.topLeft() + offset, top_bounds.size()), top_layer.image)
        painter.end()

        final_transform = QTransform()
        final_transform.translate(offset.x(), offset.y())

        def _do_merge(parent=layer_parent, removed=top_layer, base=base_layer, matrix=final_transform,
                      img=merged_image, update_active=is_active_layer) -> None:
            self._remove_layer_internal(removed)
            base.set_image(img)
            base.set_transform(matrix)
            if removed.visible != base.visible:
                self.content_changed.emit()
            if update_active:
                self._active_layer_id = base.id
                self.active_layer_changed.emit(base)

        def _undo_merge(parent=layer_parent, restored=top_layer, base=base_layer, state=base_layer_state,
                        idx=layer_index, update_active=is_active_layer) -> None:
            base.restore_state(state)
            self._insert_layer_internal(restored, parent, idx)
            if update_active:
                self._active_layer_id = restored.id
                self.active_layer_changed.emit(restored)

        commit_action(_do_merge, _undo_merge, 'ImageStack.merge_layer_down')

    def layer_to_image_size(self, layer: Optional[Layer] = None) -> None:
        """Resizes a layer to match the image size. Out-of-bounds content is cropped, new content is transparent.

        Parameters
        ----------
            layer: ImageLayer | int | None, default=None
                The layer object to copy, or its id. If None, the active layer will be used, and the method will fail
                silently if no layer is active.
        """
        if layer == self._layer_stack:
            return
        if layer is None:
            layer = self.active_layer
            if layer is None:
                return
        if not isinstance(layer, ImageLayer):
            print('TODO: LayerStack to image size')
            return
        layer_image_bounds = layer.full_image_bounds
        image_bounds = self.bounds
        if layer_image_bounds == image_bounds:
            return
        base_state = layer.save_state()
        layer_image, offset_transform = layer.transformed_image()
        layer_position = QPoint(int(offset_transform.dx()), int(offset_transform.dy()))
        resized_image = QImage(self.size, QImage.Format.Format_ARGB32_Premultiplied)
        resized_image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(resized_image)
        painter.drawImage(QRect(layer_position, layer_image.size()), layer_image)
        painter.end()

        def _resize(resized=layer, img=resized_image) -> None:
            initial_bounds = resized.full_image_bounds
            resized.set_image(img)
            layer.set_transform(QTransform())
            if resized.visible and not self.bounds.contains(initial_bounds):
                self.content_changed.emit()

        def _undo_resize(restored=layer, state=base_state) -> None:
            restored.restore_state(state)
            self.content_changed.emit()

        commit_action(_resize, _undo_resize, 'ImageStack.layer_to_image_size')

    def _get_layer_mask(self, layer: Layer) -> QImage:
        """Transform the mask layer to another layer's local coordinates"""
        selection_mask = self.selection_layer.image
        transformed_mask = QImage(layer.size, QImage.Format_ARGB32_Premultiplied)
        transformed_mask.fill(Qt.transparent)
        # mask image coordinates to full image coordinates:
        painter_transform = self.selection_layer.transform
        # Image coordinates to local layer coordinates:
        painter_transform = painter_transform * layer.full_image_transform.inverted()[0]
        painter = QPainter(transformed_mask)
        painter.setTransform(painter_transform)
        painter.drawImage(QRect(0, 0, selection_mask.width(), selection_mask.height()), selection_mask)
        painter.end()
        return transformed_mask

    def copy_selected(self, layer: Optional[Layer] = None, mask: Optional[QImage] = None) -> Optional[QImage]:
        """Returns the image content within a layer that's covered by the mask, saving it in the copy buffer.

        Parameters
        ----------
            layer: Layer | None, default=None
                The layer object to copy. If None, the active layer will be used, and the method will fail
                silently if no layer is active.
            mask: QImage | None, default=None
                The mask image to apply to the un-transformed layer image. If None, use selection layer content
                transformed to local layer coordinates
        """
        if layer is None:
            layer = self.active_layer
            if layer is None:
                return
        if mask is None:
            mask = self._get_layer_mask(layer)
        image = layer.image
        painter = QPainter(image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(QRect(0, 0, image.width(), image.height()), mask)
        painter.end()
        self._copy_buffer = image
        self._copy_buffer_transform = layer.full_image_transform
        return image

    def cut_selected(self, layer: Optional[Layer] = None) -> None:
        """Replaces all masked image content in a layer with transparency, saving it in the copy buffer."""
        if layer is None:
            layer = self.active_layer
            if layer is None:
                return
        saved_state = layer.save_state()
        transformed_mask = self._get_layer_mask(layer)

        self._copy_buffer = self.copy_selected(layer, transformed_mask)
        self._copy_buffer_transform = layer.full_image_transform

        def _make_cut(to_cut=layer, mask=transformed_mask) -> None:
            to_cut.cut_masked(mask)

        def _undo_cut(to_restore=layer, state=saved_state) -> None:
            to_restore.restore_state(state)

        commit_action(_make_cut, _undo_cut, 'ImageStack.cut_selected')

    def paste(self) -> None:
        """If the copy buffer contains image data, paste it into a new layer."""
        if self._copy_buffer is not None:
            new_layer = self.create_layer('Paste layer', self._copy_buffer.copy())
            new_layer.set_transform(self._copy_buffer_transform)
            self.active_layer = new_layer

    def set_generation_area_content(self,
                                    image_data: QImage,
                                    layer: Optional[Layer] = None,
                                    composition_mode: QPainter.CompositionMode = QPainter.CompositionMode_SourceOver):
        """Updates image generation area content within a layer.
        Parameters
        ----------
        image_data: QImage
            Image data to draw into the image generation area. If the size of the image doesn't match the size of the
            bounds_rect, it will be scaled to fit.
        layer: Layer | None, default=None
            The layer object to copy, or its id. If None, the active layer will be used
        composition_mode: QPainter.CompositionMode, default=Source
            Mode used to insert image content.
        """
        if layer is None:
            layer = self.active_layer
            if layer is None:
                layer = self._layer_stack
        inverse_transform, is_invertible = layer.full_image_transform.inverted()
        assert is_invertible, f'Layer {layer.name}:{layer.id} had non-invertible transform!'
        offset = QTransform.fromTranslate(self._generation_area.x(), self.generation_area.y())
        scale = QTransform.fromScale(self._generation_area.width() / image_data.width(),
                                     self._generation_area.height() / image_data.height())
        data_transform = scale * offset * inverse_transform
        data_bounds = QRect(QPoint(), image_data.size())
        final_bounds = data_transform.map(QPolygonF(QRectF(data_bounds))).boundingRect().toAlignedRect()
        target_bounds = layer.map_rect_from_image(self._generation_area)
        assert final_bounds == target_bounds, f'expected {target_bounds}, got {final_bounds}'
        if isinstance(layer, LayerStack):
            new_layer = self._create_layer_internal(image_data=image_data)
            new_layer.set_transform(data_transform)

            def _insert(added=new_layer, parent=layer):
                self._insert_layer_internal(added, parent, 0)

            def _remove(removed=new_layer):
                self._remove_layer_internal(removed)

            commit_action(_insert, _remove, 'ImageStack.set_generation_area_content')

        else:
            assert isinstance(layer, ImageLayer)
            with layer.borrow_image() as layer_image:
                painter = QPainter(layer_image)
                painter.setTransform(data_transform)
                painter.setCompositionMode(composition_mode)
                painter.drawImage(data_bounds, image_data)
                painter.end()

    def save_image_stack_file(self, file_path: str, metadata: Optional[Dict[str, Any]]) -> None:
        """Save layers and image metadata to a file that can be opened for future editing."""
        print('TODO: replace with .ora save')
        # size = self.size
        # data: Dict[str, Any] = {'metadata': metadata, 'size': f'{size.width()}x{size.height()}', 'files': []}
        # # Create temporary directory
        # tmpdir = tempfile.mkdtemp()
        # self.selection_layer.image.save(os.path.join(tmpdir, SELECTION_LAYER_FILE_EMBEDDED))
        # for layer in self._layers:
        #     index = self._layers.index(layer)
        #     layer.image.save(os.path.join(tmpdir, f'{index}.png'))
        #     composition_mode = ''
        #     for mode_name, mode_type in COMPOSITION_MODES.items():
        #         if mode_type == layer.composition_mode:
        #             composition_mode = mode_name
        #             break
        #     data['files'].append({
        #         'name': layer.name,
        #         'pos': f'{layer.position.x()},{layer.position.y()}',
        #         'visible': layer.visible,
        #         'opacity': layer.opacity,
        #         'mode': composition_mode
        #     })
        # json_path = os.path.join(tmpdir, LAYER_DATA_FILE_EMBEDDED)
        # with open(json_path, 'w', encoding='utf-8') as file:
        #     json.dump(data, file, indent=4, ensure_ascii=False)
        # shutil.make_archive(file_path, 'zip', tmpdir)
        # shutil.move(f'{file_path}.zip', file_path)
        # shutil.rmtree(tmpdir)

    def load_image_stack_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Load layers and image metadata from a file, returning the metadata."""
        print('TODO: replace with .ora load')
        return None
        # tmpdir = tempfile.mkdtemp()
        # shutil.unpack_archive(file_path, tmpdir, format='zip')
        # old_mask_image = self.selection_layer.image
        # old_layers = self._layers.copy()
        # new_layers = []
        # old_size = self.size
        # with open(os.path.join(tmpdir, LAYER_DATA_FILE_EMBEDDED)) as json_file:
        #     data = json.load(json_file)
        # w, h = (int(substr) for substr in data['size'].split('x'))
        # new_size = QSize(w, h)
        # new_mask_image = QImage(os.path.join(tmpdir, SELECTION_LAYER_FILE_EMBEDDED))
        # for i, file_data in enumerate(data['files']):
        #     image = QImage(os.path.join(tmpdir, f'{i}.png'))
        #     name = None
        #     if 'name' in file_data:
        #         name = file_data['name']
        #     layer = self._create_layer_internal(name, image)
        #     if 'pos' in file_data:
        #         x, y = (int(substr) for substr in file_data['pos'].split(','))
        #         layer.position = QPoint(x, y)
        #     if 'visible' in file_data:
        #         layer.visible = file_data['visible']
        #     if 'opacity' in file_data:
        #         layer.opacity = file_data['opacity']
        #     if 'mode' in file_data:
        #         mode_name = file_data['mode']
        #         if mode_name in COMPOSITION_MODES:
        #             layer.composition_mode = COMPOSITION_MODES[mode_name]
        #     new_layers.append(layer)
        # shutil.rmtree(tmpdir)
        #
        # def _load():
        #     for old_layer in old_layers:
        #         self._remove_layer_internal(old_layer)
        #     self._set_size(new_size)
        #     self.selection_layer.set_image(new_mask_image)
        #     for new_layer in new_layers:
        #         self._insert_layer_internal(new_layer, self.count)
        #
        # def _undo_load():
        #     for new_layer in new_layers:
        #         self._remove_layer_internal(new_layer)
        #     self._set_size(old_size)
        #     self.selection_layer.set_image(old_mask_image)
        #     for old_layer in old_layers:
        #         self._insert_layer_internal(old_layer, self.count)
        #
        # commit_action(_load, _undo_load)
        # metadata = data['metadata']
        # return metadata

    def set_image(self, image_data: Image.Image | QImage | QPixmap):
        """
        Loads a new image to be edited. This clears all layers, updates the image size, and inserts the image as a new
        active layer.

        Parameters
        ----------
        image_data: PIL Image or QImage or QPixmap
            Layer stack size will be adjusted to match image data size.
        """
        saved_state = self._layer_stack.save_state()
        saved_selection_state = self.selection_layer.save_state()
        old_size = self.size
        old_layers = self.layers
        old_layers.remove(self._layer_stack)

        new_layer = self._create_layer_internal(None, image_data)
        new_size = new_layer.size
        gen_area = QRect(self._generation_area)
        new_gen_area = gen_area.intersected(new_layer.full_image_bounds)
        last_active_id = self._active_layer_id

        def _load(loaded=new_layer, gen_rect=new_gen_area, size=new_size):
            self.selection_layer.clear(False)
            self.selection_layer.resize_canvas(new_size, 0, 0, False)
            self.selection_layer.set_transform(QTransform())
            for layer in self.layers:
                if layer != self._layer_stack:
                    self._remove_layer_internal(layer)
            self._layer_stack.set_visible(True)
            self._layer_stack.set_opacity(1.0)
            self._layer_stack.set_composition_mode(QPainter.CompositionMode.CompositionMode_SourceOver)
            self._layer_stack.set_transform(QTransform())
            self.size = size
            self._insert_layer_internal(new_layer, self._layer_stack, 0)
            self._set_generation_area_internal(gen_rect)
            self._active_layer_id = loaded.id
            self.active_layer_changed.emit(self.active_layer)

        # noinspection PyDefaultArgument
        def _undo_load(unloaded=new_layer, state=saved_state, selection_state=saved_selection_state, gen_rect=gen_area,
                       size=old_size, active=last_active_id, restored_layers=old_layers):
            assert self.count == 1, f'Unexpected layer count {self.count} when reversing image load!'
            self._remove_layer_internal(unloaded)
            self.size = size
            for layer in restored_layers:
                self._insert_layer_internal(layer, self._layer_stack, self._layer_stack.count)
            self.layer_removed.emit(unloaded)
            self._layer_stack.restore_state(state)
            self.selection_layer.restore_state(selection_state)
            self._set_generation_area_internal(gen_rect)
            self._active_layer_id = active
            self.active_layer_changed.emit(self._active_layer_id)

        commit_action(_load, _undo_load, 'ImageStack.set_image')

    # INTERNAL:
    def _layer_content_change_slot(self, layer: Layer, _=None) -> None:
        if layer.visible and (layer == self._layer_stack or layer == self.selection_layer
                              or self._layer_stack.contains(layer)):
            if layer != self.selection_layer:
                self._image.invalidate()
            self.content_changed.emit()

    def _layer_visibility_change_slot(self, layer: ImageLayer, _) -> None:
        if layer == self._layer_stack or layer == self.selection_layer or self._layer_stack.contains(layer):
            if layer != self.selection_layer:
                self._image.invalidate()
            self.content_changed.emit()

    def _create_layer_internal(self, layer_name: Optional[str] = None,
                               image_data: Optional[QImage | QSize] = None) -> ImageLayer:
        """Returns a new layer object given valid data. This emits no signals, connects no signal handlers, and does
           not add the layer to the stack."""
        if layer_name is None:
            default_name_pattern = r'^layer (\d+)'
            max_missing_layer = 0
            for layer in self._all_layers():
                match = re.match(default_name_pattern, layer.name)
                if match:
                    max_missing_layer = max(max_missing_layer, int(match.group(1)) + 1)
            layer_name = f'layer {max_missing_layer}'
        assert_type(layer_name, str)
        assert_type(image_data, (QImage, QSize))
        if image_data is None:
            layer = ImageLayer(self.size, layer_name)
        else:
            layer = ImageLayer(image_data, layer_name)
        return layer

    def _connect_layer(self, layer: Layer) -> None:
        assert layer == self._layer_stack or self._layer_stack.contains(layer), (f'layer {layer.name}:{layer.id} is not'
                                                                                 f' in the image stack.')
        layer.size_changed.connect(self._layer_content_change_slot)
        layer.content_changed.connect(self._layer_content_change_slot)
        layer.opacity_changed.connect(self._layer_content_change_slot)
        layer.composition_mode_changed.connect(self._layer_content_change_slot)
        layer.transform_changed.connect(self._layer_content_change_slot)
        layer.visibility_changed.connect(self._layer_visibility_change_slot)

    def _disconnect_layer(self, layer: Layer) -> None:
        assert self._layer_stack.contains(layer), f'layer {layer.name}:{layer.id} is not in the image stack.'
        layer.size_changed.disconnect(self._layer_content_change_slot)
        layer.content_changed.disconnect(self._layer_content_change_slot)
        layer.opacity_changed.disconnect(self._layer_content_change_slot)
        layer.composition_mode_changed.disconnect(self._layer_content_change_slot)
        layer.transform_changed.disconnect(self._layer_content_change_slot)
        layer.visibility_changed.disconnect(self._layer_visibility_change_slot)

    def _insert_layer_internal(self, layer: Layer, parent: LayerStack, index: int, connect_signals=True):
        assert layer is not None and layer.parent is None and not self._layer_stack.contains(layer)
        assert parent is not None and (parent == self._layer_stack or self._layer_stack.contains(parent))
        parent.insert_layer(layer, index)
        if connect_signals:
            self._connect_layer(layer)
        self._update_z_values()
        self.layer_added.emit(layer)
        if isinstance(layer, LayerStack):
            for child_layer in layer.recursive_child_layers:
                if connect_signals:
                    self._connect_layer(child_layer)
                self.layer_added.emit(child_layer)
        if self._layer_stack.count == 1:
            AppStateTracker.set_app_state(APP_STATE_EDITING)
        if self._active_layer_id is None:
            self._active_layer_id = layer
            self.active_layer_changed.emit(layer)
        if layer.visible:
            self._image.invalidate()
            self.content_changed.emit()

    def _remove_layer_internal(self, layer: Layer, disconnect_signals=True) -> None:
        """Removes a layer from the stack, optionally disconnect layer signals, and emit all required image stack
           signals. This does not alter the undo history."""
        assert layer is not None
        layer_parent = cast(LayerStack, layer.parent)
        assert layer_parent is not None
        assert layer_parent.contains(layer)
        assert self._layer_stack.contains(layer), f'layer {layer.name}:{layer.id} is not in the image stack.'
        if disconnect_signals:
            self._disconnect_layer(layer)
        if self._active_layer_id == layer.id:
            active_layer = self.active_layer
            assert active_layer is not None
            active_parent, index = self._find_offset_index(active_layer, 1, False)
            if active_parent.get_layer_by_index(index).id == layer.id:
                active_parent, index = self._find_offset_index(active_layer, -1, False)
            if active_parent.get_layer_by_index(index).id == layer.id:
                next_active_id = None
            else:
                next_active_id = active_parent.get_layer_by_index(index).id
        else:
            next_active_id = self._active_layer_id
        layer_parent.remove_layer(layer)
        self._update_z_values()
        self.layer_removed.emit(layer)
        if isinstance(layer, LayerStack):
            for child_layer in layer.recursive_child_layers:
                if disconnect_signals:
                    self._disconnect_layer(child_layer)
                self.layer_removed.emit(child_layer)
        if self._layer_stack.count == 0:
            AppStateTracker.set_app_state(APP_STATE_NO_IMAGE)
        if next_active_id != self._active_layer_id:
            self._active_layer_id = next_active_id
            active = self._layer_stack.get_layer_by_id(next_active_id)
            self.active_layer_changed.emit(active)
        if layer.visible:
            self._image.invalidate()
            self.content_changed.emit()

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
                AppConfig().set(AppConfig.EDIT_SIZE, QSize(bounds_rect.size()))
            self.generation_area_bounds_changed.emit(bounds_rect)

    def _update_z_values(self) -> None:
        flattened_stack = self._all_layers()
        self.selection_layer.z_value = 1
        for i, layer in enumerate(flattened_stack):
            layer.z_value = -i

    def _all_layers(self) -> List[Layer]:
        return [self._layer_stack, *self._layer_stack.child_layers]

    @staticmethod
    def _find_offset_index(layer: Layer, offset: int, allow_end_indices=True) -> Tuple[LayerStack, int]:

        def _recursive_offset(parent: LayerStack, index: int, off: int) -> Tuple[LayerStack, int]:
            max_idx = parent.count
            if allow_end_indices:
                max_idx += 1
            step = 1 if off > 0 else -1
            while off != 0:
                if index > 0 or index <= max_idx:
                    if parent.parent is None:
                        return parent, min(0, max(max_idx, index))
                    next_parent = cast(LayerStack, parent.parent)
                    parent_idx = next_parent.get_layer_index(parent)
                    if index > 0:
                        parent_idx += 1
                    return _recursive_offset(parent.parent, parent_idx, off)
                if index > max_idx:
                    if parent.parent is None:
                        return parent, max_idx
                index += step
                off -= step
                if 0 <= index < parent.count:
                    layer_at_index = parent.get_layer_by_index(index)
                    assert layer_at_index != layer, ('something is seriously wrong with layer hierarchy...'
                                                     '(multiple parents?)')
                    if isinstance(layer_at_index, LayerStack):
                        if step == 1:
                            inner_index = 0
                        else:
                            inner_index = layer_at_index.count
                            if allow_end_indices:
                                inner_index += 1
                        return _recursive_offset(layer_at_index, inner_index, off)
            return parent, min(0, max(max_idx, index))
        assert layer.parent is not None
        layer_parent = cast(LayerStack, layer.parent)
        layer_index = layer_parent.get_layer_index(layer)
        return _recursive_offset(layer_parent, layer_index, offset)

    @staticmethod
    def _find_offset_layer(layer: Layer, offset: int) -> Layer:
        parent, index = ImageStack._find_offset_index(layer, offset)
        return parent.get_layer_by_index(index)
