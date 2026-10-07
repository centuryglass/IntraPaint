"""Tests that layer groups saved to .ora and loaded again render the same pixels as the original stack.

Each test saves a stack built from the `layer_group_render_test` helpers, loads it into a second stack, and compares
both the full renders and each layer's compositing properties. Layer names, awkward file names and text layers are
covered in `open_raster_test`.
"""
import os
import sys
import tempfile
import zipfile

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from src.image.composite_mode import CompositeMode
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.transform_layer import TransformLayer
from src.image.open_raster import MERGED_IMAGE_FILE_NAME, read_ora_image, save_ora_image
from test.image.layers.layer_group_render_test import CANVAS_SIZE, OPAQUE, GroupRenderTestCase
from test.render_assertions import full_render

app = QApplication.instance() or QApplication(sys.argv)

ORA_FILE_NAME = 'groups.ora'


class OpenRasterGroupTest(GroupRenderTestCase):
    """Round-trips layer groups through .ora files."""

    def setUp(self) -> None:
        super().setUp()
        self.loaded_stack = ImageStack(CANVAS_SIZE, CANVAS_SIZE, CANVAS_SIZE, CANVAS_SIZE)
        self.background = self.add_background()

    def round_trip(self) -> None:
        """Saves the image stack to a temporary .ora file and loads it into self.loaded_stack."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ora_path = os.path.join(temp_dir, ORA_FILE_NAME)
            save_ora_image(self.image_stack, ora_path, '')
            read_ora_image(self.loaded_stack, ora_path)

    def assert_layers_match(self, expected: Layer, actual: Layer) -> None:
        """Asserts that two layers and everything in them have the same compositing properties and pixels."""
        name = expected.name
        self.assertEqual(type(expected), type(actual), f'type of "{name}"')
        self.assertEqual(name, actual.name)
        self.assertEqual(expected.get_visible(), actual.get_visible(), f'visibility of "{name}"')
        self.assertEqual(expected.opacity, actual.opacity, f'opacity of "{name}"')
        self.assertEqual(expected.composition_mode, actual.composition_mode, f'mode of "{name}"')
        if isinstance(expected, LayerGroup):
            assert isinstance(actual, LayerGroup)
            if expected is not self.image_stack.layer_stack:
                self.assertEqual(expected.isolate, actual.isolate, f'isolation of "{name}"')
            self.assertEqual([child.name for child in expected.child_layers],
                             [child.name for child in actual.child_layers], f'children of "{name}"')
            for expected_child, actual_child in zip(expected.child_layers, actual.child_layers):
                self.assert_layers_match(expected_child, actual_child)
        else:
            assert isinstance(expected, TransformLayer) and isinstance(actual, TransformLayer)
            self.assertEqual(expected.transform, actual.transform, f'transform of "{name}"')
            self.assert_images_equal(actual.image, expected.image, f'pixels of "{name}"')

    def assert_round_trip_renders_same(self) -> None:
        """Round-trips the stack, then asserts the loaded stack matches it layer by layer and in its full render."""
        self.round_trip()
        self.assert_layers_match(self.image_stack.layer_stack, self.loaded_stack.layer_stack)
        self.loaded_stack.flush_render()
        self.assert_images_equal(full_render(self.loaded_stack), full_render(self.image_stack))
        self.assert_images_equal(self.loaded_stack.qimage(), full_render(self.image_stack), 'loaded qimage()')

    def test_isolated_and_non_isolated_groups(self) -> None:
        """Isolated and non-isolated groups keep their isolation, opacity, mode and children's modes."""
        isolated = self.add_group('isolated', isolate=True, mode=CompositeMode.MULTIPLY, opacity=0.7)
        self.add_layer('isolated lower', QPoint(6, 4), isolated)
        self.add_layer('isolated upper', QPoint(14, 10), isolated, CompositeMode.SCREEN, 0.8)
        non_isolated = self.add_group('non-isolated', opacity=0.6)
        self.add_layer('cover', QPoint(), non_isolated, size=CANVAS_SIZE, opacity=0.5)
        self.add_layer('multiply', QPoint(10, 8), non_isolated, CompositeMode.MULTIPLY)
        self.assert_round_trip_renders_same()

    def test_group_modes(self) -> None:
        """Groups in every composition mode, with children in every mode, render the same after loading."""
        modes = list(CompositeMode)
        for index, mode in enumerate(modes):
            group = self.add_group(f'group {mode.name}', isolate=index % 2 == 0, mode=mode, opacity=0.9)
            self.add_layer(f'lower {mode.name}', QPoint(index, index // 2), group)
            self.add_layer(f'upper {mode.name}', QPoint(20 - index, 10), group, modes[-1 - index], 0.8)
        self.assert_round_trip_renders_same()

    def test_hidden_and_transparent_layers_and_groups(self) -> None:
        """Hidden and fully transparent layers and groups stay hidden, and keep their content for when they're shown."""
        group = self.add_group('group', isolate=True)
        self.add_layer('shown', QPoint(6, 4), group, CompositeMode.OVERLAY)
        self.add_layer('hidden', QPoint(10, 8), group).visible = False
        self.add_layer('opacity 0', QPoint(12, 6), group, opacity=0.0)
        hidden_group = self.add_group('hidden group', group, isolate=True, mode=CompositeMode.SCREEN)
        self.add_layer('in hidden group', QPoint(4, 2), hidden_group)
        self.add_layer('hidden in hidden group', QPoint(14, 12), hidden_group).visible = False
        hidden_group.visible = False
        transparent_group = self.add_group('transparent group', group, isolate=True, opacity=0.0)
        self.add_layer('in transparent group', QPoint(8, 2), transparent_group)
        self.assert_round_trip_renders_same()
        for stack in (self.image_stack, self.loaded_stack):
            for layer in stack.layer_stack.recursive_child_layers:
                layer.set_visible(True)
                if layer.opacity == 0.0:
                    layer.set_opacity(1.0)
            stack.flush_render()
        self.assert_images_equal(full_render(self.loaded_stack), full_render(self.image_stack),
                                 'after showing every layer')

    def test_nested_groups(self) -> None:
        """Nested groups with content past the canvas edges keep their structure and render the same."""
        outer = self.add_group('outer', isolate=True, mode=CompositeMode.HARD_LIGHT, opacity=0.8)
        self.add_layer('outer layer', QPoint(-10, -6), outer)
        middle = self.add_group('middle', outer, isolate=True, mode=CompositeMode.SCREEN, opacity=0.6)
        self.add_layer('middle layer', QPoint(36, 30), middle, CompositeMode.MULTIPLY)
        inner = self.add_group('inner', middle)
        self.add_layer('inner lower', QPoint(10, 8), inner)
        self.add_layer('inner upper', QPoint(20, 16), inner, CompositeMode.DIFFERENCE, 0.7)
        self.add_group('empty', inner, isolate=True)
        self.assert_round_trip_renders_same()

    def test_layer_stack_opacity_and_mode(self) -> None:
        """The layer stack's own opacity and mode are restored on load."""
        group = self.add_group('group', isolate=True, mode=CompositeMode.OVERLAY)
        self.add_layer('layer', QPoint(14, 10), group)
        self.image_stack.layer_stack.opacity = 0.5
        self.image_stack.layer_stack.composition_mode = CompositeMode.SCREEN
        self.assert_round_trip_renders_same()

    def test_merged_image_matches_render(self) -> None:
        """The archive's merged image, which other programs read, is the full render of the stack."""
        group = self.add_group('group', isolate=True, mode=CompositeMode.COLOR_BURN, opacity=0.7)
        self.add_layer('lower', QPoint(6, 4), group, min_alpha=OPAQUE)
        self.add_layer('upper', QPoint(14, 10), group, CompositeMode.SCREEN, 0.8)
        with tempfile.TemporaryDirectory() as temp_dir:
            ora_path = os.path.join(temp_dir, ORA_FILE_NAME)
            save_ora_image(self.image_stack, ora_path, '')
            with zipfile.ZipFile(ora_path) as zip_file:
                merged = QImage.fromData(zip_file.read(MERGED_IMAGE_FILE_NAME))
        self.assertFalse(merged.isNull())
        self.assert_images_equal(merged, full_render(self.image_stack))

    def test_active_layer_above_nested_group(self) -> None:
        """A selected layer stays active after loading when a nested group comes after it in the same group."""
        group = self.add_group('group', isolate=True)
        nested = self.add_group('nested', group)
        self.add_layer('in nested', QPoint(2, 2), nested)
        active = self.add_layer('active', QPoint(6, 4), group)
        self.assertEqual(group.child_layers, [active, nested])
        self.image_stack.active_layer = active
        self.round_trip()
        self.assertEqual(self.loaded_stack.active_layer.name, 'active')

    def test_group_extending_past_canvas_keeps_offsets(self) -> None:
        """Layers inside a group keep their offsets, including negative ones, so the group keeps its bounds."""
        group = self.add_group('group', isolate=True, mode=CompositeMode.MULTIPLY)
        self.add_layer('top left', QPoint(-10, -6), group)
        self.add_layer('bottom right', QPoint(36, 30), group)
        self.round_trip()
        loaded_group = self.loaded_stack.layer_stack.child_layers[0]
        self.assertEqual(loaded_group.name, 'group')
        self.assertEqual(loaded_group.bounds, group.bounds)
        self.assertEqual(group.bounds, QRect(-10, -6, 70, 56))
