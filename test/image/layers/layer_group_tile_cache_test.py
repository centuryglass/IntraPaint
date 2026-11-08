"""Tests that a LayerGroup's tile-cached composite matches a fresh full render exactly after every kind of edit.

Each test drives a series of edits through the cache and compares the cached image with an uncached render after each
one, with no tolerance. A tile composited onto stale content drifts by a step or two per edit over partly transparent
pixels, so repeated small edits catch it.
"""
import sys
from typing import Callable
from unittest.mock import patch

import numpy as np
from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QColor, QImage, QPainter, QTransform
from PySide6.QtWidgets import QApplication

from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer_group import LayerGroup
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_data_as_numpy_8bit
from src.util.visual.tile_cache import TILE_SIZE
from test.base_test_case import IntraPaintTestCase
from test.render_assertions import full_group_render, full_render

app = QApplication.instance() or QApplication(sys.argv)

# Spans several tiles in each direction, with partial tiles at the right and bottom edges:
CANVAS_SIZE = QSize(TILE_SIZE * 2 + 90, TILE_SIZE + 70)
LAYER_SIZE = QSize(TILE_SIZE + 40, TILE_SIZE - 60)
# An edit area in the top row of tiles that crosses the boundary between the first two:
TILE_EDGE_EDIT = QRect(TILE_SIZE - 6, 50, 12, 12)


