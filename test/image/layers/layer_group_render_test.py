"""Characterization tests for LayerGroup.render: exact pixels for each compositing option and render argument.

Expected images come from `_composite`, which draws with QPainter or a mode's custom composite op directly, so they
don't go through Layer.render or LayerGroup.render. For the HSL modes the expected image comes from the same op the
renderer calls, so these tests check what that op is given, not its arithmetic.

Each test that renders the whole stack also compares tiled region renders with the full render.
"""
import sys
import unittest
from typing import Optional

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QImage, QPainter, QTransform
from PySide6.QtWidgets import QApplication

from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.ui.image_viewer import ImageViewer
from src.util.visual.image_utils import create_transparent_image, image_data_as_numpy_8bit
from test.base_test_case import IntraPaintTestCase
from test.render_assertions import assert_tiled_render_matches, displayed_image, full_render

app = QApplication.instance() or QApplication(sys.argv)

CANVAS_SIZE = QSize(48, 40)
CHILD_SIZE = QSize(24, 20)
# One tile size that divides the canvas width, one that divides neither dimension:
TILE_SIZES = (16, 13)
# Background alpha floors: noisy partial alpha, and fully opaque.
PARTIAL_ALPHA = 40
OPAQUE = 255

QT_MODES = tuple(mode for mode in CompositeMode if mode.qt_composite_mode() is not None)
HSL_MODES = tuple(mode for mode in CompositeMode if mode.qt_composite_mode() is None)

ISSUE_132 = ('https://github.com/centuryglass/IntraPaint/issues/132: a non-isolated group composites the content '
             'beneath it over itself, and should render as isolated below full opacity or outside Normal mode')
ISSUE_151 = ('https://github.com/centuryglass/IntraPaint/issues/151: HSL blend modes change base pixels outside the '
             'layer')


def _noise_image(size: QSize, seed: int, min_alpha: int = PARTIAL_ALPHA) -> QImage:
    """Returns a premultiplied image of random colors, with random alpha no lower than min_alpha."""
    rng = np.random.default_rng(seed)
    alpha = rng.integers(min_alpha, 256, (size.height(), size.width()), dtype=np.uint16)
    color = rng.integers(0, 256, (size.height(), size.width(), 3), dtype=np.uint16)
    pixels = np.empty((size.height(), size.width(), 4), dtype=np.uint8)
    pixels[:, :, :3] = color * alpha[:, :, np.newaxis] // 255
    pixels[:, :, 3] = alpha
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    np.copyto(image_data_as_numpy_8bit(image), pixels)
    return image


def _composite(base: QImage, top: QImage, offset: QPoint, mode: CompositeMode = CompositeMode.NORMAL,
               opacity: float = 1.0) -> None:
    """Draws top onto base with its top left corner at offset, the way a pixel-aligned layer composites."""
    qt_mode = mode.qt_composite_mode()
    if qt_mode is None:
        bounds = QRect(offset, top.size()).intersected(QRect(QPoint(), base.size()))
        mode.custom_composite_op()(top, base, opacity, QTransform.fromTranslate(offset.x(), offset.y()), bounds)
        return
    painter = QPainter(base)
    painter.setOpacity(opacity)
    painter.setCompositionMode(qt_mode)
    painter.drawImage(offset, top)
    painter.end()


