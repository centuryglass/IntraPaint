"""Tests that every layer change reports a changed area covering every pixel it changes.

Region compositing (https://github.com/centuryglass/IntraPaint/issues/25) will redraw only the reported areas, so a
change that reports too little leaves stale pixels. Each test renders the full canvas before and after one change, and
asserts that the reported areas, in image coordinates, cover every pixel that differs. Over-reporting passes.

`ChangedAreaRecorder` collects the reports. It reads `Layer.content_changed` from every layer in the stack, maps a
`TransformLayer`'s rect with `TransformLayer.map_changed_rect_to_image` when it's emitted, and takes a `LayerGroup`'s
rect as image coordinates. It ignores what a group emits from `LayerGroup._start_render`: that render only rolls up its
children's changes as the group's whole bounds, and the region compositor replaces it with the union of their rects.
"""
import sys
from contextlib import ExitStack
from typing import Callable, Optional
from unittest.mock import patch

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QColor, QImage, QTransform
from PySide6.QtWidgets import QApplication

from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.transform_layer import TransformLayer
from src.image.text_rect import TextRect
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_data_as_numpy_8bit, image_data_as_numpy_8bit_readonly
from test.base_test_case import IntraPaintTestCase
from test.render_assertions import full_render

app = QApplication.instance() or QApplication(sys.argv)

CANVAS_SIZE = QSize(120, 90)
ISSUE_210 = ('https://github.com/centuryglass/IntraPaint/issues/210: adding, removing and reordering layers schedule a '
             'group render without reporting a changed area')
LAYER_SIZE = QSize(40, 30)


