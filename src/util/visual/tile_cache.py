"""A cache of square image tiles on a fixed grid in image coordinates, rendered on demand and invalidated by area.

Tiles are keyed by grid position, so the area a cached image covers can grow, shrink or move without moving any tile.
The cache knows nothing about what it renders: its owner reports changed areas and passes a render function to each
read. The cache doesn't keep that function, so a bound method of the owner doesn't put the owner in a reference
cycle.
"""
from typing import Callable, Iterator, TypeAlias

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QImage, QPainter, QRegion

# Tile width and height in pixels. Keep this a multiple of libmypaint's TILE_DIM (src/image/mypaint/libmypaint.py),
# so a MyPaint tile never spans two cache tiles.
TILE_SIZE = 256

TileKey: TypeAlias = tuple[int, int]

# Renders the content of an area, in image coordinates, into a transparent image the size of that area:
RenderAreaFn: TypeAlias = Callable[[QImage, QRect], None]


class TileCache:
    """Square tiles covering image coordinates, each rendered when first read and dropped when its area changes.

    A tile's content must not depend on which other tiles are cached or on how many tiles one render call covers, since
    missing tiles are rendered in batches.
    """

    def __init__(self, tile_size: int = TILE_SIZE,
                 image_format: QImage.Format = QImage.Format.Format_ARGB32_Premultiplied) -> None:
        if tile_size < 1:
            raise ValueError(f'Tile size must be positive, got {tile_size}')
        self._tile_size = tile_size
        self._format = image_format
        self._tiles: dict[TileKey, QImage] = {}

    @property
    def tile_size(self) -> int:
        """Returns the width and height of every tile."""
        return self._tile_size

    @property
    def cached_count(self) -> int:
        """Returns the number of tiles currently cached."""
        return len(self._tiles)

    def tile_rect(self, key: TileKey) -> QRect:
        """Returns the area a tile covers, in image coordinates."""
        return QRect(key[0] * self._tile_size, key[1] * self._tile_size, self._tile_size, self._tile_size)

    def tile_keys(self, area: QRect) -> list[TileKey]:
        """Returns the keys of every tile that intersects area, in rows from the top left."""
        if area.isEmpty():
            return []
        size = self._tile_size
        return [(x, y) for y in range(area.top() // size, area.bottom() // size + 1)
                for x in range(area.left() // size, area.right() // size + 1)]

    def tile_aligned(self, area: QRect) -> QRect:
        """Returns the union of the tiles that intersect area, or an empty rect if area is empty."""
        keys = self.tile_keys(area)
        if not keys:
            return QRect()
        return self.tile_rect(keys[0]).united(self.tile_rect(keys[-1]))

    def is_cached(self, key: TileKey) -> bool:
        """Returns whether a tile is cached."""
        return key in self._tiles

    def invalidate(self, area: QRect) -> None:
        """Drops every cached tile that intersects area."""
        for key in self.tile_keys(area):
            self._tiles.pop(key, None)

    def clear(self) -> None:
        """Drops every cached tile."""
        self._tiles.clear()

    def discard_outside(self, area: QRect) -> None:
        """Drops every cached tile that doesn't intersect area, freeing tiles nothing reads."""
        keep = set(self.tile_keys(area))
        for key in [key for key in self._tiles if key not in keep]:
            del self._tiles[key]

    def tiles(self, area: QRect, render_area: RenderAreaFn) -> Iterator[tuple[QRect, QImage]]:
        """Yields the area and image of every tile that intersects area, rendering any that aren't cached with
        render_area.

        Each image is a shallow copy, so painting on it leaves the cached tile unchanged.
        """
        keys = self.tile_keys(area)
        self._render_missing(keys, render_area)
        for key in keys:
            yield self.tile_rect(key), QImage(self._tiles[key])

    def draw(self, target: QImage, area: QRect, target_origin: QPoint, render_area: RenderAreaFn) -> None:
        """Replaces the pixels of target inside area with the tiles' content, rendering missing tiles with render_area.

        Parameters
        ----------
        target: QImage
            The image to update.
        area: QRect
            The area to copy, in image coordinates.
        target_origin: QPoint
            The image coordinates of target's top left pixel.
        render_area: RenderAreaFn
            Renders missing tiles.
        """
        self.draw_region(target, QRegion(area), target_origin, render_area)

    def draw_region(self, target: QImage, region: QRegion, target_origin: QPoint, render_area: RenderAreaFn) -> None:
        """Replaces the pixels of target inside region with the tiles' content, as `draw` does for one rect."""
        if region.isEmpty():
            return
        keys = list(dict.fromkeys(key for rect in region for key in self.tile_keys(rect)))
        self._render_missing(keys, render_area)
        painter = QPainter(target)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.translate(-target_origin.x(), -target_origin.y())
        painter.setClipRegion(region)
        for key in keys:
            tile_rect = self.tile_rect(key)
            painter.drawImage(tile_rect.topLeft(), self._tiles[key])
        painter.end()

    def _render_missing(self, keys: list[TileKey], render_area: RenderAreaFn) -> None:
        """Renders and caches every tile in keys that isn't cached.

        When the missing tiles fill at least half of the grid rectangle around them, one render covers that rectangle.
        Otherwise each tile renders on its own.
        """
        missing = [key for key in keys if key not in self._tiles]
        if not missing:
            return
        min_x = min(key[0] for key in missing)
        max_x = max(key[0] for key in missing)
        min_y = min(key[1] for key in missing)
        max_y = max(key[1] for key in missing)
        grid_count = (max_x - min_x + 1) * (max_y - min_y + 1)
        if len(missing) > 1 and len(missing) * 2 >= grid_count:
            area = self.tile_rect((min_x, min_y)).united(self.tile_rect((max_x, max_y)))
            image = self._render(area, render_area)
            for key in missing:
                self._tiles[key] = image.copy(self.tile_rect(key).translated(-area.x(), -area.y()))
        else:
            for key in missing:
                self._tiles[key] = self._render(self.tile_rect(key), render_area)

    def _render(self, area: QRect, render_area: RenderAreaFn) -> QImage:
        image = QImage(area.size(), self._format)
        image.fill(0)
        render_area(image, area)
        return image
