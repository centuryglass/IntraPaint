"""Tests the input hint text BaseTool builds from configured modifier keys."""
from src.config.key_config import KeyConfig
from src.tools.base_tool import BaseTool, FIXED_ASPECT_HINT
from test.base_test_case import IntraPaintTestCase


class ModifierHintTest(IntraPaintTestCase):
    """Checks how modifier_hint draws configured modifiers."""

    def test_one_keycap_per_binding(self) -> None:
        """A binding gets one keycap image, however many modifiers it holds."""
        KeyConfig().set(KeyConfig.FIXED_ASPECT_MODIFIER, 'Ctrl+Shift')
        self.assertEqual(BaseTool.modifier_hint(KeyConfig.FIXED_ASPECT_MODIFIER, FIXED_ASPECT_HINT).count('<img'), 1)
        KeyConfig().set(KeyConfig.FIXED_ASPECT_MODIFIER, 'Alt')
        self.assertEqual(BaseTool.modifier_hint(KeyConfig.FIXED_ASPECT_MODIFIER, FIXED_ASPECT_HINT).count('<img'), 1)
