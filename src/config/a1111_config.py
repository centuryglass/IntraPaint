"""Provides access to configurable options for the Automatic1111 or Forge Stable-Diffusion WebUI."""
import logging

from PySide6.QtWidgets import QApplication

from src.api.a1111_webservice import A1111Webservice
from src.config.config import Config
from src.util.shared_constants import PROJECT_DIR
from src.util.singleton import Singleton

CONFIG_DEFINITIONS = f'{PROJECT_DIR}/resources/config/a1111_setting_definitions.json'
logger = logging.getLogger(__name__)


# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'config.a1111_config'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


WEB_CONFIG_TYPE_ERROR = _tr(TR_ID, 'key "{key}" had unexpected type {value_type}, value {value}')


class A1111Config(Config, metaclass=Singleton):
    """Provides access to configurable options for the Automatic1111 or Forge Stable-Diffusion WebUI."""

    def __init__(self) -> None:
        super().__init__(CONFIG_DEFINITIONS, None, A1111Config)

    def load_all(self, webservice: A1111Webservice) -> None:
        """Populate options and load values from the remote webservice."""
        models = list(map(lambda m: m['title'], webservice.get_models()))
        vae_options = list(map(lambda v: v['model_name'], webservice.get_vae()))
        vae_options.insert(0, 'Automatic')
        vae_options.insert(0, 'None')
        self.update_options(A1111Config.SD_MODEL_CHECKPOINT, models)
        self.update_options(A1111Config.SD_VAE, vae_options)
        settings = webservice.get_config()
        missing = {}
        for key, value in settings.items():
            if not hasattr(A1111Config, key.upper()):
                missing[key] = value
                continue
            prev_value = self.get(key)
            try:
                if isinstance(prev_value, bool):
                    self.set(key, bool(value))
                elif isinstance(prev_value, int):
                    self.set(key, int(value))
                elif isinstance(prev_value, float):
                    self.set(key, float(value))
                elif isinstance(prev_value, str):
                    self.set(key, str(value))
                elif isinstance(prev_value, (list, dict)):
                    self.set(key, value)
                else:
                    raise RuntimeError(WEB_CONFIG_TYPE_ERROR.format(key=key, value_type=type(value), value=value))
            except ValueError as load_err:
                # Might be an issue with options lists omitting hash strings, check if there's another match:
                try:
                    options = self.get_options(key)
                    match_found = False
                    for option in options:
                        if not isinstance(option, str) or not isinstance(value, str):
                            continue
                        if option.startswith(value) or value.startswith(option):
                            self.set(key, option)
                            match_found = True
                            break
                    if not match_found:
                        raise RuntimeError(f'No match found in {len(options)} available options.') from load_err
                except (RuntimeError, TypeError, ValueError) as err:
                    logger.error(f'Applying "{key}"="{value}" failed: {load_err}, {err}')
        for key, value in missing.items():
            logger.debug(f'NOT USED: {key}={value}')

    def save_all(self, webservice: A1111Webservice) -> None:
        """Sends all settings back to the webui."""
        settings = {}
        for category in self.get_categories():
            for key in self.get_category_keys(category):
                settings[key] = self.get(key)
        webservice.set_config(settings)

    # DYNAMIC PROPERTIES:
    # Generate with `python /home/anthony/Workspace/ML/IntraPaint/scripts/dynamic_import_typing.py src/config/a1111_config.py`

    CLIP_STOP_AT_LAST_LAYERS: str
    SD_CHECKPOINTS_KEEP_IN_CPU: str
    SD_CHECKPOINTS_LIMIT: str
    SD_MODEL_CHECKPOINT: str
    SD_VAE: str
    SD_VAE_CHECKPOINT_CACHE: str
