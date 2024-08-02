"""
Draws content to an image layer.
"""
import math
from typing import Optional, Set, List, cast

from PyQt6.QtCore import QRect, QSize, QPoint, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QTransform, QImage
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsItem

from src.image.canvas.layer_canvas import LayerCanvas
from src.image.layers.image_layer import ImageLayer
from src.image.layers.transform_layer import TransformLayer
from src.image.mypaint.mp_brush import MPBrush
from src.image.mypaint.mp_surface import MPSurface
from src.image.mypaint.mp_tile import MPTile


class MyPaintLayerCanvas(LayerCanvas):
    """Connects a MyPaint surface with an image layer."""

    def __init__(self, scene: QGraphicsScene, layer: Optional[ImageLayer] = None,
                 edit_region: Optional[QRect] = None) -> None:
        """Initialize a MyPaint surface, and connect to the image layer."""
        super().__init__(scene, layer, edit_region)
        self._mask: Optional[QImage] = None
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
        self._last_stroke_bounds = QRect()
        self._mp_surface.start_stroke()

    def scene_items(self) -> List[QGraphicsItem]:
        """Returns all graphics items present in the scene that belong to the canvas."""
        return [item for item in self.scene.items() if isinstance(item, MPTile)]

    def _get_tile_mask(self, tile: MPTile) -> Optional[QImage]:
        if self._mask is None or self._layer is None:
            return None
        tile_bounds = QRect(int(tile.x()) - self._layer.bounds.x(), int(tile.y()) - self._layer.bounds.y(),
                            tile.size.width(), tile.size.height())
        return self._mask.copy(tile_bounds)

    def set_input_mask(self, mask_image: Optional[QImage]) -> None:
        """Sets a mask image, restricting canvas changes to areas covered by non-transparent mask areas"""
        self._mask = mask_image
        for tile in self.scene_items():
            assert isinstance(tile, MPTile)
            tile.mask = self._get_tile_mask(tile)

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

    def _update_canvas_transform(self, layer: ImageLayer, transform: QTransform) -> None:
        """Updates the canvas transformation within the graphics scene."""
        self._mp_surface.scene_transform = layer.transform

    def _handle_tile_updates(self, tile: MPTile) -> None:
        """Make sure added/updated MyPaint tiles are in the correct scene with the right z-value, and track bounds."""
        if self._scene is None:
            return
        if tile.scene() is None:
            self._scene.addItem(tile)
            tile.mask = self._get_tile_mask(tile)
        tile.setZValue(self._z_value)
        if self._layer is not None:
            tile.setOpacity(self._layer.opacity)
            tile.composition_mode = self._layer.composition_mode
            tile.alpha_lock = self._layer.alpha_locked
        tile.update()
        # If currently drawing, use tiles to track the stroke bounds:
        if self._drawing:
            assert self._layer is not None
            self._last_stroke_tiles.add(tile)
            tile_bounds = QRect(QPoint(), tile.size)
            tile_bounds = tile.mapRectToScene(QRectF(tile_bounds)).toAlignedRect()
            tile_bounds = self._layer.map_rect_from_image(tile_bounds)
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
                self._layer_content_change_slot(self._layer)

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

    def _layer_content_change_slot(self, layer: Optional[ImageLayer]) -> None:
        """Refreshes the layer content within the canvas, or clears it if the layer is hidden."""
        assert layer == self._layer
        if layer is None or not layer.visible or self._edit_region is None or self._edit_region.isEmpty():
            self._mp_surface.clear()
        else:
            image = layer.cropped_image_content(self._edit_region)
            self._mp_surface.load_image(image)

    def _layer_composition_mode_change_slot(self, layer: ImageLayer, mode: QPainter.CompositionMode) -> None:
        assert layer == self._layer
        for tile in self.scene_items():
            tile = cast(MPTile, tile)
            tile.composition_mode = mode

    def _layer_alpha_lock_change_slot(self, layer: ImageLayer, locked: bool):
        assert layer == self._layer
        for tile in self.scene_items():
            tile = cast(MPTile, tile)
            tile.alpha_lock = locked

    def _copy_changes_to_layer(self, layer: ImageLayer):
        """Copies content back to the connected layer."""
        if self._layer is not None and self._layer.visible and self._edit_region is not None \
                and not self._edit_region.isEmpty() and not self._last_stroke_bounds.isEmpty():
            self._last_stroke_bounds = self._last_stroke_bounds.intersected(self._layer.bounds)
            tile_change_image = self._layer.cropped_image_content(self._last_stroke_bounds)
            for tile in self._last_stroke_tiles:
                if not tile.is_valid:
                    continue
                tile_pt = tile.mapToScene(QPointF())
                if isinstance(self._layer, TransformLayer):
                    tile_pt = QPointF(self._layer.map_from_image(tile_pt))
                tile_pt -= QPointF(self._last_stroke_bounds.topLeft())
                tile.copy_tile_into_image(tile_change_image,
                                          destination=QRect(tile_pt.toPoint(), tile.size),
                                          skip_if_transparent=False,
                                          color_correction=True)
            self.disconnect_layer_signals()
            self._layer.insert_image_content(tile_change_image, self._last_stroke_bounds, register_to_undo_history=True)
            self.connect_layer_signals()
