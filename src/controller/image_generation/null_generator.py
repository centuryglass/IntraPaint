"""Represents the option to run IntraPaint without an image generator."""
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication, QWidget

from src.controller.image_generation.image_generator import ImageGenerator
from src.image.layers.image_stack import ImageStack
from src.ui.window.main_window import MainWindow
from src.util.shared_constants import PROJECT_DIR

# The QCoreApplication.translate context for strings in this file
TR_ID = 'controller.image_generation.null_generator'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


NULL_GENERATOR_NAME = _tr('No image generator')
NULL_GENERATOR_DESCRIPTION = _tr('<p>IntraPaint does not need an image generator to function.  If you don\'t want to '
                                 'set up an image generator, you can still use it like any other image editor.')
NULL_GENERATOR_SETUP = _tr('This option has no setup requirements.')
NULL_GENERATOR_PREVIEW_IMAGE = f'{PROJECT_DIR}/resources/generator_preview/none.png'


class NullGenerator(ImageGenerator):
    """Represents the option to run IntraPaint without an image generator."""

    def __init__(self, window: MainWindow, image_stack: ImageStack) -> None:
        super().__init__(window, image_stack)
        self._preview = QImage(NULL_GENERATOR_PREVIEW_IMAGE)
        self._panel = QWidget()  # Intentionally left empty

    def get_display_name(self) -> str:
        """Returns a display name identifying the generator."""
        return NULL_GENERATOR_NAME

    def get_description(self) -> str:
        """Returns an extended description of this generator."""
        return NULL_GENERATOR_DESCRIPTION

    def get_preview_image(self) -> QImage:
        """Returns a preview image for this generator."""
        return self._preview

    def get_setup_text(self) -> str:
        """Returns a rich text description of how to set up this generator."""
        return NULL_GENERATOR_SETUP

    def is_available(self) -> bool:
        """Returns whether the generator is supported on the current system."""
        return True

    def configure_or_connect(self) -> bool:
        """Handles any required steps necessary to configure the generator, install required components, and/or
           connect to required external services, returning whether the process completed correctly."""
        return True

    def disconnect_or_disable(self) -> None:
        """No-op (there's nothing to disconnect/disable)."""

    def get_control_panel(self) -> QWidget:
        """Returns a widget with inputs for controlling this generator."""
        return self._panel
