"""Tests FilterBrush strokes with each image filter against golden images, and checks properties that must hold for any
   filter stroke."""
from typing import Any

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QColor, QImage

from src.image.brush.filter_brush import FilterBrush
from src.image.filter.blur import BlurFilter, MODE_GAUSSIAN, MODE_SIMPLE
from src.image.filter.brightness_contrast import BrightnessContrastFilter
from src.image.filter.filter import ImageFilter
from src.image.filter.invert import InvertFilter
from src.image.filter.posterize import PosterizeFilter
from src.image.filter.rgb_color_balance import RGBColorBalanceFilter
from src.image.filter.saturation import SaturationFilter
from src.image.filter.sharpen import SharpenFilter
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_data_as_numpy_8bit, create_transparent_image
from test.image.brush.brush_test_case import BrushTestCase, LAYER_SIZE, brush_test_pattern, opacity_gradient_image, \
    line_points, rect_mask
from test.image.brush.qt_paint_brush_test import zigzag_points

GOLDEN_DIR = 'test/resources/test_images/filter_brush'

# Largest per-channel difference accepted where PIL filters translucent pixels; see assert_stroke_matches_golden.
PIL_TRANSLUCENT_TOLERANCE = 8


def opaque_test_pattern() -> QImage:
    """Returns brush_test_pattern with every pixel made opaque, transparent pixels becoming black."""
    return brush_test_pattern().convertToFormat(QImage.Format.Format_RGB32).convertToFormat(
        QImage.Format.Format_ARGB32_Premultiplied)


