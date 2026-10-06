"""Test key string parsing and formatting in key_code_utils."""
from PySide6.QtCore import Qt

from src.util.key_code_utils import get_key_code, get_key_string, get_key_with_modifiers, get_modifiers, \
    get_modifier_string
from test.base_test_case import IntraPaintTestCase

Mod = Qt.KeyboardModifier


class TestKeyCodeUtils(IntraPaintTestCase):
    """Test key string parsing and formatting in key_code_utils."""

    def test_get_key_code(self) -> None:
        """Single key strings map to their Qt key codes."""
        self.assertEqual(get_key_code('A'), Qt.Key.Key_A)
        self.assertEqual(get_key_code('F5'), Qt.Key.Key_F5)
        self.assertEqual(get_key_code('Esc'), Qt.Key.Key_Escape)

    def test_get_key_code_rejects_invalid_strings(self) -> None:
        """Empty, multi-key and unrecognized strings raise ValueError naming the input."""
        for key_string in ('', 'A,B', 'NotAKey'):
            with self.assertRaisesRegex(ValueError, f'"{key_string}"'):
                get_key_code(key_string)

    def test_get_key_string_round_trip(self) -> None:
        """Key codes format with Qt's portable names, which parse back to the same code."""
        self.assertEqual(get_key_string(Qt.Key.Key_A), 'A')
        self.assertEqual(get_key_string(Qt.Key.Key_Escape), 'Esc')
        for key in (Qt.Key.Key_A, Qt.Key.Key_Escape, Qt.Key.Key_PageDown, Qt.Key.Key_F12, Qt.Key.Key_BracketLeft):
            self.assertEqual(get_key_code(get_key_string(key)), key)

    def test_get_modifiers(self) -> None:
        """Modifier names combine, case-insensitively, from a '+'-separated string or a list."""
        self.assertEqual(get_modifiers('Ctrl'), Mod.ControlModifier)
        self.assertEqual(get_modifiers('control+SHIFT'), Mod.ControlModifier | Mod.ShiftModifier)
        self.assertEqual(get_modifiers(['alt', 'Ctrl']), Mod.AltModifier | Mod.ControlModifier)
        self.assertEqual(get_modifiers([]), Mod.NoModifier)

    def test_get_modifiers_rejects_unknown_names(self) -> None:
        """Anything other than ctrl, control, shift or alt raises ValueError, including Meta and the empty string."""
        for modifier_str in ('A', 'Meta', 'Ctrl+A', ''):
            with self.assertRaises(ValueError, msg=modifier_str):
                get_modifiers(modifier_str)

    def test_get_key_with_modifiers(self) -> None:
        """The last segment is the key, and earlier segments are modifiers."""
        self.assertEqual(get_key_with_modifiers('A'), (Qt.Key.Key_A, Mod.NoModifier))
        self.assertEqual(get_key_with_modifiers('Ctrl+A'), (Qt.Key.Key_A, Mod.ControlModifier))
        self.assertEqual(get_key_with_modifiers('Ctrl+Shift+S'),
                         (Qt.Key.Key_S, Mod.ControlModifier | Mod.ShiftModifier))

    def test_get_key_with_modifiers_adds_shift_for_shifted_symbols(self) -> None:
        """Symbols typed with Shift, like '?' and '!', imply ShiftModifier."""
        self.assertEqual(get_key_with_modifiers('?'), (Qt.Key.Key_Question, Mod.ShiftModifier))
        self.assertEqual(get_key_with_modifiers('Alt+!'), (Qt.Key.Key_Exclam, Mod.AltModifier | Mod.ShiftModifier))
        self.assertEqual(get_key_with_modifiers('/'), (Qt.Key.Key_Slash, Mod.NoModifier))

    def test_get_key_with_modifiers_modifier_only(self) -> None:
        """A string of modifier names that Qt can't parse as a key returns no key and all the modifiers."""
        self.assertEqual(get_key_with_modifiers('Ctrl'), (None, Mod.ControlModifier))

    def test_get_key_with_modifiers_rejects_key_lists(self) -> None:
        """A comma-separated key list fails its assertion."""
        with self.assertRaises(AssertionError):
            get_key_with_modifiers('A,B')

    def test_get_modifier_string(self) -> None:
        """Modifiers format as display symbols in Alt, Shift, Ctrl, Meta order."""
        self.assertEqual(get_modifier_string(Mod.NoModifier), '')
        self.assertEqual(get_modifier_string(Mod.ControlModifier), '⌃')
        self.assertEqual(get_modifier_string(Mod.ControlModifier | Mod.ShiftModifier | Mod.AltModifier
                                             | Mod.MetaModifier), '⎇+⇧+⌃+⌘')
