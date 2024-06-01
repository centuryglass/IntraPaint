"""
Draws content to an image layer.
"""
import math
from typing import Optional, List, Set

from PyQt5.QtCore import QRect, Qt, QSize
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QGraphicsScene

from src.image.image_layer import ImageLayer


class LayerCanvas:
    """Connects a MyPaint surface with an image layer."""

    def __init__(self, scene: QGraphicsScene, layer: Optional[ImageLayer] = None,
                 edit_region: Optional[QRect] = None) -> None:
        """Initialize a MyPaint surface, and connect to the image layer."""
        self._layer: Optional[ImageLayer] = None
        if edit_region is not None:
            self._edit_region = edit_region
        elif layer is not None:
            self._edit_region = QRect(0, 0, layer.width, layer.height)
        else:
            self._edit_region = None
        self._eraser = False
        self._color = QColor(0, 0, 0)
        self._brush_size = 1
        self._z_value = 0
        self._scene = scene
        self._drawing = False
        if layer is not None:
            self.connect_to_layer(layer)

    def connect_to_layer(self, new_layer: Optional[ImageLayer]):
        """Disconnects from the current layer, and connects to a new one."""
        if self._layer is not None:
            if self._drawing:
                self.end_stroke()
            self._layer.visibility_changed.disconnect(self._load_layer_content)
            self._layer.content_changed.disconnect(self._load_layer_content)
        self._layer = new_layer
        if new_layer is not None:
            self._layer.visibility_changed.connect(self._load_layer_content)
            self._layer.content_changed.connect(self._load_layer_content)
            if self._edit_region is None:
                self.edit_region = QRect(0, 0, new_layer.width, new_layer.height)
        self._load_layer_content()

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
    def edit_region(self) -> QRect:
        """Returns the bounds within the layer that the canvas is editing."""
        return self._edit_region

    @edit_region.setter
    def edit_region(self, new_region: QRect) -> None:
        """Updates the bounds within the layer that the canvas is editing."""
        self._edit_region = new_region
        if new_region is not None:
            self._update_scene_content_bounds(new_region)
            if self._layer is not None:
                self._load_layer_content()

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
        self._copy_changes_to_layer()

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

    def _update_scene_content_bounds(self, new_bounds: QRect) -> None:
        """Resize and reposition the internal graphics representation."""
        raise NotImplementedError('Implement _update_scene_content_size to adjust the canvas size.')

    def _draw(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
                  y_tilt: Optional[float]) -> None:
        """Use active settings to draw to the canvas with the given inputs."""
        raise NotImplementedError('implement _draw to update the canvas image.')

    def _load_layer_content(self) -> None:
        """Refreshes the layer content within the canvas, or clears it if the layer is hidden."""
        raise NotImplementedError('implement _load_layer_content to copy layer content to the canvas.')

    def _copy_changes_to_layer(self):
        """Copies content back to the connected layer."""
        raise NotImplementedError('implement _copy_changes_to_layer to write the canvas content back to the layer.')