class GroupRenderTestCase(IntraPaintTestCase):
    """Builds small image stacks out of noisy, partly transparent layers at whole-pixel offsets."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(CANVAS_SIZE, CANVAS_SIZE, QSize(8, 8), CANVAS_SIZE)
        self._seed = 0

    def add_layer(self, name: str, offset: QPoint, parent: Optional[LayerGroup] = None,
                  mode: CompositeMode = CompositeMode.NORMAL, opacity: float = 1.0, size: QSize = CHILD_SIZE,
                  min_alpha: int = PARTIAL_ALPHA) -> ImageLayer:
        """Adds a noisy layer at the top of parent, or of the layer stack."""
        self._seed += 1
        layer = self.image_stack.create_layer(name, _noise_image(size, self._seed, min_alpha),
                                              layer_parent=parent or self.image_stack.layer_stack, layer_index=0)
        layer.transform = QTransform.fromTranslate(offset.x(), offset.y())
        layer.composition_mode = mode
        layer.opacity = opacity
        return layer

    def add_background(self, min_alpha: int = PARTIAL_ALPHA) -> ImageLayer:
        """Adds a noisy layer covering the canvas, at the top of the layer stack."""
        return self.add_layer('background', QPoint(), size=CANVAS_SIZE, min_alpha=min_alpha)

    def add_group(self, name: str, parent: Optional[LayerGroup] = None, isolate: bool = False,
                  mode: CompositeMode = CompositeMode.NORMAL, opacity: float = 1.0) -> LayerGroup:
        """Adds a layer group at the top of parent, or of the layer stack."""
        group = self.image_stack.create_layer_group(name, layer_parent=parent or self.image_stack.layer_stack,
                                                    layer_index=0)
        group.isolate = isolate
        group.composition_mode = mode
        group.opacity = opacity
        return group

    @staticmethod
    def offset(layer: Layer) -> QPoint:
        """Returns a pixel-aligned layer's position."""
        return layer.transform.map(QPoint())

    def canvas_with(self, *layers: ImageLayer, base: Optional[QImage] = None) -> QImage:
        """Returns the canvas with layers composited directly onto base, bottom first, in their own modes."""
        image = create_transparent_image(CANVAS_SIZE) if base is None else base.copy()
        for layer in layers:
            _composite(image, layer.image, self.offset(layer), layer.composition_mode, layer.opacity)
        return image

    def isolated(self, group: LayerGroup, *layers: ImageLayer) -> QImage:
        """Returns layers composited onto a transparent image covering the group's bounds, bottom first."""
        bounds = group.bounds
        image = create_transparent_image(bounds.size())
        for layer in layers:
            _composite(image, layer.image, self.offset(layer) - bounds.topLeft(), layer.composition_mode,
                       layer.opacity)
        return image

    def canvas_with_group(self, base: QImage, group: LayerGroup, group_image: QImage) -> QImage:
        """Returns base with an isolated group image composited at the group's bounds, in its mode and opacity."""
        image = base.copy()
        _composite(image, group_image, group.bounds.topLeft(), group.composition_mode, group.opacity)
        return image

    def assert_stack_renders(self, expected: QImage) -> None:
        """Asserts the full render matches expected, and that tiled renders match the full render."""
        self.assert_images_equal(full_render(self.image_stack), expected)
        for tile_size in TILE_SIZES:
            assert_tiled_render_matches(self.image_stack, tile_size, f'{tile_size}px tiles')


