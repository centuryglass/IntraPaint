"""Assorted constants required in multiple areas."""
from PyQt5.QtGui import QPainter

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
    'Default': QPainter.CompositionMode.CompositionMode_SourceOver,
    'Plus': QPainter.CompositionMode.CompositionMode_Plus,
    'Multiply': QPainter.CompositionMode.CompositionMode_Multiply,
    'Screen': QPainter.CompositionMode.CompositionMode_Screen,
    'Overlay': QPainter.CompositionMode.CompositionMode_Overlay,
    'Darken': QPainter.CompositionMode.CompositionMode_Darken,
    'Lighten': QPainter.CompositionMode.CompositionMode_Lighten,
    'Color dodge': QPainter.CompositionMode.CompositionMode_ColorDodge,
    'Color burn': QPainter.CompositionMode.CompositionMode_ColorBurn,
    'Hard light': QPainter.CompositionMode.CompositionMode_HardLight,
    'Soft light': QPainter.CompositionMode.CompositionMode_SoftLight,
    'Difference': QPainter.CompositionMode.CompositionMode_Difference,
    'Exclusion': QPainter.CompositionMode.CompositionMode_Exclusion,
    'Destination over': QPainter.CompositionMode.CompositionMode_DestinationOver,
    'Clear': QPainter.CompositionMode.CompositionMode_Clear,
    'Replace': QPainter.CompositionMode.CompositionMode_Source,
    'Source in': QPainter.CompositionMode.CompositionMode_SourceIn,
    'Destination in': QPainter.CompositionMode.CompositionMode_DestinationIn,
    'Source out': QPainter.CompositionMode.CompositionMode_SourceOut,
    'Destination out': QPainter.CompositionMode.CompositionMode_DestinationOut,
    'Source atop': QPainter.CompositionMode.CompositionMode_SourceAtop,
    'Destination atop': QPainter.CompositionMode.CompositionMode_DestinationAtop,
    'Xor': QPainter.CompositionMode.CompositionMode_Xor
}