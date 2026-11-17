"""Tests NewImageModal."""
from unittest.mock import patch

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller import color_controller
from src.ui.modal.new_image_modal import NewImageModal, BACKGROUND_COLOR_OPTION_CUSTOM, \
    BACKGROUND_COLOR_OPTION_BLACK, BACKGROUND_COLOR_OPTION_WHITE, BACKGROUND_COLOR_OPTION_BACKGROUND
from test.base_test_case import IntraPaintTestCase


class NewImageModalTest(IntraPaintTestCase):
    """Tests NewImageModal."""

    def test_background_color_leaves_brush_color_alone(self) -> None:
        """Opening and cancelling the modal doesn't change the brush color, even with a custom background color."""
        brush_color = Cache().get(Cache.LAST_BRUSH_COLOR)
        Cache().set(Cache.NEW_IMAGE_BACKGROUND_COLOR, '#ff123456')
        modal = NewImageModal(512, 512)
        self.assertEqual(modal.background_color(), QColor('#ff123456'))
        self.assertTrue(modal._swatches[BACKGROUND_COLOR_OPTION_CUSTOM].isChecked())
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), brush_color)
        modal._cancel()
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), brush_color)

    def test_confirm_saves_background_color_only(self) -> None:
        """Confirming the modal saves the background color and leaves the brush color alone."""
        brush_color = Cache().get(Cache.LAST_BRUSH_COLOR)
        Cache().set(Cache.NEW_IMAGE_BACKGROUND_COLOR, '#ff123456')
        modal = NewImageModal(512, 512)
        modal._confirm()
        self.assertEqual(Cache().get(Cache.NEW_IMAGE_BACKGROUND_COLOR), '#ff123456')
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), brush_color)

    def test_swatches_pick_background(self) -> None:
        """Clicking a swatch selects that background color."""
        modal = NewImageModal(512, 512)
        modal._swatches[BACKGROUND_COLOR_OPTION_BLACK].click()
        self.assertEqual(modal.background_color(), QColor('black'))
        modal._swatches[BACKGROUND_COLOR_OPTION_WHITE].click()
        self.assertEqual(modal.background_color(), QColor('white'))

    def test_custom_swatch_opens_color_dialog(self) -> None:
        """The custom swatch takes the color dialog's result, and keeps the old selection if the dialog is canceled."""
        modal = NewImageModal(512, 512)
        with patch('src.ui.modal.new_image_modal.ColorDialog.show_color_dialog', return_value=QColor('#ff102030')):
            modal._swatches[BACKGROUND_COLOR_OPTION_CUSTOM].click()
        self.assertEqual(modal.background_color(), QColor('#ff102030'))
        modal._swatches[BACKGROUND_COLOR_OPTION_BLACK].click()
        with patch('src.ui.modal.new_image_modal.ColorDialog.show_color_dialog', return_value=None):
            modal._swatches[BACKGROUND_COLOR_OPTION_CUSTOM].click()
        self.assertEqual(modal.background_color(), QColor('black'))
        self.assertTrue(modal._swatches[BACKGROUND_COLOR_OPTION_BLACK].isChecked())

    def test_size_presets(self) -> None:
        """Presets fill in the size, repeated sizes are left out, and optional ones appear only when given."""
        Cache().set(Cache.GENERATION_SIZE, QSize(768, 768))
        modal = NewImageModal(512, 512, QSize(300, 200), QSize(768, 768))
        self.assertEqual(len(modal._preset_buttons), 3)
        modal._preset_buttons[2].click()
        self.assertEqual(modal.new_size(), QSize(300, 200))
        modal._preset_buttons[0].click()
        self.assertEqual(modal.new_size(), QSize(512, 512))
        self.assertEqual(len(NewImageModal(512, 512)._preset_buttons), 2)

    def test_size_limits(self) -> None:
        """Presets larger than the maximum image size are clamped."""
        max_size = AppConfig().get(AppConfig.MAX_IMAGE_SIZE)
        modal = NewImageModal(512, 512, QSize(max_size.width() + 100, 64))
        modal._preset_buttons[-1].click()
        self.assertEqual(modal.new_size(), QSize(max_size.width(), 64))

    def test_background_color_swatch(self) -> None:
        """The background color swatch fills with the current background color, and is remembered separately from the
        custom color."""
        color_controller.set_background(QColor('#ff102030'), commit=False)
        Cache().set(Cache.NEW_IMAGE_BACKGROUND_COLOR, '#ff123456')
        modal = NewImageModal(512, 512)
        modal._swatches[BACKGROUND_COLOR_OPTION_BACKGROUND].click()
        self.assertEqual(modal.background_color(), QColor('#ff102030'))
        modal._confirm()
        self.assertTrue(Cache().get(Cache.NEW_IMAGE_USES_BACKGROUND_COLOR))
        self.assertEqual(Cache().get(Cache.NEW_IMAGE_BACKGROUND_COLOR), '#ff123456')
        self.assertEqual(color_controller.new_image_color(), QColor('#ff102030'))

        reopened = NewImageModal(512, 512)
        self.assertTrue(reopened._swatches[BACKGROUND_COLOR_OPTION_BACKGROUND].isChecked())
        reopened._swatches[BACKGROUND_COLOR_OPTION_BLACK].click()
        reopened._confirm()
        self.assertFalse(Cache().get(Cache.NEW_IMAGE_USES_BACKGROUND_COLOR))
        self.assertEqual(color_controller.new_image_color(), QColor('black'))
