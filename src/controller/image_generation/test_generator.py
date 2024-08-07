"""Mock generator for testing and development."""
from typing import Optional

from PyQt6.QtCore import pyqtSignal, pyqtBoundSignal
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication, QWidget

from src.config.application_config import AppConfig
from src.controller.image_generation.image_generator import ImageGenerator
from src.image.filter.blur import BlurFilter, MODE_GAUSSIAN
from src.image.filter.brightness_contrast import BrightnessContrastFilter
from src.image.filter.posterize import PosterizeFilter
from src.image.filter.rgb_color_balance import RGBColorBalanceFilter
from src.image.filter.sharpen import SharpenFilter
from src.image.layers.image_stack import ImageStack
from src.ui.panel.generators.testing_panel import TestControlPanel
from src.ui.window.main_window import MainWindow
from src.util.shared_constants import PROJECT_DIR, EDIT_MODE_TXT2IMG

# The QCoreApplication.translate context for strings in this file
TR_ID = 'controller.image_generation.test_generator'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


TEST_GENERATOR_NAME = _tr('Test/development image generator')
TEST_GENERATOR_DESCRIPTION = _tr('Mock image generator, for testing and development')
TEST_GENERATOR_SETUP = _tr('No setup required.')


class TestGenerator(ImageGenerator):
    """Mock generator for testing and development."""

    def __init__(self, window: MainWindow, image_stack: ImageStack) -> None:
        super().__init__(window, image_stack)
        self._test_image = QImage(f'{PROJECT_DIR}/resources/icons/app_icon.png').convertToFormat(
            QImage.Format.Format_ARGB32_Premultiplied)

    def get_display_name(self) -> str:
        """Returns a display name identifying the generator."""
        return TEST_GENERATOR_NAME

    def get_description(self) -> str:
        """Returns an extended description of this generator."""
        return TEST_GENERATOR_DESCRIPTION

    def get_preview_image(self) -> QImage:
        """Returns a preview image for this generator."""
        return QImage()

    def get_setup_text(self) -> str:
        """Returns a rich text description of how to set up this generator."""
        return TEST_GENERATOR_SETUP

    def is_available(self) -> bool:
        """Returns whether the generator is supported on the current system."""
        return True

    def configure_or_connect(self) -> bool:
        """Handles any required steps necessary to configure the generator, install required components, and/or
           connect to required external services, returning whether the process completed correctly."""
        return True

    def get_control_panel(self) -> QWidget:
        """Returns a widget with inputs for controlling this generator."""
        return TestControlPanel()

    def generate(self,
                 status_signal: pyqtSignal | pyqtBoundSignal,
                 source_image: Optional[QImage] = None,
                 mask_image: Optional[QImage] = None) -> None:
        """Generates new images. Image size, image count, prompts, etc. should be loaded from AppConfig as needed.
        Implementations should call self._cache_generated_image to pass back each generated image.

        Parameters
        ----------
        status_signal : pyqtSignal[dict]
            Signal to emit when status updates are available. Expected keys are 'seed' and 'progress'.
        source_image : QImage, optional
            Image used as a basis for the edited image.
        mask_image : QImage, optional
            Mask marking edited image region.
        """
        edit_mode = AppConfig().get(AppConfig.EDIT_MODE)
        if edit_mode == EDIT_MODE_TXT2IMG or source_image is None:
            source_image = self._test_image.scaled(AppConfig().get(AppConfig.GENERATION_SIZE))

        # Create mock generated images using all available filters:
        blur_image = BlurFilter.blur(source_image, MODE_GAUSSIAN, 5)
        self._cache_generated_image(blur_image, 0)
        brightened_image = BrightnessContrastFilter.brightness_contrast_filter(source_image, 10.0, 10.0)
        self._cache_generated_image(brightened_image, 1)
        posterized_image = PosterizeFilter.posterize(source_image, 2)
        self._cache_generated_image(posterized_image, 2)
        recolored_image = RGBColorBalanceFilter.color_balance(source_image, 10.0, 1.0, 1.0, 1.0)
        self._cache_generated_image(recolored_image, 3)
        sharpened_image = SharpenFilter.sharpen(source_image, 5.0)
        self._cache_generated_image(sharpened_image, 4)
