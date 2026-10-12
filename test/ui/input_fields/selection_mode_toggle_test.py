"""Tests SelectionModeToggle: it edits `Cache.SELECTION_MODE`, highlights the mode held modifiers select, and shows
   the selection modifier keys on its buttons."""
from PySide6.QtCore import Qt, QPoint
from PySide6 import QtTest
from PySide6.QtWidgets import QFrame

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.ui.input_fields.selection_mode_toggle import SelectionModeToggle, MODE_LABELS, MODE_ORDER
from src.ui.widget.key_hint_label import KeyHintLabel
from src.util.visual.selection_mode import SelectionMode, SelectionModifiers
from test.base_test_case import IntraPaintTestCase

SHIFT = Qt.KeyboardModifier.ShiftModifier
ALT = Qt.KeyboardModifier.AltModifier
CTRL = Qt.KeyboardModifier.ControlModifier


class SelectionModeToggleTest(IntraPaintTestCase):
    """Tests SelectionModeToggle."""

    def setUp(self) -> None:
        super().setUp()
        Cache().restore_default_options(Cache.SELECTION_MODE)

    def _toggle(self, modifiers: SelectionModifiers = SelectionModifiers.ADD_AND_SUBTRACT) -> SelectionModeToggle:
        toggle = SelectionModeToggle(modifiers=modifiers)
        toggle.resize(toggle.sizeHint())
        toggle.show()  # Delivers the pending resize that lays out the buttons.
        return toggle

    def assert_highlighted(self, toggle: SelectionModeToggle, mode: SelectionMode) -> None:
        """Asserts that only the given mode's button is drawn pressed in."""
        for other_mode in MODE_ORDER:
            shadow = toggle.option_label(MODE_LABELS[other_mode]).frameShadow()
            self.assertEqual(shadow == QFrame.Shadow.Sunken, other_mode == mode, f'{other_mode} highlight')

    def test_shows_stored_mode(self) -> None:
        """The toggle starts on the stored mode, and follows changes to it."""
        Cache().set(Cache.SELECTION_MODE, SelectionMode.INTERSECT.value)
        toggle = self._toggle()
        self.assert_highlighted(toggle, SelectionMode.INTERSECT)
        Cache().set(Cache.SELECTION_MODE, SelectionMode.SUBTRACT.value)
        self.assert_highlighted(toggle, SelectionMode.SUBTRACT)

    def test_click_sets_stored_mode(self) -> None:
        """Clicking a button stores its mode. Buttons fill the grid row by row: Add, Subtract, then Replace,
           Intersect."""
        toggle = self._toggle()
        for index, mode in enumerate(MODE_ORDER):
            x, y, width, height = toggle.cell_geometry(index)
            QtTest.QTest.mouseClick(toggle, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                                    QPoint(x + width // 2, y + height // 2))
            self.assertEqual(Cache().get(Cache.SELECTION_MODE), mode.value)
            self.assert_highlighted(toggle, mode)

    def test_held_modifiers_highlight_override(self) -> None:
        """Held selection modifiers highlight the mode they select without storing it, until they are released."""
        Cache().set(Cache.SELECTION_MODE, SelectionMode.REPLACE.value)
        toggle = self._toggle()
        for modifiers, mode in ((SHIFT, SelectionMode.ADD), (ALT, SelectionMode.SUBTRACT),
                                (SHIFT | ALT, SelectionMode.INTERSECT), (CTRL | SHIFT, SelectionMode.REPLACE)):
            toggle.set_held_modifiers(modifiers)
            self.assert_highlighted(toggle, mode)
            self.assertEqual(Cache().get(Cache.SELECTION_MODE), SelectionMode.REPLACE.value)
        toggle.set_held_modifiers(Qt.KeyboardModifier.NoModifier)
        self.assert_highlighted(toggle, SelectionMode.REPLACE)

    def test_without_modifiers_ignores_held_keys(self) -> None:
        """With no modifier rule, held modifiers change nothing, and no keycaps are shown."""
        toggle = self._toggle(SelectionModifiers.NONE)
        toggle.set_held_modifiers(ALT)
        self.assert_highlighted(toggle, SelectionMode.ADD)
        self.assertEqual(toggle.findChildren(KeyHintLabel), [])

    def test_brush_rule_shows_subtract_only(self) -> None:
        """Under the brush rule, only Subtract shows a keycap, Shift changes nothing, and Shift with Alt keeps the stored
           mode, since that press draws a fixed-angle line."""
        Cache().set(Cache.SELECTION_MODE, SelectionMode.REPLACE.value)
        toggle = self._toggle(SelectionModifiers.BRUSH)
        self.assertEqual(len(toggle.findChildren(KeyHintLabel)), 1)
        toggle.set_held_modifiers(ALT)
        self.assert_highlighted(toggle, SelectionMode.SUBTRACT)
        for modifiers in (SHIFT, SHIFT | ALT):
            toggle.set_held_modifiers(modifiers)
            self.assert_highlighted(toggle, SelectionMode.REPLACE)

    def test_keycaps_follow_keybindings(self) -> None:
        """Each button shows its modifier keycaps inside its own bounds, and an unbound modifier's keycaps hide."""
        toggle = self._toggle()
        keycaps = toggle.findChildren(KeyHintLabel)
        self.assertEqual(len(keycaps), 5)  # Add, Subtract, Replace, and Add and Subtract on Intersect.
        for index in range(len(MODE_ORDER)):
            x, y, width, height = toggle.cell_geometry(index)
            cell = toggle.option_label(MODE_LABELS[MODE_ORDER[index]]).geometry()
            self.assertEqual((cell.x(), cell.y(), cell.width(), cell.height()), (x, y, width, height))
        for keycap in keycaps:
            self.assertTrue(any(toggle.option_label(MODE_LABELS[mode]).geometry().contains(keycap.geometry())
                                for mode in MODE_ORDER), 'Keycap outside every button')
        KeyConfig().set(KeyConfig.SELECTION_SUBTRACT_MODIFIER, '')
        # Replace's, and Add's on Intersect. Add's own keycap stays hidden, since Add is the stored mode.
        self.assertEqual(sum(1 for keycap in keycaps if not keycap.isHidden()), 2)

    def test_stored_mode_hides_its_keycaps(self) -> None:
        """The stored mode's button hides its keycaps, without resizing, and shows them again once another mode is
           stored. A button highlighted by held modifiers keeps its keycaps."""
        toggle = self._toggle()
        add_keycap = toggle.option_label(MODE_LABELS[SelectionMode.ADD]).geometry()
        visible = [keycap for keycap in toggle.findChildren(KeyHintLabel) if not keycap.isHidden()]
        self.assertEqual(len(visible), 4)
        self.assertFalse(any(add_keycap.contains(keycap.geometry()) for keycap in visible))
        size = toggle.sizeHint()
        Cache().set(Cache.SELECTION_MODE, SelectionMode.REPLACE.value)
        visible = [keycap for keycap in toggle.findChildren(KeyHintLabel) if not keycap.isHidden()]
        self.assertEqual(len(visible), 4)
        self.assertTrue(any(add_keycap.contains(keycap.geometry()) for keycap in visible))
        self.assertEqual(toggle.sizeHint(), size)
        toggle.set_held_modifiers(SHIFT)
        self.assert_highlighted(toggle, SelectionMode.ADD)
        self.assertTrue(any(add_keycap.contains(keycap.geometry()) and not keycap.isHidden()
                            for keycap in toggle.findChildren(KeyHintLabel)))
