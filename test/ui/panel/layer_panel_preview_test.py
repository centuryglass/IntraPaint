"""Tests that layer panel previews of layer groups show the group's flushed render.

A group's preview is its cached image, cropped to content: children composited onto a transparent image covering the
group's bounds, then drawn there in the group's own mode and opacity. Expected images come from the
`layer_group_render_test` helpers, which composite with QPainter or a mode's custom op directly instead of going
through LayerGroup.render.

Previews update on a timer after the layer signals a content change. Tests run the pending update directly with
`flush_preview`.
"""
import sys
from contextlib import nullcontext
from typing import Optional

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.ui.panel.layer_ui.layer_panel import LayerPanel
from src.ui.panel.layer_ui.layer_widget import LayerWidget
from src.util.visual.image_utils import create_transparent_image, crop_to_content
from test.image.layers.layer_group_render_test import CANVAS_SIZE, HSL_MODES, ISSUE_151, QT_MODES, \
    GroupRenderTestCase, _composite
from test.render_assertions import full_render

app = QApplication.instance() or QApplication(sys.argv)

ISSUE_HIDDEN_GROUP_PREVIEW = ('https://github.com/centuryglass/IntraPaint/issues/208: a hidden group\'s layer '
                              'panel preview is blank, while a hidden image layer\'s preview shows its content')


