"""Translated display text shared by several modules.

This module calls `_tr` when it is first imported, so it must not be imported before the translator is installed.
Path, flag and numeric constants that startup code needs earlier are in `src.util.shared_constants`.
"""
from typing import Optional

from PIL import Image
from PySide6.QtWidgets import QApplication

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'util.shared_text'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


# Display text:
BUTTON_TEXT_GENERATE = _tr('Generate')
BUTTON_TOOLTIP_GENERATE = _tr('Start AI image generation or modification')

# Layer change failure errors:
ERROR_TITLE_EDIT_FAILED = _tr('Editing failed')
ERROR_MESSAGE_LAYER_LOCKED = _tr('The selected layer is locked, unlock it or select a different layer.')
ERROR_MESSAGE_LAYER_GROUP_LOCKED = _tr('The selected layer is in a locked group, unlock it or select a different'
                                       ' layer.')
ERROR_MESSAGE_LAYER_HIDDEN = _tr('The selected layer is hidden, un-hide it before trying to edit it.')
ERROR_MESSAGE_LAYER_GROUP_HIDDEN = _tr('The selected layer is in the hidden group "{group_name}", un-hide the group'
                                       ' before trying to edit it.')
ERROR_MESSAGE_LAYER_NONE = _tr('The selected layer is not an image layer, select an image layer first.')
ERROR_MESSAGE_EMPTY_MASK = _tr('Changes are restricted to selected content only, but nothing is selected in this layer.'
                               ' Select layer content or enable changes in unselected areas.')

# Errors caused by locks and selection restrictions, which error dialogs show with the signal color:
LOCK_ERROR_MESSAGES = (ERROR_MESSAGE_LAYER_LOCKED, ERROR_MESSAGE_LAYER_GROUP_LOCKED, ERROR_MESSAGE_EMPTY_MASK)

# Network/Connection keys:
AUTH_ERROR_MESSAGE = _tr('Not authenticated')
URL_REQUEST_TITLE = _tr('Image generator connection')
URL_REQUEST_MESSAGE = _tr('Enter server URL:')
ERROR_MESSAGE_TIMEOUT = _tr('Request timed out')
URL_REQUEST_RETRY_MESSAGE = _tr('Server connection failed, enter a new URL or click "OK" to retry')
AUTH_ERROR = _tr('Failed to connect to image generator at "{url}": Login cancelled.')
MISC_CONNECTION_ERROR = _tr('Failed to connect to image generator at "{url}".  Click "Activate" to try again or choose'
                            ' a different address. <br/> Full error text: <br/><blockquote>{error_text}</blockquote>')

# "Describe" feature:
DESCRIBE_ERROR_TITLE = _tr('Describe failed')
DESCRIBE_ERROR_MESSAGE_NO_IMAGE = _tr('Open or create an image first.')

# Image generation:
GENERATE_ERROR_TITLE = _tr('Image generation failed')
GENERATE_ERROR_MESSAGE_EMPTY_MASK = _tr('Nothing was selected in the generation area. Either use the selection'
                                        ' tool to mark part of the generation area for inpainting, move the image'
                                        ' generation area to cover selected content, or switch to another image'
                                        ' generation mode.')

# Upscaling:
UPSCALE_ERROR_TITLE = _tr('Upscale failure')
UPSCALED_LAYER_NAME = _tr('Upscaled image content')
UPSCALE_OPTION_NONE = _tr('None')

PIL_SCALING_MODES = {
    _tr('Bilinear'): Image.Resampling.BILINEAR,
    _tr('Nearest'): Image.Resampling.NEAREST,
    _tr('Hamming'): Image.Resampling.HAMMING,
    _tr('Bicubic'): Image.Resampling.BICUBIC,
    _tr('Lanczos'): Image.Resampling.LANCZOS,
    _tr('Box'): Image.Resampling.BOX
}
COLOR_PICK_HINT = _tr('{modifier_or_modifiers}: pick color')
KEYS_TOOLTIP = _tr('{description}\nKeys: {decrease} / {increase}')
KEY_TOOLTIP = _tr('{description}\nKey: {key}')


def keys_tooltip(description: str, decrease_key: str, increase_key: str) -> str:
    """Returns a tooltip that lists the keys that step a value down and up. An unbound key is left out, and the
    description alone is returned when neither is bound."""
    if decrease_key != '' and increase_key != '':
        return KEYS_TOOLTIP.format(description=description, decrease=decrease_key, increase=increase_key)
    if decrease_key != '' or increase_key != '':
        return KEY_TOOLTIP.format(description=description, key=decrease_key or increase_key)
    return description
