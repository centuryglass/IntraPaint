"""Assorted constants required in multiple areas."""
import os.path

from PySide6.QtGui import QPainter
from PIL import Image
from PySide6.QtWidgets import QApplication
from platformdirs import user_data_dir, user_log_dir


# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'util.shared_constants'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
APP_ICON_PATH = f'{PROJECT_DIR}/resources/icons/app_icon.png'
DATA_DIR = user_data_dir('IntraPaint', 'centuryglass')
LOG_DIR = user_log_dir('IntraPaint', 'centuryglass')
for app_dir in [DATA_DIR, LOG_DIR]:
    if not os.path.isdir(app_dir):
        os.makedirs(app_dir)

# Numeric:
INT_MIN = -2147483647
INT_MAX = 2147483647
# For when zero values are best avoided due to division-by-zero errors and the like:
MIN_NONZERO = 0.001
# Not actually hard limits, just reasonable extremes guaranteed to be within hard limits:
FLOAT_MIN = -9999999.0
FLOAT_MAX = 9999999.0

# Editing modes:
EDIT_MODE_INPAINT = _tr('Inpaint')
EDIT_MODE_TXT2IMG = _tr('Text to Image')
EDIT_MODE_IMG2IMG = _tr('Image to Image')

# When used as the controlnet image path, this signifies that the image should be taken from the image generation area:
CONTROLNET_REUSE_IMAGE_CODE = 'SELECTION'

# Display text:
BUTTON_TEXT_GENERATE = _tr('Generate')
SHORT_LABEL_WIDTH = _tr('W:')
SHORT_LABEL_HEIGHT = _tr('H:')
SHORT_LABEL_X_POS = _tr('X:')
SHORT_LABEL_Y_POS = _tr('Y:')

LABEL_TEXT_WIDTH = _tr('Width:')
LABEL_TEXT_HEIGHT = _tr('Height:')
LABEL_TEXT_COLOR = _tr('Color:')
LABEL_TEXT_SIZE = _tr('Size:')
LABEL_TEXT_SCALE = _tr('Scale:')
LABEL_TEXT_IMAGE_PADDING = _tr('Padding:')
BUTTON_TEXT_ZOOM_IN = _tr('Zoom In')
BUTTON_TEXT_RESET_ZOOM = _tr('Reset Zoom')

# Argument used to disable or alter certain UI elements for better use in timelapse footage:
TIMELAPSE_MODE_FLAG = '--timelapse_mode'

# Image composition modes: display strings mapped to mode values.
COMPOSITION_MODES = {
    _tr('Normal'): QPainter.CompositionMode.CompositionMode_SourceOver,
    _tr('Plus'): QPainter.CompositionMode.CompositionMode_Plus,
    _tr('Multiply'): QPainter.CompositionMode.CompositionMode_Multiply,
    _tr('Screen'): QPainter.CompositionMode.CompositionMode_Screen,
    _tr('Overlay'): QPainter.CompositionMode.CompositionMode_Overlay,
    _tr('Darken'): QPainter.CompositionMode.CompositionMode_Darken,
    _tr('Lighten'): QPainter.CompositionMode.CompositionMode_Lighten,
    _tr('Color Dodge'): QPainter.CompositionMode.CompositionMode_ColorDodge,
    _tr('Color Burn'): QPainter.CompositionMode.CompositionMode_ColorBurn,
    _tr('Hard Light'): QPainter.CompositionMode.CompositionMode_HardLight,
    _tr('Soft Light'): QPainter.CompositionMode.CompositionMode_SoftLight,
    _tr('Difference'): QPainter.CompositionMode.CompositionMode_Difference,
    _tr('Exclusion'): QPainter.CompositionMode.CompositionMode_Exclusion,
    _tr('Destination over'): QPainter.CompositionMode.CompositionMode_DestinationOver,
    _tr('Clear'): QPainter.CompositionMode.CompositionMode_Clear,
    _tr('Replace'): QPainter.CompositionMode.CompositionMode_Source,
    _tr('Destination In'): QPainter.CompositionMode.CompositionMode_DestinationIn,
    _tr('Destination Out'): QPainter.CompositionMode.CompositionMode_DestinationOut,
    _tr('Source Atop'): QPainter.CompositionMode.CompositionMode_SourceAtop,
    _tr('Destination Atop'): QPainter.CompositionMode.CompositionMode_DestinationAtop
}

PIL_SCALING_MODES = {
    _tr('Bilinear'): Image.Resampling.BILINEAR,
    _tr('Nearest'): Image.Resampling.NEAREST,
    _tr('Hamming'): Image.Resampling.HAMMING,
    _tr('Bicubic'): Image.Resampling.BICUBIC,
    _tr('Lanczos'): Image.Resampling.LANCZOS,
    _tr('Box'): Image.Resampling.BOX
}
MAX_WIDGET_SIZE = 16777215