class IsolationTest(GroupRenderTestCase):
    """Tests isolated and non-isolated groups over transparent, partly transparent and opaque content."""

    def check_isolated_group(self, background_alpha: Optional[int]) -> None:
        """Asserts that an isolated group's children composite onto a transparent image before the group is drawn."""
        background = None if background_alpha is None else self.add_background(background_alpha)
        group = self.add_group('group', isolate=True)
        lower = self.add_layer('lower', QPoint(6, 4), group)
        upper = self.add_layer('upper', QPoint(14, 10), group, CompositeMode.MULTIPLY, 0.8)
        base = self.canvas_with() if background is None else self.canvas_with(background)
        self.assert_stack_renders(self.canvas_with_group(base, group, self.isolated(group, lower, upper)))

    def test_isolated_group_over_nothing(self) -> None:
        """An isolated group with nothing beneath it renders its children as they composite with each other."""
        self.check_isolated_group(None)

    def test_isolated_group_over_partial_alpha(self) -> None:
        """An isolated group's children don't blend with partly transparent content beneath the group."""
        self.check_isolated_group(PARTIAL_ALPHA)

    def test_isolated_group_over_opaque(self) -> None:
        """An isolated group's children don't blend with opaque content beneath the group."""
        self.check_isolated_group(OPAQUE)

    def test_non_isolated_group_covering_canvas(self) -> None:
        """Children of a non-isolated group that covers the canvas blend directly with the content beneath it."""
        background = self.add_background()
        group = self.add_group('group')
        cover = self.add_layer('cover', QPoint(), group, size=CANVAS_SIZE)
        multiply = self.add_layer('multiply', QPoint(14, 10), group, CompositeMode.MULTIPLY, 0.8)
        self.assert_stack_renders(self.canvas_with(background, cover, multiply))

    def test_non_isolated_group_smaller_than_canvas_over_opaque(self) -> None:
        """Children of a non-isolated group smaller than the canvas blend directly with opaque content beneath it."""
        background = self.add_background(OPAQUE)
        group = self.add_group('group')
        lower = self.add_layer('lower', QPoint(6, 4), group)
        multiply = self.add_layer('multiply', QPoint(14, 10), group, CompositeMode.MULTIPLY, 0.8)
        self.assert_stack_renders(self.canvas_with(background, lower, multiply))

    @pytest.mark.xfail(strict=True, reason=ISSUE_132)
    def test_non_isolated_group_smaller_than_canvas_over_partial_alpha(self) -> None:
        """Children of a non-isolated group smaller than the canvas blend directly with partly transparent content."""
        background = self.add_background()
        group = self.add_group('group')
        lower = self.add_layer('lower', QPoint(6, 4), group)
        multiply = self.add_layer('multiply', QPoint(14, 10), group, CompositeMode.MULTIPLY, 0.8)
        self.assert_stack_renders(self.canvas_with(background, lower, multiply))

    @pytest.mark.xfail(strict=True, reason=ISSUE_132)
    def test_non_isolated_group_below_full_opacity_renders_isolated(self) -> None:
        """A non-isolated group below full opacity renders as if it were isolated."""
        background = self.add_background(OPAQUE)
        group = self.add_group('group', opacity=0.5)
        lower = self.add_layer('lower', QPoint(6, 4), group)
        multiply = self.add_layer('multiply', QPoint(14, 10), group, CompositeMode.MULTIPLY)
        self.assert_stack_renders(self.canvas_with_group(self.canvas_with(background), group,
                                                         self.isolated(group, lower, multiply)))

    @pytest.mark.xfail(strict=True, reason=ISSUE_132)
    def test_non_isolated_group_outside_normal_mode_renders_isolated(self) -> None:
        """A non-isolated group in a mode other than Normal renders as if it were isolated."""
        background = self.add_background(OPAQUE)
        group = self.add_group('group', mode=CompositeMode.SCREEN)
        lower = self.add_layer('lower', QPoint(6, 4), group)
        multiply = self.add_layer('multiply', QPoint(14, 10), group, CompositeMode.MULTIPLY)
        self.assert_stack_renders(self.canvas_with_group(self.canvas_with(background), group,
                                                         self.isolated(group, lower, multiply)))


class GroupModeTest(GroupRenderTestCase):
    """Tests group opacity, and blend modes on groups and on the layers inside them."""

    def setUp(self) -> None:
        super().setUp()
        self.background = self.add_background()

    def test_isolated_group_opacity(self) -> None:
        """An isolated group's opacity applies once to its composited children."""
        group = self.add_group('group', isolate=True, opacity=0.4)
        lower = self.add_layer('lower', QPoint(6, 4), group, opacity=0.7)
        upper = self.add_layer('upper', QPoint(14, 10), group)
        self.assert_stack_renders(self.canvas_with_group(self.canvas_with(self.background), group,
                                                         self.isolated(group, lower, upper)))

    def test_layer_stack_opacity(self) -> None:
        """The layer stack's own opacity applies to the whole composite."""
        layer = self.add_layer('layer', QPoint(14, 10), mode=CompositeMode.OVERLAY)
        self.image_stack.layer_stack.opacity = 0.5
        expected = self.canvas_with()
        _composite(expected, self.canvas_with(self.background, layer), QPoint(), opacity=0.5)
        self.assert_stack_renders(expected)

    def check_isolated_group_modes(self, modes: tuple[CompositeMode, ...], use_subtests: bool) -> None:
        """Asserts that an isolated group composites its children in each mode."""
        group = self.add_group('group', isolate=True, opacity=0.7)
        lower = self.add_layer('lower', QPoint(6, 4), group)
        upper = self.add_layer('upper', QPoint(14, 10), group, CompositeMode.DIFFERENCE)
        for mode in modes:
            group.composition_mode = mode
            expected = self.canvas_with_group(self.canvas_with(self.background), group,
                                              self.isolated(group, lower, upper))
            if use_subtests:
                with self.subTest(mode=mode.name):
                    self.assert_stack_renders(expected)
            else:
                self.assert_stack_renders(expected)

    def test_isolated_group_in_qt_modes(self) -> None:
        """An isolated group composites in every mode QPainter supports."""
        self.check_isolated_group_modes(QT_MODES, True)

    # No subtests in the expected failures: a failed subtest fails the test outright instead of counting as one.
    @pytest.mark.xfail(strict=True, reason=ISSUE_151)
    def test_isolated_group_in_hsl_modes(self) -> None:
        """An isolated group composites in every mode with custom compositing."""
        self.check_isolated_group_modes(HSL_MODES, False)

    def check_child_modes(self, isolate: bool, modes: tuple[CompositeMode, ...], use_subtests: bool) -> None:
        """Asserts that a group's top child blends in each mode with the content beneath it.

        A transparent layer covering the canvas makes a non-isolated group take its direct compositing path.
        """
        group = self.add_group('group', isolate=isolate)
        cover = self.image_stack.create_layer('cover', layer_parent=group, layer_index=0)
        lower = self.add_layer('lower', QPoint(6, 4), group)
        upper = self.add_layer('upper', QPoint(14, 10), group, opacity=0.7)
        for mode in modes:
            upper.composition_mode = mode
            if isolate:
                expected = self.canvas_with_group(self.canvas_with(self.background), group,
                                                  self.isolated(group, cover, lower, upper))
            else:
                expected = self.canvas_with(self.background, cover, lower, upper)
            if use_subtests:
                with self.subTest(mode=mode.name):
                    self.assert_stack_renders(expected)
            else:
                self.assert_stack_renders(expected)

    def test_child_qt_modes_in_isolated_group(self) -> None:
        """A layer in an isolated group blends only with the group's other children, in every QPainter mode."""
        self.check_child_modes(True, QT_MODES, True)

    def test_child_qt_modes_in_non_isolated_group(self) -> None:
        """A layer in a non-isolated group blends with the content beneath the group, in every QPainter mode."""
        self.check_child_modes(False, QT_MODES, True)

    @pytest.mark.xfail(strict=True, reason=ISSUE_151)
    def test_child_hsl_modes_in_isolated_group(self) -> None:
        """A layer in an isolated group blends only with the group's other children, in every custom mode."""
        self.check_child_modes(True, HSL_MODES, False)

    @pytest.mark.xfail(strict=True, reason=ISSUE_151)
    def test_child_hsl_modes_in_non_isolated_group(self) -> None:
        """A layer in a non-isolated group blends with the content beneath the group, in every custom mode."""
        self.check_child_modes(False, HSL_MODES, False)


