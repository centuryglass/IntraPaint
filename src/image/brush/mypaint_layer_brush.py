"""
Performs drawing operations on an image layer using the MyPaint brush engine.
"""
import math
from typing import Optional

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage

from src.image.brush.layer_brush import LayerBrush
from src.image.layers.image_layer import ImageLayer
from src.image.mypaint.mypaint_brush import MyPaintBrush
from src.image.mypaint.mypaint_layer_surface import MyPaintLayerSurface
from src.image.mypaint.mypaint_scene_tile import MyPaintSceneTile


class MyPaintLayerBrush(LayerBrush):
    """Connects a MyPaint surface with an image layer."""

    def __init__(self, layer: Optional[ImageLayer] = None) -> None:
        """Initialize a MyPaint surface, and connect to the image layer."""
        super().__init__(layer)
        self._mp_surface = MyPaintLayerSurface(None)
        self._last_stroke_bounds = QRect()
        self._last_stroke_tiles: set[MyPaintSceneTile] = set()
        self._last_eraser_value: Optional[float] = None
        super()._set_brush_color(self._mp_surface.brush.color)
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
    def brush(self) -> MyPaintBrush:
        """Returns the MyPaint brush that belongs to this brush."""
        return self._mp_surface.brush

    def connect_to_layer(self, new_layer: Optional[ImageLayer]):
        """Disconnects from the current layer, and connects to a new one."""
        super().connect_to_layer(new_layer)
        self._mp_surface.layer = new_layer

    def start_stroke(self) -> None:
        """Signals the start of a brush stroke, to be called once whenever user input starts or resumes."""
        super().start_stroke()
        self._last_stroke_tiles.clear()
        self._last_stroke_bounds = QRect()
        self._mp_surface.start_stroke()

    def end_stroke(self) -> None:
        """Finishes a brush stroke, copying it back to the layer."""
        super().end_stroke()
        self._mp_surface.end_stroke()

    def set_input_mask(self, mask_image: Optional[QImage]) -> None:
        """Sets a mask image, restricting brush changes to areas covered by non-transparent mask areas"""
        super().set_input_mask(mask_image)
        self._mp_surface.input_mask = mask_image

    def _set_brush_size(self, new_size: int) -> None:
        """Update the base brush size."""
        super()._set_brush_size(new_size)
        size_log_radius = math.log(new_size / 2)
        self._mp_surface.brush.set_value(MyPaintBrush.RADIUS_LOGARITHMIC, size_log_radius)

    def _set_brush_color(self, new_color: QColor) -> None:
        """Updates the brush color."""
        super()._set_brush_color(new_color)
        self._mp_surface.brush.color = new_color

    def _set_is_eraser(self, should_erase: bool) -> None:
        """Sets whether the active brush should work as an eraser."""
        super()._set_is_eraser(should_erase)
        if should_erase:
            if self._last_eraser_value is None:
                self._last_eraser_value = self._mp_surface.brush.get_value(MyPaintBrush.ERASER)
            self._mp_surface.brush.set_value(MyPaintBrush.ERASER, 1.0)
        else:
            self._mp_surface.brush.set_value(MyPaintBrush.ERASER, self._last_eraser_value
                                             if self._last_eraser_value is not None else 0.0)
            self._last_eraser_value = None

    def _draw(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
              y_tilt: Optional[float]) -> None:
        """Use active settings to draw with the brush using the given inputs."""
        if pressure is not None or x_tilt is not None or y_tilt is not None:
            pressure = 1.0 if pressure is None else pressure
            x_tilt = 0.0 if x_tilt is None else x_tilt
            y_tilt = 0.0 if y_tilt is None else y_tilt
            self._mp_surface.stroke_to(x, y, pressure, x_tilt, y_tilt)
        else:
            self._mp_surface.basic_stroke_to(x, y)
