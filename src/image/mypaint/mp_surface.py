"""A Python wrapper for libmypaint image surface data."""
import math
from ctypes import sizeof, pointer, byref, c_float, c_double, c_int, c_void_p
from time import time
from typing import Any, Optional

from PySide6.QtCore import QObject, QPoint, QSize, QRect, Signal, QPointF
from PySide6.QtGui import QImage, QColor, QTransform

from src.image.mypaint.libmypaint import libmypaint, MyPaintTiledSurface, MyPaintTileRequestStartFunction, \
    MyPaintTileRequestEndFunction, MyPaintSurfaceDestroyFunction, \
    TilePixelBuffer, TILE_DIM, \
    RectangleBuffer, MyPaintRectangles, RECTANGLE_BUF_SIZE, c_uint16_p
from src.image.mypaint.mp_brush import MPBrush
from src.image.mypaint.mp_tile import MPTile
from src.util.image_utils import create_transparent_image


class MPSurface(QObject):
    """A LibMyPaint surface that emits image tiles as QGraphicsItem objects."""
    tile_created = Signal(MPTile)
    tile_updated = Signal(MPTile)
    surface_cleared = Signal()

    def __init__(self, size: QSize) -> None:
        """Initialize the surface data."""
        super().__init__()
        self._surface_data = MyPaintTiledSurface()
        self._surface_data.tile_size = sizeof(TilePixelBuffer)
        self._brush = MPBrush()
        self._color = QColor(0, 0, 0)
        self._tiles: dict[str, MPTile] = {}
        self._tile_buffer: Any = None

        self._null_buffer = TilePixelBuffer()
        self._null_tile = MPTile(self._null_buffer)

        self._size = QSize(0, 0)
        self._scene_position = QPoint(0, 0)
        self._scene_transform = QTransform()
        self._tiles_width = 0
        self._tiles_height = 0

        self._rectangles = RectangleBuffer()
        self._rectangle_buf = MyPaintRectangles()
        self._roi = pointer(self._rectangle_buf)
        self._rectangle_buf.rectangles = self._rectangles
        self._rectangle_buf.num_rectangles = RECTANGLE_BUF_SIZE
        self._dtime_start = time()
        self._z_value: Optional[int] = None

        self._scene = None

        # Initialize surface data, starting with empty functions:
        def empty_update_function(_unused, _unused2) -> None:
            """No action, to be replaced on tiled_surface_init."""

        def destroy_surface(_unused) -> None:
            """No action needed, python will handle the memory management."""

        self._surface_data.parent.destroy = MyPaintSurfaceDestroyFunction(destroy_surface)
        self._surface_data.tile_request_start = MyPaintTileRequestStartFunction(empty_update_function)
        self._surface_data.tile_request_end = MyPaintTileRequestEndFunction(empty_update_function)
        if size is not None and not size.isEmpty():
            self.reset_surface(size)

        def on_tile_request_start(_, request: c_void_p) -> None:
            """Locate or create the required tile and pass it back to libmypaint when a tile operation starts."""
            tx = request[0].tx  # type: ignore
            ty = request[0].ty  # type: ignore
            if tx >= self._tiles_width or ty >= self._tiles_height or tx < 0 or ty < 0:
                tile = self._null_tile
            else:
                tile = self.get_tile_from_idx(tx, ty, True)
            request[0].buffer = c_uint16_p(tile.get_bits(False))  # type: ignore

        def on_tile_request_end(_, request: c_void_p) -> None:
            """Update tile cache and send an update signal when a tile painting operation finishes."""
            tx = request[0].tx  # type: ignore
            ty = request[0].ty  # type: ignore
            tile = self.get_tile_from_idx(tx, ty)
            if tile is not None:
                tile.update_cache()
            else:
                tile = self._null_tile
            request[0].buffer = c_uint16_p(tile.get_bits(False))  # type: ignore
            if tile != self._null_tile:
                self.tile_updated.emit(tile)

        self._on_start = MyPaintTileRequestStartFunction(on_tile_request_start)
        self._on_end = MyPaintTileRequestEndFunction(on_tile_request_end)

        libmypaint.mypaint_tiled_surface_init(byref(self._surface_data), self._on_start, self._on_end)

    def set_z_values(self, z_value: int) -> None:
        """Applies a new z-value to all tiles that are currently in scenes."""
        self._z_value = z_value
        for tile in self._tiles.values():
            if tile.scene() is not None and tile.zValue() != z_value:
                tile.setZValue(z_value)
                tile.update()

    @property
    def brush(self) -> MPBrush:
        """Returns the active MyPaint brush."""
        return self._brush

    @property
    def scene_transform(self) -> QTransform:
        """Returns the surface's transformation within the scene."""
        return QTransform(self._scene_transform)

    @scene_transform.setter
    def scene_transform(self, transform: QTransform) -> None:
        """Updates the surface's position in the scene, moving all active tiles."""
        self._scene_transform = transform
        for tile in self._tiles.values():
            if tile.is_valid and tile.scene() is not None:
                tile.setTransform(QTransform.fromTranslate(tile.x(), tile.y())
                                  * self._scene_transform
                                  * QTransform.fromTranslate(-tile.x(), -tile.y()))
                tile.update()

    def _assert_valid_surface(self) -> None:
        """Throws a runtime error if called when surface size is null."""
        if self._size.isNull():
            raise RuntimeError('Surface was not initialized with a non-null size.')

    def start_stroke(self) -> None:
        """Start a brush stroke."""
        self._assert_valid_surface()
        libmypaint.mypaint_brush_reset(self.brush.brush_ptr)
        libmypaint.mypaint_brush_new_stroke(self.brush.brush_ptr)
        self._dtime_start = time()

    def stroke_to(self, x: float, y: float, pressure: float, x_tilt: float, y_tilt: float):
        """Continue a brush stroke, providing tablet inputs."""
        self._assert_valid_surface()
        dtime = 0.1  # time() - self._dtime_start
        libmypaint.mypaint_surface_begin_atomic(byref(self._surface_data))
        libmypaint.mypaint_brush_stroke_to(self.brush.brush_ptr, byref(self._surface_data),
                                           c_float(x), c_float(y), c_float(pressure), c_float(x_tilt), c_float(y_tilt),
                                           c_double(dtime), c_float(1.0), c_float(0.0), c_float(0.0), c_int(1))
        libmypaint.mypaint_surface_end_atomic(byref(self._surface_data), self._roi)

    def basic_stroke_to(self, x: float, y: float) -> None:
        """Continue a brush stroke, without tablet inputs."""
        self._assert_valid_surface()
        self.stroke_to(x, y, 1.0, 0.0, 0.0)

    def load_image(self, image: QImage) -> None:
        """Loads a QImage into the canvas, clearing existing canvas content."""
        self._assert_valid_surface()
        if self._tile_buffer is None or self.width <= 0 or self.height <= 0:
            raise RuntimeError(f'Cannot load image, surface is in an invalid state (w={self.width},h={self.height},'
                               f'buf={self._tiles}')
        image = image.scaled(self.size)
        if image.format() != QImage.Format.Format_ARGB32_Premultiplied:
            image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
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
                    tile.set_cache(image.copy(QRect(x_px, y_px, tile.size.width(), tile.size.height())))
                    self.tile_updated.emit(tile)

    def clear(self) -> None:
        """Clears all tile data, and removes tiles from the graphics scene."""
        if self._size.isNull():
            return
        for tile in self._tiles.values():
            tile.clear()
            tile.invalidate()
        self._tiles = {}
        self.surface_cleared.emit()

    def get_tile_from_idx(self, x: int, y: int, clear_buffer_if_new: bool = True) -> MPTile:
        """Returns the tile at the given tile coordinates."""
        self._assert_valid_surface()
        if x < 0 or x >= self._tiles_width or y < 0 or y >= self._tiles_height:
            return self._null_tile
        point = f'{x},{y}'
        if point in self._tiles:
            tile = self._tiles[point]
        else:
            buffer_idx = x + y * self._tiles_width
            pixel_buffer = self._tile_buffer[buffer_idx]

            def tile_dim(img_dim, idx, max_idx):
                """Get a tile's width or height."""
                if idx != max_idx or img_dim % TILE_DIM == 0:
                    return TILE_DIM
                return img_dim % TILE_DIM
            width = tile_dim(self.width, x, self._tiles_width - 1)
            height = tile_dim(self.height, y, self._tiles_height - 1)
            tile = MPTile(pixel_buffer, clear_buffer_if_new, QSize(width, height))
            self._tiles[point] = tile
            tile.setPos(QPointF(self._scene_position.x() + x * TILE_DIM, self._scene_position.y() + y * TILE_DIM))
            tile.setTransform(QTransform.fromTranslate(tile.x(), tile.y())
                              * self._scene_transform
                              * QTransform.fromTranslate(-tile.x(), -tile.y()))
            if self._z_value is not None:
                tile.setZValue(self._z_value)
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
        if not self._size.isNull():
            self.clear()
            self._null_tile.clear()
        self._size = size
        self._tiles_width = math.ceil(width / TILE_DIM)
        self._tiles_height = math.ceil(height / TILE_DIM)
        num_tiles = self._tiles_width * self._tiles_height
        tile_buffer_type = TilePixelBuffer * num_tiles
        self._tile_buffer = tile_buffer_type()

    def render_image(self, destination_image: Optional[QImage] = None, source: Optional[QRect] = None,
                     destination: Optional[QRect] = None) -> QImage:
        """Combines all tiles into a single QImage. This operation does no scaling; any surface data that does not 
        overlap with the image bounds will not be copied.
        
        Parameters
        ----------
        destination_image: QImage, optional
            If not None, image data will be copied into this image instead of into a new QImage.
        source: QRect, optional
            Area within the surface to copy into the image. If not provided, the entire surface bounds will be used.
        destination: QRect, optional
            Area within the image where the data will be copied. If not defined, the entire image bounds will be
            used.

        Returns
        -------
        The image where the data was copied.
        """
        self._assert_valid_surface()
        skip_transparent_tiles = destination_image is None
        if destination_image is None:
            destination_image = create_transparent_image(self.size)
        if source is None:
            source = QRect(0, 0, self._size.width(), self._size.height())
        if destination is None:
            destination = QRect(0, 0, destination_image.width(), destination_image.height())
        for point_str, tile in self._tiles.items():
            x_tile, y_tile = point_str.split(',')
            x_px = int(x_tile) * TILE_DIM
            y_px = int(y_tile) * TILE_DIM
            tile_source = QRect(x_px, y_px, tile.size.width(), tile.size.height()).intersected(source)
            if tile_source.isEmpty():
                continue
            img_x = destination.x() + tile_source.x() - source.x()
            img_y = destination.y() + tile_source.y() - source.y()
            width = min(tile_source.width(), destination.x() + destination.width(), destination_image.width())
            height = min(tile_source.height(), destination.y() + destination.height(), destination_image.height())
            target = QRect(img_x, img_y, width, height)
            if target.intersected(tile_source).isEmpty():
                continue
            tile_source.translate(-x_px, -y_px)
            tile.copy_tile_into_image(destination_image, tile_source, target, skip_transparent_tiles)
        return destination_image
