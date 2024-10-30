"""Assorted constants required in multiple areas."""
import os.path

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
MAX_WIDGET_SIZE = 16777215

# Editing modes:
EDIT_MODE_INPAINT = _tr('Inpaint')
EDIT_MODE_TXT2IMG = _tr('Text to Image')
EDIT_MODE_IMG2IMG = _tr('Image to Image')

# Display text:
BUTTON_TEXT_GENERATE = _tr('Generate')
BUTTON_TOOLTIP_GENERATE = _tr('Start AI image generation or modification')
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
ASPECT_RATIO_CHECK_LABEL = _tr('Keep aspect ratio')

# Layer change failure errors:
ERROR_TITLE_EDIT_FAILED = _tr('Editing failed')
ERROR_MESSAGE_LAYER_LOCKED = _tr('The selected layer is locked, unlock it or select a different layer.')
ERROR_MESSAGE_LAYER_GROUP_LOCKED = _tr('The selected layer is in a locked group, unlock it or select a different'
                                       ' layer.')
ERROR_MESSAGE_LAYER_HIDDEN = _tr('The selected layer is hidden, un-hide it before trying to edit it.')
ERROR_MESSAGE_LAYER_NONE = _tr('The selected layer is not an image layer, select an image layer first.')
ERROR_MESSAGE_EMPTY_MASK = _tr('Changes are restricted to selected content only, but nothing is selected in this layer.'
                               ' Select layer content or enable changes in unselected areas.')

# Network/Connection keys:
AUTH_ERROR_MESSAGE = _tr('Not authenticated')
URL_REQUEST_TITLE = _tr('Image generator connection')
URL_REQUEST_MESSAGE = _tr('Enter server URL:')
ERROR_MESSAGE_TIMEOUT = _tr('Request timed out')
URL_REQUEST_RETRY_MESSAGE = _tr('Server connection failed, enter a new URL or click "OK" to retry')
ERROR_MESSAGE_EXISTING_OPERATION = _tr('The AI image generator is busy creating other images, try again later.')
AUTH_ERROR = _tr('Login cancelled.')

# "Interrogate" feature:
INTERROGATE_ERROR_TITLE = _tr('Interrogate failure')
INTERROGATE_ERROR_MESSAGE_NO_IMAGE = _tr('Open or create an image first.')
INTERROGATE_LOADING_TEXT = _tr('Running CLIP interrogate')

# Image generation:
GENERATE_ERROR_TITLE = _tr('Image generation failed')
GENERATE_ERROR_MESSAGE_EMPTY_MASK = _tr('Nothing was selected in the image generation area. Either use the selection'
                                        ' tool to mark part of the image generation area for inpainting, move the image'
                                        ' generation area to cover selected content, or switch to another image'
                                        ' generation mode.')

# Upscaling:
UPSCALE_ERROR_TITLE = _tr('Upscale failure')
UPSCALED_LAYER_NAME = _tr('Upscaled image content')

# ControlNet:


# Argument used to disable or alter certain UI elements for better use in timelapse footage:
TIMELAPSE_MODE_FLAG = '--timelapse_mode'

PIL_SCALING_MODES = {
    _tr('Bilinear'): Image.Resampling.BILINEAR,
    _tr('Nearest'): Image.Resampling.NEAREST,
    _tr('Hamming'): Image.Resampling.HAMMING,
    _tr('Bicubic'): Image.Resampling.BICUBIC,
    _tr('Lanczos'): Image.Resampling.LANCZOS,
    _tr('Box'): Image.Resampling.BOX
}
COLOR_PICK_HINT = _tr('{modifier_or_modifiers}: pick color')
ICON_SIZE = 32
SMALL_ICON_SIZE = 24
