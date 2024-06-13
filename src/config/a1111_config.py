"""Provides access to configurable options for the Automatic1111 or Forge Stable-Diffusion WebUI."""
from typing import Optional
import logging

from src.api.a1111_webservice import A1111Webservice
from src.config.config import Config

CONFIG_DEFINITIONS = 'resources/a1111_setting_definitions.json'
logger = logging.getLogger(__name__)

class A1111Config(Config):
    _instance: Optional['A1111Config'] = None

    @staticmethod
    def instance() -> 'A1111Config':
        """Returns the shared config object instance."""
        if A1111Config._instance is None:
            A1111Config._instance = A1111Config()
        return A1111Config._instance

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
                raise RuntimeError(f'key "{key}" had unexpected type {type(value)}, value {value}')
        for key, value in missing.items():
            logger.debug(f'NOT USED: {key}={value}')

    def save_all(self, webservice: A1111Webservice) -> None:
        """Sends all settings back to the webui."""
        settings = {}
        for category in self.get_categories():
            for key in self.get_category_keys(category):
                settings[key] = self.get(key)
        webservice.set_config(settings)