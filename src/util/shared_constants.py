"""Assorted constants required in multiple areas."""
import os.path

from platformdirs import user_data_dir, user_log_dir

# In the one-file PyInstaller bundle, PROJECT_DIR is the temporary extraction folder deleted on exit. Read bundled
# resources from it, never write there.
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
APP_ICON_PATH = f'{PROJECT_DIR}/resources/icons/app_icon.png'
# DATA_DIR_ENV_VAR and LOG_DIR_ENV_VAR replace the platformdirs locations when set. They must be set before this module
# is first imported. conftest.py sets both so test runs stay out of the real user profile.
DATA_DIR_ENV_VAR = 'INTRAPAINT_DATA_DIR'
LOG_DIR_ENV_VAR = 'INTRAPAINT_LOG_DIR'
DATA_DIR = os.environ.get(DATA_DIR_ENV_VAR) or user_data_dir('IntraPaint', 'centuryglass')
LOG_DIR = os.environ.get(LOG_DIR_ENV_VAR) or user_log_dir('IntraPaint', 'centuryglass')
for app_dir in [DATA_DIR, LOG_DIR]:
    os.makedirs(app_dir, exist_ok=True)
# AppConfig's saved file. src/util/translation.py reads it at startup, before AppConfig exists.
APP_CONFIG_PATH = f'{DATA_DIR}/config.json'

# Numeric:
INT_MIN = -2147483647
INT_MAX = 2147483647
# It's a pretty insignificant micro-optimization to replace "x / 255" with "x * INV_255", but why not?
INV_255 = 1 / 255
# For when zero values are best avoided due to division-by-zero errors and the like:
MIN_NONZERO = 0.001
# Not actually hard limits, just reasonable extremes guaranteed to be within hard limits:
FLOAT_MIN = -9999999.0
FLOAT_MAX = 9999999.0
MAX_WIDGET_SIZE = 16777215

# Editing modes. These are the stored `Cache.EDIT_MODE` values, so they must match the options in
# cache_value_definitions.json and must not be translated.
EDIT_MODE_INPAINT = 'Inpaint'
EDIT_MODE_TXT2IMG = 'Text to Image'
EDIT_MODE_IMG2IMG = 'Image to Image'

# Argument used to disable or alter certain UI elements for better use in timelapse footage:
TIMELAPSE_MODE_FLAG = '--timelapse_mode'

# Environment variable setting whether debug cursors are loaded:
DEBUG_CURSOR_ENV_VAR = 'INTRAPAINT_DEBUG_CURSORS'

ICON_SIZE = 32
SMALL_ICON_SIZE = 24