class GroupStructureTest(GroupRenderTestCase):
    """Tests nested, hidden, transparent, empty and offset groups."""

    def setUp(self) -> None:
        super().setUp()
        self.background = self.add_background()

    def test_nested_isolated_groups(self) -> None:
        """An isolated group inside another composites onto the outer group's image in its own mode and opacity."""
        outer = self.add_group('outer', isolate=True, opacity=0.8)
        outer_layer = self.add_layer('outer layer', QPoint(2, 3), outer)
        inner = self.add_group('inner', outer, isolate=True, mode=CompositeMode.SCREEN, opacity=0.6)
        inner_lower = self.add_layer('inner lower', QPoint(10, 8), inner)
        inner_upper = self.add_layer('inner upper', QPoint(20, 16), inner, CompositeMode.MULTIPLY)
        outer_image = self.isolated(outer, outer_layer)
        _composite(outer_image, self.isolated(inner, inner_lower, inner_upper),
                   inner.bounds.topLeft() - outer.bounds.topLeft(), inner.composition_mode, inner.opacity)
        self.assert_stack_renders(self.canvas_with_group(self.canvas_with(self.background), outer, outer_image))

    def test_non_isolated_group_inside_isolated_group(self) -> None:
        """A non-isolated group covering its isolated parent blends its children with the parent's other layers."""
        outer = self.add_group('outer', isolate=True, opacity=0.8)
        outer_layer = self.add_layer('outer layer', QPoint(10, 8), outer)
        inner = self.add_group('inner', outer)
        inner_lower = self.add_layer('inner lower', QPoint(6, 4), inner)
        inner_upper = self.add_layer('inner upper', QPoint(18, 14), inner, CompositeMode.MULTIPLY)
        self.assertEqual(inner.bounds, outer.bounds)
        self.assert_stack_renders(self.canvas_with_group(self.canvas_with(self.background), outer,
                                                         self.isolated(outer, outer_layer, inner_lower,
                                                                       inner_upper)))

    def check_hidden_and_transparent_children(self, isolate: bool) -> None:
        """Asserts that hidden layers and groups, and layers or groups at opacity 0, don't render inside a group.

        A transparent layer covering the canvas makes a non-isolated group take its direct compositing path.
        """
        group = self.add_group('group', isolate=isolate)
        cover = self.image_stack.create_layer('cover', layer_parent=group, layer_index=0)
        shown = self.add_layer('shown', QPoint(6, 4), group, CompositeMode.MULTIPLY)
        self.add_layer('hidden', QPoint(10, 8), group).visible = False
        self.add_layer('opacity 0', QPoint(12, 6), group, opacity=0.0)
        hidden_group = self.add_group('hidden group', group, isolate=True)
        self.add_layer('in hidden group', QPoint(4, 2), hidden_group)
        hidden_group.visible = False
        transparent_group = self.add_group('transparent group', group, opacity=0.0)
        self.add_layer('in transparent group', QPoint(8, 2), transparent_group)
        if isolate:
            expected = self.canvas_with_group(self.canvas_with(self.background), group,
                                              self.isolated(group, cover, shown))
        else:
            expected = self.canvas_with(self.background, cover, shown)
        self.assert_stack_renders(expected)

    def test_hidden_and_transparent_children_of_isolated_group(self) -> None:
        """Hidden or fully transparent children of an isolated group don't render."""
        self.check_hidden_and_transparent_children(True)

    def test_hidden_and_transparent_children_of_non_isolated_group(self) -> None:
        """Hidden or fully transparent children of a non-isolated group don't render."""
        self.check_hidden_and_transparent_children(False)

    def test_hidden_and_transparent_groups(self) -> None:
        """A hidden group, or one at opacity 0, leaves the content beneath it unchanged."""
        hidden = self.add_group('hidden', isolate=True)
        self.add_layer('in hidden', QPoint(6, 4), hidden)
        hidden.visible = False
        transparent = self.add_group('transparent', mode=CompositeMode.MULTIPLY, opacity=0.0)
        self.add_layer('in transparent', QPoint(14, 10), transparent)
        self.assert_stack_renders(self.canvas_with(self.background))

    def test_empty_groups(self) -> None:
        """Empty groups, isolated or not, leave the content beneath them unchanged."""
        self.add_group('empty')
        self.add_group('empty isolated', isolate=True, mode=CompositeMode.MULTIPLY, opacity=0.5)
        self.add_group('empty nested', self.add_group('outer', isolate=True))
        self.assert_stack_renders(self.canvas_with(self.background))

    def test_group_extending_past_canvas(self) -> None:
        """An isolated group with content past every canvas edge renders the part inside the canvas."""
        group = self.add_group('group', isolate=True, mode=CompositeMode.OVERLAY, opacity=0.6)
        top_left = self.add_layer('top left', QPoint(-10, -6), group)
        bottom_right = self.add_layer('bottom right', QPoint(36, 30), group, CompositeMode.SCREEN)
        self.assertTrue(group.bounds.contains(QRect(QPoint(), CANVAS_SIZE)))
        self.assert_stack_renders(self.canvas_with_group(self.canvas_with(self.background), group,
                                                         self.isolated(group, top_left, bottom_right)))

    def test_group_outside_canvas(self) -> None:
        """A group entirely outside the canvas leaves it unchanged."""
        group = self.add_group('group', isolate=True, mode=CompositeMode.MULTIPLY)
        self.add_layer('outside', QPoint(CANVAS_SIZE.width() + 4, -30), group)
        self.assert_stack_renders(self.canvas_with(self.background))


