"""Connects a libmypaint tiled surface to an ImageLayer."""
import logging
import math
from ctypes import sizeof, pointer, byref, c_float, c_double, c_int
from typing import Any, Optional

from PySide6.QtCore import QObject, QSize, QRect, QTimer
from PySide6.QtGui import QColor, QImage

from src.image.layers.image_layer import ImageLayer
from src.image.mypaint.libmypaint import libmypaint, MyPaintTiledSurface, MyPaintTileRequestStartFunction, \
    MyPaintTileRequestEndFunction, MyPaintSurfaceDestroyFunction, \
    TilePixelBuffer, TILE_DIM, \
    RectangleBuffer, MyPaintRectangles, RECTANGLE_BUF_SIZE
from src.image.mypaint.mypaint_brush import MyPaintBrush
from src.image.mypaint.mypaint_layer_tile import MyPaintLayerTile
from src.util.visual.image_utils import numpy_bounds_index, image_data_as_numpy_8bit_readonly

logger = logging.getLogger(__name__)
TILE_UPDATE_TIMER_MS = 100

# Time between input events passed to libmypaint, which drives its speed inputs and dabs_per_second. It is fixed, so
# output doesn't depend on input timing. libmypaint still prints "Time is running backwards!" during some strokes: the
# negative step comes from its own dab interpolation, not from this value.
STROKE_DTIME_SECONDS = 0.1


