"""
Draws content to an image layer.
"""
import math
from typing import Optional, List, Set

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QGraphicsScene

from src.image.image_layer import ImageLayer
from src.image.mypaint.mp_brush import MPBrush
from src.image.mypaint.mp_surface import MPSurface
from src.image.mypaint.mp_tile import MPTile
from src.undo_stack import commit_action


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
        self._mp_surface = MPSurface(QRect() if self._edit_region is None else self._edit_region.size())
        self._color = QColor(0, 0, 0)
        self._brush_size = 1
        self._z_value = 0
        self._scene = scene
        self._drawing = False
        self._last_stroke_bounds = QRect()
        self._last_stroke_tiles: Set[MPTile] = set()
        self._mp_surface.tile_created.connect(self._handle_tile_updates)
        self._mp_surface.tile_updated.connect(self._handle_tile_updates)

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
    def z_value(self) -> int:
        """Returns the level where content will be shown in a GraphicsScene."""
        return self._z_value

    @z_value.setter
    def z_value(self, z_value: int) -> None:
        """Updates the level where content will be shown in a GraphicsScene."""
        if self._z_value != z_value:
            self._z_value = z_value
            self._mp_surface.set_z_values(z_value)

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
        self._brush_size = size
        size_log_radius = math.log(size / 2)
        self._mp_surface.brush.set_value(MPBrush.RADIUS_LOGARITHMIC, size_log_radius)

    @property
    def brush_path(self) -> Optional[str]:
        """Gets the name of the active MyPaint brush, if any."""
        return self._mp_surface.brush.path

    @brush_path.setter
    def brush_path(self, new_path: str) -> None:
        """Loads a new MyPaint Brush."""
        self._mp_surface.brush.load_file(new_path, True)

    @property
    def brush(self) -> MPBrush:
        """Returns the canvas brush object."""
        return self._mp_surface.brush

    @property
    def edit_region(self) -> QRect:
        """Returns the bounds within the layer that the canvas is editing."""
        return self.edit_region

    @edit_region.setter
    def edit_region(self, new_region: QRect) -> None:
        """Updates the bounds within the layer that the canvas is editing."""
        self._edit_region = new_region
        if self._mp_surface.size != new_region.size():
            self._mp_surface.reset_surface(new_region.size())
        if self._layer is not None:
            self._load_layer_content()

    def start_stroke(self) -> None:
        """Signals the start of a brush stroke, to be called once whenever user input starts or resumes."""
        if self._layer is None or not self._layer.visible:
            return
        if self._drawing:
            self.end_stroke()
        self._last_stroke_tiles.clear()
        self._drawing = True
        self._mp_surface.start_stroke()

    def stroke_to(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
                  y_tilt: Optional[float]) -> None:
        """Continue a brush stroke with optional tablet inputs."""
        if self._layer is None or not self._layer.visible:
            return
        if not self._drawing:
            self.start_stroke()
        if pressure is not None or x_tilt is not None or y_tilt is not None:
            self._mp_surface.stroke_to(x, y, pressure, x_tilt, y_tilt)
        else:
            self._mp_surface.basic_stroke_to(x, y)

    def end_stroke(self) -> None:
        """Finishes a brush stroke, copying it back to the layer."""
        self._drawing = False
        self._copy_changes_to_layer()

    def _load_layer_content(self) -> None:
        """Refreshes the layer content within the canvas, or clears it if the layer is hidden."""
        if self._layer is None or not self._layer.visible or self._edit_region.isEmpty():
            self._mp_surface.clear()
        else:
            image = self._layer.cropped_image_content(self._edit_region)
            self._mp_surface.load_image(image)

    def _copy_changes_to_layer(self, use_stroke_bounds: bool = False):
        """Copies content back to the connected layer."""
        if self._layer is not None and self._layer.visible and self._edit_region is not None \
                and not self._edit_region.isEmpty() and not self._last_stroke_bounds.isEmpty():

            tile_change_image = QImage(self._last_stroke_bounds.size(), QImage.Format_ARGB32_Premultiplied)
            tile_change_image.fill(Qt.GlobalColor.transparent)
            change_x = self._last_stroke_bounds.x()
            change_y = self._last_stroke_bounds.y()
            for tile in self._last_stroke_tiles:
                if not tile.is_valid:
                    continue
                tile.copy_tile_into_image(tile_change_image, destination=QRect(int(tile.x() - change_x),
                                                                               int(tile.y() - change_y),
                                                                               tile.size.width(), tile.size.height()))
            reverse_image = self._layer.cropped_image_content(self._last_stroke_bounds)
            layer = self._layer

            def apply():
                """Copy the combined tile changes into the image."""
                with layer.borrow_image() as layer_image:
                    layer_painter = QPainter(layer_image)
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
            tile_bounds = QRect(int(tile.x()), int(tile.y()), tile.size.width(), tile.size.height())
            if self._last_stroke_bounds.isEmpty():
                self._last_stroke_bounds = tile_bounds
            else:
                self._last_stroke_bounds = self._last_stroke_bounds.united(tile_bounds)
