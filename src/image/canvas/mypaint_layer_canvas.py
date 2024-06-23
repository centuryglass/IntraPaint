"""
Draws content to an image layer.
"""
import math
from typing import Optional, Set

from PyQt5.QtCore import QRect, QPoint, QSize
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QGraphicsScene

from src.image.canvas.layer_canvas import LayerCanvas
from src.image.image_layer import ImageLayer
from src.image.mypaint.mp_brush import MPBrush
from src.image.mypaint.mp_surface import MPSurface
from src.image.mypaint.mp_tile import MPTile
from src.undo_stack import commit_action


class MyPaintLayerCanvas(LayerCanvas):
    """Connects a MyPaint surface with an image layer."""

    def __init__(self, scene: QGraphicsScene, layer: Optional[ImageLayer] = None,
                 edit_region: Optional[QRect] = None) -> None:
        """Initialize a MyPaint surface, and connect to the image layer."""
        super().__init__(scene, layer, edit_region)
        self._mp_surface = MPSurface(QSize() if self.edit_region is None else self.edit_region.size())
        self._last_stroke_bounds = QRect()
        self._last_stroke_tiles: Set[MPTile] = set()
        self._last_eraser_value: Optional[float] = None
        super()._set_brush_color(self._mp_surface.brush.color)
        self._mp_surface.tile_created.connect(self._handle_tile_updates)
        self._mp_surface.tile_updated.connect(self._handle_tile_updates)
        if layer is not None:
            self.connect_to_layer(layer)

    @property
    def brush_path(self) -> Optional[str]:
        """Gets the name of the active MyPaint brush, if any."""
        return self._mp_surface.brush.path

    @brush_path.setter
    def brush_path(self, new_path: str) -> None:
        """Loads a new MyPaint Brush."""
        self._mp_surface.brush.load_file(new_path, True)
        self._last_eraser_value = None

    @property
    def brush(self) -> MPBrush:
        """Returns the MyPaint brush that belongs to this canvas."""
        return self._mp_surface.brush

    def start_stroke(self) -> None:
        """Signals the start of a brush stroke, to be called once whenever user input starts or resumes."""
        super().start_stroke()
        self._last_stroke_tiles.clear()
        self._mp_surface.start_stroke()

    @property
    def _bounds_x(self):
        """Returns last stroke bounding box x-coordinate."""
        return self._last_stroke_bounds.x()

    @property
    def _bounds_y(self):
        """Returns last stroke bounding box y-coordinate."""
        return self._last_stroke_bounds.y()

    @property
    def _bounds_w(self):
        """Returns last stroke bounding box width."""
        return self._last_stroke_bounds.width()

    @property
    def _bounds_h(self):
        """Returns last stroke bounding box height."""
        return self._last_stroke_bounds.height()

    def _update_canvas_position(self, _, new_position: QPoint) -> None:
        """Updates the canvas position within the graphics scene."""
        self._mp_surface.scene_position = new_position

    def _handle_tile_updates(self, tile: MPTile) -> None:
        """Make sure added/updated MyPaint tiles are in the correct scene with the right z-value, and track bounds."""
        if self._scene is None:
            return
        if tile.scene() is None:
            self._scene.addItem(tile)
        tile.setZValue(self._z_value)
        tile.update()
        # If currently drawing, use tiles to track the stroke bounds:
        if self._drawing:
            self._last_stroke_tiles.add(tile)
            tile_bounds = QRect(int(tile.x() - self._mp_surface.scene_position.x()),
                                int(tile.y() - self._mp_surface.scene_position.y()),
                                tile.size.width(), tile.size.height())
            if self._last_stroke_bounds.isEmpty():
                self._last_stroke_bounds = tile_bounds
            else:
                self._last_stroke_bounds = self._last_stroke_bounds.united(tile_bounds)

    def _set_brush_size(self, new_size: int) -> None:
        """Update the base brush size."""
        super()._set_brush_size(new_size)
        size_log_radius = math.log(new_size / 2)
        self._mp_surface.brush.set_value(MPBrush.RADIUS_LOGARITHMIC, size_log_radius)

    def _set_brush_color(self, new_color: QColor) -> None:
        """Updates the brush color."""
        super()._set_brush_color(new_color)
        self._mp_surface.brush.color = new_color

    def _set_is_eraser(self, should_erase: bool) -> None:
        """Sets whether the active brush should work as an eraser."""
        super()._set_is_eraser(should_erase)
        if should_erase:
            if self._last_eraser_value is None:
                self._last_eraser_value = self._mp_surface.brush.get_value(MPBrush.ERASER)
            self._mp_surface.brush.set_value(MPBrush.ERASER, 1.0)
        else:
            self._mp_surface.brush.set_value(MPBrush.ERASER, self._last_eraser_value
                                             if self._last_eraser_value is not None else 0.0)
            self._last_eraser_value = None

    def _set_z_value(self, z_value: int) -> None:
        """Updates the level where content will be shown in a GraphicsScene."""
        super()._set_z_value(z_value)
        self._mp_surface.set_z_values(z_value)

    def _update_scene_content_bounds(self, new_bounds: QRect) -> None:
        """Resize the internal graphics representation."""
        if self._mp_surface.size != new_bounds.size():
            self._mp_surface.reset_surface(new_bounds.size())
            if self._layer is not None:
                self._load_layer_content(self._layer)

    def _draw(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
              y_tilt: Optional[float]) -> None:
        """Use active settings to draw to the canvas with the given inputs."""
        if pressure is not None or x_tilt is not None or y_tilt is not None:
            pressure = 0.0 if pressure is None else pressure
            x_tilt = 0.0 if x_tilt is None else x_tilt
            y_tilt = 0.0 if y_tilt is None else y_tilt
            self._mp_surface.stroke_to(x, y, pressure, x_tilt, y_tilt)
        else:
            self._mp_surface.basic_stroke_to(x, y)

    def _load_layer_content(self, layer: Optional[ImageLayer]) -> None:
        """Refreshes the layer content within the canvas, or clears it if the layer is hidden."""
        assert layer == self._layer
        if layer is None or not layer.visible or self._edit_region is None or self._edit_region.isEmpty():
            self._mp_surface.clear()
        else:
            image = layer.cropped_image_content(self._edit_region)
            self._mp_surface.load_image(image)

    def _copy_changes_to_layer(self, use_stroke_bounds: bool = False):
        """Copies content back to the connected layer."""
        if self._layer is not None and self._layer.visible and self._edit_region is not None \
                and not self._edit_region.isEmpty() and not self._last_stroke_bounds.isEmpty():

            tile_change_image = self._layer.cropped_image_content(self._last_stroke_bounds)
            reverse_image = tile_change_image.copy()
            change_x = self._last_stroke_bounds.x()
            change_y = self._last_stroke_bounds.y()
            for tile in self._last_stroke_tiles:
                if not tile.is_valid:
                    continue
                destination_x = int(tile.x() - self._mp_surface.scene_position.x() - change_x)
                destination_y = int(tile.y() - self._mp_surface.scene_position.y() - change_y)
                tile.copy_tile_into_image(tile_change_image,
                                          destination=QRect(destination_x, destination_y,
                                                            tile.size.width(), tile.size.height()),
                                          skip_if_transparent=False,
                                          color_correction=True)
            reverse_image = self._layer.cropped_image_content(self._last_stroke_bounds)
            layer = self._layer

            def apply():
                """Copy the combined tile changes into the image."""
                with layer.borrow_image() as layer_image:
                    layer_painter = QPainter(layer_image)
                    layer_painter.setCompositionMode(QPainter.CompositionMode_Source)
                    layer_painter.drawImage(change_x, change_y, tile_change_image)

            def reverse():
                """To undo, copy in the cached previous image data."""
                with layer.borrow_image() as layer_image:
                    layer_painter = QPainter(layer_image)
                    layer_painter.setCompositionMode(QPainter.CompositionMode_Source)
                    layer_painter.drawImage(change_x, change_y, reverse_image)

            self._layer.visibility_changed.disconnect(self._load_layer_content)
            self._layer.content_changed.disconnect(self._load_layer_content)
            commit_action(apply, reverse)
            self._layer.visibility_changed.connect(self._load_layer_content)
            self._layer.content_changed.connect(self._load_layer_content)
