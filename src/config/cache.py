"""Use the Config module's data sharing capabilities to cache temporary values."""

from src.config.config import Config
from src.util.singleton import Singleton

CONFIG_DEFINITIONS = 'resources/config/cache_value_definitions.json'
DEFAULT_FILE_PATH = '.cache.json'


class Cache(Config, metaclass=Singleton):

    def __init__(self, json_path: str = DEFAULT_FILE_PATH) -> None:
        """Initialize the cache, registering expected value types."""
        super().__init__(CONFIG_DEFINITIONS, json_path, Cache)

    # DYNAMIC PROPERTIES:
    # Generate with `python /home/anthony/Workspace/ML/IntraPaint/scripts/dynamic_import_typing.py src/config/cache.py`

    CONTROLNET_CONTROL_TYPES: str
    CONTROLNET_MODELS: str
    CONTROLNET_MODULES: str
    CONTROLNET_VERSION: str
    FILL_THRESHOLD: str
    LAST_ACTIVE_TOOL: str
    LAST_BRUSH_COLOR: str
    LAST_FILE_PATH: str
    LAST_SEED: str
    LORA_MODELS: str
    SAMPLE_MERGED: str
    STYLES: str