class MyPaintLayerSurface(QObject):
    """A LibMyPaint surface that connects directly to an ImageLayer."""

    def __init__(self, layer: Optional[ImageLayer]) -> None:
        """Initialize the surface data."""
        super().__init__()
        self._layer: Optional[ImageLayer] = None
        self._surface_data = MyPaintTiledSurface()
        self._surface_data.tile_size = sizeof(TilePixelBuffer)
        self._brush = MyPaintBrush()
        self._color = QColor(0, 0, 0)
        self._tiles: dict[int, MyPaintLayerTile] = {}  # Keyed by tile index, x + y * tiles_width
        self._tile_buffer: Any = None
        self._mask_image: Optional[QImage] = None

        self._pending_changed_tiles: set[MyPaintLayerTile] = set()
        self._writing_tiles = False
        self._stroke_tiles: set[MyPaintLayerTile] = set()
        self._saved_lock_alpha: Optional[float] = None
        self._pending_tile_timer = QTimer()
        self._pending_tile_timer.timeout.connect(self.apply_pending_tile_updates)
        self._pending_tile_timer.setSingleShot(True)
        self._pending_tile_timer.setInterval(TILE_UPDATE_TIMER_MS)

        self._null_buffer = TilePixelBuffer()
        self._null_tile = MyPaintLayerTile(self._null_buffer)

        self._size = QSize()
        self._tiles_width = 0
        self._tiles_height = 0

        # libmypaint expects to be initialized with a rectangle buffer, but we don't really need to do anything with
        # this.
        self._rectangles = RectangleBuffer()
        self._rectangle_buf = MyPaintRectangles()
        self._roi = pointer(self._rectangle_buf)
        self._rectangle_buf.rectangles = self._rectangles
        self._rectangle_buf.num_rectangles = RECTANGLE_BUF_SIZE

        # Initialize surface data, starting with empty functions:
        def empty_update_function(_unused, _unused2) -> None:
            """No action, to be replaced on tiled_surface_init."""

        def destroy_surface(_unused) -> None:
            """No action needed, python will handle the memory management."""

        self._surface_data.parent.destroy = MyPaintSurfaceDestroyFunction(destroy_surface)
        self._surface_data.tile_request_start = MyPaintTileRequestStartFunction(empty_update_function)
        self._surface_data.tile_request_end = MyPaintTileRequestEndFunction(empty_update_function)

        # libmypaint calls these once per tile per dab for brushes that sample color, so they stay minimal.
        def on_tile_request_start(_, request: Any) -> None:
            """Pass libmypaint the requested tile's buffer, creating the tile if needed."""
            tile_request = request.contents
            tx = tile_request.tx
            ty = tile_request.ty
            if 0 <= tx < self._tiles_width and 0 <= ty < self._tiles_height:
                tile = self._tiles.get(tx + ty * self._tiles_width)
                if tile is None:
                    tile = self.get_tile_from_idx(tx, ty)
                tile_request.buffer = tile.buffer_pointer
            else:
                tile_request.buffer = self._null_tile.buffer_pointer

        def on_tile_request_end(_, request: Any) -> None:
            """Mark a tile that libmypaint may have changed, to be written back to the layer."""
            tile_request = request.contents
            if tile_request.readonly:
                return
            tx = tile_request.tx
            ty = tile_request.ty
            if 0 <= tx < self._tiles_width and 0 <= ty < self._tiles_height:
                tile = self._tiles[tx + ty * self._tiles_width]
                self._pending_changed_tiles.add(tile)
                self._stroke_tiles.add(tile)
                if not self._pending_tile_timer.isActive():
                    self._pending_tile_timer.start()

        self._on_start = MyPaintTileRequestStartFunction(on_tile_request_start)
        self._on_end = MyPaintTileRequestEndFunction(on_tile_request_end)

        libmypaint.mypaint_tiled_surface_init(byref(self._surface_data), self._on_start, self._on_end)
        if layer is not None:
            self.layer = layer

    def apply_pending_tile_updates(self) -> None:
        """Write all pending tile updates back to the connected layer."""
        if self._pending_tile_timer.isActive():
            self._pending_tile_timer.stop()
        if len(self._pending_changed_tiles) == 0 or self._layer is None:
            return
        change_bounds = QRect()
        for tile in self._pending_changed_tiles:
            if change_bounds.isNull():
                change_bounds = tile.bounds
            else:
                change_bounds = change_bounds.united(tile.bounds)
        self._writing_tiles = True
        try:
            with self._layer.borrow_image(change_bounds) as layer_image:
                for tile in self._pending_changed_tiles:
                    tile.write_pixels_to_layer_image(layer_image)
        finally:
            self._writing_tiles = False
        self._pending_changed_tiles.clear()

    @property
    def brush(self) -> MyPaintBrush:
        """Returns the active MyPaint brush."""
        return self._brush

    @property
    def layer(self) -> Optional[ImageLayer]:
        """Accesses the layer that's currently connected to the surface (if any)."""
        return self._layer

    @layer.setter
    def layer(self, layer: Optional[ImageLayer]):
        if layer == self._layer:
            return
        self.clear()
        if self._layer is not None:
            self._disconnect_layer_signals()
        self._layer = layer
        if layer is not None:
            self.reset_surface(layer.size)
            self._connect_layer_signals()

    @property
    def tiles_width(self) -> int:
        """Returns the surface width in number of tiles."""
        return self._tiles_width

    @property
    def tiles_height(self) -> int:
        """Returns the surface height in number of tiles."""
        return self._tiles_height

    @property
    def input_mask(self) -> Optional[QImage]:
        """Accesses the optional input mask used to restrict accepted input."""
        return self._mask_image

    @input_mask.setter
    def input_mask(self, new_mask: Optional[QImage]) -> None:
        if new_mask is None and self._mask_image is None:
            return
        if new_mask is not None and self._layer is not None:
            assert new_mask.size() == self._layer.size
        for tile in self._tiles.values():
            if new_mask is None:
                tile.mask = None
            else:
                tile.mask = numpy_bounds_index(image_data_as_numpy_8bit_readonly(new_mask), tile.bounds)
        self._mask_image = new_mask

    @property
    def width(self) -> int:
        """Returns the surface width in pixels."""
        return self._size.width()

    @property
    def height(self) -> int:
        """Returns the surface height in pixels."""
        return self._size.height()

    @property
    def size(self) -> QSize:
        """Returns the surface size in pixels."""
        return self._size

    @size.setter
    def size(self, size: QSize) -> None:
        """Updates the surface size in pixels."""
        self.reset_surface(size)

    def _should_allow_stroke(self) -> bool:
        if self._layer is None:
            logger.warning('attempted to draw with no layer connected.')
            return False
        if self._layer.locked or self._layer.parent_locked:
            logger.warning('attempted to draw to a locked layer.')
            return False
        if not self._layer.visible:
            logger.warning('attempted to draw to a hidden layer.')
            return False
        return True

    def start_stroke(self) -> None:
        """Start a brush stroke."""
        if not self._should_allow_stroke():
            return
        assert self._layer is not None
        if self._layer.alpha_locked and self._saved_lock_alpha is None:
            # libmypaint's lock_alpha keeps the 15-bit buffer's alpha equal to the layer's, so blending brushes
            # can't pick up paint the lock hides.
            self._saved_lock_alpha = self.brush.get_value(MyPaintBrush.LOCK_ALPHA)
            self.brush.set_value(MyPaintBrush.LOCK_ALPHA, 1.0)
        libmypaint.mypaint_brush_reset(self.brush.brush_ptr)
        libmypaint.mypaint_brush_new_stroke(self.brush.brush_ptr)

    def stroke_to(self, x: float, y: float, pressure: float, x_tilt: float, y_tilt: float):
        """Continue a brush stroke, providing tablet inputs."""
        if not self._should_allow_stroke():
            return
        libmypaint.mypaint_surface_begin_atomic(byref(self._surface_data))
        libmypaint.mypaint_brush_stroke_to(self.brush.brush_ptr, byref(self._surface_data),
                                           c_float(x), c_float(y), c_float(pressure), c_float(x_tilt), c_float(y_tilt),
                                           c_double(STROKE_DTIME_SECONDS), c_float(1.0), c_float(0.0), c_float(0.0),
                                           c_int(1))
        libmypaint.mypaint_surface_end_atomic(byref(self._surface_data), self._roi)

    def end_stroke(self) -> None:
        """Copy over changes immediately when a brush stroke ends, then reload the stroke's tiles from the layer.

        Reloading starts the next stroke from the layer's content, discarding paint the input mask hid and the
        precision lost writing to the 8-bit layer.
        """
        if self._should_allow_stroke():
            self.apply_pending_tile_updates()
        for tile in self._stroke_tiles:
            tile.load_pixels_from_layer()
        self._stroke_tiles.clear()
        if self._saved_lock_alpha is not None:
            self.brush.set_value(MyPaintBrush.LOCK_ALPHA, self._saved_lock_alpha)
            self._saved_lock_alpha = None

    def basic_stroke_to(self, x: float, y: float) -> None:
        """Continue a brush stroke, without tablet inputs."""
        if not self._should_allow_stroke():
            return
        self.stroke_to(x, y, 1.0, 0.0, 0.0)

    def clear(self) -> None:
        """Disconnects and discards all tiles."""
        for tile in self._tiles.values():
            tile.set_layer(None)
        self._tiles.clear()
        self._pending_changed_tiles.clear()
        self._stroke_tiles.clear()

    def get_tile_from_idx(self, x: int, y: int, clear_buffer_if_new: bool = True) -> MyPaintLayerTile:
        """Returns the tile at the given tile coordinates."""
        assert self._layer is not None
        if x < 0 or x >= self._tiles_width or y < 0 or y >= self._tiles_height:
            return self._null_tile
        buffer_idx = x + y * self._tiles_width
        tile = self._tiles.get(buffer_idx)
        if tile is None:
            pixel_buffer = self._tile_buffer[buffer_idx]
            tile_bounds = QRect(x * TILE_DIM, y * TILE_DIM, TILE_DIM, TILE_DIM)
            tile = MyPaintLayerTile(pixel_buffer, self._layer, tile_bounds, clear_buffer_if_new)
            if self._mask_image is not None:
                tile.mask = numpy_bounds_index(image_data_as_numpy_8bit_readonly(self._mask_image), tile.bounds)
            self._tiles[buffer_idx] = tile
        return tile

    def reset_surface(self, size: QSize) -> None:
        """Clears surface data and recreates it with a given size."""
        width = size.width()
        height = size.height()
        assert width > 0 and height > 0, f'Surface size must be positive, got {width}x{height}'
        self.clear()
        self._null_tile.clear()
        self._size = size
        self._tiles_width = math.ceil(width / TILE_DIM)
        self._tiles_height = math.ceil(height / TILE_DIM)
        num_tiles = self._tiles_width * self._tiles_height
        tile_buffer_type = TilePixelBuffer * num_tiles
        self._tile_buffer = tile_buffer_type()

    def _connect_layer_signals(self) -> None:
        if self._layer is not None:
            self._layer.size_changed.connect(self._layer_size_change_slot)
            self._layer.content_changed.connect(self._layer_content_change_slot)

    def _disconnect_layer_signals(self) -> None:
        if self._layer is not None:
            self._layer.size_changed.disconnect(self._layer_size_change_slot)
            self._layer.content_changed.disconnect(self._layer_content_change_slot)

    def _layer_size_change_slot(self, layer: ImageLayer, size: QSize) -> None:
        assert layer == self._layer
        self.reset_surface(size)

    def _layer_content_change_slot(self, layer: ImageLayer, change_bounds: QRect) -> None:
        """Reloads tiles that other edits changed. Tiles keep their own writes unrounded: reloading them would round
           the 15-bit buffer to 8 bits, so the stroke would depend on when apply_pending_tile_updates ran."""
        assert layer == self._layer
        if self._writing_tiles:
            return
        for tile in self._tiles.values():
            if tile.bounds.intersects(change_bounds):
                tile.load_pixels_from_layer()
