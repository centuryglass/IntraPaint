"""Tests `apply_generated_image`, the one route that writes a generated option into the image stack."""
from unittest import mock

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QColor, QImage

from src.config.application_config import AppConfig
from src.controller.image_generation.apply_option import apply_generated_image, ApplyResult
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
