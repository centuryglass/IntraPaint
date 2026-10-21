"""Tests KeyConfig keybinding validation."""
from unittest.mock import patch

from PySide6.QtCore import Qt

from src.config.key_config import KeyConfig
from src.tools.base_tool import FIXED_ASPECT_HINT, BaseTool
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


class KeyConfigModifierTest(IntraPaintTestCase):
    """An empty modifier binding means no modifier, not an error."""

    def test_get_modifier_empty_value_means_no_modifier(self) -> None:
        """get_modifier returns NoModifier for an unbound modifier instead of raising."""
        config = KeyConfig()
        config.set(KeyConfig.FIXED_ASPECT_MODIFIER, '')
        self.assertEqual(Qt.KeyboardModifier.NoModifier,
                         config.get_modifier(KeyConfig.FIXED_ASPECT_MODIFIER))

    def test_modifier_hint_omitted_for_empty_binding(self) -> None:
        """modifier_hint returns an empty string for an unbound modifier instead of raising."""
        KeyConfig().set(KeyConfig.FIXED_ASPECT_MODIFIER, '')
        self.assertEqual('', BaseTool.modifier_hint(KeyConfig.FIXED_ASPECT_MODIFIER, FIXED_ASPECT_HINT))
