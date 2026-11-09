"""Tests that the layer stack's item repaints only changed areas, and still shows exactly what the stack renders."""
import sys

import numpy as np
from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QImage, QTransform
from PySide6.QtWidgets import QApplication

from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer_resize_mode import LayerResizeMode
from src.image.composite_mode import CompositeMode
from src.ui.graphics_items.layer_graphics_item import LayerGraphicsItem
from src.ui.image_viewer import ImageViewer
from src.util.visual.image_utils import image_data_as_numpy_8bit
from src.util.visual.tile_cache import TILE_SIZE
from test.base_test_case import IntraPaintTestCase
from test.render_assertions import clear_area, displayed_image, full_render

app = QApplication.instance() or QApplication(sys.argv)

# Larger than one tile in each dimension, and not a multiple of the tile size:
CANVAS_SIZE = QSize(TILE_SIZE + 44, TILE_SIZE + 24)
LAYER_SIZE = QSize(120, 90)


def _noise_image(size: QSize, seed: int) -> QImage:
    """Returns a premultiplied image of random colors with partial alpha."""
    rng = np.random.default_rng(seed)
    alpha = rng.integers(40, 256, (size.height(), size.width()), dtype=np.uint16)
    color = rng.integers(0, 256, (size.height(), size.width(), 3), dtype=np.uint16)
    pixels = np.empty((size.height(), size.width(), 4), dtype=np.uint8)
    pixels[:, :, :3] = color * alpha[:, :, np.newaxis] // 255
    pixels[:, :, 3] = alpha
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    np.copyto(image_data_as_numpy_8bit(image), pixels)
    return image


def _paint_noise(layer: ImageLayer, area: QRect, seed: int) -> None:
    """Replaces area of a layer with noise, reporting only area as changed."""
    noise = image_data_as_numpy_8bit(_noise_image(area.size(), seed))
    with layer.borrow_image(area) as image:
        assert image is not None
        pixels = image_data_as_numpy_8bit(image)
        pixels[area.y():area.y() + area.height(), area.x():area.x() + area.width()] = noise


