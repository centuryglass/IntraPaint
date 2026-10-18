"""Tests SelectionModeBar: it edits `Cache.SELECTION_MODE` in the fixed order Replace, Add, Subtract, Intersect, hints the
   mode held modifiers select, and names the modifiers in its tooltips."""
from PySide6.QtCore import Qt

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.ui.input_fields.selection_mode_bar import SelectionModeBar, MODE_ORDER
from src.util.visual.selection_mode import SelectionMode, SelectionModifiers
from test.base_test_case import IntraPaintTestCase

SHIFT = Qt.KeyboardModifier.ShiftModifier
ALT = Qt.KeyboardModifier.AltModifier
CTRL = Qt.KeyboardModifier.ControlModifier


class SelectionModeBarTest(IntraPaintTestCase):
    """Tests SelectionModeBar."""

    def setUp(self) -> None:
        super().setUp()
        Cache().restore_default_options(Cache.SELECTION_MODE)

    def test_segment_order_is_fixed(self) -> None:
        """The segments run Replace, Add, Subtract, Intersect."""
        bar = SelectionModeBar()
        self.assertEqual([segment.value for segment in bar.segments],
                         [SelectionMode.REPLACE.value, SelectionMode.ADD.value, SelectionMode.SUBTRACT.value,
                          SelectionMode.INTERSECT.value])

    def test_follows_and_sets_stored_mode(self) -> None:
        """The bar shows the stored mode and follows changes to it, and choosing a segment stores its mode."""
        Cache().set(Cache.SELECTION_MODE, SelectionMode.INTERSECT.value)
        bar = SelectionModeBar()
        self.assertEqual(bar.value(), SelectionMode.INTERSECT.value)
        Cache().set(Cache.SELECTION_MODE, SelectionMode.SUBTRACT.value)
        self.assertEqual(bar.value(), SelectionMode.SUBTRACT.value)
        for mode in MODE_ORDER:
            bar.set_value(mode.value)
            self.assertEqual(Cache().get(Cache.SELECTION_MODE), mode.value)

    def test_held_modifiers_hint_override(self) -> None:
        """Held selection modifiers hint the mode they select without storing it, until they are released."""
        Cache().set(Cache.SELECTION_MODE, SelectionMode.REPLACE.value)
        bar = SelectionModeBar()
        for modifiers, mode in ((SHIFT, SelectionMode.ADD), (ALT, SelectionMode.SUBTRACT),
                                (SHIFT | ALT, SelectionMode.INTERSECT)):
            bar.set_held_modifiers(modifiers)
            self.assertEqual(bar.hint_value(), mode.value)
            self.assertEqual(Cache().get(Cache.SELECTION_MODE), SelectionMode.REPLACE.value)
        bar.set_held_modifiers(Qt.KeyboardModifier.NoModifier)
        self.assertIsNone(bar.hint_value())

    def test_without_modifiers_ignores_held_keys(self) -> None:
        """With no modifier rule, held modifiers hint nothing, and tooltips name no keys."""
        bar = SelectionModeBar(modifiers=SelectionModifiers.NONE)
        bar.set_held_modifiers(ALT)
        self.assertIsNone(bar.hint_value())
        self.assertNotIn('hold', bar.segment_tooltip(2).lower())

    def test_brush_rule_names_subtract_only(self) -> None:
        """Under the brush rule only Subtract has a modifier, and Shift with Alt keeps the stored mode, since that
           press draws a fixed-angle line."""
        Cache().set(Cache.SELECTION_MODE, SelectionMode.REPLACE.value)
        bar = SelectionModeBar(modifiers=SelectionModifiers.BRUSH)
        bar.set_held_modifiers(ALT)
        self.assertEqual(bar.hint_value(), SelectionMode.SUBTRACT.value)
        for modifiers in (SHIFT, SHIFT | ALT):
            bar.set_held_modifiers(modifiers)
            self.assertIsNone(bar.hint_value())
        self.assertEqual(bar.modifier_hint(SelectionMode.ADD), '')
        self.assertEqual(bar.modifier_hint(SelectionMode.SUBTRACT), 'Alt')

    def test_tooltips_follow_keybindings(self) -> None:
        """Each tooltip names the modifiers that pick its mode, and drops them when they are unbound."""
        bar = SelectionModeBar()
        self.assertIn('hold Alt', bar.segment_tooltip(2))
        self.assertIn('hold Shift+Alt', bar.segment_tooltip(3))
        KeyConfig().set(KeyConfig.SELECTION_SUBTRACT_MODIFIER, '')
        self.assertNotIn('hold', bar.segment_tooltip(2))
