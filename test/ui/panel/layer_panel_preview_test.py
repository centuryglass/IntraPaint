"""Tests that layer panel previews of layer groups show the group's own content.

A group's preview is `LayerGroup.preview_image` cropped to content: its descendants composited onto a transparent
image covering the group's bounds. Like an image layer's preview, it ignores the group's own visibility, opacity and
mode, and the visibility of the groups it is in. Expected images come from the `layer_group_render_test` helpers,
which composite with QPainter or a mode's custom op directly instead of going through LayerGroup.render.

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


class LayerPanelGroupPreviewTest(GroupRenderTestCase):
    """Compares group previews in a LayerPanel with independently composited group content."""

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

    def content_image(self, group: LayerGroup, *children: ImageLayer | tuple[LayerGroup, QImage]) -> QImage:
        """Returns children composited in order onto a transparent image covering the group's bounds.

        A child given as (group, image) is a nested group, drawn from image in the nested group's mode and opacity.
        """
        bounds = group.bounds
        image = create_transparent_image(bounds.size())
        for child in children:
            if isinstance(child, tuple):
                nested, nested_image = child
                _composite(image, nested_image, nested.bounds.topLeft() - bounds.topLeft(),
                           nested.composition_mode, nested.opacity)
            else:
                _composite(image, child.image, self.offset(child) - bounds.topLeft(), child.composition_mode,
                           child.opacity)
        return image

    def assert_preview_shows(self, group: LayerGroup, expected: QImage) -> None:
        """Asserts that a group's preview shows expected, cropped to content."""
        self.assert_images_equal(self.preview(group), crop_to_content(expected), f'preview of {group.name}')

    def assert_preview_blank(self, group: LayerGroup) -> None:
        """Asserts that a group's preview is fully transparent."""
        preview = self.preview(group)
        self.assert_images_equal(preview, create_transparent_image(preview.size()), f'preview of {group.name}')

    def test_isolated_group_preview(self) -> None:
        """An isolated group's preview shows its children composited together, without its own mode or opacity."""
        self.open_panel()
        self.assert_preview_shows(self.group, self.content_image(self.group, self.lower, self.upper))

    def test_non_isolated_group_preview(self) -> None:
        """A non-isolated group's preview shows its children without the content beneath the group."""
        self.group.isolate = False
        self.open_panel()
        self.assert_preview_shows(self.group, self.content_image(self.group, self.lower, self.upper))

    def test_visible_normal_group_preview_matches_cached_image(self) -> None:
        """A visible group at full opacity in Normal mode previews its cached image."""
        self.group.opacity = 1.0
        self.group.composition_mode = CompositeMode.NORMAL
        self.open_panel()
        self.assert_preview_shows(self.group, self.content_image(self.group, self.lower, self.upper))
        self.assert_images_equal(self.preview(self.group), crop_to_content(self.group.get_qimage()))

    def test_group_mode_previews(self) -> None:
        """A group's preview leaves out the group's own composition mode, for every mode."""
        self.open_panel()
        for mode in CompositeMode:
            with self.subTest(mode=mode.name):
                self.group.composition_mode = mode
                self.assert_preview_shows(self.group, self.content_image(self.group, self.lower, self.upper))

    def check_child_mode_previews(self, modes: tuple[CompositeMode, ...], use_subtests: bool) -> None:
        """Asserts that a group's preview composites a child in each mode."""
        self.open_panel()
        for mode in modes:
            with self.subTest(mode=mode.name) if use_subtests else nullcontext():
                self.upper.composition_mode = mode
                self.assert_preview_shows(self.group, self.content_image(self.group, self.lower, self.upper))

    def test_child_qt_mode_previews(self) -> None:
        """A group's preview composites its children in their own modes, for every Qt mode."""
        self.check_child_mode_previews(QT_MODES, True)

    @pytest.mark.xfail(strict=True, reason=ISSUE_151)
    def test_child_hsl_mode_previews(self) -> None:
        """A group's preview composites its children in their own modes, for every HSL mode."""
        self.check_child_mode_previews(HSL_MODES, False)

    def test_nested_group_previews(self) -> None:
        """Nested group previews leave out hidden and fully transparent layers and groups inside them."""
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
        inner_content = self.content_image(inner, inner_shown)
        self.assert_preview_shows(inner, inner_content)
        self.assert_preview_shows(self.group, self.content_image(self.group, self.lower, self.upper,
                                                                 (inner, inner_content)))

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
        self.assert_preview_shows(self.group, self.content_image(self.group, self.lower, self.upper))

    def test_preview_after_child_property_changes(self) -> None:
        """A group's preview follows its children's opacity, mode, visibility and position."""
        self.open_panel()
        self.upper.opacity = 0.3
        self.assert_preview_shows(self.group, self.content_image(self.group, self.lower, self.upper))
        self.upper.composition_mode = CompositeMode.DARKEN
        self.assert_preview_shows(self.group, self.content_image(self.group, self.lower, self.upper))
        self.lower.visible = False
        self.assert_preview_shows(self.group, self.content_image(self.group, self.upper))
        self.upper.transform = self.upper.transform.translate(-3, 5)
        self.assert_preview_shows(self.group, self.content_image(self.group, self.upper))

    def test_preview_after_group_opacity_change(self) -> None:
        """A group's preview shows its content at full opacity, before and after its opacity returns to 1.

        At opacity 1 in Normal mode the preview reads the group's cached image, which must not keep the old opacity.
        Reading the pixmap at each opacity fills that cache, as the view does.
        """
        self.group.composition_mode = CompositeMode.NORMAL
        self.open_panel()
        expected = self.content_image(self.group, self.lower, self.upper)
        for opacity in (0.3, 0.0, 1.0):
            with self.subTest(opacity=opacity):
                self.group.opacity = opacity
                self.assert_preview_shows(self.group, expected)
                self.assertFalse(self.group.pixmap.isNull())

    def test_preview_after_group_mode_change(self) -> None:
        """A group's preview shows its content in Normal mode, before and after its mode returns to Normal.

        Destination In is used because it leaves the group's cached image blank on its transparent base. Reading the
        pixmap in each mode fills that cache, as the view does.
        """
        self.group.opacity = 1.0
        self.open_panel()
        expected = self.content_image(self.group, self.lower, self.upper)
        for mode in (CompositeMode.DESTINATION_IN, CompositeMode.NORMAL):
            with self.subTest(mode=mode.name):
                self.group.composition_mode = mode
                self.assert_preview_shows(self.group, expected)
                self.assertFalse(self.group.pixmap.isNull())

    def test_preview_after_isolate_change(self) -> None:
        """Turning isolation off and on leaves a group's preview showing its children alone."""
        self.open_panel()
        for isolate in (False, True):
            with self.subTest(isolate=isolate):
                self.group.isolate = isolate
                self.assert_preview_shows(self.group, self.content_image(self.group, self.lower, self.upper))

    def test_hidden_group_preview_shows_content(self) -> None:
        """A hidden group's preview shows its visible children, as a hidden image layer's preview shows its content."""
        self.open_panel()
        expected = self.content_image(self.group, self.lower, self.upper)
        self.group.visible = False
        self.assertFalse(self.widget_for(self.group).layer.visible)
        self.assert_preview_shows(self.group, expected)
        self.group.visible = True
        self.assert_preview_shows(self.group, expected)

    def test_hidden_group_with_all_layers_hidden_is_blank(self) -> None:
        """A hidden group whose layers are all hidden, directly or through a hidden nested group, has a blank preview."""
        nested = self.add_group('nested', self.group, isolate=True)
        self.add_layer('in nested', QPoint(2, 2), nested)
        nested.visible = False
        self.lower.visible = False
        self.upper.visible = False
        self.group.visible = False
        self.open_panel()
        self.assert_preview_blank(self.group)

    def test_nested_hidden_group_with_visible_child(self) -> None:
        """A hidden nested group previews its visible child, and its parent's preview leaves the nested group out.

        The nested group's preview keeps showing its child when the parent is hidden too.
        """
        nested = self.add_group('nested', self.group, isolate=True, mode=CompositeMode.SCREEN, opacity=0.5)
        nested_child = self.add_layer('nested child', QPoint(2, 2), nested)
        self.add_layer('nested hidden child', QPoint(20, 12), nested).visible = False
        nested.visible = False
        self.open_panel()
        nested_content = self.content_image(nested, nested_child)
        self.assert_preview_shows(nested, nested_content)
        self.assert_preview_shows(self.group, self.content_image(self.group, self.lower, self.upper))
        self.group.visible = False
        self.assert_preview_shows(nested, nested_content)
        self.group.visible = True
        nested.visible = True
        self.assertTrue(nested.visible)
        self.assert_preview_shows(self.group, self.content_image(self.group, self.lower, self.upper,
                                                                 (nested, nested_content)))

    def test_hidden_layer_stays_hidden_after_preview(self) -> None:
        """Rendering a hidden group's preview leaves the group, its parents and its properties unchanged."""
        inner = self.add_group('inner', self.group, isolate=True)
        self.add_layer('inner layer', QPoint(2, 2), inner)
        self.group.visible = False
        self.open_panel()
        self.preview(inner)
        self.preview(self.group)
        self.assertFalse(self.group.get_visible())
        self.assertFalse(inner.visible)
        self.assertEqual((self.group.opacity, self.group.composition_mode), (0.7, CompositeMode.MULTIPLY))
        self.assert_stack_renders(self.canvas_with(self.background))
