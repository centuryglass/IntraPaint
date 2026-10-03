"""Tests NewImageModal."""
from PySide6.QtGui import QColor

from src.config.cache import Cache
from src.ui.modal.new_image_modal import NewImageModal, BACKGROUND_COLOR_OPTION_CUSTOM
from test.base_test_case import IntraPaintTestCase


class NewImageModalTest(IntraPaintTestCase):
    """Tests NewImageModal."""

    def test_background_color_leaves_brush_color_alone(self) -> None:
        """Opening and cancelling the modal doesn't change the brush color, even with a custom background color."""
        brush_color = Cache().get(Cache.LAST_BRUSH_COLOR)
        Cache().set(Cache.NEW_IMAGE_BACKGROUND_COLOR, '#ff123456')
        modal = NewImageModal(512, 512)
        self.assertEqual(modal._color_dropdown.currentText(), BACKGROUND_COLOR_OPTION_CUSTOM)
        self.assertEqual(modal._color_button.color, QColor('#ff123456'))
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
