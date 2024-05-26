"""A Python wrapper for libmypaint image surface data."""
import math
from typing import Any, Optional
from ctypes import sizeof, c_void_p, POINTER, pointer, byref, c_float, c_double, c_int
from PyQt5.QtCore import Qt, QObject, QPoint, QSize, pyqtSignal
from PyQt5.QtGui import QImage, QColor
from src.image.mypaint.mp_brush import MPBrush
from src.image.mypaint.mp_tile import MPTile
from src.image.mypaint.libmypaint import libmypaint, MyPaintTiledSurface, MyPaintTileRequestStartFunction, \
    MyPaintTileRequestEndFunction, MyPaintSurfaceDestroyFunction, \
    MyPaintTileRequest, TilePixelBuffer, TILE_DIM, \
    RectangleBuffer, MyPaintRectangles, RECTANGLE_BUF_SIZE, c_uint16_p


class MPSurface(QObject):
    """A LibMyPaint surface that emits image tiles as QGraphicsItem objects."""
    tile_created = pyqtSignal(MPTile)
    tile_updated = pyqtSignal(MPTile)
    surface_cleared = pyqtSignal()

    def __init__(self, size: QSize) -> None:
        """Initialize the surface data."""
        super().__init__()
        if size.width() <= 0 or size.height() <= 0:
            raise ValueError(f'Surface width and height must be positive, got {size}')
        self._surface = MyPaintTiledSurface()
        self._surface.tile_size = sizeof(TilePixelBuffer)
        self._brush = MPBrush()
        self._color = QColor(0, 0, 0)
        self._tiles: dict[str, MPTile] = {}
        self._tile_buffer: Any = None

        self._null_buffer = TilePixelBuffer()
        self._null_tile = MPTile(self._null_buffer)

        self._size = QSize(0, 0)
        self._tiles_width = 0
        self._tiles_height = 0

        self._rectangles = RectangleBuffer()
        self._rectangle_buf = MyPaintRectangles()
        self._roi = pointer(self._rectangle_buf)
        self._rectangle_buf.rectangles = self._rectangles
        self._rectangle_buf.num_rectangles = RECTANGLE_BUF_SIZE
        self._dtime = 0.0

        self._scene = None

        # Initialize surface data, starting with empty functions:
        def empty_update_function(unused_surface: c_void_p, unused_request: POINTER(MyPaintTileRequest)) -> None:
            """No action, to be replaced on tiled_surface_init."""

        def destroy_surface(unused_surface: c_void_p) -> None:
            """No action needed, python will handle the memory management."""

        self._surface.parent.destroy = MyPaintSurfaceDestroyFunction(destroy_surface)
        self._surface.tile_request_start = MyPaintTileRequestStartFunction(empty_update_function)
        self._surface.tile_request_end = MyPaintTileRequestEndFunction(empty_update_function)
        self.reset_surface(size)

        def on_tile_request_start(unused_surface: POINTER(MyPaintTiledSurface),
                                  request: POINTER(MyPaintTileRequest)) -> None:
            """Locate or create the required tile and pass it back to libmypaint when a tile operation starts."""
            tx = request[0].tx
            ty = request[0].ty
            if tx >= self._tiles_width or ty >= self._tiles_height or tx < 0 or ty < 0:
                tile = self._null_tile
            else:
                tile = self.get_tile_from_idx(tx, ty, True)
            request[0].buffer = c_uint16_p(tile.get_bits(False))

        def on_tile_request_end(unused_surface: POINTER(MyPaintTiledSurface),
                                request: POINTER(MyPaintTileRequest)) -> None:
            """Update tile cache and send an update signal when a tile painting operation finishes."""
            tx = request[0].tx
            ty = request[0].ty
            tile = self.get_tile_from_idx(tx, ty)
            if tile is not None:
                tile.update_cache()
            else:
                tile = self._null_tile
            request[0].buffer = c_uint16_p(tile.get_bits(False))
            if tile != self._null_tile:
                self.tile_updated.emit(tile)

        self._on_start = MyPaintTileRequestStartFunction(on_tile_request_start)
        self._on_end = MyPaintTileRequestEndFunction(on_tile_request_end)

        libmypaint.mypaint_tiled_surface_init(byref(self._surface), self._on_start, self._on_end)

    @property
    def brush(self) -> MPBrush:
        """Returns the active MyPaint brush."""
        return self._brush

    def start_stroke(self) -> None:
        """Start a brush stroke."""
        libmypaint.mypaint_brush_reset(self.brush.brush_ptr)
        libmypaint.mypaint_brush_new_stroke(self.brush.brush_ptr)

    def stroke_to(self, x: float, y: float, pressure: float, x_tilt: float, y_tilt: float):
        """Continue a brush stroke, providing tablet inputs."""
        dtime = 0.1
        libmypaint.mypaint_surface_begin_atomic(byref(self._surface))
        libmypaint.mypaint_brush_stroke_to(self.brush.brush_ptr, byref(self._surface),
                                           c_float(x), c_float(y), c_float(pressure), c_float(x_tilt), c_float(y_tilt),
                                           c_double(dtime), c_float(1.0), c_float(0.0), c_float(0.0), c_int(1))
        libmypaint.mypaint_surface_end_atomic(byref(self._surface), self._roi)

    def basic_stroke_to(self, x: float, y: float) -> None:
        """Continue a brush stroke, without tablet inputs."""
        self.stroke_to(x, y, 1.0, 0.0, 0.0)

    def load_image(self, image: QImage) -> None:
        """Loads a QImage into the canvas, clearing existing canvas content."""
        if self._tile_buffer is None or self.width <= 0 or self.height <= 0:
            raise RuntimeError(f'Cannot load image, surface is in an invalid state (w={self.width},h={self.height},'
                               f'buf={self._tiles}')
        image = image.scaled(self.size)
        if image.format() != QImage.Format_ARGB32_Premultiplied:
            image = image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        self.clear()

        for y in range(self._tiles_height):
            for x in range(self._tiles_width):
                # Avoid initializing tiles if unnecessary: Try copying image data directly into the pixel buffer,
                # only create/fetch the tile if that operation wasn't cancelled due to empty content or bounds issues.
                buffer_idx = x + y * self._tiles_width
                pixel_buffer = self._tile_buffer[buffer_idx]
                x_px = x * TILE_DIM
                y_px = y * TILE_DIM
                if MPTile.copy_image_into_pixel_buffer(pixel_buffer, image, x_px, y_px, True):
                    tile = self.get_tile_from_idx(x, y, False)
                    tile.update_cache()
                    self.tile_updated.emit(tile)

    def clear(self) -> None:
        """Clears all tile data, and removes tiles from the graphics scene."""
        for tile in self._tiles.values():
            tile.clear()
            scene = tile.scene()
            if scene is not None:
                scene.removeItem(tile)
        self._tiles = {}
        self.surface_cleared.emit()

    def get_tile_from_idx(self, x: int, y: int, clear_buffer_if_new: bool = True) -> MPTile:
        """Returns the tile at the given tile coordinates."""
        if x < 0 or x >= self._tiles_width or y < 0 or y >= self._tiles_height:
            return self._null_tile
        point = f'{x},{y}'
        if point in self._tiles:
            tile = self._tiles[point]
        else:
            buffer_idx = x + y * self._tiles_width
            pixel_buffer = self._tile_buffer[buffer_idx]
            tile = MPTile(pixel_buffer, clear_buffer_if_new)
            self._tiles[point] = tile
            tile.setPos(QPoint(x * TILE_DIM, y * TILE_DIM))
        if tile.scene() is None:
            self.tile_created.emit(tile)
        return tile

    @property
    def tiles_width(self) -> int:
        """Returns the surface width in number of tiles."""
        return self._tiles_width

    @property
    def tiles_height(self) -> int:
        """Returns the surface height in number of tiles."""
        return self._tiles_height

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

    def reset_surface(self, size: QSize) -> None:
        """Clears surface data and recreates it with a given size."""
        width = size.width()
        height = size.height()
        assert width > 0 and height > 0, f'Surface size must be positive, got {width}x{height}'
        self.clear()
        self._size = size
        self._tiles_width = math.ceil(width / TILE_DIM)
        self._tiles_height = math.ceil(height / TILE_DIM)
        num_tiles = self._tiles_width * self._tiles_height
        tile_buffer_type = TilePixelBuffer * num_tiles
        self._tile_buffer = tile_buffer_type()
        self._null_tile.clear()

    def render_image(self, destination_image: Optional[QImage] = None) -> QImage:
        """Combines all tiles into a single QImage."""
        if destination_image is not None:
            assert destination_image.size() == self.size, f'image size {destination_image.size()} doesn\'t match ' \
                                                          f'surface size {self.size}.'
        else:
            destination_image = QImage(self.size, QImage.Format_ARGB32_Premultiplied)
            destination_image.fill(Qt.transparent)
        for point_str, tile in self._tiles.items():
            x, y = point_str.split(',')
            tile.copy_tile_into_image(destination_image, int(x) * TILE_DIM, int(y) * TILE_DIM, True)
        return destination_image
