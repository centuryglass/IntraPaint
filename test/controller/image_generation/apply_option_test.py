"""Tests `apply_generated_image`, the one route that writes a generated option into the image stack."""
from unittest import mock

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QColor, QImage

from src.config.application_config import AppConfig
from src.controller.image_generation.apply_option import apply_generated_image, ApplyResult
from src.controller.image_generation.result_patch import make_result_patch
from src.image.composite_mode import CompositeMode
from src.image.layers.image_stack import ImageStack
from src.util.shared_constants import EDIT_MODE_INPAINT, EDIT_MODE_TXT2IMG
from test.base_test_case import IntraPaintTestCase

IMAGE_SIZE = QSize(128, 128)
GENERATION_AREA = QRect(32, 32, 64, 64)
MASK_BOUNDS = QRect(16, 16, 16, 16)
SOURCE_COLOR = QColor(200, 30, 30)
GENERATED_COLOR = QColor(30, 30, 200)


def _solid(size: QSize, color: QColor) -> QImage:
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return image


def _mask() -> QImage:
    """Returns a generation-area mask that is opaque only inside `MASK_BOUNDS`."""
    mask = QImage(GENERATION_AREA.size(), QImage.Format.Format_ARGB32_Premultiplied)
    mask.fill(QColor(0, 0, 0, 0))
    for x in range(MASK_BOUNDS.left(), MASK_BOUNDS.right() + 1):
        for y in range(MASK_BOUNDS.top(), MASK_BOUNDS.bottom() + 1):
            mask.setPixelColor(x, y, QColor(0, 0, 0, 255))
    return mask


class ApplyOptionTest(IntraPaintTestCase):
    """Covers the mask, the generation area, layer fallbacks and context pins."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(IMAGE_SIZE, GENERATION_AREA.size(), QSize(8, 8), QSize(10240, 10240))
        self.layer = self.image_stack.create_layer('source', _solid(IMAGE_SIZE, SOURCE_COLOR))
        self.image_stack.generation_area = GENERATION_AREA
        self.option = _solid(GENERATION_AREA.size(), GENERATED_COLOR)

    def _apply(self, layer=None, mode=EDIT_MODE_TXT2IMG, option=None, **kwargs):
        outcome = apply_generated_image(self.image_stack, option or self.option, layer or self.layer,
                                        GENERATION_AREA, mode, _mask(), 'fallback', **kwargs)
        self.image_stack.flush_render()
        return outcome

    def test_writes_generation_area_from_qimage_and_pil(self) -> None:
        """A QImage or PIL option replaces the generation area content and leaves the rest alone."""
        pil_option = Image.new('RGBA', (GENERATION_AREA.width(), GENERATION_AREA.height()),
                               (GENERATED_COLOR.red(), GENERATED_COLOR.green(), GENERATED_COLOR.blue(), 255))
        for option in (self.option, pil_option):
            with self.subTest(option=type(option).__name__):
                self.layer.image.fill(SOURCE_COLOR)  # type: ignore
                outcome = self._apply(option=option)
                self.assertEqual(outcome.result, ApplyResult.APPLIED)
                self.assertIs(outcome.layer, self.layer)
                self.assertEqual(self.layer.image.pixelColor(GENERATION_AREA.center()), GENERATED_COLOR)  # type: ignore
                self.assertEqual(self.layer.image.pixelColor(2, 2), SOURCE_COLOR)  # type: ignore

    def test_inpaint_keeps_only_masked_area(self) -> None:
        """In inpaint mode the option is applied only where the mask is set."""
        self._apply(mode=EDIT_MODE_INPAINT)
        image = self.layer.image  # type: ignore
        self.assertEqual(image.pixelColor(GENERATION_AREA.topLeft() + MASK_BOUNDS.center()), GENERATED_COLOR)
        self.assertEqual(image.pixelColor(GENERATION_AREA.topLeft() + QPoint(50, 50)), SOURCE_COLOR)

    def test_restores_generation_area_and_activates_layer(self) -> None:
        """The batch's generation area is restored and the written layer becomes active."""
        other = self.image_stack.create_layer('other')
        self.image_stack.generation_area = QRect(0, 0, 64, 64)
        self._apply()
        self.assertEqual(self.image_stack.generation_area, GENERATION_AREA)
        self.assertIsNot(other, self.layer)
        self.assertIs(self.image_stack.active_layer, self.layer)

    def test_blocked_layers_fall_back_to_a_new_layer(self) -> None:
        """Locked, hidden and non-image layers get the content on a new layer named by the caller."""
        for expected, attribute, value in ((ApplyResult.BLOCKED_LOCKED, 'locked', True),
                                           (ApplyResult.BLOCKED_HIDDEN, 'visible', False)):
            with self.subTest(expected=expected):
                layer = self.image_stack.create_layer('target', _solid(IMAGE_SIZE, SOURCE_COLOR))
                setattr(layer, attribute, value)
                outcome = self._apply(layer=layer)
                self.assertEqual(outcome.result, expected)
                self.assertIsNot(outcome.layer, layer)
                self.assertEqual(outcome.layer.name, 'fallback')
                self.assertEqual(layer.image.pixelColor(GENERATION_AREA.center()), SOURCE_COLOR)  # type: ignore
        outcome = self._apply(layer=self.image_stack.layer_stack)
        self.assertEqual(outcome.result, ApplyResult.BLOCKED_NOT_IMAGE_LAYER)

    def test_context_pins_clear_only_when_requested_and_configured(self) -> None:
        """Pins clear when the caller asks and `CLEAR_CONTEXT_PINS_AFTER_GENERATING` is set."""
        selection = self.image_stack.selection_layer
        for configured in (False, True):
            for requested in (False, True):
                with self.subTest(configured=configured, requested=requested), \
                        mock.patch.object(selection, 'clear_context_pins') as clear_pins:
                    AppConfig().set(AppConfig.CLEAR_CONTEXT_PINS_AFTER_GENERATING, configured)
                    self._apply(clear_context_pins=requested)
                    self.assertEqual(clear_pins.called, configured and requested)