class RenderArgumentTest(GroupRenderTestCase):
    """Tests LayerGroup.render's arguments, called on a group directly."""

    def setUp(self) -> None:
        super().setUp()
        self.background = self.add_background(OPAQUE)
        self.group = self.add_group('group', isolate=True, mode=CompositeMode.MULTIPLY, opacity=0.7)
        self.lower = self.add_layer('lower', QPoint(6, 4), self.group)
        self.upper = self.add_layer('upper', QPoint(14, 10), self.group, CompositeMode.SCREEN, 0.8)
        self.top = self.add_layer('top', QPoint(20, 2), opacity=0.5)

    def expected_group_render(self, base: QImage) -> QImage:
        """Returns base with the group composited onto it at its own position."""
        if not self.group.isolate:
            return self.canvas_with(self.lower, self.upper, base=base)
        return self.canvas_with_group(base, self.group, self.isolated(self.group, self.lower, self.upper))

    def make_non_isolated(self) -> None:
        """Turns off isolation, at Normal mode and full opacity, where children blend with the content beneath."""
        self.group.isolate = False
        self.group.composition_mode = CompositeMode.NORMAL
        self.group.opacity = 1.0

    def test_image_bounds(self) -> None:
        """Only the pixels inside image_bounds change, and they match an unbounded render."""
        for isolate in (True, False):
            if not isolate:
                self.make_non_isolated()
            full = self.expected_group_render(self.background.image)
            for bounds in (QRect(10, 6, 13, 9), QRect(-5, 20, 30, 40), QRect(QPoint(), CANVAS_SIZE)):
                with self.subTest(isolate=isolate, bounds=bounds):
                    rendered = self.background.image
                    self.group.render(rendered, image_bounds=bounds)
                    expected = self.background.image
                    painter = QPainter(expected)
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                    clipped = bounds.intersected(QRect(QPoint(), CANVAS_SIZE))
                    painter.drawImage(clipped.topLeft(), full.copy(clipped))
                    painter.end()
                    self.assert_images_equal(rendered, expected)

    def test_translation(self) -> None:
        """A translation moves the group's content, and a fractional translation rounds to whole pixels."""
        for transform, offset in ((QTransform.fromTranslate(7, -5), QPoint(7, -5)),
                                  (QTransform.fromTranslate(7.4, -5.6), QPoint(7, -6))):
            with self.subTest(dx=transform.dx(), dy=transform.dy()):
                rendered = self.background.image
                self.group.render(rendered, transform)
                expected = self.background.image
                _composite(expected, self.isolated(self.group, self.lower, self.upper),
                           self.group.bounds.topLeft() + offset, self.group.composition_mode, self.group.opacity)
                self.assert_images_equal(rendered, expected)

    def test_non_translation_transforms_raise(self) -> None:
        """Any transform beyond a translation raises ValueError."""
        for name, transform in (('scale', QTransform.fromScale(2, 2)), ('rotate', QTransform().rotate(30)),
                                ('shear', QTransform().shear(0.2, 0)),
                                ('translate and scale', QTransform.fromTranslate(3, 4).scale(1.5, 1.0)),
                                ('flip', QTransform.fromScale(-1, 1).translate(-CANVAS_SIZE.width(), 0))):
            with self.subTest(transform=name):
                with self.assertRaises(ValueError):
                    self.group.render(create_transparent_image(CANVAS_SIZE), transform)

    def test_z_max(self) -> None:
        """z_max leaves out layers above it, and a group renders the children at or below it in its mode."""
        layer_stack = self.image_stack.layer_stack
        background = self.canvas_with(self.background)
        lower_only = self.canvas_with_group(background, self.group, self.isolated(self.group, self.lower))
        cases = ((self.background.z_value, background), (self.lower.z_value, lower_only),
                 (self.upper.z_value, self.expected_group_render(background)),
                 (self.group.z_value, self.expected_group_render(background)),
                 (self.top.z_value, self.canvas_with(self.top, base=self.expected_group_render(background))))
        for z_max, expected in cases:
            with self.subTest(z_max=z_max):
                rendered = create_transparent_image(CANVAS_SIZE)
                layer_stack.render(rendered, QTransform(), z_max=z_max)
                self.assert_images_equal(rendered, expected)

    def test_render_to_new_image_z_max(self) -> None:
        """A z_max render of a group into a new image, as ImageStack flattening does, covers the group's bounds."""
        bounds = self.group.bounds
        lower_only = create_transparent_image(bounds.size())
        _composite(lower_only, self.isolated(self.group, self.lower), QPoint(), self.group.composition_mode,
                   self.group.opacity)
        self.assert_images_equal(self.group.render_to_new_image(z_max=self.lower.z_value), lower_only)

    def test_image_adjuster(self) -> None:
        """image_adjuster replaces each visible image layer's image, and is never called for groups."""
        hidden = self.add_layer('hidden', QPoint(2, 2), self.group)
        hidden.visible = False
        adjusted: list[str] = []

        def _swap_red_and_blue(layer: Layer, image: QImage) -> QImage:
            adjusted.append(layer.name)
            return image.rgbSwapped()

        rendered = create_transparent_image(CANVAS_SIZE)
        self.image_stack.layer_stack.render(rendered, QTransform(), image_adjuster=_swap_red_and_blue)
        self.assertCountEqual(adjusted, ['background', 'lower', 'upper', 'top'])
        expected = self.canvas_with()
        _composite(expected, self.background.image.rgbSwapped(), QPoint())
        group_image = create_transparent_image(self.group.bounds.size())
        for layer in (self.lower, self.upper):
            _composite(group_image, layer.image.rgbSwapped(), self.offset(layer) - self.group.bounds.topLeft(),
                       layer.composition_mode, layer.opacity)
        expected = self.canvas_with_group(expected, self.group, group_image)
        _composite(expected, self.top.image.rgbSwapped(), self.offset(self.top), opacity=self.top.opacity)
        self.assert_images_equal(rendered, expected)

    def test_returned_mask(self) -> None:
        """returned_mask gets every rendered child's image, ignoring opacity and mode, and doesn't change the render."""
        hidden = self.add_layer('hidden', QPoint(2, 2), self.group)
        hidden.visible = False
        expected_mask = self.canvas_with()
        for layer in (self.lower, self.upper):
            _composite(expected_mask, layer.image, self.offset(layer))
        for isolate in (True, False):
            if not isolate:
                self.make_non_isolated()
            with self.subTest(isolate=isolate):
                unmasked = self.background.image
                self.group.render(unmasked)
                rendered = self.background.image
                mask = create_transparent_image(CANVAS_SIZE)
                self.group.render(rendered, returned_mask=mask)
                self.assert_images_equal(mask, expected_mask)
                self.assert_images_equal(rendered, unmasked)


