"""Tests the eyedropper tool through synthetic mouse input.

These pin the eyedropper as it stands: one merged-image pixel, alpha included, written to the foreground color on left
click. #58 plans to change the sampling options and give the right button the background color.
"""
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QTransform

from src.config.cache import Cache
from src.controller import color_controller
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_layer import ImageLayer
from src.tools.eyedropper_tool import EyedropperTool
from src.tools.fill_tool import FillTool
from test.tools.tool_test_case import ToolTestCase

INITIAL_FOREGROUND = QColor(10, 20, 30)
INITIAL_BACKGROUND = QColor(200, 210, 220)
SAMPLE_POINT = QPoint(4, 5)


def solid_image(size: QSize, color: QColor) -> QImage:
    """Returns a premultiplied ARGB image filled with one color."""
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return image


def source_over(*colors: QColor) -> QColor:
    """Returns colors composited bottom to top with SourceOver, the way the image stack renders layers."""
    image = solid_image(QSize(1, 1), QColor(Qt.GlobalColor.transparent))
    painter = QPainter(image)
    for color in colors:
        painter.fillRect(0, 0, 1, 1, color)
    painter.end()
    return image.pixelColor(0, 0)


class EyedropperToolTest(ToolTestCase):
    """Eyedropper tool testing"""

    IMAGE_SIZE = QSize(16, 16)

    def setUp(self) -> None:
        super().setUp()
        self.eyedropper_tool = EyedropperTool(self.image_stack)
        self.tool_controller.add_tool(self.eyedropper_tool)
        color_controller.set_foreground(INITIAL_FOREGROUND, commit=False)
        color_controller.set_background(INITIAL_BACKGROUND, commit=False)
        Cache().set(Cache.RECENT_COLORS, [])
        self.activate_tool(self.eyedropper_tool)

    def add_layer(self, color: QColor, size: QSize | None = None) -> ImageLayer:
        """Adds a layer filled with one color above the others and flushes the render."""
        layer = self.image_stack.create_layer(image_data=solid_image(size or self.IMAGE_SIZE, color))
        self.image_stack.flush_render()
        return layer

    def assert_colors_equal(self, actual: QColor, expected: QColor) -> None:
        """Asserts that two colors match in all four channels."""
        self.assertEqual(actual.getRgb(), expected.getRgb())

    def assert_colors_unchanged(self) -> None:
        """Asserts that the foreground and background still hold their setUp values."""
        self.assert_colors_equal(color_controller.foreground(), INITIAL_FOREGROUND)
        self.assert_colors_equal(color_controller.background(), INITIAL_BACKGROUND)

    def test_left_click_sets_foreground_from_opaque_pixel(self) -> None:
        """Left click copies an opaque pixel to the foreground and leaves the background alone."""
        color = QColor(30, 140, 220)
        self.add_layer(color)
        self.mouse_drag([SAMPLE_POINT])
        self.assert_colors_equal(color_controller.foreground(), color)
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), color.name(QColor.NameFormat.HexArgb))
        self.assert_colors_equal(color_controller.background(), INITIAL_BACKGROUND)

    def test_pick_commits_to_recent_colors(self) -> None:
        """A pick pushes the sampled color to the front of the recent colors."""
        color = QColor(30, 140, 220)
        self.add_layer(color)
        self.mouse_drag([SAMPLE_POINT])
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), [color.name(QColor.NameFormat.HexArgb)])

    def test_samples_clicked_pixel(self) -> None:
        """The sampled color comes from the pixel under the cursor, not elsewhere in the layer."""
        image = solid_image(self.IMAGE_SIZE, QColor(Qt.GlobalColor.white))
        marked = QColor(200, 30, 60)
        image.setPixelColor(SAMPLE_POINT, marked)
        self.image_stack.create_layer(image_data=image)
        self.image_stack.flush_render()
        self.mouse_drag([SAMPLE_POINT + QPoint(1, 0)])
        self.assert_colors_equal(color_controller.foreground(), QColor(Qt.GlobalColor.white))
        self.mouse_drag([SAMPLE_POINT])
        self.assert_colors_equal(color_controller.foreground(), marked)

    def test_translucent_pixel_keeps_unpremultiplied_color_and_alpha(self) -> None:
        """A translucent pixel sets the foreground to its unpremultiplied color with its alpha."""
        color = QColor(255, 0, 0, 128)
        self.add_layer(color)
        self.mouse_drag([SAMPLE_POINT])
        self.assert_colors_equal(color_controller.foreground(), color)
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#80ff0000')

    def test_transparent_pixel_sets_transparent_foreground(self) -> None:
        """A fully transparent pixel sets the foreground to transparent black. #58 plans to leave the color unchanged
           instead."""
        self.add_layer(QColor(Qt.GlobalColor.transparent))
        self.mouse_drag([SAMPLE_POINT])
        self.assertEqual(color_controller.foreground().alpha(), 0)
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#00000000')

    def test_samples_merged_layers(self) -> None:
        """The sample is the composite of every visible layer, whichever layer is active."""
        bottom_color = QColor(0, 0, 255)
        top_color = QColor(255, 0, 0, 128)
        bottom = self.add_layer(bottom_color)
        self.add_layer(top_color)
        self.image_stack.active_layer = bottom
        self.mouse_drag([SAMPLE_POINT])
        expected = source_over(bottom_color, top_color)
        self.assertNotEqual(expected.getRgb(), top_color.getRgb())
        self.assert_colors_equal(color_controller.foreground(), expected)

    def test_ignores_sample_merged_setting(self) -> None:
        """With SAMPLE_MERGED off, the eyedropper still samples the merged image, not the active layer."""
        Cache().set(Cache.SAMPLE_MERGED, False)
        bottom_color = QColor(0, 0, 255)
        top_color = QColor(255, 0, 0, 128)
        bottom = self.add_layer(bottom_color)
        self.add_layer(top_color)
        self.image_stack.active_layer = bottom
        self.mouse_drag([SAMPLE_POINT])
        self.assert_colors_equal(color_controller.foreground(), source_over(bottom_color, top_color))

    def test_hidden_layer_is_not_sampled(self) -> None:
        """A hidden layer doesn't contribute to the sample."""
        bottom_color = QColor(0, 200, 0)
        self.add_layer(bottom_color)
        top = self.add_layer(QColor(255, 0, 0))
        top.visible = False
        self.image_stack.flush_render()
        self.mouse_drag([SAMPLE_POINT])
        self.assert_colors_equal(color_controller.foreground(), bottom_color)

    def test_layer_opacity_applies_to_sample(self) -> None:
        """A layer's opacity is part of the sampled composite."""
        bottom_color = QColor(0, 0, 255)
        self.add_layer(bottom_color)
        top = self.add_layer(QColor(255, 0, 0))
        top.opacity = 0.5
        self.image_stack.flush_render()
        self.mouse_drag([SAMPLE_POINT])
        sampled = color_controller.foreground()
        self.assertEqual(sampled.alpha(), 255)
        self.assertGreater(sampled.red(), 100)
        self.assertGreater(sampled.blue(), 100)

    def test_right_click_sets_no_color(self) -> None:
        """Right click changes neither the foreground nor the background. #58 plans to make it set the background."""
        self.add_layer(QColor(30, 140, 220))
        self.mouse_drag([SAMPLE_POINT], Qt.MouseButton.RightButton)
        self.assert_colors_unchanged()
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), [])

    def test_middle_click_sets_no_color(self) -> None:
        """Middle click changes neither color slot."""
        self.add_layer(QColor(30, 140, 220))
        self.mouse_drag([SAMPLE_POINT], Qt.MouseButton.MiddleButton)
        self.assert_colors_unchanged()

    def test_drag_samples_only_at_press(self) -> None:
        """A left drag samples where it was pressed; moving the cursor afterward doesn't resample."""
        image = solid_image(self.IMAGE_SIZE, QColor(Qt.GlobalColor.white))
        start_color = QColor(200, 30, 60)
        image.setPixelColor(SAMPLE_POINT, start_color)
        self.image_stack.create_layer(image_data=image)
        self.image_stack.flush_render()
        self.mouse_drag([SAMPLE_POINT, SAMPLE_POINT + QPoint(3, 0), SAMPLE_POINT + QPoint(6, 0)])
        self.assert_colors_equal(color_controller.foreground(), start_color)

    def test_click_outside_all_content_sets_opaque_black(self) -> None:
        """A click outside the image and every layer sets the foreground to opaque black, the documented fallback of
           `image_stack_color_at_point`."""
        self.add_layer(QColor(30, 140, 220))
        self.mouse_drag([QPoint(-4, SAMPLE_POINT.y())])
        self.assert_colors_equal(color_controller.foreground(), QColor(0, 0, 0))

    def test_click_outside_image_samples_layer_content_there(self) -> None:
        """A click outside the image bounds but inside a layer samples that layer's content."""
        color = QColor(30, 140, 220)
        layer = self.add_layer(color)
        layer.transform = QTransform.fromTranslate(-8, 0)
        self.image_stack.flush_render()
        self.mouse_drag([QPoint(-4, SAMPLE_POINT.y())])
        self.assert_colors_equal(color_controller.foreground(), color)

    def test_ctrl_delegate_from_fill_tool_picks_without_filling(self) -> None:
        """Holding the eyedropper modifier over the fill tool hands a left click to the eyedropper, which sets the
           foreground and leaves the layer unfilled."""
        color = QColor(30, 140, 220)
        layer = self.add_layer(color)
        self.image_stack.active_layer = layer
        fill_tool = FillTool(self.image_stack)
        self.tool_controller.add_tool(fill_tool)
        self.tool_controller.register_tool_delegate(fill_tool, self.eyedropper_tool, Qt.KeyboardModifier.ControlModifier)
        self.activate_tool(fill_tool)
        initial_image = layer.image
        HotkeyFilter.instance().modifiers_changed.emit(Qt.KeyboardModifier.ControlModifier)
        try:
            self.assertIs(self.tool_controller.active_tool, self.eyedropper_tool)
            self.mouse_drag([SAMPLE_POINT], modifiers=Qt.KeyboardModifier.ControlModifier)
        finally:
            HotkeyFilter.instance().modifiers_changed.emit(Qt.KeyboardModifier.NoModifier)
        self.assertIs(self.tool_controller.active_tool, fill_tool)
        self.assert_colors_equal(color_controller.foreground(), color)
        self.assert_images_equal(layer.image, initial_image)