def _noise_image(size: QSize, seed: int) -> QImage:
    """Returns a premultiplied image where every pixel differs from its neighbors, with partial alpha throughout."""
    rng = np.random.default_rng(seed)
    pixels = rng.integers(0, 256, (size.height(), size.width(), 4), dtype=np.uint8)
    alpha = rng.integers(60, 256, (size.height(), size.width()), dtype=np.uint8)
    pixels[:, :, 3] = alpha
    pixels[:, :, :3] = (pixels[:, :, :3].astype(np.uint16) * alpha[:, :, np.newaxis] // 255).astype(np.uint8)
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    np.copyto(image_data_as_numpy_8bit(image), pixels)
    return image


class ChangedAreaRecorder:
    """Collects the changed areas an image stack's layers report, in image coordinates."""

    def __init__(self, image_stack: ImageStack, exit_stack: ExitStack) -> None:
        self._connected: set[Layer] = set()
        self._rolling_up: set[LayerGroup] = set()
        self.rects: list[QRect] = []
        recorder = self
        start_render = LayerGroup._start_render  # pylint: disable=protected-access

        def _recorded_start_render(group: LayerGroup) -> None:
            recorder._rolling_up.add(group)
            try:
                start_render(group)
            finally:
                recorder._rolling_up.discard(group)

        exit_stack.enter_context(patch.object(LayerGroup, '_start_render', _recorded_start_render))
        root = image_stack.layer_stack
        root.layer_added.connect(self._connect)
        for layer in (root, *root.recursive_child_layers):
            self._connect(layer)

    def _connect(self, layer: Layer) -> None:
        if layer not in self._connected:
            self._connected.add(layer)
            layer.content_changed.connect(self._record)

    def _record(self, layer: Layer, rect: QRect) -> None:
        if layer in self._rolling_up:
            return
        if isinstance(layer, TransformLayer):
            rect = layer.map_changed_rect_to_image(rect)
        self.rects.append(QRect(rect))


class ChangedAreaTestCase(IntraPaintTestCase):
    """Builds a stack with a background, a translated layer, and an isolated group holding a translated layer and a
       scaled, rotated one. `NonIsolatedGroupTest` covers the same group without isolation."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(CANVAS_SIZE, CANVAS_SIZE, QSize(8, 8), CANVAS_SIZE)
        self.background = self.image_stack.create_layer('background', _noise_image(CANVAS_SIZE, 0))
        self.translated = self.image_stack.create_layer('translated', _noise_image(LAYER_SIZE, 1),
                                                        transform=QTransform.fromTranslate(10, 8))
        self.group = self.image_stack.create_layer_group('group')
        self.group.isolate = True
        rotated = QTransform.fromTranslate(60, 10).rotate(30).scale(1.5, 1.2)
        self.rotated = self.image_stack.create_layer('rotated', _noise_image(LAYER_SIZE, 2), layer_parent=self.group,
                                                     layer_index=0, transform=rotated)
        self.grouped = self.image_stack.create_layer('grouped', _noise_image(LAYER_SIZE, 3), layer_parent=self.group,
                                                     layer_index=1, transform=QTransform.fromTranslate(60, 50))
        self.image_stack.flush_render()
        exit_stack = ExitStack()
        self.addCleanup(exit_stack.close)
        self.recorder = ChangedAreaRecorder(self.image_stack, exit_stack)

    def assert_change_covered(self, change: Callable[[], None], msg: Optional[str] = None) -> None:
        """Runs a change, then asserts the areas reported during it cover every pixel it changed in the full render."""
        self.image_stack.flush_render()
        before = full_render(self.image_stack)
        self.recorder.rects.clear()
        change()
        self.image_stack.flush_render()
        after = full_render(self.image_stack)
        # A canvas resize changes the render's size. Pixels outside the new canvas aren't drawn, so they don't count.
        width, height = after.width(), after.height()

        def _padded(image: QImage) -> np.ndarray:
            pixels = np.zeros((height, width, 4), dtype=np.uint8)
            visible = image_data_as_numpy_8bit_readonly(image)[:height, :width]
            pixels[:visible.shape[0], :visible.shape[1]] = visible
            return pixels

        changed = np.any(_padded(before) != _padded(after), axis=2)
        self.assertTrue(changed.any(), 'the change left the full render unchanged, so it tests nothing')
        covered = np.zeros_like(changed)
        canvas = QRect(0, 0, width, height)
        for rect in self.recorder.rects:
            rect = rect.intersected(canvas)
            if not rect.isEmpty():
                covered[rect.y():rect.y() + rect.height(), rect.x():rect.x() + rect.width()] = True
        missed = changed & ~covered
        if missed.any():
            ys, xs = np.nonzero(missed)
            missed_bounds = QRect(QPoint(int(xs.min()), int(ys.min())), QPoint(int(xs.max()), int(ys.max())))
            message = (f'{int(missed.sum())} changed pixels are outside every reported area, within {missed_bounds}.'
                       f' Reported: {self.recorder.rects}')
            self.fail(message if msg is None else f'{msg}: {message}')

    def assert_undo_redo_covered(self, change: Callable[[], None]) -> None:
        """Asserts that a change, its undo and its redo each report every pixel they change."""
        self.assert_change_covered(change, 'change')
        self.assert_change_covered(UndoStack().undo, 'undo')
        self.assert_change_covered(UndoStack().redo, 'redo')


class ImageEditTest(ChangedAreaTestCase):
    """Image content edits through borrow_image and set_image."""

    @staticmethod
    def _fill(layer: ImageLayer, rect: QRect, color: QColor) -> Callable[[], None]:
        def _change() -> None:
            with layer.borrow_image(rect) as image:
                assert image is not None
                np_image = image_data_as_numpy_8bit(image)
                np_image[rect.y():rect.y() + rect.height(), rect.x():rect.x() + rect.width()] = \
                    (color.blue(), color.green(), color.red(), color.alpha())
        return _change

    def test_borrow_image_on_untransformed_layer(self) -> None:
        """An edit through borrow_image on a layer with no transform, with undo and redo."""
        self.assert_undo_redo_covered(self._fill(self.background, QRect(5, 5, 12, 9), QColor(255, 0, 0)))

    def test_borrow_image_on_translated_layer(self) -> None:
        """An edit through borrow_image on a translated layer, with undo and redo."""
        self.assert_undo_redo_covered(self._fill(self.translated, QRect(4, 3, 10, 8), QColor(0, 255, 0)))

    def test_borrow_image_on_rotated_layer(self) -> None:
        """An edit through borrow_image on a scaled, rotated layer inside a group, with undo and redo."""
        self.assert_undo_redo_covered(self._fill(self.rotated, QRect(20, 10, 10, 8), QColor(0, 0, 255)))

    def test_set_image_same_size(self) -> None:
        """Replacing a translated layer's image with one the same size, with undo and redo."""
        self.assert_undo_redo_covered(lambda: setattr(self.translated, 'image', _noise_image(LAYER_SIZE, 10)))

    def test_set_image_smaller(self) -> None:
        """Replacing a translated layer's image with a smaller one clears its old area, with undo and redo."""
        self.assert_undo_redo_covered(lambda: setattr(self.translated, 'image', _noise_image(QSize(10, 10), 11)))

    def test_clear(self) -> None:
        """Clearing a rotated layer, with undo and redo."""
        self.assert_undo_redo_covered(self.rotated.clear)


class LayerPropertyTest(ChangedAreaTestCase):
    """Transform, opacity, blend mode, visibility and isolation changes."""

    def test_translate_layer(self) -> None:
        """Moving a layer changes both its old and new areas."""
        self.assert_undo_redo_covered(lambda: setattr(self.translated, 'transform',
                                                      QTransform.fromTranslate(70, 55)))

    def test_rotate_layer(self) -> None:
        """Rotating a layer inside a group changes both its old and new areas."""
        self.assert_undo_redo_covered(lambda: self.grouped.rotate(45))

    def test_opacity(self) -> None:
        """Changing a rotated layer's opacity."""
        self.assert_undo_redo_covered(lambda: setattr(self.rotated, 'opacity', 0.4))

    def test_blend_mode(self) -> None:
        """Changing a translated layer's blend mode."""
        self.assert_undo_redo_covered(lambda: setattr(self.translated, 'composition_mode', CompositeMode.DIFFERENCE))

    def test_hide_layer(self) -> None:
        """Hiding and showing a rotated layer."""
        self.assert_undo_redo_covered(lambda: setattr(self.rotated, 'visible', False))

    def test_hide_group(self) -> None:
        """Hiding and showing a group."""
        self.assert_undo_redo_covered(lambda: setattr(self.group, 'visible', False))

    def test_show_layer_in_hidden_group(self) -> None:
        """Showing a hidden layer inside a hidden group shows the group too."""
        self.rotated.visible = False
        self.group.visible = False
        self.assert_undo_redo_covered(lambda: setattr(self.rotated, 'visible', True))

    def test_group_opacity_and_mode(self) -> None:
        """Changing a group's opacity and blend mode."""
        self.assert_undo_redo_covered(lambda: setattr(self.group, 'opacity', 0.5))
        self.assert_undo_redo_covered(lambda: setattr(self.group, 'composition_mode', CompositeMode.MULTIPLY))

    def test_isolate(self) -> None:
        """Turning off isolation on a group with a blend mode in it."""
        self.grouped.composition_mode = CompositeMode.DIFFERENCE
        self.assert_undo_redo_covered(lambda: setattr(self.group, 'isolate', False))

    def test_group_flip(self) -> None:
        """Flipping a group moves each layer inside it."""
        self.assert_undo_redo_covered(self.group.flip_horizontal)
        self.assert_undo_redo_covered(self.group.flip_vertical)

    def test_signals_delayed(self) -> None:
        """Changes made while all_signals_delayed holds back signals are reported when it exits."""
        def _change() -> None:
            with self.image_stack.layer_stack.all_signals_delayed():
                self.translated.set_transform(QTransform.fromTranslate(75, 2))
                with self.rotated.borrow_image(QRect(0, 0, 8, 8)) as image:
                    assert image is not None
                    image.fill(0)
                self.grouped.set_opacity(0.5)
        self.assert_change_covered(_change)


class LayerStructureTest(ChangedAreaTestCase):
    """Adding, removing and reordering layers."""

    @pytest.mark.xfail(strict=True, reason=ISSUE_210)
    def test_add_layer(self) -> None:
        """Adding a translated layer, with undo and redo."""
        self.assert_undo_redo_covered(lambda: self.image_stack.create_layer(
            'added', _noise_image(LAYER_SIZE, 20), transform=QTransform.fromTranslate(50, 40)))

    @pytest.mark.xfail(strict=True, reason=ISSUE_210)
    def test_remove_layer(self) -> None:
        """Removing a layer from a group, with undo and redo."""
        self.assert_undo_redo_covered(lambda: self.image_stack.remove_layer(self.grouped))

    @pytest.mark.xfail(strict=True, reason=ISSUE_210)
    def test_reorder_within_group(self) -> None:
        """Moving a layer within its group changes where they overlap."""
        self.grouped.transform = QTransform.fromTranslate(65, 25)
        self.assert_undo_redo_covered(lambda: self.image_stack.move_layer(self.grouped, self.group, 0))

    @pytest.mark.xfail(strict=True, reason=ISSUE_210)
    def test_move_into_group(self) -> None:
        """Moving a layer into a group changes its place in the stack."""
        self.translated.transform = QTransform.fromTranslate(65, 25)
        self.assert_undo_redo_covered(lambda: self.image_stack.move_layer(self.translated, self.group, 0))


class NonIsolatedGroupTest(ChangedAreaTestCase):
    """Changes to a non-isolated group's bounds."""

    def setUp(self) -> None:
        super().setUp()
        self.group.set_isolate(False)

    def test_group_bounds_shrink(self) -> None:
        """Rotating a layer out past the group's bounds, then undoing it, shrinks the group's bounds."""
        self.assert_undo_redo_covered(lambda: self.grouped.rotate(45))

    def test_crop_layer_in_group(self) -> None:
        """Cropping the layer that sets the group's bounds shrinks them."""
        self.assert_change_covered(lambda: self.rotated.crop_to_bounds(QRect(5, 5, 20, 15)))


class OtherChangeTest(ChangedAreaTestCase):
    """Text layer edits, MyPaint strokes, and crop and resize."""

    def test_text_layer_edit(self) -> None:
        """Shrinking a translated text layer with a filled background clears its old area."""
        text_rect = TextRect()
        text_rect.text = 'text'
        text_rect.fill_background = True
        text_rect.background_color = QColor(200, 30, 30)
        text_rect.size = QSize(50, 30)
        text_layer = self.image_stack.create_text_layer(text_rect)
        text_layer.transform = QTransform.fromTranslate(30, 40)
        edited = TextRect(text_rect)
        edited.size = QSize(20, 12)
        edited.background_color = QColor(30, 30, 200)
        self.assert_undo_redo_covered(lambda: setattr(text_layer, 'text_rect', edited))

    def test_mypaint_stroke(self) -> None:
        """A MyPaint stroke on a rotated layer writes its tiles back through borrow_image."""
        # pylint: disable-next=import-outside-toplevel
        from src.image.mypaint.mypaint_layer_surface import MyPaintLayerSurface
        surface = MyPaintLayerSurface(self.rotated)
        surface.brush.color = QColor(0, 0, 0)

        def _stroke() -> None:
            surface.start_stroke()
            for x, y in ((5.0, 5.0), (20.0, 15.0), (35.0, 25.0)):
                surface.basic_stroke_to(x, y)
            surface.end_stroke()
        self.assert_undo_redo_covered(_stroke)

    def test_crop_layer(self) -> None:
        """Cropping a rotated layer to bounds, with undo and redo."""
        self.assert_undo_redo_covered(lambda: self.rotated.crop_to_bounds(QRect(5, 5, 20, 15)))

    def test_resize_canvas(self) -> None:
        """Growing the canvas and offsetting its content, with undo and redo."""
        self.assert_undo_redo_covered(lambda: self.image_stack.resize_canvas(QSize(140, 100), 10, 6))
