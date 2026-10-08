"""Tests flushing scheduled renders, what the view displays, and whether region renders match full renders."""
import sys
import unittest

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QImage, QTransform
from PySide6.QtWidgets import QApplication

from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer_group import LayerGroup
from src.image.open_raster import read_ora_image
from src.ui.graphics_items.layer_graphics_item import LayerGraphicsItem
from src.ui.image_viewer import ImageViewer
from src.util.visual.image_utils import image_data_as_numpy_8bit
from test.base_test_case import IntraPaintTestCase
from test.render_assertions import (assert_region_renders_match, assert_tiled_render_matches, displayed_image,
                                    full_render)

app = QApplication.instance() or QApplication(sys.argv)

CANVAS_SIZE = QSize(160, 120)
LAYER_SIZE = QSize(90, 70)
# One tile size aligned with libmypaint's TILE_DIM, one that doesn't divide the canvas evenly:
TILE_SIZES = (64, 37)
LAYER_MOVE_TEST_IMAGE = 'test/resources/test_images/layer_move_test.ora'

ISSUE_147 = ('https://github.com/centuryglass/IntraPaint/issues/147: scaled and rotated layers sample differently in '
             'a region render')


def _gradient_image(size: QSize, seed: int) -> QImage:
    """Returns a premultiplied image where every pixel differs from its neighbors, with partial alpha throughout."""
    rng = np.random.default_rng(seed)
    pixels = rng.integers(0, 256, (size.height(), size.width(), 4), dtype=np.uint8)
    alpha = rng.integers(40, 256, (size.height(), size.width()), dtype=np.uint8)
    pixels[:, :, 3] = alpha
    pixels[:, :, :3] = (pixels[:, :, :3].astype(np.uint16) * alpha[:, :, np.newaxis] // 255).astype(np.uint8)
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    np.copyto(image_data_as_numpy_8bit(image), pixels)
    return image


class RenderTestCase(IntraPaintTestCase):
    """Builds an image stack with a partly transparent, noisy background layer covering the canvas."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(CANVAS_SIZE, CANVAS_SIZE, QSize(8, 8), CANVAS_SIZE)
        self.background = self.image_stack.create_layer('background', _gradient_image(CANVAS_SIZE, 0))

    def add_layer(self, name: str, transform: QTransform, parent: LayerGroup | None = None,
                  mode: CompositeMode = CompositeMode.NORMAL, opacity: float = 1.0) -> ImageLayer:
        """Adds a noisy, partly transparent layer above the others, or at the top of a group."""
        layer = self.image_stack.create_layer(name, _gradient_image(LAYER_SIZE, len(self.image_stack.all_layers())),
                                              layer_parent=parent, layer_index=0 if parent is not None else None)
        layer.transform = transform
        layer.composition_mode = mode
        layer.opacity = opacity
        return layer

    def assert_tiles_match(self) -> None:
        """Asserts that tiled renders at each of TILE_SIZES match the full render."""
        for tile_size in TILE_SIZES:
            assert_tiled_render_matches(self.image_stack, tile_size, f'{tile_size}px tiles')


class FlushRenderTest(RenderTestCase):
    """Tests that flush_render brings group caches and listeners up to date without the event loop."""

    def test_group_cache_updates_on_flush(self) -> None:
        """The layer stack's cached image keeps its old content until the scheduled render is flushed."""
        layer_stack = self.image_stack.layer_stack
        self.image_stack.flush_render()
        before = layer_stack.get_qimage().copy()
        with self.background.borrow_image(QRect(10, 10, 4, 4)) as image:
            image.fill(0)
        self.assert_images_equal(layer_stack.get_qimage(), before)
        self.image_stack.flush_render()
        self.assert_images_equal(layer_stack.get_qimage(), full_render(self.image_stack))

    def test_nested_group_change_reaches_root(self) -> None:
        """Flushing renders a nested group before its parents, so an edit inside it reaches the layer stack."""
        outer = self.image_stack.create_layer_group('outer')
        inner = self.image_stack.create_layer_group('inner', layer_parent=outer)
        layer = self.add_layer('nested', QTransform.fromTranslate(20, 10), parent=inner)
        self.image_stack.flush_render()
        with layer.borrow_image(QRect(0, 0, 8, 8)) as image:
            image.fill(0)
        self.image_stack.flush_render()
        self.assert_images_equal(self.image_stack.layer_stack.get_qimage(), full_render(self.image_stack))

    def test_flush_emits_content_changed_once(self) -> None:
        """A flush emits ImageStack.content_changed once for a pending change, and not again with nothing pending."""
        self.image_stack.flush_render()
        emitted: list[None] = []
        self.image_stack.content_changed.connect(lambda: emitted.append(None))
        with self.background.borrow_image(QRect(0, 0, 4, 4)) as image:
            image.fill(0)
        self.image_stack.flush_render()
        self.assertEqual(len(emitted), 1)
        self.image_stack.flush_render()
        self.assertEqual(len(emitted), 1)


class DisplayedImageTest(RenderTestCase):
    """Tests that the view displays the same pixels the compositor renders."""

    def setUp(self) -> None:
        super().setUp()
        self.viewer = ImageViewer(None, self.image_stack, use_keybindings=False)

    def assert_view_matches_render(self) -> None:
        """Flushes pending renders, then asserts the view shows the full render."""
        self.image_stack.flush_render()
        self.assert_images_equal(displayed_image(self.viewer, self.image_stack), full_render(self.image_stack))

    def test_view_matches_render(self) -> None:
        """The view shows the composite, without outlines or the transparency background."""
        self.add_layer('top', QTransform.fromTranslate(30, 20), mode=CompositeMode.MULTIPLY, opacity=0.7)
        self.assert_view_matches_render()

    def test_view_follows_edits(self) -> None:
        """After an edit is flushed, the view shows the edited composite."""
        self.assert_view_matches_render()
        with self.background.borrow_image(QRect(5, 5, 20, 20)) as image:
            image.fill(0)
        self.assert_view_matches_render()

    def test_view_with_layer_stack_offset(self) -> None:
        """Content past the canvas's top left corner moves the layer stack's bounds, and the view follows them."""
        self.add_layer('offset', QTransform.fromTranslate(-30, -20))
        self.assertLess(self.image_stack.layer_stack.bounds.x(), 0)
        self.assert_view_matches_render()

    def test_view_with_layer_stack_opacity(self) -> None:
        """The layer stack's own opacity shows on screen the way it renders."""
        self.image_stack.layer_stack.opacity = 0.5
        self.assert_view_matches_render()

    def test_layer_stack_item_paints_composite_as_is(self) -> None:
        """The layer stack's item paints at full opacity in Normal mode, since its composite already applies both.

        displayed_image renders over transparency, where most modes act like Normal, so this checks the item itself.
        """
        layer_stack = self.image_stack.layer_stack
        layer_stack.opacity = 0.5
        layer_stack.composition_mode = CompositeMode.MULTIPLY
        scene = self.viewer.scene()
        assert scene is not None
        stack_items = [item for item in scene.items()
                       if isinstance(item, LayerGraphicsItem) and item.layer is layer_stack]
        self.assertEqual(len(stack_items), 1)
        self.assertEqual(stack_items[0].opacity(), 1.0)
        self.assertEqual(stack_items[0].composition_mode, CompositeMode.NORMAL)


class RegionRenderTest(RenderTestCase):
    """Tests that rendering a region of the canvas on its own matches that region of the full render."""

    def test_pixel_aligned_layer_in_qt_modes(self) -> None:
        """A translated layer over partial alpha renders the same in tiles, in every mode QPainter composites."""
        layer = self.add_layer('top', QTransform.fromTranslate(13, 7), opacity=0.7)
        for mode in CompositeMode:
            if mode.qt_composite_mode() is not None:
                with self.subTest(mode=mode.name):
                    layer.set_composition_mode(mode)
                    self.assert_tiles_match()

    def test_pixel_aligned_layer_in_hsl_modes(self) -> None:
        """A translated layer over partial alpha renders the same in tiles, in the modes with custom compositing."""
        layer = self.add_layer('top', QTransform.fromTranslate(13, 7), opacity=0.7)
        for mode in CompositeMode:
            if mode.qt_composite_mode() is None:
                with self.subTest(mode=mode.name):
                    layer.set_composition_mode(mode)
                    self.assert_tiles_match()

    def test_fractional_translation(self) -> None:
        """A layer translated by a fraction of a pixel renders the same in tiles."""
        self.add_layer('top', QTransform.fromTranslate(13.4, 7.6))
        self.assert_tiles_match()

    def test_arbitrary_regions(self) -> None:
        """Single pixels, odd-sized regions and the whole canvas render the same as the full render."""
        self.add_layer('top', QTransform.fromTranslate(40, 30), mode=CompositeMode.SCREEN)
        assert_region_renders_match(self.image_stack, [QRect(0, 0, 1, 1), QRect(39, 29, 1, 1), QRect(41, 3, 77, 13),
                                                       QRect(159, 119, 1, 1), QRect(QPoint(), CANVAS_SIZE)])

    def test_isolated_group(self) -> None:
        """An isolated group smaller than the canvas, with its own opacity and mode, renders the same in tiles."""
        group = self.image_stack.create_layer_group('group')
        group.isolate = True
        self.add_layer('inner', QTransform.fromTranslate(30, 20), parent=group, mode=CompositeMode.DIFFERENCE)
        for mode in (CompositeMode.NORMAL, CompositeMode.MULTIPLY, CompositeMode.HUE):
            with self.subTest(mode=mode.name):
                group.set_composition_mode(mode)
                group.set_opacity(0.6)
                self.assert_tiles_match()

    def test_non_isolated_group_covering_canvas(self) -> None:
        """A non-isolated group that covers the whole canvas renders the same in tiles."""
        group = self.image_stack.create_layer_group('group')
        self.image_stack.create_layer('cover', _gradient_image(CANVAS_SIZE, 9), layer_parent=group, layer_index=0)
        self.add_layer('inner', QTransform.fromTranslate(30, 20), parent=group)
        self.assertTrue(group.bounds.contains(QRect(QPoint(), CANVAS_SIZE)))
        self.assert_tiles_match()

    def test_non_isolated_group_smaller_than_canvas(self) -> None:
        """A non-isolated group smaller than the canvas renders the same in tiles."""
        group = self.image_stack.create_layer_group('group')
        self.add_layer('inner', QTransform.fromTranslate(30, 20), parent=group)
        self.assert_tiles_match()

    @pytest.mark.xfail(strict=True, reason=ISSUE_147)
    def test_scaled_layer(self) -> None:
        """A scaled layer renders the same in tiles."""
        self.add_layer('scaled', QTransform.fromTranslate(11, 6).scale(1.3, 0.9))
        self.assert_tiles_match()

    @pytest.mark.xfail(strict=True, reason=ISSUE_147)
    def test_rotated_layer(self) -> None:
        """A rotated layer renders the same in tiles."""
        self.add_layer('rotated', QTransform.fromTranslate(60, 10).rotate(30))
        self.assert_tiles_match()

    @pytest.mark.xfail(strict=True, reason=ISSUE_147)
    def test_layer_move_test_image(self) -> None:
        """The nested, transformed groups in layer_move_test.ora render the same in tiles."""
        read_ora_image(self.image_stack, LAYER_MOVE_TEST_IMAGE)
        self.assert_tiles_match()


if __name__ == '__main__':
    unittest.main()