class ApplyPatchTest(IntraPaintTestCase):
    """Applying a result patch to an empty layer adds only what the result changed."""

    def test_patch_on_empty_layer_leaves_unchanged_pixels_transparent(self) -> None:
        """The composite shows the result, and the new layer holds nothing where the result equals the source."""
        stack = ImageStack(IMAGE_SIZE, GENERATION_AREA.size(), QSize(8, 8), QSize(10240, 10240))
        stack.create_layer('source', _solid(IMAGE_SIZE, SOURCE_COLOR))
        stack.generation_area = GENERATION_AREA
        stack.flush_render()
        sent = stack.qimage_generation_area_content()
        result = sent.copy()
        for x in range(MASK_BOUNDS.left(), MASK_BOUNDS.right() + 1):
            for y in range(MASK_BOUNDS.top(), MASK_BOUNDS.bottom() + 1):
                result.setPixelColor(x, y, GENERATED_COLOR)
        patch = make_result_patch(result, sent, None)
        new_layer = stack.create_layer('patched')
        apply_generated_image(stack, patch, new_layer, GENERATION_AREA, EDIT_MODE_INPAINT, _mask(), 'fallback')
        stack.flush_render()
        layer_content = new_layer.image  # type: ignore
        self.assertEqual(layer_content.pixelColor(GENERATION_AREA.left() + 40, GENERATION_AREA.top() + 40).alpha(), 0)
        self.assertGreater(layer_content.pixelColor(GENERATION_AREA.left() + 20,
                                                    GENERATION_AREA.top() + 20).alpha(), 0)
        composite = stack.qimage_generation_area_content()
        self.assertEqual(composite.pixelColor(20, 20), GENERATED_COLOR)
        self.assertEqual(composite.pixelColor(40, 40), SOURCE_COLOR)


class TopLayerFallbackTest(IntraPaintTestCase):
    """A target that can't display the result as its own pixels gets a new layer at the top of the stack."""

    def setUp(self) -> None:
        super().setUp()
        self.stack = ImageStack(IMAGE_SIZE, GENERATION_AREA.size(), QSize(8, 8), QSize(10240, 10240))
        self.base = self.stack.create_layer('base', _solid(IMAGE_SIZE, SOURCE_COLOR))
        self.stack.generation_area = GENERATION_AREA
        self.option = _solid(GENERATION_AREA.size(), GENERATED_COLOR)

    def _apply(self, layer):
        outcome = apply_generated_image(self.stack, self.option, layer, GENERATION_AREA, EDIT_MODE_TXT2IMG, None,
                                        'fallback')
        self.stack.flush_render()
        return outcome

    def _assert_fell_back(self, target, expected: ApplyResult) -> None:
        before = target.image.copy()  # type: ignore
        outcome = self._apply(target)
        self.assertEqual(outcome.result, expected)
        self.assertIs(self.stack.layer_stack.get_layer_by_id(outcome.layer.id), outcome.layer)
        self.assertIs(outcome.layer.layer_parent, self.stack.layer_stack)
        self.assertEqual(self.stack.layer_stack.get_layer_index(outcome.layer), 0)
        self.assertEqual(target.image, before)  # type: ignore
        self.assertEqual(self.stack.qimage_generation_area_content().pixelColor(32, 32), GENERATED_COLOR)

    def test_plain_normal_layer_is_applied_directly(self) -> None:
        """Nothing above and Normal at full opacity writes into the target."""
        outcome = self._apply(self.base)
        self.assertEqual(outcome.result, ApplyResult.APPLIED)
        self.assertIs(outcome.layer, self.base)

    def test_blend_mode_and_opacity(self) -> None:
        """A Multiply or partly transparent target falls back."""
        for attribute, value in (('composition_mode', CompositeMode.MULTIPLY), ('opacity', 0.5)):
            with self.subTest(attribute=attribute):
                layer = self.stack.create_layer('target', _solid(IMAGE_SIZE, SOURCE_COLOR))
                setattr(layer, attribute, value)
                self._assert_fell_back(layer, ApplyResult.NEEDS_TOP_LAYER_BLENDING)

    def test_non_normal_group(self) -> None:
        """A target inside a group with a non-Normal mode falls back."""
        group = self.stack.create_layer_group('group')
        layer = self.stack.create_layer('target', _solid(IMAGE_SIZE, SOURCE_COLOR), layer_parent=group, layer_index=0)
        group.composition_mode = CompositeMode.MULTIPLY
        self._assert_fell_back(layer, ApplyResult.NEEDS_TOP_LAYER_BLENDING)

    def test_layer_above_drawing_in_area(self) -> None:
        """Content above the target in the area forces the fallback, and content elsewhere doesn't."""
        above = self.stack.create_layer('above')
        above.get_qimage().setPixelColor(2, 2, QColor(0, 0, 0))
        self.assertEqual(self._apply(self.base).result, ApplyResult.APPLIED)
        above.get_qimage().setPixelColor(40, 40, QColor(0, 0, 0))
        self._assert_fell_back(self.base, ApplyResult.NEEDS_TOP_LAYER_COVERED)
