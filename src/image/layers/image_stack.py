"""Manages an edited image composed of multiple layers."""
import logging
import os
import re
from typing import Optional, Tuple, cast, List, Callable, TypeAlias

import numpy as np
from PIL import Image
from PySide6.QtCore import QObject, QSize, QPoint, QRect, Signal
from PySide6.QtGui import QPainter, QPixmap, QImage, QColor, QTransform
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.image.layers.layer import Layer, LayerParent
from src.image.layers.layer_stack import LayerStack
from src.image.layers.selection_layer import SelectionLayer
from src.image.layers.text_layer import TextLayer
from src.image.layers.transform_layer import TransformLayer
from src.image.text_rect import TextRect
from src.undo_stack import UndoStack, _UndoAction, _UndoGroup
from src.util.application_state import AppStateTracker, APP_STATE_NO_IMAGE, APP_STATE_EDITING
from src.util.cached_data import CachedData
from src.util.visual.geometry_utils import adjusted_placement_in_bounds, map_rect_precise
from src.util.visual.image_utils import create_transparent_image, image_content_bounds, \
    image_is_fully_transparent, image_data_as_numpy_8bit
from src.util.visual.pil_image_utils import qimage_to_pil_image
from src.util.math_utils import clamp

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'image.layers.image_stack'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


NEW_IMAGE_LAYER_GROUP_NAME = _tr('new image')
ACTION_NAME_MERGE_LAYERS = _tr('merge layers')
ACTION_NAME_LAYER_TO_IMAGE_SIZE = _tr('resize layer to image')
ACTION_NAME_CLEAR_SELECTED = _tr('cut/clear selection')

RenderAdjustFn: TypeAlias = Callable[[int, QImage, QRect, QPainter], Optional[QImage]]


