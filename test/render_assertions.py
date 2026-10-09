"""Rendering helpers and assertions for layer compositing tests.

- `full_render` composites an ImageStack's canvas from scratch, bypassing every cache.
- `render_region` composites one canvas region on its own, the way a tile is rendered.
- `assert_region_renders_match` and `assert_tiled_render_matches` compare region renders with the same region of the
  full render.
- `displayed_image` reads back what an ImageViewer paints for the layer stack.

Comparisons are exact: the tiled compositor planned in https://github.com/centuryglass/IntraPaint/issues/25 needs
region renders to match full renders bit for bit. Call `ImageStack.flush_render` before reading a cached image or the
view, since layer groups schedule their renders on timers that tests don't wait for.
"""
from typing import Iterable, Optional

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSizeF
from PySide6.QtGui import QImage, QPainter, QTransform

from src.image.layers.image_stack import ImageStack
from src.ui.graphics_items.layer_graphics_item import LayerGraphicsItem
from src.ui.image_viewer import ImageViewer
from src.util.visual.image_utils import create_transparent_image, image_data_as_numpy_8bit_readonly
from test.base_test_case import assert_images_equal

# Mismatched regions listed in a failure message, before the rest are counted:
MAX_LISTED_REGIONS = 5


def full_render(image_stack: ImageStack) -> QImage:
    """Returns a fresh composite of the whole canvas."""
    image = create_transparent_image(image_stack.size)
    image_stack.render(image, QTransform())
    return image


def render_region(image_stack: ImageStack, region: QRect) -> QImage:
    """Returns a fresh composite of one canvas region, rendered into a region-sized image."""
    image = create_transparent_image(region.size())
    image_stack.render(image, QTransform.fromTranslate(-region.x(), -region.y()))
    return image


def tile_regions(image_stack: ImageStack, tile_size: int) -> list[QRect]:
    """Returns a grid of tile_size squares covering the canvas, clipped to the canvas at its right and bottom edges."""
    canvas = QRect(QPoint(), image_stack.size)
    return [QRect(x, y, tile_size, tile_size).intersected(canvas)
            for y in range(0, canvas.height(), tile_size)
            for x in range(0, canvas.width(), tile_size)]


def _mismatch_message(mismatched: list[QRect], region_count: int, msg: Optional[str]) -> str:
    listed = ', '.join(f'({r.x()}, {r.y()}, {r.width()}x{r.height()})' for r in mismatched[:MAX_LISTED_REGIONS])
    if len(mismatched) > MAX_LISTED_REGIONS:
        listed += f' and {len(mismatched) - MAX_LISTED_REGIONS} more'
    message = f'{len(mismatched)} of {region_count} region renders differ from the full render: {listed}'
    return message if msg is None else f'{msg}: {message}'


def assert_region_renders_match(image_stack: ImageStack, regions: Iterable[QRect], msg: Optional[str] = None) -> None:
    """Asserts that rendering each canvas region on its own gives the same pixels as that region of the full render.

    On failure, the first mismatched region's two images are saved as `assert_images_equal` saves them, and the
    message lists every mismatched region.
    """
    full = full_render(image_stack)
    canvas = QRect(QPoint(), image_stack.size)
    regions = list(regions)
    mismatched: list[tuple[QRect, QImage]] = []
    for region in regions:
        assert canvas.contains(region), f'region {region} is not inside the canvas {canvas}'
        rendered = render_region(image_stack, region)
        if not np.array_equal(image_data_as_numpy_8bit_readonly(rendered),
                              image_data_as_numpy_8bit_readonly(full.copy(region))):
            mismatched.append((region, rendered))
    if mismatched:
        first_region, first_render = mismatched[0]
        assert_images_equal(first_render, full.copy(first_region),
                            _mismatch_message([region for region, _ in mismatched], len(regions), msg))


def assert_tiled_render_matches(image_stack: ImageStack, tile_size: int, msg: Optional[str] = None) -> None:
    """Asserts that a canvas assembled from tile_size region renders matches the full render.

    On failure, the assembled and full images are saved as `assert_images_equal` saves them, and the message lists
    every mismatched tile.
    """
    full = full_render(image_stack)
    full_pixels = image_data_as_numpy_8bit_readonly(full)
    tiled = create_transparent_image(image_stack.size)
    painter = QPainter(tiled)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    regions = tile_regions(image_stack, tile_size)
    mismatched: list[QRect] = []
    for region in regions:
        rendered = render_region(image_stack, region)
        painter.drawImage(region.topLeft(), rendered)
        expected = full_pixels[region.y():region.y() + region.height(), region.x():region.x() + region.width()]
        if not np.array_equal(image_data_as_numpy_8bit_readonly(rendered), expected):
            mismatched.append(region)
    painter.end()
    if mismatched:
        assert_images_equal(tiled, full, _mismatch_message(mismatched, len(regions), msg))


def displayed_image(viewer: ImageViewer, image_stack: ImageStack) -> QImage:
    """Returns the canvas as the viewer paints the layer stack, without the view background or any overlay.

    The scene is rendered at 1:1 with every other item hidden, so the layer stack item's own opacity, composition
    mode and transform apply as they do on screen.
    """
    scene = viewer.scene()
    assert scene is not None
    stack_items = [item for item in scene.items()
                   if isinstance(item, LayerGraphicsItem) and item.layer is image_stack.layer_stack]
    assert len(stack_items) == 1, f'expected one item for the layer stack, found {len(stack_items)}'
    hidden = [item for item in scene.items() if item is not stack_items[0] and item.isVisible()]
    for item in hidden:
        item.setVisible(False)
    try:
        image = create_transparent_image(image_stack.size)
        painter = QPainter(image)
        scene.render(painter, QRectF(QPointF(), QSizeF(image_stack.size)), QRectF(QRect(QPoint(), image_stack.size)))
        painter.end()
    finally:
        for item in hidden:
            item.setVisible(True)
    return image
