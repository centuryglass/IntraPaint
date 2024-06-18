"""Assorted constants required in multiple areas."""

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
