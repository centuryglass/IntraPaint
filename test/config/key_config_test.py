"""Tests KeyConfig keybinding validation."""
from unittest.mock import patch

from src.config.key_config import KeyConfig
from test.base_test_case import IntraPaintTestCase


def _validation_errors() -> list[str]:
    """Runs keybinding validation and returns the reported messages."""
    with patch('src.config.key_config.show_warning_dialog') as warning:
        KeyConfig().validate_keybindings()
    if not warning.called:
        return []
    return [str(warning.call_args.args[2])]


class KeyConfigValidationTest(IntraPaintTestCase):
    """Validation reports problems instead of raising."""

    def test_defaults_valid(self) -> None:
        """The default bindings produce no warnings."""
        self.assertEqual([], _validation_errors())

    def test_speed_modifier_in_binding(self) -> None:
        """A speed-modified binding that includes the speed modifier is reported."""
        config = KeyConfig()
        config.set(KeyConfig.SPEED_MODIFIER, 'Alt')
        config.set(KeyConfig.PAN_LEFT, 'Alt+Left')
        errors = _validation_errors()
        self.assertEqual(1, len(errors))
        self.assertIn('speed modifier', errors[0])
        self.assertIn('Alt+Left', errors[0])

    def test_speed_modified_variant_collision(self) -> None:
        """A speed-modified variant that collides with another binding names both entries."""
        config = KeyConfig()
        config.set(KeyConfig.SPEED_MODIFIER, 'Alt')
        config.set(KeyConfig.PAN_LEFT, 'Z')
        config.set(KeyConfig.BRUSH_TOOL_KEY, 'Alt+Z')
        errors = _validation_errors()
        self.assertEqual(1, len(errors))
        self.assertIn('with speed modifier', errors[0])
        self.assertIn('Alt+Z', errors[0])