def _noise_image(size: QSize, seed: int) -> QImage:
    """Returns a premultiplied image where every pixel differs from its neighbors, with partial alpha throughout."""
    rng = np.random.default_rng(seed)
    pixels = rng.integers(0, 256, (size.height(), size.width(), 4), dtype=np.uint8)
    alpha = rng.integers(40, 256, (size.height(), size.width()), dtype=np.uint8)
    pixels[:, :, 3] = alpha
    pixels[:, :, :3] = (pixels[:, :, :3].astype(np.uint16) * alpha[:, :, np.newaxis] // 255).astype(np.uint8)
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    np.copyto(image_data_as_numpy_8bit(image), pixels)
    return image


def _dab(layer: ImageLayer, area: QRect, color: QColor) -> None:
    """Paints a translucent rectangle over area, in the layer's own coordinates, blending with what's there."""
    with layer.borrow_image(area) as image:
        assert image is not None
        painter = QPainter(image)
        painter.fillRect(area, color)
        painter.end()


class LayerGroupTileCacheTest(IntraPaintTestCase):
    """Edits a stack with a partly transparent background, a non-isolated group and an isolated group."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(CANVAS_SIZE, CANVAS_SIZE, QSize(8, 8), CANVAS_SIZE)
        self.background = self.image_stack.create_layer('background', _noise_image(CANVAS_SIZE, 0))
        self.pass_through = self.image_stack.create_layer_group('pass-through')
        self.passed = self.add_layer('passed', QPoint(30, 20), self.pass_through, CompositeMode.MULTIPLY, 0.8)
        self.isolated = self.image_stack.create_layer_group('isolated')
        self.isolated.isolate = True
        self.lower = self.add_layer('lower', QPoint(TILE_SIZE - 50, 40), self.isolated)
        self.upper = self.add_layer('upper', QPoint(TILE_SIZE + 10, 70), self.isolated, CompositeMode.SCREEN, 0.7)
        self.assert_cache_matches('initial')

    def add_layer(self, name: str, offset: QPoint, parent: LayerGroup,
                  mode: CompositeMode = CompositeMode.NORMAL, opacity: float = 1.0) -> ImageLayer:
        """Adds a noisy, partly transparent layer at the top of a group."""
        layer = self.image_stack.create_layer(name, _noise_image(LAYER_SIZE, len(self.image_stack.all_layers())),
                                              layer_parent=parent, layer_index=0)
        layer.transform = QTransform.fromTranslate(offset.x(), offset.y())
        layer.composition_mode = mode
        layer.opacity = opacity
        return layer

    def assert_cache_matches(self, step: str) -> None:
        """Flushes renders, then asserts every group's cached image matches an uncached render of that group."""
        self.image_stack.flush_render()
        for group in (self.image_stack.layer_stack, self.pass_through, self.isolated):
            if group.layer_parent is None and group is not self.image_stack.layer_stack:
                continue
            self.assert_images_equal(group.get_qimage(), full_group_render(group), f'{group.name} after {step}')
        layer_stack = self.image_stack.layer_stack
        canvas_in_stack = QRect(QPoint(), CANVAS_SIZE).translated(-layer_stack.bounds.topLeft())
        self.assert_images_equal(layer_stack.get_qimage().copy(canvas_in_stack), full_render(self.image_stack),
                                 f'canvas after {step}')

    def run_steps(self, steps: list[tuple[str, Callable[[], None]]]) -> None:
        """Runs each step, checking the caches after each one."""
        for name, step in steps:
            step()
            self.assert_cache_matches(name)

    def test_repeated_strokes_over_partial_alpha(self) -> None:
        """Many overlapping translucent dabs across tile boundaries leave the cache exact, with no drift."""
        steps: list[tuple[str, Callable[[], None]]] = []
        for i in range(12):
            area = TILE_EDGE_EDIT.translated(i * 3, i * 2)
            color = QColor(200, 40 + i * 10, 90, 70)
            steps.append((f'background dab {i}', lambda a=area, c=color: _dab(self.background, a, c)))
            local_area = area.translated(-self.lower.transformed_bounds.topLeft())
            steps.append((f'lower dab {i}', lambda a=local_area, c=color: _dab(self.lower, a, c)))
            passed_area = area.translated(-self.passed.transformed_bounds.topLeft())
            steps.append((f'passed dab {i}', lambda a=passed_area, c=color: _dab(self.passed, a, c)))
        self.run_steps(steps)

    def test_edits_touching_one_pixel_of_a_tile(self) -> None:
        """Edits whose first or last row or column falls in the next tile update that tile."""
        color = QColor(30, 200, 200, 110)
        self.run_steps([
            ('last column in next tile', lambda: _dab(self.background, QRect(TILE_SIZE - 9, 10, 10, 10), color)),
            ('first column in previous tile',
             lambda: _dab(self.background, QRect(TILE_SIZE * 2 - 1, 30, 10, 10), color)),
            ('last row in next tile', lambda: _dab(self.background, QRect(40, TILE_SIZE - 9, 10, 10), color)),
            ('first row in previous tile', lambda: _dab(self.background, QRect(60, TILE_SIZE - 1, 10, 10), color)),
        ])

    def test_property_changes(self) -> None:
        """Opacity, composition mode, visibility and isolation changes on layers and groups leave the cache exact."""
        self.run_steps([
            ('layer opacity', lambda: setattr(self.upper, 'opacity', 0.35)),
            ('layer Qt mode', lambda: setattr(self.upper, 'composition_mode', CompositeMode.DARKEN)),
            ('layer HSL mode', lambda: setattr(self.passed, 'composition_mode', CompositeMode.HUE)),
            ('group opacity', lambda: setattr(self.isolated, 'opacity', 0.6)),
            ('group mode', lambda: setattr(self.isolated, 'composition_mode', CompositeMode.OVERLAY)),
            ('group HSL mode', lambda: setattr(self.isolated, 'composition_mode', CompositeMode.COLOR)),
            ('hide layer', lambda: setattr(self.lower, 'visible', False)),
            ('show layer', lambda: setattr(self.lower, 'visible', True)),
            ('hide group', lambda: setattr(self.pass_through, 'visible', False)),
            ('show group', lambda: setattr(self.pass_through, 'visible', True)),
            ('isolate', lambda: setattr(self.pass_through, 'isolate', True)),
            ('dab after isolating', lambda: _dab(self.passed, QRect(10, 10, 30, 30), QColor(0, 90, 200, 90))),
            ('un-isolate', lambda: setattr(self.pass_through, 'isolate', False)),
            ('undo', UndoStack().undo),
            ('redo', UndoStack().redo),
        ])

    def test_structure_changes(self) -> None:
        """Adding, removing and reordering layers and groups leaves the cache exact."""
        def _add_layer() -> None:
            self.add_layer('added', QPoint(TILE_SIZE * 2 - 20, 30), self.pass_through, CompositeMode.SOFT_LIGHT)

        def _add_nested_group() -> None:
            nested = self.image_stack.create_layer_group('nested', layer_parent=self.isolated, layer_index=0)
            nested_layer = self.add_layer('nested layer', QPoint(-20, TILE_SIZE - 30), nested,
                                          CompositeMode.DIFFERENCE, 0.9)
            _dab(nested_layer, QRect(5, 5, 40, 40), QColor(10, 220, 10, 120))

        self.run_steps([
            ('add layer', _add_layer),
            ('add nested group', _add_nested_group),
            ('reorder within group', lambda: self.image_stack.move_layer(self.upper, self.isolated,
                                                                         self.isolated.count - 1)),
            ('move between groups', lambda: self.image_stack.move_layer(self.lower, self.pass_through, 0)),
            ('reorder groups', lambda: self.image_stack.move_layer(self.isolated, self.image_stack.layer_stack, 0)),
            ('remove layer', lambda: self.image_stack.remove_layer(self.passed)),
            ('undo remove', UndoStack().undo),
            ('remove group', lambda: self.image_stack.remove_layer(self.pass_through)),
            ('undo remove group', UndoStack().undo),
        ])

    def test_transforms(self) -> None:
        """Moving, scaling and rotating layers, including past the canvas edges, leaves the cache exact."""
        def _transform(layer: ImageLayer, transform: QTransform) -> Callable[[], None]:
            return lambda: setattr(layer, 'transform', transform)

        self.run_steps([
            ('move one tile', _transform(self.upper, QTransform.fromTranslate(TILE_SIZE * 2 + 10, 70))),
            ('move past top left', _transform(self.lower, QTransform.fromTranslate(-TILE_SIZE - 30, -50))),
            ('dab past top left', lambda: _dab(self.lower, QRect(0, 0, 60, 60), QColor(250, 250, 0, 60))),
            ('fractional move', _transform(self.passed, QTransform.fromTranslate(40.5, 21.25))),
            ('scale', _transform(self.upper, QTransform.fromScale(1.3, 0.7) * QTransform.fromTranslate(100, 20))),
            ('rotate', _transform(self.lower, QTransform().rotate(23) * QTransform.fromTranslate(TILE_SIZE, 10))),
            ('dab on rotated layer', lambda: _dab(self.lower, QRect(20, 20, 50, 50), QColor(0, 0, 250, 100))),
            ('move back', _transform(self.lower, QTransform.fromTranslate(TILE_SIZE - 50, 40))),
            ('flip group', self.isolated.flip_horizontal),
        ])

    def test_small_edit_renders_only_touched_tiles(self) -> None:
        """After a small edit, reading the cached image re-renders only the tiles the edit touches."""
        layer_stack = self.image_stack.layer_stack
        _dab(self.background, TILE_EDGE_EDIT, QColor(255, 0, 0, 80))
        self.image_stack.flush_render()
        with patch.object(LayerGroup, '_render_area', autospec=True,
                          side_effect=LayerGroup._render_area) as render_area:  # pylint: disable=protected-access
            image = layer_stack.get_qimage()
        touched = QRect(0, 0, TILE_SIZE * 2, TILE_SIZE)
        rendered = [call.args[2] for call in render_area.call_args_list if call.args[0] is layer_stack]
        self.assertEqual(rendered, [touched])
        self.assert_images_equal(image, full_group_render(layer_stack))

    def test_returned_image_is_independent(self) -> None:
        """Painting on the image get_qimage returns leaves the cache unchanged, and later edits leave it unchanged."""
        layer_stack = self.image_stack.layer_stack
        returned = layer_stack.get_qimage()
        returned_copy = returned.copy()
        _dab(self.background, TILE_EDGE_EDIT, QColor(255, 0, 0, 80))
        self.image_stack.flush_render()
        self.assert_images_equal(layer_stack.get_qimage(), full_group_render(layer_stack))
        self.assert_images_equal(returned, returned_copy)
        returned.fill(QColor(0, 0, 0, 255))
        self.assert_images_equal(layer_stack.get_qimage(), full_group_render(layer_stack))