class ImageStack(QObject):
    """Manages an edited image composed of multiple layers."""
    generation_area_bounds_changed = Signal(QRect)
    content_changed = Signal()
    size_changed = Signal(QSize)
    layer_added = Signal(Layer)
    layer_removed = Signal(Layer)
    active_layer_changed = Signal(Layer)
    layer_order_changed = Signal()

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
        self._content_change_signal_enabled = True
        self.generation_area = self._generation_area

        def _update_gen_area_size(size: QSize) -> None:
            if size != self._generation_area.size():
                self.generation_area = QRect(self._generation_area.topLeft(), size)

        AppConfig().connect(self, AppConfig.EDIT_SIZE, _update_gen_area_size)

        self._layer_stack = LayerStack(NEW_IMAGE_LAYER_GROUP_NAME)
        self._image = CachedData(None)
        self._active_layer_id = self._layer_stack.id

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
            selection_bounds = self._selection_layer.transformed_bounds
            content_bounds = self._layer_stack.bounds.united(self.bounds).united(selection_bounds)
            if content_bounds.isNull():
                return
            if not selection_bounds.contains(content_bounds) or (selection_bounds.width() * selection_bounds.height()) \
                    > (content_bounds.width() * content_bounds.height() * 10):
                self._selection_layer.adjust_local_bounds(self._selection_layer.map_rect_from_image(content_bounds),
                                                          False)
                assert self._selection_layer.transformed_bounds.contains(content_bounds, proper=False), \
                    f'expected containing {content_bounds}, got {self._selection_layer.transformed_bounds}'
            self._image.invalidate()
            self._emit_content_changed()

        self._layer_stack.content_changed.connect(_content_change)
        self._layer_stack.visibility_changed.connect(_content_change)
        self._layer_stack.opacity_changed.connect(_content_change)
        self._layer_stack.composition_mode_changed.connect(_content_change)
        self._layer_stack.layer_added.connect(self._layer_added_slot)
        self._layer_stack.layer_removed.connect(self._layer_removed_slot)

        # Selection update handling:

        # noinspection PyUnusedLocal
        def handle_selection_layer_update(*args):
            """Refresh appropriate caches and send on signals if the selection layer changes."""
            if self._selection_layer.visible:
                self._emit_content_changed()

        self._selection_layer.content_changed.connect(handle_selection_layer_update)

        # noinspection PyUnusedLocal
        def handle_selection_layer_visibility_change(*args):
            """Refresh appropriate caches and send on signals if the selection layer is shown or hidden."""
            self._emit_content_changed()

        self._selection_layer.content_changed.connect(handle_selection_layer_visibility_change)

    # PROPERTY DEFINITIONS:

    @property
    def count(self) -> int:
        """Returns the number of layers"""
        return self._layer_stack.count

    @property
    def active_layer(self) -> Layer:
        """Returns the active layer object, or None if the image stack is empty."""
        layer = self._layer_stack.get_layer_by_id(self._active_layer_id)
        assert layer is not None, f'Active layer {self._active_layer_id} not found'
        return layer

    @active_layer.setter
    def active_layer(self, new_active_layer: Layer) -> None:
        """Updates the active layer."""
        assert isinstance(new_active_layer, Layer)
        last_active = self.active_layer
        parent_iter: Layer | LayerParent = new_active_layer
        while isinstance(parent_iter, Layer) and parent_iter.layer_parent is not None:
            parent_iter = parent_iter.layer_parent
        assert parent_iter == self._layer_stack, (f'active layer {new_active_layer.name}:{new_active_layer.id} not '
                                                  'found in layer stack.')
        if last_active == new_active_layer:
            return

        def _set_active(layer=new_active_layer):
            self._set_active_layer_internal(layer)

        def _undo_set_active(layer=last_active):
            self._set_active_layer_internal(layer)

        UndoStack().commit_action(_set_active, _undo_set_active, 'ImageStack.active_layer')

    @property
    def active_layer_id(self) -> int:
        """Returns the unique integer ID of the active layer."""
        return self._active_layer_id

    @active_layer_id.setter
    def active_layer_id(self, new_active_id: int) -> None:
        assert new_active_id == self._layer_stack.id or self._layer_stack.get_layer_by_id(new_active_id) is not None
        self._active_layer_id = new_active_id

    @property
    def layer_stack(self) -> LayerStack:
        """Returns the root layer group."""
        return self._layer_stack

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
        return self._layer_stack.bounds

    @property
    def size(self) -> QSize:
        """Gets the size of the edited image."""
        return QSize(self._size.width(), self._size.height())

    @size.setter
    def size(self, new_size) -> None:
        """Updates the full image size, scaling the mask layer."""
        assert isinstance(new_size, QSize)
        if new_size == self._size:
            return
        self._size = QSize(new_size)
        # Re-apply bounds to make sure they still fit:
        if not QRect(QPoint(0, 0), new_size).contains(self._generation_area):
            self._set_generation_area_internal(self._generation_area)
        self.size_changed.emit(self.size)
        self._selection_layer.set_size(new_size, False)

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
        assert isinstance(new_min, QSize)
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
        assert isinstance(new_max, QSize)
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
        assert isinstance(bounds_rect, QRect)
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
            prev_action: Optional[_UndoAction | _UndoGroup]
            with UndoStack().last_action(action_type) as prev_action:
                if isinstance(prev_action, _UndoAction) and prev_action.type == action_type \
                        and prev_action.action_data is not None:
                    last_bounds = prev_action.action_data['prev_bounds']
                    prev_action.redo = lambda: update_fn(last_bounds, bounds_rect)
                    prev_action.undo = lambda: update_fn(bounds_rect, last_bounds)
                    prev_action.redo()
                    return

            UndoStack().commit_action(lambda: update_fn(last_bounds, bounds_rect),
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
            X offset where existing image content will be placed in the adjusted image
        y_offset: int
            Y offset where existing image content will be placed in the adjusted layer
        """
        assert isinstance(new_size, QSize)
        last_size = self.size
        selection_state = self.selection_layer.save_state()
        layer_state = self._layer_stack.save_state()
        transform = QTransform.fromTranslate(x_offset, y_offset)
        canvas_image_bounds = QRect(QPoint(), new_size)

        @self._with_batch_content_update
        def _resize(bounds=canvas_image_bounds, translate=transform):
            self.size = bounds.size()
            self.selection_layer.set_transform(self.selection_layer.transform * translate)
            mapped_bounds = self.selection_layer.map_rect_from_image(bounds)
            self.selection_layer.adjust_local_bounds(mapped_bounds, False)
            for layer in self.image_layers:
                if layer.locked:
                    continue
                with layer.with_alpha_lock_disabled():
                    layer.set_transform(layer.transform * translate)
                    mapped_bounds = layer.map_rect_from_image(bounds)
                    layer.adjust_local_bounds(mapped_bounds, False)

        @self._with_batch_content_update
        def _undo_resize(size=last_size, sel_state=selection_state, stack_state=layer_state):
            self.size = size
            self._layer_stack.restore_state(stack_state)
            self._selection_layer.restore_state(sel_state)

        UndoStack().commit_action(_resize, _undo_resize, 'ImageStack.resize_canvas')

    def qimage(self, crop_to_image: bool = True) -> QImage:
        """Returns combined visible layer content as a QImage object, optionally including unsaved layers."""
        if crop_to_image and self._image.valid:
            return self._image.data
        if not self._layer_stack.visible:
            size = QSize(self.size if crop_to_image else self._layer_stack.bounds.size())
            size.setWidth(max(self.width, size.width()))
            size.setHeight(max(self.height, size.height()))
            image = create_transparent_image(size)
            return image
        image = self.render()
        assert image.size() == self.merged_layer_bounds.size()
        if crop_to_image:
            offset = -self.merged_layer_bounds.topLeft()
            image = image.copy(QRect(offset, self.size))
            self._image.data = image
        return image

    def render(self, base_image: Optional[QImage] = None,
               paint_param_adjuster: Optional[RenderAdjustFn] = None) -> QImage:
        """Render all layers to a QImage with a custom base image and accepting a function to control layer painting on
        a per-layer basis.

        Parameters
        ----------
        base_image: QImage, optional, default=None.
            The base image that all layer content will be painted onto.  If None, a new image will be created that's
            large enough to fit all layers.
        paint_param_adjuster: Optional[Callable[[int, QImage, QRect, QPainter) -> Optional[QImage]]
            Default=None. If provided, it will be called before each layer is painted, allowing it to directly make
            changes to the image, paint bounds, or painter as needed. Parameters are layer_id, layer_image,
            paint_bounds and layer_painter.  If it returns a QImage, that image will replace the layer image.
        Returns
        -------
        QImage: The final rendered image.
        """
        return self._layer_stack.render(base_image, paint_param_adjuster)

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
        assert isinstance(bounds_rect, QRect)
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
        image_bounds = self.bounds
        if image_bounds.contains(image_point):
            return self.qimage(True).pixelColor(image_point)
        content_bounds = self.merged_layer_bounds
        adjusted_point = image_point - content_bounds.topLeft()
        if not content_bounds.contains(adjusted_point):
            return QColor(0, 0, 0)
        return self.qimage(False).pixelColor(adjusted_point)

    # LAYER ACCESS / MANIPULATION FUNCTIONS:

    def top_layer_at_point(self, image_coordinates: QPoint) -> Optional[ImageLayer | TextLayer]:
        """Return the topmost image or text layer that contains non-transparent pixels at the given coordinates."""
        all_layers = [layer for layer in self._layer_stack.recursive_child_layers
                      if isinstance(layer, (ImageLayer, TextLayer))]
        for layer in all_layers:
            layer_point = layer.map_from_image(image_coordinates)
            if not layer.bounds.contains(layer_point):
                continue
            layer_image = layer.get_qimage()
            pixel_color = layer_image.pixelColor(layer_point)
            if pixel_color.alpha() > 0:
                return layer
        return None

    def get_layer_by_id(self, layer_id: Optional[int]) -> Optional[Layer]:
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
        - If the new layer is visible and non-empty, the 'content_changed' signal is triggered.

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
        if layer_parent is None or layer_index is None:
            layer_parent, layer_index = self._get_new_layer_placement(layer_parent)
        if image_data is None:
            image_data = create_transparent_image(self.size)
        layer = self._create_layer_internal(layer_name, image_data)
        if transform is not None:
            layer.transform = transform

        @self._with_batch_content_update
        def _create_new(parent=layer_parent, new_layer=layer, i=layer_index) -> None:
            self._insert_layer_internal(new_layer, parent, i)

        @self._with_batch_content_update
        def _remove_new(new_layer=layer):
            self._remove_layer_internal(new_layer)

        UndoStack().commit_action(_create_new, _remove_new, 'ImageStack.create_layer')
        return layer

    def create_layer_group(self,
                           layer_name: Optional[str] = None,
                           layer_parent: Optional[LayerStack] = None,
                           layer_index: Optional[int] = None) -> LayerStack:
        """Creates and inserts a new layer group.

        Parameters
        ----------
        layer_name: str or None, default=None
            Layer name string. If None, a placeholder name will be assigned.
        layer_parent: optional LayerStack, default = None:
            Layer group where the layer will be inserted. If None, the main layer stack will be used.
        layer_index: int or None, default = None
            Index where the layer will be inserted into the stack. If None, it will be inserted above the active layer,
            or at the last index if the active layer isn't in the same group."""
        if layer_parent is None or layer_index is None:
            layer_parent, layer_index = self._get_new_layer_placement(layer_parent)
        if layer_name is None:
            layer_name = self._get_default_new_layer_name()
        layer = LayerStack(layer_name)

        def _create_new(group=layer, parent=layer_parent, idx=layer_index) -> None:
            self._insert_layer_internal(group, parent, idx)

        def _remove_new(group=layer) -> None:
            self._remove_layer_internal(group)

        UndoStack().commit_action(_create_new, _remove_new, 'ImageStack.create_layer_group')
        return layer

    def create_text_layer(self,
                          layer_data: Optional[TextRect] = None,
                          layer_parent: Optional[LayerStack] = None,
                          layer_index: Optional[int] = None) -> TextLayer:
        """Creates and inserts a new text layer.

        Parameters
        ----------
        layer_data: TextRect or None, default=None
            Optional initial text data.
        layer_parent: optional LayerStack, default = None:
            Layer group where the layer will be inserted. If None, the main layer stack will be used.
        layer_index: int or None, default = None
            Index where the layer will be inserted into the stack. If None, it will be inserted above the active layer,
            or at the last index if the active layer isn't in the same group."""
        if layer_parent is None or layer_index is None:
            layer_parent, layer_index = self._get_new_layer_placement(layer_parent)
        layer = TextLayer(layer_data)

        def _create_new(group=layer, parent=layer_parent, idx=layer_index) -> None:
            self._insert_layer_internal(group, parent, idx)

        def _remove_new(group=layer) -> None:
            self._remove_layer_internal(group)

        UndoStack().commit_action(_create_new, _remove_new, 'ImageStack.create_text_layer')
        return layer

    def copy_layer(self, layer: Optional[Layer] = None) -> None:
        """Copies a layer, inserting the copy above the original.
        Parameters
        ----------
            layer: Layer | None, default=None
                The layer object to copy, or its id. If None, the active layer will be used.
        """
        if layer == self._layer_stack:
            return
        if layer is None:
            layer = self.active_layer
        assert layer.layer_parent is not None and layer.layer_parent.contains(layer)
        layer_parent = cast(LayerStack, layer.layer_parent)
        layer_parent, layer_index = self._get_new_layer_placement(layer_parent)
        layer_copy = layer.copy()
        layer_copy.set_name(layer.name + ' copy')

        def _add_copy(parent=layer_parent, new_layer=layer_copy, idx=layer_index):
            self._insert_layer_internal(new_layer, parent, idx)

        def _remove_copy(new_layer=layer_copy):
            self._remove_layer_internal(new_layer)

        UndoStack().commit_action(_add_copy, _remove_copy, 'ImageStack.copy_layer')

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
        if layer.locked or layer.parent_locked:
            return
        assert layer.layer_parent is not None and layer.layer_parent.contains(layer)
        layer_parent = cast(LayerStack, layer.layer_parent)
        layer_index = layer_parent.get_layer_index(layer)
        last_active_id = self.active_layer_id

        def _remove(removed=layer):
            self._remove_layer_internal(removed)

        def _undo_remove(parent=layer_parent, restored=layer, idx=layer_index, active_id=last_active_id):
            self._insert_layer_internal(restored, parent, idx)
            if active_id != self.active_layer_id:
                self._set_active_layer_internal(active_id)

        UndoStack().commit_action(_remove, _undo_remove, 'ImageStack.remove_layer')

    def replace_layer(self, removed_layer: Layer, replacement_layer: Layer) -> None:
        """Removes a layer from the layer stack, replacing it with another that's not in the layer stack."""

        def _replace(to_remove: Layer, to_insert: Layer) -> None:
            assert self._layer_stack.contains_recursive(to_remove), (f'removed layer {to_remove.name} was not in the'
                                                                     f' layer stack.')
            assert to_insert.layer_parent is None and not self._layer_stack.contains_recursive(to_insert)
            layer_parent = to_remove.layer_parent
            assert isinstance(layer_parent, LayerStack)
            layer_index = layer_parent.get_layer_index(to_remove)
            assert layer_index is not None
            self._insert_layer_internal(to_insert, layer_parent, layer_index)
            if self.active_layer == to_remove or (isinstance(to_remove, LayerStack) and
                                                  to_remove.contains_recursive(self.active_layer)):
                self._set_active_layer_internal(to_insert)
            self._remove_layer_internal(to_remove)

        def _install_replacement(old: Layer = removed_layer, new: Layer = replacement_layer) -> None:
            _replace(old, new)

        def _revert_replacement(old: Layer = replacement_layer, new: Layer = removed_layer) -> None:
            _replace(old, new)

        UndoStack().commit_action(_install_replacement, _revert_replacement, 'ImageStack.replace_layer')

    def replace_text_layer_with_image(self, text_layer: TextLayer) -> ImageLayer:
        """Convert a text layer into an image layer, replacing it in the layer stack and returning the new layer."""
        assert self._layer_stack.contains_recursive(text_layer)
        image_layer = text_layer.copy_as_image_layer()
        self.replace_layer(text_layer, image_layer)
        return image_layer

    def offset_active_selection(self, offset: int) -> None:
        """Picks a new active layer relative to the index of the previous active layer."""
        active_layer = self.active_layer
        layer = active_layer
        while offset > 0:
            next_layer = self.next_layer(layer)
            offset -= 1
            if next_layer is None:
                break
            layer = next_layer
        while offset < 0:
            prev_layer = self.prev_layer(layer)
            offset += 1
            if prev_layer is None:
                break
            layer = prev_layer
        if layer == active_layer:
            return
        self.active_layer = layer

    def move_layer(self, layer: Layer, new_parent: LayerStack, new_index: int) -> None:
        """Moves a layer to a specific index under a parent group."""
        if new_parent.locked or new_parent.parent_locked or layer.parent_locked:
            return
        assert self._layer_stack.contains_recursive(layer)
        assert self._layer_stack == new_parent or self._layer_stack.contains_recursive(new_parent)
        layer_parent = layer.layer_parent
        assert layer_parent is not None and isinstance(layer_parent, LayerStack)
        if layer_parent == new_parent and new_index == new_parent.get_layer_index(layer):
            return
        max_idx = new_parent.count - 1 if layer_parent == new_parent else new_parent.count
        assert 0 <= new_index <= max_idx, (f'insert attempted into {new_parent.name} at {new_index}, expected 0 < i <'
                                           f' {max_idx}')
        layer_index = layer_parent.get_layer_index(layer)
        assert layer_index is not None

        @self._with_batch_content_update
        def _move(moving=layer, parent=new_parent, idx=new_index):
            if parent == moving.layer_parent:
                parent.move_layer(moving, idx)
                self._update_z_values()
            else:
                is_active = layer.id == self.active_layer_id
                self._remove_layer_internal(moving)
                self._insert_layer_internal(moving, parent, idx)
                if is_active:
                    self._set_active_layer_internal(moving)

        @self._with_batch_content_update
        def _move_back(moving=layer, parent=layer_parent, idx=layer_index):
            if parent == moving.layer_parent:
                parent.move_layer(moving, idx)
                self._update_z_values()
            else:
                is_active = layer.id == self.active_layer_id
                self._remove_layer_internal(moving)
                self._insert_layer_internal(moving, parent, idx)
                if is_active:
                    self._set_active_layer_internal(moving)

        UndoStack().commit_action(_move, _move_back, 'ImageStack.move_layer')

    def move_layer_by_offset(self, offset: int, layer: Optional[Layer] = None) -> None:
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
        if layer is None:
            layer = self.active_layer
        if layer == self._layer_stack or layer.parent_locked:
            return
        assert layer.layer_parent is not None and layer.layer_parent.contains(layer)
        assert offset in (1, -1), f'Unexpected offset {offset}'
        if offset == 1:
            new_parent, new_index = self._next_insert_index(layer)
        else:  # -1
            new_parent, new_index = self._prev_insert_index(layer)
        self.move_layer(layer, new_parent, new_index)

    @staticmethod
    def layer_is_flat(layer: Layer) -> bool:
        """Returns true if calling flatten_layer on a layer would do nothing."""
        if isinstance(layer, ImageLayer):
            return layer.composition_mode == CompositeMode.NORMAL and layer.opacity == 1.0 \
                and layer.transform == QTransform.fromTranslate(layer.bounds.x(), layer.bounds.y())
        if isinstance(layer, LayerStack):
            return layer.count == 0
        return False

    def flatten_layer(self, layer: Optional[Layer] = None) -> None:
        """Flatten a layer within the layer stack.

        Flattening a layer does the following:
        - Converts all other layer types to ImageLayer
        - Removes all transformations other than offset by applying them directly to image data
        - Sets opacity to 100%, recalculating color alpha levels accordingly.

        The goal is to simplify a layer's properties while leaving the final image as close to unchanged as possible.
        Note that this isn't totally possible in some cases, it doesn't work with some composition modes.

        TODO: Color accuracy has issues when both the top and base are partially transparent, look into reverse
              composition further and see if this can be improved.
        """
        if layer is None:
            layer = self.active_layer
        if layer == self._layer_stack or layer.locked or layer.parent_locked:
            return
        parent = layer.layer_parent
        assert isinstance(parent, LayerStack)

        if self.layer_is_flat(layer):
            logger.warning(f'Skipping flatten, layer {layer.name} cannot be simplified further.')
            return

        def _stop_render_above_z_level(level: int) -> RenderAdjustFn:

            def _render_adjust(layer_id: int, img: QImage, bounds: QRect, painter: QPainter) -> Optional[QImage]:
                rendered_layer = self._layer_stack.get_layer_by_id(layer_id)
                assert rendered_layer is not None
                if rendered_layer.z_value > level:
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                    if not (isinstance(rendered_layer, LayerStack) and rendered_layer.contains_recursive(layer)):
                        painter.setOpacity(0)
                        return QImage()
                return None

            return _render_adjust
        if isinstance(layer, LayerStack):
            last_child = layer.child_layers[-1]
            base_z = last_child.z_value - 1
        else:
            base_z = layer.z_value - 1

        base_render = parent.render(paint_param_adjuster=_stop_render_above_z_level(base_z))
        top_render = parent.render(paint_param_adjuster=_stop_render_above_z_level(layer.z_value))
        base_render.save('base.png')
        top_render.save('top.png')
        # Subtract out base from top:
        np_base = image_data_as_numpy_8bit(base_render)
        np_combined = image_data_as_numpy_8bit(top_render)
        np_top = np_combined
        identical_regions = np_base[:, :, 3] == np_combined[:, :, 3]
        for c in range(3):
            identical_regions = identical_regions & (np_base[:, :, c] == np_combined[:, :, c])
        np_combined[identical_regions, :] = 0

        # Attempt a reversed SourceOver composition to calculate color values for the final top layer in areas where
        # both top and base are partially transparent:
        blended_px = (~identical_regions & (np_base[:, :, 3] < 255) & (np_base[:, :, 3] > 0)
                      & (np_combined[:, :, 3] < 255) & (np_combined[:, :, 3] > 0))
        alpha_combined = np_combined[:, :, 3] / 255.0
        alpha_base = np_base[:, :, 3] / 255.0
        alpha_top = alpha_combined - alpha_base
        alpha_top[blended_px] /= (1 - alpha_base[blended_px])
        alpha_top[blended_px] = np.clip(alpha_top[blended_px], .00001, 1.0)

        # Solve for the reversed rgb compositing function:
        # c, t, b = combined, top, base, CA, TA, BA = combinedAlpha, topAlpha, baseAlpha
        # c = (tAT + bAB(1 - AT)) / AC
        # cAC = tAT + bAB(1 - AT)
        # cAC - bAB(1 - AT) = tAT
        # t = (cAC - bAB(1 - AT)) / AT
        for c in range(3):
            comp_mult = np_combined[blended_px, c] * alpha_combined[blended_px]
            top_inv_alpha = 1 - alpha_top[blended_px]
            base_mult = np_base[blended_px, c] * alpha_base[blended_px]
            np_top[blended_px, c] = np.clip(comp_mult - (base_mult * top_inv_alpha) / alpha_top[blended_px],
                                            0, 255)
        np_top[blended_px, 3] = alpha_top[blended_px] * 255

        layer_offset = parent.bounds.topLeft()
        replacement_layer = self._create_layer_internal(layer.name, top_render)
        replacement_layer.set_transform(QTransform.fromTranslate(layer_offset.x(), layer_offset.y()))
        self.replace_layer(layer, replacement_layer)

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
                The layer object to merge down. If None, the active layer will be used.
        """
        if layer is None:
            layer = self.active_layer
        if layer == self._layer_stack or layer.locked or layer.parent_locked:
            return
        assert layer.layer_parent is not None \
               and layer.layer_parent.contains(layer), f'invalid layer: {layer.name}:{layer.id}'
        if not isinstance(layer, TransformLayer):
            return
        top_layer = cast(TransformLayer, layer)
        layer_parent = cast(LayerStack, top_layer.layer_parent)
        layer_index = layer_parent.get_layer_index(top_layer)
        assert layer_index is not None
        if layer_index == layer_parent.count - 1:
            return
        base_layer = layer_parent.get_layer_by_index(layer_index + 1)
        if not isinstance(base_layer, TransformLayer) or base_layer.locked or not base_layer.visible:
            return
        base_layer = cast(TransformLayer, base_layer)

        with UndoStack().combining_actions('ImageStack.merge_layer_down'):
            text_layer_names = []
            if isinstance(base_layer, TextLayer):
                text_layer_names.append(base_layer.name)
            if isinstance(top_layer, TextLayer):
                text_layer_names.append(top_layer.name)
            if len(text_layer_names) > 0:
                if not TextLayer.confirm_or_cancel_render_to_image(text_layer_names, ACTION_NAME_MERGE_LAYERS):
                    return
                if isinstance(base_layer, TextLayer):
                    base_layer = self.replace_text_layer_with_image(base_layer)
                if isinstance(top_layer, TextLayer):
                    top_layer = self.replace_text_layer_with_image(top_layer)
            assert isinstance(base_layer, ImageLayer)
            assert isinstance(top_layer, ImageLayer)

            base_layer_state = base_layer.save_state()
            is_active_layer = bool(top_layer.id == self.active_layer_id)

            top_to_base_transform = top_layer.transform * base_layer.transform.inverted()[0]
            base_bounds = base_layer.bounds
            top_bounds = map_rect_precise(top_layer.bounds, top_to_base_transform).toAlignedRect()
            merged_bounds = base_bounds.united(top_bounds)
            merged_image = create_transparent_image(merged_bounds.size())
            painter = QPainter(merged_image)
            painter.setRenderHint(QPainter.RenderHint.LosslessImageRendering)

            offset = base_bounds.topLeft() - merged_bounds.topLeft()
            base_paint_transform = QTransform.fromTranslate(offset.x(), offset.y())
            painter.setTransform(base_paint_transform, False)
            painter.drawImage(QRect(QPoint(), base_layer.size), base_layer.image)

            painter.setTransform(top_to_base_transform * base_paint_transform)
            painter.setOpacity(top_layer.opacity)
            top_image = top_layer.image
            qt_composite_mode = top_layer.composition_mode.qt_composite_mode()
            if qt_composite_mode is not None:
                painter.setCompositionMode(qt_composite_mode)
                painter.drawImage(top_layer.bounds, top_image)
            else:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                composite_op = top_layer.composition_mode.custom_composite_op()
                composite_op(top_image, merged_image, top_layer.opacity, painter.transform())
            if base_layer.alpha_locked:
                painter.setTransform(base_paint_transform)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                painter.drawImage(QPoint(), base_layer.image)
            painter.end()

            final_transform = QTransform.fromTranslate(-offset.x(), -offset.y()) * base_layer.transform

            def _do_merge(removed=top_layer, base=base_layer, matrix=final_transform,
                          img=merged_image, update_active=is_active_layer) -> None:
                self._remove_layer_internal(removed)
                with base.with_alpha_lock_disabled():
                    base.set_image(img)
                base.set_transform(matrix)
                if removed.visible != base.visible:
                    self._emit_content_changed()
                if update_active:
                    self._set_active_layer_internal(base)

            def _undo_merge(parent=layer_parent, restored=top_layer, base=base_layer, state=base_layer_state,
                            idx=layer_index, update_active=is_active_layer) -> None:
                base.restore_state(state)
                self._insert_layer_internal(restored, parent, idx)
                if update_active:
                    self._set_active_layer_internal(restored)
                if restored.visible != base.visible:
                    self._emit_content_changed()

            UndoStack().commit_action(_do_merge, _undo_merge, 'ImageStack.merge_layer_down')

    def layer_to_image_size(self, layer: Optional[Layer] = None) -> None:
        """Resizes a layer to match the image size. Out-of-bounds content is cropped, new content is transparent.

        Parameters
        ----------
            layer: ImageLayer | int | None, default=None
                The layer object to copy, or its id. If None, the active layer will be used.
        """
        if layer == self._layer_stack:
            return
        if layer is None:
            layer = self.active_layer
        with UndoStack().combining_actions('ImageStack.layer_to_image_size'):
            if isinstance(layer, TextLayer):
                layer_bounds = layer.transformed_bounds
                if self.bounds.contains(layer_bounds):
                    return  # No need to alter text layers that are already fully in the image bounds.
                if TextLayer.confirm_or_cancel_render_to_image([layer.name], ACTION_NAME_LAYER_TO_IMAGE_SIZE):
                    layer = self.replace_text_layer_with_image(layer)
            if not isinstance(layer, ImageLayer):
                assert isinstance(layer, LayerStack)
                layers = layer.recursive_child_layers
                for child_layer in layers:
                    if child_layer.locked or child_layer.parent_locked or not isinstance(child_layer, ImageLayer):
                        continue
                    self.layer_to_image_size(child_layer)
                return
            layer_image_bounds = layer.transformed_bounds
            image_bounds = self.bounds
            if layer_image_bounds == image_bounds or layer.locked or layer.parent_locked:
                return
            base_state = layer.save_state()
            layer_image, offset_transform = layer.transformed_image()
            layer_position = QPoint(int(offset_transform.dx()), int(offset_transform.dy()))
            resized_image = create_transparent_image(self.size)
            painter = QPainter(resized_image)
            painter.drawImage(QRect(layer_position, layer_image.size()), layer_image)
            painter.end()
            content_changed = layer.visible and not layer.empty

            def _resize(resized=layer, img=resized_image, changed=content_changed) -> None:
                assert isinstance(resized, ImageLayer)
                with resized.with_alpha_lock_disabled():
                    resized.set_image(img)
                    if isinstance(resized, TransformLayer):
                        resized.set_transform(QTransform())
                if changed:
                    self._emit_content_changed()

            def _undo_resize(restored=layer, state=base_state, changed=content_changed) -> None:
                restored.restore_state(state)
                if changed:
                    self._emit_content_changed()

            UndoStack().commit_action(_resize, _undo_resize, 'ImageStack.layer_to_image_size')

    def get_layer_mask(self, layer: Layer) -> QImage:
        """Transform the selection layer to another layer's local coordinates, crop to bounds, and return the
        resulting image mask."""
        selection_mask = self.selection_layer.image
        transformed_mask = create_transparent_image(layer.size)
        # mask image coordinates to image coordinates:
        painter_transform = self.selection_layer.transform
        # Image coordinates to local layer coordinates:
        if isinstance(layer, TransformLayer):
            painter_transform = painter_transform * layer.transform.inverted()[0]
        else:
            layer_pos = layer.bounds.topLeft()
            painter_transform = painter_transform * QTransform.fromTranslate(-layer_pos.x(), -layer_pos.y())
        painter = QPainter(transformed_mask)
        painter.setTransform(painter_transform)
        painter.drawImage(QRect(0, 0, selection_mask.width(), selection_mask.height()), selection_mask)
        painter.end()
        return transformed_mask

    def select_active_layer_content(self) -> None:
        """Selects all pixels in the active layer that are not fully transparent."""
        active_layer = self.active_layer
        selection_image = create_transparent_image(self.selection_layer.size)
        painter = QPainter(selection_image)
        if isinstance(active_layer, TransformLayer):
            painter.setTransform(active_layer.transform * self.selection_layer.transform.inverted()[0])
        else:
            offset = active_layer.bounds.topLeft()
            painter.setTransform(self.selection_layer.transform.inverted()[0] * QTransform.fromTranslate(offset.x(),
                                                                                                         offset.y()))
        painter.drawImage(0, 0, active_layer.image)
        painter.end()
        self.selection_layer.image = selection_image

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
        if mask is None:
            mask = self.get_layer_mask(layer)
        image = layer.image
        painter = QPainter(image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(QRect(0, 0, image.width(), image.height()), mask)
        painter.end()
        self._copy_buffer = image
        if isinstance(layer, TransformLayer):
            transform = layer.transform
        else:
            offset = layer.bounds.topLeft()
            transform = QTransform.fromTranslate(offset.x(), offset.y())
        content_bounds = image_content_bounds(image)
        if content_bounds.size() != image.size():
            image = image.copy(content_bounds)
            transform = QTransform.fromTranslate(content_bounds.x(), content_bounds.y()) * transform
        self._copy_buffer = image
        self._copy_buffer_transform = transform
        return image

    def clear_selected(self, layer: Optional[Layer] = None, save_to_copy_buffer=False) -> None:
        """Replaces all masked image content in a layer with transparency."""
        if layer is None:
            layer = self.active_layer
        if layer.locked:
            return
        transformed_mask = self.get_layer_mask(layer)
        if isinstance(layer, TextLayer):
            copy_buffer_backup = self._copy_buffer
            copy_buffer_transform_backup = self._copy_buffer_transform
            selected = self.copy_selected(layer, transformed_mask)
            if not save_to_copy_buffer:
                self._copy_buffer = copy_buffer_backup
                self._copy_buffer_transform = copy_buffer_transform_backup
            if image_is_fully_transparent(selected):
                return  # cutting selection changes nothing, no need to render to image.
            if TextLayer.confirm_or_cancel_render_to_image([layer.name], ACTION_NAME_CLEAR_SELECTED):
                with UndoStack().combining_actions('ImageStack.clear_selected'):
                    layer = self.replace_text_layer_with_image(layer)
                    layer.cut_masked(transformed_mask)
            else:
                self._copy_buffer = copy_buffer_backup
                self._copy_buffer_transform = copy_buffer_transform_backup
                return
        if save_to_copy_buffer:
            self.copy_selected(layer, transformed_mask)
        layer.cut_masked(transformed_mask)

    def cut_selected(self, layer: Optional[Layer] = None) -> None:
        """Replaces all masked image content in a layer with transparency, saving it in the copy buffer."""
        self.clear_selected(layer, True)

    def paste(self) -> None:
        """If the copy buffer contains image data, paste it into a new layer."""
        if self._copy_buffer is not None:
            new_layer = self.create_layer('Paste layer', self._copy_buffer.copy())
            if self._copy_buffer_transform is not None:
                new_layer.set_transform(self._copy_buffer_transform)
            self.active_layer = new_layer

    def set_generation_area_content(self,
                                    image_data: QImage,
                                    layer: Optional[Layer] = None,
                                    composition_mode: QPainter.CompositionMode
                                    = QPainter.CompositionMode.CompositionMode_SourceOver):
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
        if layer.locked:
            return
        scale = QTransform.fromScale(self._generation_area.width() / image_data.width(),
                                     self._generation_area.height() / image_data.height())
        offset = QTransform.fromTranslate(self._generation_area.x(), self.generation_area.y())
        data_transform = scale * offset
        if not isinstance(layer, ImageLayer):
            new_layer = self._create_layer_internal(image_data=image_data)
            new_layer.set_transform(data_transform)
            if isinstance(layer, LayerStack):
                parent: Optional[LayerParent] = layer
                insert_index = 0
            else:
                parent = layer.layer_parent
                assert isinstance(parent, LayerStack)
                layer_index = parent.get_layer_index(layer)
                assert layer_index is not None and layer_index >= 0
                insert_index = layer_index

            def _insert(added=new_layer, layer_parent=parent, index=insert_index):
                self._insert_layer_internal(added, layer_parent, index)

            def _remove(removed=new_layer):
                self._remove_layer_internal(removed)

            UndoStack().commit_action(_insert, _remove, 'ImageStack.set_generation_area_content')
        else:
            assert isinstance(layer, ImageLayer)
            data_transform = data_transform * layer.transform.inverted()[0]
            target_bounds = layer.map_rect_from_image(self._generation_area)
            if not data_transform.isIdentity():
                transformed_image = create_transparent_image(target_bounds.size())
                painter = QPainter(transformed_image)
                painter.setTransform(data_transform * QTransform.fromTranslate(-target_bounds.x(), -target_bounds.y()))
                painter.drawImage(QPoint(), image_data)
                painter.end()
                image_data = transformed_image
            layer.insert_image_content(image_data, target_bounds, composition_mode)

    def load_layer_stack(self, layer_stack: LayerStack, new_size: QSize,
                         new_active_layer: Optional[Layer] = None) -> None:
        """Loads a new image from layer data."""
        assert not self._layer_stack.contains_recursive(layer_stack)
        saved_state = self._layer_stack.save_state()
        saved_selection_state = self.selection_layer.save_state()
        old_size = self.size
        old_layers = self.layers
        old_layers.remove(self._layer_stack)
        active_id = self.active_layer_id
        new_layers: List[Layer] = []
        while layer_stack.count > 0:
            new_layers.append(layer_stack.get_layer_by_index(0))
            layer_stack.remove_layer(new_layers[-1])
        if new_active_layer is not None:
            new_active_id = new_active_layer.id
        elif len(new_layers) > 0:
            new_active_id = new_layers[0].id
        else:
            new_active_id = self._layer_stack.id

        @self._with_batch_content_update
        def _load(loaded=layer_stack, size=new_size, next_active_id=new_active_id):
            self.selection_layer.clear(False)
            self.selection_layer.adjust_local_bounds(QRect(QPoint(), size), False)
            self.selection_layer.set_transform(QTransform())
            assert self.selection_layer.transformed_bounds.size() == new_size
            self._active_layer_id = self._layer_stack.id
            while self._layer_stack.count > 0:
                self._remove_layer_internal(self._layer_stack.child_layers[0])
            self._layer_stack.set_name(loaded.name)
            self._layer_stack.set_visible(loaded.visible)
            self._layer_stack.set_composition_mode(loaded.composition_mode)
            self._layer_stack.set_opacity(loaded.opacity)
            self.size = size
            for new_layer in new_layers:
                self._insert_layer_internal(new_layer, self._layer_stack, self._layer_stack.count)
            active_layer = self._layer_stack.get_layer_by_id(next_active_id)
            assert active_layer is not None, f'failed to find layer {next_active_id}'
            self._active_layer_id = next_active_id
            self.active_layer_changed.emit(active_layer)

        @self._with_batch_content_update
        def _undo_load(selection_state=saved_selection_state, stack_state=saved_state, size=old_size,
                       active=active_id):
            self.size = size
            self.selection_layer.restore_state(selection_state)
            self._active_layer_id = self._layer_stack.id
            while self._layer_stack.count > 0:
                self._remove_layer_internal(self._layer_stack.child_layers[0])
            for restored_layer in old_layers:
                self._insert_layer_internal(restored_layer, self._layer_stack, self._layer_stack.count)
            self._layer_stack.restore_state(stack_state)
            self._update_z_values()
            self._active_layer_id = active
            active_layer = self._layer_stack.get_layer_by_id(self._active_layer_id)
            self.active_layer_changed.emit(active_layer)

        UndoStack().commit_action(_load, _undo_load, 'ImageStack.load_layer_stack')

    def load_image(self, image_data: QImage):
        """
        Loads a new image to be edited. This clears all layers, updates the image size, and inserts the image as a new
        active layer.

        Parameters
        ----------
        image_data: QImage
            Layer stack size will be adjusted to match image data size.
        """
        saved_state = self._layer_stack.save_state()
        saved_selection_state = self.selection_layer.save_state()
        old_size = self.size

        new_layer = self._create_layer_internal(None, image_data)
        new_size = new_layer.size
        gen_area = QRect(self._generation_area)
        new_gen_area = gen_area.intersected(new_layer.transformed_bounds)
        last_active_id = self.active_layer_id

        @self._with_batch_content_update
        def _load(loaded=new_layer, gen_rect=new_gen_area, size=new_size):
            self.selection_layer.clear(False)
            self.selection_layer.adjust_local_bounds(QRect(QPoint(), size), False)
            self.selection_layer.set_transform(QTransform())
            assert self.selection_layer.transformed_bounds.size() == new_size
            self._active_layer_id = self._layer_stack.id
            while self._layer_stack.count > 0:
                self._remove_layer_internal(self._layer_stack.child_layers[0])
            self._layer_stack.set_visible(True)
            self._layer_stack.set_opacity(1.0)
            self._layer_stack.set_composition_mode(CompositeMode.NORMAL)
            self._insert_layer_internal(new_layer, self._layer_stack, 0)
            assert self.has_image
            self._set_generation_area_internal(gen_rect)
            self._set_active_layer_internal(loaded)
            self.size = size

        # noinspection PyDefaultArgument
        @self._with_batch_content_update
        def _undo_load(unloaded=new_layer, state=saved_state, selection_state=saved_selection_state, gen_rect=gen_area,
                       size=old_size, active_id=last_active_id):
            assert self.count == 1, f'Unexpected layer count {self.count} when reversing image load!'
            self._remove_layer_internal(unloaded)
            self._active_layer_id = self._layer_stack.id
            self._layer_stack.restore_state(state)
            self._update_z_values()
            self.selection_layer.restore_state(selection_state)
            self._set_generation_area_internal(gen_rect)
            self._set_active_layer_internal(active_id)
            self.size = size

        UndoStack().commit_action(_load, _undo_load, 'ImageStack.set_image')

    # INTERNAL:
    def _layer_content_change_slot(self, layer: Layer, _=None) -> None:
        if layer.visible and (layer == self._layer_stack or layer == self.selection_layer
                              or self._layer_stack.contains_recursive(layer)):
            if layer != self.selection_layer:
                self._image.invalidate()
            self._emit_content_changed()

    def _layer_visibility_change_slot(self, layer: Layer, _) -> None:
        if layer == self._layer_stack or layer == self.selection_layer or self._layer_stack.contains_recursive(layer):
            if layer != self.selection_layer:
                self._image.invalidate()
            if not layer.empty:
                self._emit_content_changed()

    def _get_default_new_layer_name(self) -> str:
        default_name_pattern = r'^layer (\d+)'
        max_missing_layer = 0
        for layer in self._all_layers():
            match = re.match(default_name_pattern, layer.name)
            if match:
                max_missing_layer = max(max_missing_layer, int(match.group(1)) + 1)
        return f'layer {max_missing_layer}'

    def _get_new_layer_placement(self, layer_parent: Optional[LayerStack] = None) -> Tuple[LayerStack, int]:
        """Default layer placement:
        1. If no parent is provided, use the active layer if it is a layer group, otherwise use the active layer's
           parent
        2. Within the parent, insert above the active layer if it is under the same parent, otherwise at the start
           of the list.
        3. If the parent is locked, move the new layer up until an unlocked parent is found.
        """
        layer_index: Optional[int] = 0
        if layer_parent is None:
            active_layer = self.active_layer
            if isinstance(active_layer, LayerStack):
                layer_parent = active_layer
                index_layer: Optional[Layer] = None
            else:
                next_parent = active_layer.layer_parent
                assert next_parent is None or isinstance(next_parent, LayerStack)
                layer_parent = next_parent
                index_layer = active_layer
            while layer_parent is not None and layer_parent.locked:
                index_layer = layer_parent
                next_parent = layer_parent.layer_parent
                assert next_parent is None or isinstance(next_parent, LayerStack)
                layer_parent = next_parent
            assert layer_parent is not None, 'root layer stack was locked or layer stack was broken'
            if index_layer is not None:
                layer_index = layer_parent.get_layer_index(index_layer)
        assert layer_index is not None
        assert layer_parent is not None
        return layer_parent, layer_index

    def _create_layer_internal(self, layer_name: Optional[str] = None,
                               image_data: Optional[QImage | QSize] = None) -> ImageLayer:
        """Returns a new layer object given valid data. This emits no signals, connects no signal handlers, and does
           not add the layer to the stack."""
        if layer_name is None:
            layer_name = self._get_default_new_layer_name()
        assert isinstance(layer_name, str)
        assert isinstance(image_data, (QImage, QSize))
        if image_data is None:
            layer = ImageLayer(self.size, layer_name)
        else:
            layer = ImageLayer(image_data, layer_name)
        return layer

    def _connect_layer(self, layer: Layer) -> None:
        assert layer == self._layer_stack or self._layer_stack.contains_recursive(layer), (f'layer {layer.name}:'
                                                                                           f'{layer.id} is not in the'
                                                                                           ' image stack.')
        layer.size_changed.connect(self._layer_content_change_slot)
        layer.content_changed.connect(self._layer_content_change_slot)
        layer.opacity_changed.connect(self._layer_content_change_slot)
        layer.composition_mode_changed.connect(self._layer_content_change_slot)
        if isinstance(layer, TransformLayer):
            layer.transform_changed.connect(self._layer_content_change_slot)
        layer.visibility_changed.connect(self._layer_visibility_change_slot)
        if isinstance(layer, LayerStack):
            for child_layer in layer.recursive_child_layers:
                self._connect_layer(child_layer)

    def _disconnect_layer(self, layer: Layer) -> None:
        layer.size_changed.disconnect(self._layer_content_change_slot)
        layer.content_changed.disconnect(self._layer_content_change_slot)
        layer.opacity_changed.disconnect(self._layer_content_change_slot)
        layer.composition_mode_changed.disconnect(self._layer_content_change_slot)
        if isinstance(layer, TransformLayer):
            layer.transform_changed.disconnect(self._layer_content_change_slot)
        layer.visibility_changed.disconnect(self._layer_visibility_change_slot)

    def _layer_added_slot(self, layer: Layer) -> None:
        self._connect_layer(layer)
        self.layer_added.emit(layer)

    def _layer_removed_slot(self, layer: Layer) -> None:
        self._disconnect_layer(layer)
        self.layer_removed.emit(layer)

    def _insert_layer_internal(self, layer: Layer, parent: LayerStack, index: int):
        assert layer is not None and layer.layer_parent is None and not self._layer_stack.contains_recursive(layer)
        assert parent is not None and (parent == self._layer_stack or self._layer_stack.contains_recursive(parent))
        layer.z_value = parent.z_value - (index + 1)
        parent.insert_layer(layer, index)
        self._connect_layer(layer)
        self._update_z_values()
        if self._layer_stack.count == 1:
            AppStateTracker.set_app_state(APP_STATE_EDITING)
            if self._active_layer_id is self._layer_stack.id:
                self._active_layer_id = layer.id
                self.active_layer_changed.emit(layer)
        if layer.visible and not layer.empty:
            self._image.invalidate()
            self._emit_content_changed()

    def _remove_layer_internal(self, layer: Layer) -> None:
        """Removes a layer from the stack, optionally disconnect layer signals, and emit all required image stack
           signals. This does not alter the undo history."""
        assert layer is not None
        layer_parent = cast(LayerStack, layer.layer_parent)
        assert layer_parent is not None
        assert layer_parent.contains(layer)
        self._disconnect_layer(layer)
        if self.active_layer_id == layer.id:
            active_layer = self.active_layer
            next_active_layer = self.next_layer(active_layer)
            if isinstance(active_layer, LayerStack):
                while next_active_layer is not None and active_layer.contains_recursive(next_active_layer):
                    next_active_layer = self.next_layer(next_active_layer)
            if next_active_layer is None:
                next_active_layer = self.prev_layer(active_layer)
                if isinstance(active_layer, LayerStack):
                    while next_active_layer is not None and active_layer.contains_recursive(next_active_layer):
                        next_active_layer = self.prev_layer(next_active_layer)
            if next_active_layer is None or next_active_layer == layer or not \
                    self._layer_stack.contains_recursive(next_active_layer):
                next_active_id = self._layer_stack.id
            else:
                next_active_id = next_active_layer.id
        else:
            next_active_id = self.active_layer_id
        if next_active_id != self.active_layer_id:
            self._set_active_layer_internal(next_active_id)
        layer_parent.remove_layer(layer)
        self._update_z_values()
        if self._layer_stack.count == 0:
            AppStateTracker.set_app_state(APP_STATE_NO_IMAGE)
        if layer.visible and not layer.empty:
            self._image.invalidate()
            self._emit_content_changed()

    def _set_active_layer_internal(self, new_active_layer: Layer | int) -> None:
        if isinstance(new_active_layer, Layer):
            layer = new_active_layer
            layer_id = new_active_layer.id
        else:
            assert isinstance(new_active_layer, int)
            layer_id = new_active_layer
            if layer_id == self._layer_stack.id:
                layer = self._layer_stack
            else:
                layer_from_id = self._layer_stack.get_layer_by_id(layer_id)
                assert layer_from_id is not None
                layer = layer_from_id
        if layer == self.active_layer:
            return
        self._active_layer_id = layer_id
        self.active_layer_changed.emit(layer)

    def _get_closest_valid_generation_area(self, initial_area: QRect) -> QRect:
        adjusted_area = QRect(initial_area)
        # Make sure that the image generation area fits within allowed size limits:
        min_size = self.min_generation_area_size
        adjusted_area = adjusted_area.united(QRect(adjusted_area.topLeft(), min_size))
        max_size = self.max_generation_area_size
        adjusted_area = adjusted_area.intersected(QRect(adjusted_area.topLeft(), max_size))
        return adjusted_placement_in_bounds(adjusted_area, self.bounds)

    def _set_generation_area_internal(self, bounds_rect: QRect) -> None:
        """Updates the image generation area, adjusting as needed based on image bounds, and sending the
           selection_changed signal if any changes happened. Does not update undo history."""
        assert isinstance(bounds_rect, QRect)
        bounds_rect = self._get_closest_valid_generation_area(bounds_rect)
        if bounds_rect != self._generation_area:
            last_bounds = self._generation_area
            self._generation_area = bounds_rect
            if bounds_rect.size() != last_bounds.size():
                AppConfig().set(AppConfig.EDIT_SIZE, QSize(bounds_rect.size()))
            self.generation_area_bounds_changed.emit(bounds_rect)

    def _update_z_values(self) -> None:
        changed_values = False
        visible_changes = False
        flattened_stack = self._all_layers()
        self.selection_layer.z_value = 1
        for i, layer in enumerate(flattened_stack):
            if layer.z_value != -i:
                changed_values = True
                start = min(-layer.z_value, i)
                end = max(-layer.z_value, i)
                if any(not offset_layer.empty for offset_layer in flattened_stack[start:end]):
                    visible_changes = True
                layer.z_value = -i
        if changed_values:
            self.layer_order_changed.emit()
        if visible_changes:
            self._emit_content_changed()

    def _all_layers(self) -> List[Layer]:
        return [self._layer_stack, *self._layer_stack.recursive_child_layers]

    def _next_insert_index(self, layer: Layer) -> Tuple[LayerStack, int]:
        assert layer is not None and layer.layer_parent is not None and self._layer_stack.contains_recursive(layer)
        parent = cast(LayerStack, layer.layer_parent)
        current_index = parent.get_layer_index(layer)
        assert current_index is not None
        if current_index == (parent.count - 1):
            outer_parent = cast(LayerStack, parent.layer_parent)
            if outer_parent is None:
                return parent, current_index
            parent_index = outer_parent.get_layer_index(parent)
            assert parent_index is not None
            return outer_parent, parent_index + 1
        next_layer = parent.get_layer_by_index(current_index + 1)
        if isinstance(next_layer, LayerStack):
            return next_layer, 0
        return parent, current_index + 1

    def next_layer(self, layer: Layer) -> Optional[Layer]:
        """Given a layer in the stack, return the layer directly below it, or None if it's the bottom layer."""
        assert layer is not None and layer.layer_parent is not None and self._layer_stack.contains_recursive(layer)
        if isinstance(layer, LayerStack) and layer.count > 0:
            return layer.get_layer_by_index(0)
        parent = cast(LayerStack, layer.layer_parent)
        current_index = parent.get_layer_index(layer)
        assert current_index is not None
        while current_index == (parent.count - 1):
            outer_parent = cast(LayerStack, parent.layer_parent)
            if outer_parent is None:
                return None
            current_index = outer_parent.get_layer_index(parent)
            assert current_index is not None
            parent = outer_parent
        return parent.get_layer_by_index(current_index + 1)

    def prev_layer(self, layer: Layer) -> Optional[Layer]:
        """Given a layer in the stack, return the layer directly above it, or None if it's the top layer."""
        assert layer is not None and layer.layer_parent is not None and self._layer_stack.contains_recursive(layer)
        parent = cast(LayerStack, layer.layer_parent)
        current_index = parent.get_layer_index(layer)
        assert current_index is not None
        if current_index == 0:
            return parent
        prev_layer = parent.get_layer_by_index(current_index - 1)
        while isinstance(prev_layer, LayerStack) and prev_layer.count > 0:
            prev_layer = prev_layer.get_layer_by_index(prev_layer.count - 1)
        return prev_layer

    def _prev_insert_index(self, layer: Layer) -> Tuple[LayerStack, int]:
        assert layer is not None and layer.layer_parent is not None and self._layer_stack.contains_recursive(layer)
        parent = cast(LayerStack, layer.layer_parent)
        current_index = parent.get_layer_index(layer)
        assert current_index is not None
        if current_index == 0:
            outer_parent = cast(LayerStack, parent.layer_parent)
            if outer_parent is None:
                return parent, current_index
            parent_index = outer_parent.get_layer_index(parent)
            assert parent_index is not None
            return outer_parent, parent_index
        last_layer = parent.get_layer_by_index(current_index - 1)
        if isinstance(last_layer, LayerStack):
            return last_layer, last_layer.count
        return parent, current_index - 1

    def _emit_content_changed(self) -> None:
        if self._content_change_signal_enabled:
            self.content_changed.emit()

    def _with_batch_content_update(self, func):
        """Decorator for wrapping functions that trigger a lot of redundant content change signals.  This will
           suppress the signal while the function is executing, then emit it once at the end."""

        def _wrapper():
            self._content_change_signal_enabled = False
            func()
            self._content_change_signal_enabled = True
            self._emit_content_changed()

        return _wrapper

    @staticmethod
    def _find_offset_index(layer: Layer, offset: int, allow_end_indices=True) -> Tuple[LayerStack, int]:

        def _recursive_offset(parent: LayerStack, index: int, off: int) -> Tuple[LayerStack, int]:
            max_idx = parent.count
            if allow_end_indices:
                max_idx += 1
            step = 1 if off > 0 else -1
            while off != 0:
                if index < 0 or index >= max_idx:
                    if parent.layer_parent is None:
                        return parent, int(clamp(index, 0, max_idx))
                    next_parent = parent.layer_parent
                    assert isinstance(next_parent, LayerStack)
                    parent_idx = next_parent.get_layer_index(parent)
                    assert parent_idx is not None
                    if index > 0:
                        parent_idx += 1
                    return _recursive_offset(next_parent, parent_idx, off)
                if index > max_idx:
                    if parent.layer_parent is None:
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
            return parent, int(clamp(index, 0, max_idx))

        assert layer.layer_parent is not None
        layer_parent = cast(LayerStack, layer.layer_parent)
        layer_index = layer_parent.get_layer_index(layer)
        assert layer_index is not None
        return _recursive_offset(layer_parent, layer_index, offset)