class CachedCompositeTest(GroupRenderTestCase):
    """Tests a group's cached image and pixmap, and what the view displays, after renders are flushed."""

    def setUp(self) -> None:
        super().setUp()
        self.background = self.add_background()
        self.group = self.add_group('group', isolate=True, mode=CompositeMode.MULTIPLY, opacity=0.7)
        self.lower = self.add_layer('lower', QPoint(6, 4), self.group)
        self.upper = self.add_layer('upper', QPoint(14, 10), self.group, CompositeMode.SCREEN, 0.8)

    def expected_cache(self) -> QImage:
        """Returns the group composited in its mode and opacity onto a transparent image covering its bounds."""
        image = create_transparent_image(self.group.bounds.size())
        _composite(image, self.isolated(self.group, self.lower, self.upper), QPoint(), self.group.composition_mode,
                   self.group.opacity)
        return image

    def assert_cache_current(self) -> None:
        """Flushes renders, then asserts the group's image, its pixmap and the layer stack's image are current."""
        self.image_stack.flush_render()
        self.assert_images_equal(self.group.get_qimage(), self.expected_cache())
        self.assert_images_equal(self.group.pixmap.toImage(), self.expected_cache())
        self.assert_images_equal(self.image_stack.layer_stack.get_qimage(), full_render(self.image_stack))

    def test_cache_after_child_edit(self) -> None:
        """After an edit to a child is flushed, the group's cached image and pixmap show it."""
        self.assert_cache_current()
        with self.lower.borrow_image(QRect(2, 2, 9, 7)) as image:
            image.fill(0)
        self.assert_cache_current()

    def test_cache_after_child_property_changes(self) -> None:
        """After a child's opacity, mode or visibility changes and is flushed, the group's cached image shows it."""
        self.assert_cache_current()
        self.upper.opacity = 0.3
        self.assert_cache_current()
        self.upper.composition_mode = CompositeMode.DARKEN
        self.assert_cache_current()
        self.upper.visible = False
        self.assert_images_equal(self.group.get_qimage(), self.expected_cache())

    def test_cache_after_group_opacity_change(self) -> None:
        """After the group's own opacity changes and is flushed, its cached image shows it."""
        self.assert_cache_current()
        self.group.opacity = 0.3
        self.assert_cache_current()

    def test_cache_after_group_mode_change(self) -> None:
        """After the group's own composition mode changes and is flushed, its cached image shows it.

        Hue is used because, unlike Qt's modes, it changes the composite even on the cache's transparent base.
        """
        self.assert_cache_current()
        self.group.composition_mode = CompositeMode.HUE
        self.assert_cache_current()

    def test_view_displays_groups(self) -> None:
        """The view shows the full render of a stack with nested groups."""
        inner = self.add_group('inner', self.group, mode=CompositeMode.OVERLAY, opacity=0.5)
        self.add_layer('inner layer', QPoint(-4, 20), inner)
        viewer = ImageViewer(None, self.image_stack, use_keybindings=False)
        self.image_stack.flush_render()
        self.assert_images_equal(displayed_image(viewer, self.image_stack), full_render(self.image_stack))
        with self.upper.borrow_image(QRect(0, 0, 12, 12)) as image:
            image.fill(0)
        self.image_stack.flush_render()
        self.assert_images_equal(displayed_image(viewer, self.image_stack), full_render(self.image_stack))


