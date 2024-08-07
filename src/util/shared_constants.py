"""Assorted constants required in multiple areas."""
import os.path

from PyQt6.QtGui import QPainter
from PIL import Image
from platformdirs import user_data_dir, user_log_dir

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
EDIT_MODE_INPAINT = 'Inpaint'
EDIT_MODE_TXT2IMG = 'Text to Image'
EDIT_MODE_IMG2IMG = 'Image to Image'

# When used as the controlnet image path, this signifies that the image should be taken from the image generation area:
CONTROLNET_REUSE_IMAGE_CODE = 'SELECTION'

# Display text:
GENERATE_BUTTON_TEXT = 'Generate'

# Argument used to disable or alter certain UI elements for better use in timelapse footage:
TIMELAPSE_MODE_FLAG = '--timelapse_mode'

# Image composition modes: display strings mapped to mode values.
COMPOSITION_MODES = {
    'Normal': QPainter.CompositionMode.CompositionMode_SourceOver,
    'Plus': QPainter.CompositionMode.CompositionMode_Plus,
    'Multiply': QPainter.CompositionMode.CompositionMode_Multiply,
    'Screen': QPainter.CompositionMode.CompositionMode_Screen,
    'Overlay': QPainter.CompositionMode.CompositionMode_Overlay,
    'Darken': QPainter.CompositionMode.CompositionMode_Darken,
    'Lighten': QPainter.CompositionMode.CompositionMode_Lighten,
    'Color Dodge': QPainter.CompositionMode.CompositionMode_ColorDodge,
    'Color Burn': QPainter.CompositionMode.CompositionMode_ColorBurn,
    'Hard Light': QPainter.CompositionMode.CompositionMode_HardLight,
    'Soft Light': QPainter.CompositionMode.CompositionMode_SoftLight,
    'Difference': QPainter.CompositionMode.CompositionMode_Difference,
    'Exclusion': QPainter.CompositionMode.CompositionMode_Exclusion,
    'Destination over': QPainter.CompositionMode.CompositionMode_DestinationOver,
    'Clear': QPainter.CompositionMode.CompositionMode_Clear,
    'Replace': QPainter.CompositionMode.CompositionMode_Source,
    'Destination In': QPainter.CompositionMode.CompositionMode_DestinationIn,
    'Destination Out': QPainter.CompositionMode.CompositionMode_DestinationOut,
    'Source Atop': QPainter.CompositionMode.CompositionMode_SourceAtop,
    'Destination Atop': QPainter.CompositionMode.CompositionMode_DestinationAtop
}

PIL_SCALING_MODES = {
    'Bilinear': Image.Resampling.BILINEAR,
    'Nearest': Image.Resampling.NEAREST,
    'Hamming': Image.Resampling.HAMMING,
    'Bicubic': Image.Resampling.BICUBIC,
    'Lanczos': Image.Resampling.LANCZOS,
    'Box': Image.Resampling.BOX
}
MAX_WIDGET_SIZE = 16777215
