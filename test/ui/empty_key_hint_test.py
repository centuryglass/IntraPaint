"""Tests that hints and tooltips that name a key binding read correctly when the binding is empty."""
from src.config.key_config import KeyConfig
from src.tools.base_tool import BaseTool
from src.tools.brush_tool import BrushTool
from src.ui.generated_selector_bars import _control_hint, HINT_PAN_MIDDLE_ONLY
from src.util.shared_text import keys_tooltip
from src.util.visual.key_hint_text import rich_text_key_hints
from src.util.visual.text_drawing_utils import middle_button_hint_text
from test.base_test_case import IntraPaintTestCase


class EmptyKeyHintTest(IntraPaintTestCase):
    """Checks the handling chosen for each kind of hint."""

    def test_keys_tooltip_lists_only_bound_keys(self) -> None:
        """A tooltip lists both keys, the one bound key, or only the description."""
        self.assertEqual(keys_tooltip('Size', 'A', 'B'), 'Size\nKeys: A / B')
        self.assertEqual(keys_tooltip('Size', '', 'B'), 'Size\nKey: B')
        self.assertEqual(keys_tooltip('Size', 'A', ''), 'Size\nKey: A')
        self.assertEqual(keys_tooltip('Size', '', ''), 'Size')

    def test_join_hints_skips_empty_hints(self) -> None:
        """Joined hints leave no stray separator."""
        self.assertEqual(BaseTool.join_hints('a', '', 'b'), 'a - b')
        self.assertEqual(BaseTool.join_hints('', '', 'b'), 'b')
        self.assertEqual(BaseTool.join_hints('a', '', separator='<br/>'), 'a')
        self.assertEqual(BaseTool.join_hints('', ''), '')

    def test_brush_control_hints_with_unbound_modifiers(self) -> None:
        """Brush hints drop the clause of each unbound modifier."""
        key_config = KeyConfig()
        for config_key in (KeyConfig.LINE_MODIFIER, KeyConfig.FIXED_ANGLE_MODIFIER):
            key_config.set(config_key, '')
        hint = BrushTool.brush_control_hints()
        self.assertNotIn(' - ', hint)
        self.assertNotEqual(hint, '')
        key_config.set(KeyConfig.BRUSH_SIZE_DRAG_MODIFIER, '')
        self.assertEqual(BrushTool.brush_control_hints(), '')

    def test_selector_hint_drops_unbound_clauses(self) -> None:
        """The generated image selector's hint line leaves out clauses with no bound key and has no empty gaps."""
        key_config = KeyConfig()
        full_single = _control_hint(True, 4)
        full_grid = _control_hint(False, 4)
        key_config.set(KeyConfig.COMPARE_ORIGINAL_MODIFIER, '')
        for config_key in (KeyConfig.MOVE_DOWN, KeyConfig.MOVE_UP, KeyConfig.ZOOM_IN, KeyConfig.ZOOM_OUT,
                           KeyConfig.PAN_VIEW_KEY):
            key_config.set(config_key, [])
        single = _control_hint(True, 4)
        grid = _control_hint(False, 4)
        self.assertLess(len(single), len(full_single))
        self.assertLess(len(grid), len(full_grid))
        for hint in (single, grid):
            self.assertNotIn('&nbsp; &nbsp;', hint)
            self.assertFalse(hint.startswith(' '))
            self.assertFalse(hint.startswith('&nbsp;'))
            self.assertFalse(hint.endswith('&nbsp;'))
        self.assertIn(rich_text_key_hints(key_config.get(KeyConfig.MOVE_LEFT)), grid)
        expected_pan = HINT_PAN_MIDDLE_ONLY.format(middle_mouse_icon=middle_button_hint_text())
        self.assertIn(expected_pan, single)
        self.assertIn(expected_pan, grid)
