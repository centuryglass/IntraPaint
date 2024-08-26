"""
Draws content to an image layer.
"""
from typing import Optional, List

from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QColor, QTransform, QImage
from PySide6.QtWidgets import QGraphicsScene, QGraphicsItem

from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.image.layers.layer import Layer


class LayerCanvas:
    """Connects a MyPaint surface with an image layer."""

    def __init__(self, scene: QGraphicsScene, layer: Optional[ImageLayer] = None) -> None:
        """Initialize a MyPaint surface, and connect to the image layer."""
        self._layer: Optional[ImageLayer] = None
        self._eraser = False
        self._color = QColor(0, 0, 0)
        self._brush_size = 1
        self._z_value = 0
        self._scene = scene
        self._drawing = False
        if layer is not None:
            self.connect_to_layer(layer)

    def connect_to_layer(self, new_layer: Optional[Layer]):
        """Disconnects from the current layer, and connects to a new one."""
        if self._layer is not None:
            if self._drawing:
                self.end_stroke()
            self.disconnect_layer_signals()
        if not isinstance(new_layer, ImageLayer):
            new_layer = None
        self._layer = new_layer
        if self._layer is not None:
            self._update_scene_content_bounds(self._layer.bounds)
            self.connect_layer_signals()
            self._layer_size_change_slot(self._layer, self._layer.size)
            self._update_canvas_transform(self._layer, self._layer.transform)
            self._set_z_value(self._layer.z_value)

        self._layer_content_change_slot(self._layer)

    @property
    def scene(self) -> QGraphicsScene:
        """Access the scene rendering the canvas."""
        return self._scene

    @property
    def eraser(self) -> bool:
        """Returns whether the brush is acting as an eraser."""
        return self._eraser

    @eraser.setter
    def eraser(self, should_erase: bool) -> None:
        """Sets whether the active brush should work as an eraser."""
        self._set_is_eraser(should_erase)

    @property
    def z_value(self) -> int:
        """Returns the level where content will be shown in a GraphicsScene."""
        return self._z_value

    @z_value.setter
    def z_value(self, z_value: int) -> None:
        """Updates the level where content will be shown in a GraphicsScene."""
        self._set_z_value(z_value)

    @property
    def brush_size(self) -> int:
        """Gets the current brush size."""
        return self._brush_size

    @brush_size.setter
    def brush_size(self, size: int):
        """Sets the base brush size.

        Parameters
        ----------
        size : int
            Base brush blot diameter in pixels.
        """
        self._set_brush_size(size)

    @property
    def brush_color(self) -> QColor:
        """Returns the current brush color."""
        return self._color

    @brush_color.setter
    def brush_color(self, new_color: QColor) -> None:
        """Updates the active brush color."""
        self._set_brush_color(new_color)

    @property
    def drawing(self) -> bool:
        """Returns whether the stroke is still in-progress."""
        return self._drawing

    @property
    def layer(self) -> Optional[ImageLayer]:
        """Returns the active ImageLayer, or None if no ImageLayer is active."""
        return self._layer

    def start_stroke(self) -> None:
        """Signals the start of a brush stroke, to be called once whenever user input starts or resumes."""
        if self._layer is None or not self._layer.visible:
            return
        if self._drawing:
            self.end_stroke()
        self._drawing = True

    def stroke_to(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
                  y_tilt: Optional[float]) -> None:
        """Continue a brush stroke with optional tablet inputs."""
        if self._layer is None or not self._layer.visible:
            return
        if not self._drawing:
            self.start_stroke()
        self._draw(x, y, pressure, x_tilt, y_tilt)

    def end_stroke(self) -> None:
        """Finishes a brush stroke, copying it back to the layer."""
        self._drawing = False
        if self._layer is not None:
            self._copy_changes_to_layer(self._layer)

    def set_input_mask(self, mask_image: Optional[QImage]) -> None:
        """Sets a mask image, restricting canvas changes to areas covered by non-transparent mask areas"""
        raise NotImplementedError()

    def scene_items(self) -> List[QGraphicsItem]:
        """Returns all graphics items present in the scene that belong to the canvas."""
        raise NotImplementedError('Implement scene_items to return all canvas graphics items in the scene')

    def disconnect_layer_signals(self) -> None:
        """Disconnect signal handlers for the connected layer."""
        assert self._layer is not None
        self._layer.visibility_changed.disconnect(self._layer_content_change_slot)
        self._layer.content_changed.disconnect(self._layer_content_change_slot)
        self._layer.size_changed.disconnect(self._layer_size_change_slot)
        self._layer.transform_changed.disconnect(self._layer_transform_change_slot)
        self._layer.opacity_changed.disconnect(self._layer_opacity_change_slot)
        self._layer.composition_mode_changed.disconnect(self._layer_composition_mode_change_slot)
        self._layer.z_value_changed.disconnect(self._layer_z_value_change_slot)
        self._layer.alpha_lock_changed.disconnect(self._layer_alpha_lock_change_slot)

    def connect_layer_signals(self) -> None:
        """Reconnect signal handlers for the connected layer. Only call after disconnect_layer_signals, or within
           connect_to_layer."""
        assert self._layer is not None
        self._layer.visibility_changed.connect(self._layer_content_change_slot)
        self._layer.content_changed.connect(self._layer_content_change_slot)
        self._layer.size_changed.connect(self._layer_size_change_slot)
        self._layer.transform_changed.connect(self._layer_transform_change_slot)
        self._layer.opacity_changed.connect(self._layer_opacity_change_slot)
        self._layer.composition_mode_changed.connect(self._layer_composition_mode_change_slot)
        self._layer.z_value_changed.connect(self._layer_z_value_change_slot)
        self._layer.alpha_lock_changed.connect(self._layer_alpha_lock_change_slot)

    def _set_brush_size(self, new_size: int) -> None:
        self._brush_size = new_size

    def _set_brush_color(self, new_color: QColor) -> None:
        """Updates the brush color."""
        self._color = new_color

    def _set_is_eraser(self, should_erase: bool) -> None:
        """Sets whether the active brush should work as an eraser."""
        self._eraser = should_erase

    def _set_z_value(self, z_value: int) -> None:
        """Updates the level where content will be shown in a GraphicsScene."""
        if self._z_value != z_value:
            self._z_value = z_value

    def _update_canvas_transform(self, layer: ImageLayer, transform: QTransform) -> None:
        """Updates the canvas transformation within the graphics scene."""
        raise NotImplementedError('Implement _update_canvas_transform to adjust canvas transformation in the scene.')

    def _update_scene_content_bounds(self, new_bounds: QRect) -> None:
        """Resize and reposition the internal graphics representation."""
        raise NotImplementedError('Implement _update_scene_content_size to adjust the canvas size.')

    def _draw(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
              y_tilt: Optional[float]) -> None:
        """Use active settings to draw to the canvas with the given inputs."""
        raise NotImplementedError('implement _draw to update the canvas image.')

    def _layer_content_change_slot(self, layer: Optional[ImageLayer]) -> None:
        """Refreshes the layer content within the canvas, or clears it if the layer is hidden."""
        raise NotImplementedError('implement _load_layer_content to copy layer content to the canvas.')

    def _layer_composition_mode_change_slot(self, layer: ImageLayer, mode: CompositeMode) -> None:
        raise NotImplementedError('Implement _layer_composition_mode_change_slot to change the canvas rendering mode.')

    def _layer_alpha_lock_change_slot(self, layer: ImageLayer, locked: bool):
        raise NotImplementedError()

    # noinspection PyUnusedLocal
    def _layer_size_change_slot(self, layer: ImageLayer, size: QSize) -> None:
        assert layer == self._layer
        self._update_scene_content_bounds(layer.bounds)

    def _layer_transform_change_slot(self, layer: ImageLayer, _):
        self._update_canvas_transform(layer, layer.transform)

    # noinspection PyUnusedLocal
    def _layer_bounds_change_slot(self, layer: ImageLayer, *args) -> None:
        assert layer == self._layer
        self._update_scene_content_bounds(layer.bounds)

    def _layer_z_value_change_slot(self, layer: ImageLayer, z_value: int) -> None:
        assert layer == self._layer
        self.z_value = z_value

    def _layer_opacity_change_slot(self, _, opacity: float) -> None:
        for item in self.scene_items():
            item.setOpacity(opacity)
            item.update()

    def _copy_changes_to_layer(self, layer: ImageLayer):
        """Copies content back to the connected layer."""
        raise NotImplementedError('implement _copy_changes_to_layer to write the canvas content back to the layer.')
