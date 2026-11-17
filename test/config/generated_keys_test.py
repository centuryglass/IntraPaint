"""Tests that `src/config/generated_keys.py` matches the definition files, and that each config class exposes it."""
import importlib.util
import os

from src.config import generated_keys
from src.config.a1111_config import A1111Config
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.config import Config
from src.config.key_config import KeyConfig
from test.base_test_case import IntraPaintTestCase, PROJECT_ROOT

_SPEC = importlib.util.spec_from_file_location('generate_config_keys',
                                               os.path.join(PROJECT_ROOT, 'scripts', 'generate_config_keys.py'))
assert _SPEC is not None and _SPEC.loader is not None
generate_config_keys = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(generate_config_keys)

CONFIG_CLASSES: dict[str, type[Config]] = {
    'AppConfigKeys': AppConfig,
    'CacheKeys': Cache,
    'KeyConfigKeys': KeyConfig,
    'A1111ConfigKeys': A1111Config,
}


def _constants(key_class: type) -> dict[str, str]:
    """Returns a generated key class's constants, by attribute name."""
    return {name: value for name, value in vars(key_class).items() if name.isupper()}


class GeneratedKeysTest(IntraPaintTestCase):
    """The generated key constants match the definitions and reach the config classes unshadowed."""

    def test_module_is_current(self) -> None:
        """The committed module matches a fresh render of the definition files."""
        with open(generate_config_keys.OUTPUT_PATH, encoding='utf-8') as file:
            committed = file.read()
        self.assertEqual(committed, generate_config_keys.render(),
                         'src/config/generated_keys.py is out of date: run python scripts/generate_config_keys.py')

    def test_every_config_class_inherits_its_keys(self) -> None:
        """Each config class inherits its generated key class, which defines exactly the config's keys."""
        self.assertEqual(sorted(generate_config_keys.KEY_CLASSES.values()), sorted(CONFIG_CLASSES))
        for class_name, config_class in CONFIG_CLASSES.items():
            key_class = getattr(generated_keys, class_name)
            with self.subTest(config=config_class.__name__):
                self.assertTrue(issubclass(config_class, key_class))
                self.assertEqual(sorted(_constants(key_class).values()), sorted(config_class().get_keys()))

    def test_constants_are_not_shadowed(self) -> None:
        """No key constant shares a name with a `Config` attribute, or is overridden by its config class."""
        config_attributes = set(dir(Config))
        for class_name, config_class in CONFIG_CLASSES.items():
            constants = _constants(getattr(generated_keys, class_name))
            with self.subTest(config=config_class.__name__):
                self.assertEqual(sorted(config_attributes.intersection(constants)), [])
                self.assertEqual({name: getattr(config_class, name) for name, key in constants.items()
                                  if getattr(config_class, name) != key}, {})
