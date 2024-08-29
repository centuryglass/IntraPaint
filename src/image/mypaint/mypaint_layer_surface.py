"""Connects a libmypaint image surface to  """
import logging
import math
from ctypes import sizeof, pointer, byref, c_float, c_double, c_int, c_void_p
from time import time
from typing import Any, Optional, Set

from PySide6.QtCore import QObject, QSize, QRect, QTimer
from PySide6.QtGui import QColor, QImage

from src.image.layers.image_layer import ImageLayer
from src.image.mypaint.libmypaint import libmypaint, MyPaintTiledSurface, MyPaintTileRequestStartFunction, \
    MyPaintTileRequestEndFunction, MyPaintSurfaceDestroyFunction, \
    TilePixelBuffer, TILE_DIM, \
    RectangleBuffer, MyPaintRectangles, RECTANGLE_BUF_SIZE, c_uint16_p
from src.image.mypaint.mypaint_brush import MyPaintBrush
from src.image.mypaint.mypaint_layer_tile import MyPaintLayerTile
from src.util.image_utils import numpy_bounds_index, image_data_as_numpy_8bit_readonly

logger = logging.getLogger(__name__)
TILE_UPDATE_TIMER_MS = 100


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
        self._tiles: dict[str, MyPaintLayerTile] = {}
        self._tile_buffer: Any = None
        self._mask_image: Optional[QImage] = None

        self._pending_changed_tiles: Set[MyPaintLayerTile] = set()
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
        self._dtime_start = time()

        # Initialize surface data, starting with empty functions:
        def empty_update_function(_unused, _unused2) -> None:
            """No action, to be replaced on tiled_surface_init."""

        def destroy_surface(_unused) -> None:
            """No action needed, python will handle the memory management."""

        self._surface_data.parent.destroy = MyPaintSurfaceDestroyFunction(destroy_surface)
        self._surface_data.tile_request_start = MyPaintTileRequestStartFunction(empty_update_function)
        self._surface_data.tile_request_end = MyPaintTileRequestEndFunction(empty_update_function)

        def on_tile_request_start(_, request: c_void_p) -> None:
            """Locate or create the required tile and pass it back to libmypaint when a tile operation starts."""
            tx = request[0].tx  # type: ignore
            ty = request[0].ty  # type: ignore
            if tx >= self._tiles_width or ty >= self._tiles_height or tx < 0 or ty < 0:
                tile = self._null_tile
            else:
                tile = self.get_tile_from_idx(tx, ty, True)
            request[0].buffer = c_uint16_p(tile.pixel_buffer)  # type: ignore

        def on_tile_request_end(_, request: c_void_p) -> None:
            """Write tile data back to the layer when a tile painting operation finishes."""
            tx = request[0].tx  # type: ignore
            ty = request[0].ty  # type: ignore
            tile = self.get_tile_from_idx(tx, ty)
            if tile is not None:
                self._pending_changed_tiles.add(tile)
                if not self._pending_tile_timer.isActive():
                    self._pending_tile_timer.start()
            else:
                tile = self._null_tile
            request[0].buffer = c_uint16_p(tile.pixel_buffer)  # type: ignore

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
        if len(self._pending_changed_tiles) == 1:
            self._pending_changed_tiles.pop().write_pixels_to_layer()
            return
        change_bounds = QRect()
        for tile in self._pending_changed_tiles:
            if change_bounds.isNull():
                change_bounds = tile.bounds
            else:
                change_bounds = change_bounds.united(tile.bounds)
        self._disconnect_layer_signals()
        with self._layer.borrow_image(change_bounds) as layer_image:
            for tile in self._pending_changed_tiles:
                tile.write_pixels_to_layer_image(layer_image)
        self._connect_layer_signals()
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
        self._layer = layer
        if layer is not None:
            self.reset_surface(layer.size)

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
        if self._layer.locked:
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
        libmypaint.mypaint_brush_reset(self.brush.brush_ptr)
        libmypaint.mypaint_brush_new_stroke(self.brush.brush_ptr)
        self._dtime_start = time()

    def stroke_to(self, x: float, y: float, pressure: float, x_tilt: float, y_tilt: float):
        """Continue a brush stroke, providing tablet inputs."""
        if not self._should_allow_stroke():
            return
        dtime = 0.1  # time() - self._dtime_start
        libmypaint.mypaint_surface_begin_atomic(byref(self._surface_data))
        libmypaint.mypaint_brush_stroke_to(self.brush.brush_ptr, byref(self._surface_data),
                                           c_float(x), c_float(y), c_float(pressure), c_float(x_tilt), c_float(y_tilt),
                                           c_double(dtime), c_float(1.0), c_float(0.0), c_float(0.0), c_int(1))
        libmypaint.mypaint_surface_end_atomic(byref(self._surface_data), self._roi)

    def end_stroke(self) -> None:
        """Copy over changes immediately when a brush stroke ends."""
        if self._should_allow_stroke():
            self.apply_pending_tile_updates()

    def basic_stroke_to(self, x: float, y: float) -> None:
        """Continue a brush stroke, without tablet inputs."""
        if not self._should_allow_stroke():
            return
        self.stroke_to(x, y, 1.0, 0.0, 0.0)

    def clear(self) -> None:
        """Disconnects and discards all tiles."""
        if self._size.isNull():
            return
        for tile in self._tiles.values():
            tile.set_layer(None)
        self._tiles.clear()

    def get_tile_from_idx(self, x: int, y: int, clear_buffer_if_new: bool = True) -> MyPaintLayerTile:
        """Returns the tile at the given tile coordinates."""
        assert self._layer is not None
        if x < 0 or x >= self._tiles_width or y < 0 or y >= self._tiles_height:
            return self._null_tile
        point = f'{x},{y}'
        if point in self._tiles:
            tile = self._tiles[point]
        else:
            buffer_idx = x + y * self._tiles_width
            pixel_buffer = self._tile_buffer[buffer_idx]
            tile_bounds = QRect(x * TILE_DIM, y * TILE_DIM, TILE_DIM, TILE_DIM)
            tile = MyPaintLayerTile(pixel_buffer, self._layer, tile_bounds, clear_buffer_if_new)
            if self._mask_image is not None:
                tile.mask = numpy_bounds_index(image_data_as_numpy_8bit_readonly(self._mask_image), tile.bounds)
            self._tiles[point] = tile
        return tile

    def reset_surface(self, size: QSize) -> None:
        """Clears surface data and recreates it with a given size."""
        width = size.width()
        height = size.height()
        assert width > 0 and height > 0, f'Surface size must be positive, got {width}x{height}'
        if not self._size.isNull():
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

    def _disconnect_layer_signals(self) -> None:
        if self._layer is not None:
            self._layer.size_changed.disconnect(self._layer_size_change_slot)

    def _layer_size_change_slot(self, layer: ImageLayer, size: QSize) -> None:
        assert layer == self._layer
        self.reset_surface(size)

    def _layer_content_change_slot(self, layer: ImageLayer, change_bounds: QRect) -> None:
        assert layer == self._layer
        for tile in self._tiles.values():
            if tile.bounds.intersects(change_bounds):
                tile.load_pixels_from_layer()