class LayerGraphicsItemTest(IntraPaintTestCase):
    """Edits a canvas spanning several tiles and compares what the view shows with a full render."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(CANVAS_SIZE, CANVAS_SIZE, QSize(8, 8), CANVAS_SIZE)
        self.background = self.image_stack.create_layer('background', _noise_image(CANVAS_SIZE, 0))
        self.top = self.image_stack.create_layer('top', _noise_image(LAYER_SIZE, 1))
        self.top.transform = QTransform.fromTranslate(TILE_SIZE - 60, TILE_SIZE - 40)
        self.top.composition_mode = CompositeMode.MULTIPLY
        self.viewer = ImageViewer(None, self.image_stack, use_keybindings=False)
        scene = self.viewer.scene()
        assert scene is not None
        items = [item for item in scene.items()
                 if isinstance(item, LayerGraphicsItem) and item.layer is self.image_stack.layer_stack]
        assert len(items) == 1
        self.item = items[0]
        self.image_stack.flush_render()

    def pixmap_serial(self) -> int:
        """Returns the item pixmap's serial number, which a copy or rebuild changes and painting into it keeps."""
        return self.item.pixmap().cacheKey() >> 32

    def stack_image_serial(self) -> int:
        """Returns the serial number of the layer stack's cached image, which changes if the image is copied."""
        return self.image_stack.layer_stack.get_qimage().cacheKey() >> 32

    def assert_view_matches_render(self, msg: str) -> None:
        """Flushes pending renders, then asserts the view shows the full render."""
        self.image_stack.flush_render()
        self.assert_images_equal(displayed_image(self.viewer, self.image_stack), full_render(self.image_stack), msg)

    def test_small_edits_paint_into_the_pixmap(self) -> None:
        """A series of small edits leaves the view exact, painting into the existing pixmap without rebuilding it.

        Neither the pixmap nor the layer stack's cached image is copied, so they share no data.
        """
        serial = self.pixmap_serial()
        stack_serial = self.stack_image_serial()
        edits = [QRect(3, 5, 7, 4), QRect(40, 60, 1, 1), QRect(100, 20, 30, 50), QRect(0, 0, 2, 2)]
        for seed, area in enumerate(edits, start=10):
            with self.subTest(area=area):
                _paint_noise(self.background, area, seed)
                self.assert_view_matches_render(f'after painting {area}')
        clear_area(self.top, QRect(10, 10, 20, 15))
        self.assert_view_matches_render('after clearing part of the transformed layer')
        self.assertEqual(self.pixmap_serial(), serial)
        self.assertEqual(self.stack_image_serial(), stack_serial)

    def test_edits_at_tile_and_canvas_edges(self) -> None:
        """Edits that cross a tile edge, or touch the canvas's corners and far edges, show exactly."""
        width, height = CANVAS_SIZE.width(), CANVAS_SIZE.height()
        edits = [QRect(TILE_SIZE - 3, 30, 6, 6),  # Across a vertical tile edge
                 QRect(30, TILE_SIZE - 1, 5, 2),  # Across a horizontal tile edge
                 QRect(TILE_SIZE - 2, TILE_SIZE - 2, 4, 4),  # Across a tile corner
                 QRect(TILE_SIZE, TILE_SIZE, 1, 1),  # The first pixel of a tile
                 QRect(width - 5, 0, 5, height),  # The right edge, in partial tiles
                 QRect(0, height - 1, width, 1),  # The bottom row
                 QRect(width - 1, height - 1, 1, 1)]  # The bottom right pixel
        for seed, area in enumerate(edits, start=20):
            with self.subTest(area=area):
                _paint_noise(self.background, area, seed)
                self.assert_view_matches_render(f'after painting {area}')

    def test_edit_on_transformed_layer_across_tiles(self) -> None:
        """An edit to a translated layer, reported in its own coordinates, shows where the layer is on the canvas."""
        _paint_noise(self.top, QRect(55, 35, 10, 10), 30)  # Covers the tile corner at (TILE_SIZE, TILE_SIZE)
        self.assert_view_matches_render('after painting the translated layer')

    def test_resize_between_edits(self) -> None:
        """Resizing the canvas between edits rebuilds the pixmap at the new size, and later edits show exactly.

        The rebuilt pixmap shares no data with the layer stack's cached image, so the next edit copies neither.
        """
        _paint_noise(self.background, QRect(10, 10, 8, 8), 40)
        self.assert_view_matches_render('before resizing')
        serial = self.pixmap_serial()
        new_size = QSize(CANVAS_SIZE.width() + 30, CANVAS_SIZE.height() - 20)
        self.image_stack.resize_canvas(new_size, 12, -6, LayerResizeMode.RESIZE_ALL, True)
        self.assert_view_matches_render('after resizing')
        self.assertEqual(self.item.pixmap().size(), self.image_stack.layer_stack.bounds.size())
        self.assertNotEqual(self.pixmap_serial(), serial)
        serial = self.pixmap_serial()
        stack_serial = self.stack_image_serial()
        _paint_noise(self.background, QRect(new_size.width() - 9, 4, 9, 9), 41)
        self.assert_view_matches_render('after an edit following the resize')
        self.assertEqual(self.pixmap_serial(), serial, 'the edit copied the rebuilt pixmap')
        self.assertEqual(self.stack_image_serial(), stack_serial, 'the rebuilt pixmap shares the stack image')

    def test_layer_stack_bounds_move(self) -> None:
        """When the layer stack's bounds move without changing size, the view follows, and later edits show exactly."""
        self.top.transform = QTransform.fromTranslate(20, 20)
        self.assert_view_matches_render('after moving the top layer inside the background')
        bounds = self.image_stack.layer_stack.bounds
        self.background.transform = QTransform.fromTranslate(-15, -9)
        self.assert_view_matches_render('after moving the layer stack bounds')
        self.assertEqual(self.image_stack.layer_stack.bounds, bounds.translated(-15, -9))
        _paint_noise(self.top, QRect(0, 0, 20, 12), 50)
        self.assert_view_matches_render('after painting a layer in the moved stack')