class LayerPanelGroupPreviewTest(GroupRenderTestCase):
    """Compares group previews in a LayerPanel with independently composited group images."""

    def setUp(self) -> None:
        super().setUp()
        self.background = self.add_background()
        self.group = self.add_group('group', isolate=True, mode=CompositeMode.MULTIPLY, opacity=0.7)
        self.lower = self.add_layer('lower', QPoint(6, 4), self.group)
        self.upper = self.add_layer('upper', QPoint(14, 10), self.group, CompositeMode.SCREEN, 0.8)
        self.panel: Optional[LayerPanel] = None

    def tearDown(self) -> None:
        if self.panel is not None:
            self.panel.close()
        super().tearDown()

    def open_panel(self) -> None:
        """Creates the panel for the current layer stack, and flushes pending renders."""
        self.image_stack.flush_render()
        self.panel = LayerPanel(self.image_stack)

    def widget_for(self, layer: Layer) -> LayerWidget:
        """Returns the one LayerWidget showing a layer."""
        assert self.panel is not None
        widgets = [widget for widget in self.panel.findChildren(LayerWidget) if widget.layer is layer]
        self.assertEqual(len(widgets), 1, f'widgets for {layer.name}')
        return widgets[0]

    @staticmethod
    def flush_preview(widget: LayerWidget) -> None:
        """Runs the widget's scheduled preview update now, if one is pending."""
        # pylint: disable=protected-access
        if widget._preview_render_timer.isActive():
            widget._update_layer_preview_image()

    def preview(self, layer: Layer) -> QImage:
        """Returns the image a layer's preview draws, after any pending render and preview update."""
        self.image_stack.flush_render()
        widget = self.widget_for(layer)
        self.flush_preview(widget)
        return widget._layer_image  # pylint: disable=protected-access

    def group_image(self, group: LayerGroup, *children: ImageLayer | tuple[LayerGroup, QImage]) -> QImage:
        """Returns a group's expected cached image: children composited in order, then the group's mode and opacity.

        A child given as (group, image) is a nested group, drawn from its own expected image.
        """
        bounds = group.bounds
        children_image = create_transparent_image(bounds.size())
        for child in children:
            if isinstance(child, tuple):
                nested, nested_image = child
                _composite(children_image, nested_image, nested.bounds.topLeft() - bounds.topLeft(),
                           nested.composition_mode, nested.opacity)
            else:
                _composite(children_image, child.image, self.offset(child) - bounds.topLeft(),
                           child.composition_mode, child.opacity)
        image = create_transparent_image(bounds.size())
        _composite(image, children_image, QPoint(), group.composition_mode, group.opacity)
        return image

    def nested_children_image(self, group: LayerGroup, *children: ImageLayer) -> QImage:
        """Returns a nested group's image as its parent draws it: children only, before its own mode and opacity."""
        bounds = group.bounds
        image = create_transparent_image(bounds.size())
        for child in children:
            _composite(image, child.image, self.offset(child) - bounds.topLeft(), child.composition_mode,
                       child.opacity)
        return image

    def assert_preview_shows(self, group: LayerGroup, expected: QImage) -> None:
        """Asserts that a group's preview shows expected cropped to content, and that it matches the cached image."""
        preview = self.preview(group)
        self.assert_images_equal(preview, crop_to_content(expected), f'preview of {group.name}')
        self.assert_images_equal(preview, crop_to_content(group.get_qimage()), f'cached image of {group.name}')

    def test_isolated_group_preview(self) -> None:
        """An isolated group's preview shows its children composited together, in the group's mode and opacity."""
        self.open_panel()
        self.assert_preview_shows(self.group, self.group_image(self.group, self.lower, self.upper))

    def test_non_isolated_group_preview(self) -> None:
        """A non-isolated group's preview shows its children without the content beneath the group."""
        self.group.isolate = False
        self.open_panel()
        self.assert_preview_shows(self.group, self.group_image(self.group, self.lower, self.upper))

    def test_group_mode_previews(self) -> None:
        """A group's preview applies the group's own composition mode, for every mode."""
        self.open_panel()
        for mode in CompositeMode:
            with self.subTest(mode=mode.name):
                self.group.composition_mode = mode
                self.assert_preview_shows(self.group, self.group_image(self.group, self.lower, self.upper))

    def check_child_mode_previews(self, modes: tuple[CompositeMode, ...], use_subtests: bool) -> None:
        """Asserts that a group's preview composites a child in each mode."""
        self.open_panel()
        for mode in modes:
            with self.subTest(mode=mode.name) if use_subtests else nullcontext():
                self.upper.composition_mode = mode
                self.assert_preview_shows(self.group, self.group_image(self.group, self.lower, self.upper))

    def test_child_qt_mode_previews(self) -> None:
        """A group's preview composites its children in their own modes, for every Qt mode."""
        self.check_child_mode_previews(QT_MODES, True)

    @pytest.mark.xfail(strict=True, reason=ISSUE_151)
    def test_child_hsl_mode_previews(self) -> None:
        """A group's preview composites its children in their own modes, for every HSL mode."""
        self.check_child_mode_previews(HSL_MODES, False)

    def test_nested_group_previews(self) -> None:
        """Nested group previews leave out hidden and fully transparent layers and groups."""
        inner = self.add_group('inner', self.group, isolate=True, mode=CompositeMode.OVERLAY, opacity=0.6)
        inner_shown = self.add_layer('inner shown', QPoint(-4, 18), inner)
        self.add_layer('inner hidden', QPoint(2, 2), inner).visible = False
        self.add_layer('inner opacity 0', QPoint(8, 2), inner, opacity=0.0)
        hidden_group = self.add_group('hidden group', self.group, isolate=True)
        self.add_layer('in hidden group', QPoint(20, 0), hidden_group)
        hidden_group.visible = False
        transparent_group = self.add_group('transparent group', self.group, opacity=0.0)
        self.add_layer('in transparent group', QPoint(24, 16), transparent_group)
        self.open_panel()
        self.assert_preview_shows(inner, self.group_image(inner, inner_shown))
        self.assert_preview_shows(self.group, self.group_image(
            self.group, self.lower, self.upper, (inner, self.nested_children_image(inner, inner_shown))))

    def test_layer_stack_preview(self) -> None:
        """The layer stack's preview shows the full canvas render."""
        self.open_panel()
        self.assertEqual(self.image_stack.layer_stack.bounds, QRect(QPoint(), CANVAS_SIZE))
        self.assert_images_equal(self.preview(self.image_stack.layer_stack),
                                 crop_to_content(full_render(self.image_stack)))

    def test_preview_after_child_edit(self) -> None:
        """After a child's pixels change and renders flush, the group schedules a preview update that shows them."""
        self.open_panel()
        self.preview(self.group)
        with self.lower.borrow_image(QRect(2, 2, 9, 7)) as image:
            image.fill(0)
        self.image_stack.flush_render()
        widget = self.widget_for(self.group)
        self.assertTrue(widget._preview_render_timer.isActive())  # pylint: disable=protected-access
        self.assert_preview_shows(self.group, self.group_image(self.group, self.lower, self.upper))

    def test_preview_after_child_property_changes(self) -> None:
        """A group's preview follows its children's opacity, mode, visibility and position."""
        self.open_panel()
        self.upper.opacity = 0.3
        self.assert_preview_shows(self.group, self.group_image(self.group, self.lower, self.upper))
        self.upper.composition_mode = CompositeMode.DARKEN
        self.assert_preview_shows(self.group, self.group_image(self.group, self.lower, self.upper))
        self.lower.visible = False
        self.assert_preview_shows(self.group, self.group_image(self.group, self.upper))
        self.upper.transform = self.upper.transform.translate(-3, 5)
        self.assert_preview_shows(self.group, self.group_image(self.group, self.upper))

    def test_preview_after_group_opacity_change(self) -> None:
        """After the group's own opacity changes, its preview shows the new opacity."""
        self.open_panel()
        self.preview(self.group)
        self.group.opacity = 0.3
        self.assert_preview_shows(self.group, self.group_image(self.group, self.lower, self.upper))

    def test_preview_after_group_mode_change(self) -> None:
        """After the group's own mode changes, its preview shows the new mode.

        Hue is used because, unlike Qt's modes, it changes the image even on the cache's transparent base.
        """
        self.open_panel()
        self.preview(self.group)
        self.group.composition_mode = CompositeMode.HUE
        self.assert_preview_shows(self.group, self.group_image(self.group, self.lower, self.upper))

    def test_preview_after_isolate_change(self) -> None:
        """Turning isolation off and on leaves a group's preview showing its children alone."""
        self.open_panel()
        for isolate in (False, True):
            with self.subTest(isolate=isolate):
                self.group.isolate = isolate
                self.assert_preview_shows(self.group, self.group_image(self.group, self.lower, self.upper))

    def test_hidden_group_preview_is_blank(self) -> None:
        """A hidden group's preview shows nothing, and shows its content again once the group is shown.

        `test_hidden_group_preview_shows_content` pins the preview a hidden group should have.
        """
        self.open_panel()
        self.group.visible = False
        preview = self.preview(self.group)
        self.assert_images_equal(preview, create_transparent_image(preview.size()))
        self.group.visible = True
        self.assert_preview_shows(self.group, self.group_image(self.group, self.lower, self.upper))

    @pytest.mark.xfail(strict=True, reason=ISSUE_HIDDEN_GROUP_PREVIEW)
    def test_hidden_group_preview_shows_content(self) -> None:
        """A hidden group's preview shows its content, as a hidden image layer's preview does."""
        self.open_panel()
        expected = self.preview(self.group)
        self.group.visible = False
        self.assert_images_equal(self.preview(self.group), expected)