class FilterBrushTest(BrushTestCase):
    """Drives FilterBrush directly on an ImageLayer, with each filter the filter tool offers."""

    brush: FilterBrush

    def setUp(self) -> None:
        super().setUp()
        # Filters only use the image stack when applied from the menu:
        self.image_stack = ImageStack(LAYER_SIZE, LAYER_SIZE, QSize(8, 8), QSize(1024, 1024))
        self.layer = ImageLayer(brush_test_pattern(), 'filter test layer')
        self.brush = FilterBrush(BlurFilter(self.image_stack), self.layer)
        self.brush.brush_size = 24
        self.brush.opacity = 1.0
        self.brush.hardness = 1.0
        self.brush.antialiasing = False
        self.brush.pressure_size = True
        self.brush.pressure_opacity = False
        self.brush.pressure_hardness = False

    def use_filter(self, image_filter: ImageFilter, parameter_values: list[Any] | None = None) -> None:
        """Switches the brush to a filter, with the given parameter values or the filter's defaults."""
        self.brush.image_filter = image_filter
        if parameter_values is not None:
            self.brush.parameter_values = parameter_values

    def assert_stroke_matches_golden(self, image: QImage, golden_name: str, tolerance: int = 0) -> None:
        """Checks that a stroke left only valid premultiplied pixels, then compares it with its golden image.

        A nonzero tolerance accepts premultiplied channels that differ from the golden by up to that much. PIL-based
        filters on translucent pixels round differently between machines (local runs and CI disagree by a few
        levels), so only those strokes need it.
        """
        self.assert_valid_premultiplied(image)
        golden_path = f'{GOLDEN_DIR}/{golden_name}.png'
        if tolerance > 0:
            golden = QImage(golden_path).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            actual = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            if not golden.isNull() and golden.size() == actual.size():
                difference = np.abs(image_data_as_numpy_8bit(actual).astype(np.int16)
                                    - image_data_as_numpy_8bit(golden).astype(np.int16))
                if int(difference.max()) <= tolerance:
                    return
        self.assert_image_matches_golden(image, golden_path)

    def filter_stroke_matches_golden(self, image_filter: ImageFilter, parameter_values: list[Any] | None,
                                     golden_name: str) -> None:
        """Draws the zigzag stroke with a filter, and compares the result with its golden image."""
        self.use_filter(image_filter, parameter_values)
        image = self.stroke(zigzag_points())
        self.assertNotEqual(image, brush_test_pattern(), 'filter stroke changed nothing')
        self.assert_stroke_matches_golden(image, golden_name)

    def test_blur_default(self) -> None:
        """Box blur at the default radius."""
        self.filter_stroke_matches_golden(BlurFilter(self.image_stack), None, 'blur_default')

    def test_blur_gaussian(self) -> None:
        """Gaussian blur with a larger radius."""
        self.filter_stroke_matches_golden(BlurFilter(self.image_stack), [MODE_GAUSSIAN, 6.0], 'blur_gaussian')

    def test_blur_simple(self) -> None:
        """Simple blur, which ignores the radius parameter."""
        self.filter_stroke_matches_golden(BlurFilter(self.image_stack), [MODE_SIMPLE, 0.0], 'blur_simple')

    def test_sharpen_default(self) -> None:
        """Sharpen at the default factor."""
        self.filter_stroke_matches_golden(SharpenFilter(self.image_stack), None, 'sharpen_default')

    def test_sharpen_strong(self) -> None:
        """Sharpen at a high factor, across an opacity gradient."""
        self.use_layer(opacity_gradient_image())
        self.use_filter(SharpenFilter(self.image_stack), [6.0])
        self.assert_stroke_matches_golden(self.stroke(zigzag_points()), 'sharpen_strong', PIL_TRANSLUCENT_TOLERANCE)

    def test_brightness_contrast(self) -> None:
        """Brighter, with reduced contrast."""
        self.filter_stroke_matches_golden(BrightnessContrastFilter(self.image_stack), [1.6, 0.5],
                                          'brightness_contrast')

    def test_brightness_contrast_darker(self) -> None:
        """Darker, with increased contrast."""
        self.filter_stroke_matches_golden(BrightnessContrastFilter(self.image_stack), [0.5, 2.5],
                                          'brightness_contrast_darker')

    def test_posterize_default(self) -> None:
        """Posterize at the default bit count."""
        self.filter_stroke_matches_golden(PosterizeFilter(self.image_stack), None, 'posterize_default')

    def test_posterize_one_bit(self) -> None:
        """Posterize to one bit per channel."""
        self.filter_stroke_matches_golden(PosterizeFilter(self.image_stack), [1], 'posterize_one_bit')

    def test_saturation_increased(self) -> None:
        """Saturation raised above the default."""
        self.filter_stroke_matches_golden(SaturationFilter(self.image_stack), [2.5], 'saturation_increased')

    def test_saturation_grayscale(self) -> None:
        """Saturation reduced to zero."""
        self.filter_stroke_matches_golden(SaturationFilter(self.image_stack), [0.0], 'saturation_grayscale')

    def test_rgb_color_balance(self) -> None:
        """Color balance with each channel scaled differently, on an opaque layer."""
        self.use_layer(opaque_test_pattern())
        self.filter_stroke_matches_golden(RGBColorBalanceFilter(self.image_stack), [1.5, 0.5, 1.0, 1.0],
                                          'rgb_color_balance')

    def test_rgb_color_balance_alpha(self) -> None:
        """Color balance that halves alpha and lowers green and blue, on an opaque layer."""
        self.use_layer(opaque_test_pattern())
        self.filter_stroke_matches_golden(RGBColorBalanceFilter(self.image_stack), [1.0, 0.75, 0.5, 0.5],
                                          'rgb_color_balance_alpha')

    def test_rgb_color_balance_keeps_translucent_pixels_valid(self) -> None:
        """Color balance with every factor at 1.0 leaves valid premultiplied pixels where the layer is translucent."""
        self.use_filter(RGBColorBalanceFilter(self.image_stack), [1.0, 1.0, 1.0, 1.0])
        self.assert_valid_premultiplied(self.stroke(zigzag_points()))

    def test_rgb_color_balance_boost_with_lower_alpha_keeps_pixels_valid(self) -> None:
        """Color balance that raises a channel while lowering alpha leaves valid premultiplied pixels."""
        self.use_layer(opaque_test_pattern())
        self.use_filter(RGBColorBalanceFilter(self.image_stack), [1.0, 2.0, 0.5, 0.5])
        self.assert_valid_premultiplied(self.stroke(zigzag_points()))

    def test_rgb_color_balance_identity_leaves_translucent_pixels_unchanged(self) -> None:
        """Color balance with every factor at 1.0 returns translucent pixels unchanged."""
        image = brush_test_pattern()
        filtered = RGBColorBalanceFilter.color_balance(image, 1.0, 1.0, 1.0, 1.0)
        self.assertTrue(np.array_equal(image_data_as_numpy_8bit(filtered), image_data_as_numpy_8bit(image)))

    def test_invert(self) -> None:
        """Color inversion, which has no parameters."""
        self.filter_stroke_matches_golden(InvertFilter(self.image_stack), [], 'invert')

    def test_soft_translucent_blur(self) -> None:
        """A soft, antialiased brush at partial opacity fades between filtered and original content."""
        self.brush.brush_size = 30
        self.brush.opacity = 0.7
        self.brush.hardness = 0.3
        self.brush.antialiasing = True
        self.filter_stroke_matches_golden(BlurFilter(self.image_stack), [MODE_GAUSSIAN, 4.0], 'blur_soft_translucent')

    def test_soft_translucent_invert(self) -> None:
        """A soft, antialiased brush at partial opacity with a local filter."""
        self.brush.brush_size = 30
        self.brush.opacity = 0.7
        self.brush.hardness = 0.3
        self.brush.antialiasing = True
        self.filter_stroke_matches_golden(InvertFilter(self.image_stack), [], 'invert_soft_translucent')

    def configure_opacity_gradient(self) -> None:
        """Puts an opacity gradient on the test layer and sets up a soft translucent brush."""
        self.use_layer(opacity_gradient_image())
        self.brush.brush_size = 30
        self.brush.opacity = 0.8
        self.brush.hardness = 0.4
        self.brush.antialiasing = True

    def test_blur_across_opacity_gradient(self) -> None:
        """Soft blur strokes across pixels that are already partly transparent."""
        self.configure_opacity_gradient()
        self.use_filter(BlurFilter(self.image_stack), [MODE_GAUSSIAN, 5.0])
        self.stroke(line_points(QPoint(180, 30), QPoint(10, 30), 7))
        image = self.stroke(line_points(QPoint(20, 120), QPoint(170, 75), 7))
        self.assert_stroke_matches_golden(image, 'blur_opacity_gradient')

    def test_brightness_across_opacity_gradient(self) -> None:
        """Soft brightness/contrast strokes across pixels that are already partly transparent."""
        self.configure_opacity_gradient()
        self.use_filter(BrightnessContrastFilter(self.image_stack), [1.8, 1.5])
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'brightness_contrast_opacity_gradient', PIL_TRANSLUCENT_TOLERANCE)

    @pytest.mark.xfail(strict=True, reason='PIL filters average the color of transparent pixels as black: '
                                           'https://github.com/centuryglass/IntraPaint/issues/161')
    def test_blur_next_to_transparency_keeps_color(self) -> None:
        """Blurring opaque white into transparent pixels lowers alpha without darkening the color."""
        initial_image = create_transparent_image(LAYER_SIZE)
        initial_image.fill(QColor(0, 0, 0, 0))
        np_initial = image_data_as_numpy_8bit(initial_image)
        np_initial[:, :LAYER_SIZE.width() // 2, :] = 255
        self.use_layer(initial_image)
        self.use_filter(BlurFilter(self.image_stack), [MODE_GAUSSIAN, 6.0])
        image = self.stroke(line_points(QPoint(40, 64), QPoint(150, 64), 8))
        self.assert_valid_premultiplied(image)
        np_image = image_data_as_numpy_8bit(image).astype(np.int32)
        alpha = np_image[:, :, 3]
        visible = alpha > 0
        # Unpremultiplying a channel stored at alpha a can be off by up to 255 / a:
        darkened = np.any(np_image[visible, :3] * 255.0 / alpha[visible, np.newaxis]
                          < 255 - 255.0 / alpha[visible, np.newaxis], axis=1)
        self.assertFalse(np.any(darkened), f'{np.count_nonzero(darkened)} blurred pixels are darker than white')

    def test_local_filter_bounds_match_segment_bounds(self) -> None:
        """A local filter reads only the pixels under the segment."""
        self.use_filter(InvertFilter(self.image_stack), [])
        self.assertTrue(self.brush.image_filter.is_local())
        bounds = QRect(0, 0, 20, 20)
        self.assertEqual(self.brush._filter_bounds(bounds), bounds)  # pylint: disable=protected-access

    def test_radius_filter_bounds_are_padded_and_clipped_to_layer(self) -> None:
        """A radius filter pads the segment bounds by its radius, clipped to the layer."""
        self.use_filter(BlurFilter(self.image_stack), [MODE_GAUSSIAN, 6.0])
        self.assertFalse(self.brush.image_filter.is_local())
        # pylint: disable=protected-access
        self.assertEqual(self.brush._filter_bounds(QRect(50, 40, 20, 20)), QRect(44, 34, 32, 32))
        self.assertEqual(self.brush._filter_bounds(QRect(2, 3, 20, 20)), QRect(0, 0, 28, 29))
        width, height = LAYER_SIZE.width(), LAYER_SIZE.height()
        self.assertEqual(self.brush._filter_bounds(QRect(width - 22, height - 21, 20, 20)),
                         QRect(width - 28, height - 27, 28, 27))

    def test_radius_filter_near_layer_edge(self) -> None:
        """A blur stroke along the layer edges, where the padded filter bounds are clipped to the layer."""
        self.use_filter(BlurFilter(self.image_stack), [MODE_GAUSSIAN, 6.0])
        width, height = LAYER_SIZE.width(), LAYER_SIZE.height()
        points = (line_points(QPoint(2, 2), QPoint(width - 3, 2), 9)
                  + line_points(QPoint(width - 3, 2), QPoint(width - 3, height - 3), 9)[1:]
                  + line_points(QPoint(width - 3, height - 3), QPoint(2, height - 3), 9)[1:])
        image = self.stroke(points)
        self.assert_stroke_matches_golden(image, 'blur_layer_edge')

    def test_input_mask_restricts_changes(self) -> None:
        """Filtering stays inside the input mask, even with a filter that reads pixels outside it."""
        initial_image = self.layer.image
        selected = QRect(40, 20, 80, 50)
        self.brush.set_input_mask(rect_mask(selected))
        self.use_filter(BlurFilter(self.image_stack), [MODE_GAUSSIAN, 6.0])
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'blur_input_mask')
        self.assert_changes_inside(image, initial_image, selected)

    def test_overlapping_segments_do_not_refilter(self) -> None:
        """Within one stroke, every segment filters the layer content from before the stroke, so crossing a filtered
           area doesn't invert it a second time."""
        self.use_filter(InvertFilter(self.image_stack), [])
        initial_image = self.layer.image
        image = self.stroke(zigzag_points())
        self.assert_valid_premultiplied(image)
        point = QPoint(95, 45)  # The zigzag crosses itself near here.
        inverted = initial_image.copy()
        inverted.invertPixels(QImage.InvertMode.InvertRgb)
        self.assertEqual(image.pixelColor(point), inverted.pixelColor(point))

    def test_mid_stroke_draws_match_one_draw_at_end(self) -> None:
        """Drawing buffered input partway through a stroke doesn't change the result."""
        self.brush.brush_size = 26
        self.brush.opacity = 0.7
        self.brush.hardness = 0.4
        self.brush.antialiasing = True
        self.use_filter(BlurFilter(self.image_stack), [MODE_GAUSSIAN, 4.0])
        buffered_image = self.stroke(zigzag_points())
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, brush_test_pattern())
        flushed_image = self.stroke(zigzag_points(), flush_after_each_point=True)
        self.assert_images_equal(flushed_image, buffered_image)

    def test_undo_restores_layer(self) -> None:
        """Each filter stroke is one undo step, and undoing it restores the layer."""
        UndoStack().clear()
        image = self.stroke(zigzag_points())
        self.assertNotEqual(image, brush_test_pattern())
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, brush_test_pattern())