class ImageStackQImageTest(GroupRenderTestCase):
    """Tests ImageStack.qimage and the renders that generation and filters read."""

    def setUp(self) -> None:
        super().setUp()
        self.background = self.add_background()
        self.group = self.add_group('group', isolate=True, mode=CompositeMode.OVERLAY, opacity=0.7)
        self.lower = self.add_layer('lower', QPoint(-6, 4), self.group)
        self.upper = self.add_layer('upper', QPoint(14, 10), self.group, CompositeMode.MULTIPLY, 0.8)
        self.top = self.add_layer('top', QPoint(30, 26), opacity=0.5)

    def expected_canvas(self) -> QImage:
        """Returns the expected composite of the whole canvas."""
        group_composite = self.canvas_with_group(self.canvas_with(self.background), self.group,
                                                 self.isolated(self.group, self.lower, self.upper))
        return self.canvas_with(self.top, base=group_composite)

    def test_qimage(self) -> None:
        """qimage() is the canvas composite, and follows edits once they're flushed."""
        self.assert_images_equal(self.image_stack.qimage(), self.expected_canvas())
        with self.upper.borrow_image(QRect(0, 0, 12, 12)) as image:
            image.fill(0)
        self.image_stack.flush_render()
        self.assert_images_equal(self.image_stack.qimage(), self.expected_canvas())

    def test_qimage_uncropped(self) -> None:
        """qimage(crop_to_image=False) covers all layer content, including content past the canvas edges."""
        bounds = self.image_stack.layer_stack.bounds
        self.assertEqual(bounds.topLeft(), QPoint(-6, 0))
        self.assertEqual(bounds.bottomRight(), self.top.transformed_bounds.bottomRight())
        expected = create_transparent_image(bounds.size())
        _composite(expected, self.background.image, -bounds.topLeft())
        _composite(expected, self.isolated(self.group, self.lower, self.upper),
                   self.group.bounds.topLeft() - bounds.topLeft(), self.group.composition_mode, self.group.opacity)
        _composite(expected, self.top.image, self.offset(self.top) - bounds.topLeft(), opacity=self.top.opacity)
        self.assert_images_equal(self.image_stack.qimage(crop_to_image=False), expected)

    def test_qimage_with_hidden_layer_stack(self) -> None:
        """qimage() is fully transparent while the layer stack is hidden."""
        self.image_stack.layer_stack.visible = False
        self.image_stack.flush_render()
        self.assert_images_equal(self.image_stack.qimage(), create_transparent_image(CANVAS_SIZE))

    def test_generation_area_content(self) -> None:
        """The generation area's content is that area of the canvas composite."""
        area = QRect(5, 7, 30, 24)
        self.image_stack.generation_area = area
        self.assert_images_equal(self.image_stack.qimage_generation_area_content(), self.expected_canvas().copy(area))

    def test_translated_render_with_image_adjuster(self) -> None:
        """A region render with an image adjuster, as filter previews use, adjusts every layer's image."""
        region = QRect(4, 6, 29, 21)

        def _swap_red_and_blue(_: Layer, image: QImage) -> QImage:
            return image.rgbSwapped()

        rendered = create_transparent_image(region.size())
        self.image_stack.render(rendered, QTransform.fromTranslate(-region.x(), -region.y()),
                                image_adjuster=_swap_red_and_blue)
        group_image = create_transparent_image(self.group.bounds.size())
        for layer in (self.lower, self.upper):
            _composite(group_image, layer.image.rgbSwapped(), self.offset(layer) - self.group.bounds.topLeft(),
                       layer.composition_mode, layer.opacity)
        expected = self.canvas_with()
        _composite(expected, self.background.image.rgbSwapped(), QPoint())
        expected = self.canvas_with_group(expected, self.group, group_image)
        _composite(expected, self.top.image.rgbSwapped(), self.offset(self.top), opacity=self.top.opacity)
        self.assert_images_equal(rendered, expected.copy(region))


if __name__ == '__main__':
    unittest.main()
