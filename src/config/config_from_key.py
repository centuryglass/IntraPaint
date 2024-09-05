"""Get the config object that contains a particular key."""
from src.config.a1111_config import A1111Config
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.config import Config
from src.config.key_config import KeyConfig


def get_config_from_key(key: str) -> Config:
    """Get the config object that contains a particular key."""
    if key in AppConfig().get_keys():
        return AppConfig()
    if key in Cache().get_keys():
        return Cache()
    if key in KeyConfig().get_keys():
        return KeyConfig()
    if key in A1111Config().get_keys():
        return A1111Config()
    raise KeyError(f'Config key "{key}" not found in any config file type.')
