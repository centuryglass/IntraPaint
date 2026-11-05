"""Tests the shared key hint formatting every keycap, tooltip and text hint uses."""
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

from src.ui.widget.key_hint_label import KeyHintLabel
from src.ui.widget.keycap_badge import KeycapBadge
from src.util.visual.key_hint_text import fitted_key_hint_labels, key_hint_labels, key_hint_text, \
    rich_text_key_hints, shortest_key_label
from src.util.visual.keycap import keycap_font, keycap_row_size
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class KeyHintLabelsTest(IntraPaintTestCase):
    """Tests how bindings split into keycap labels."""

    def test_one_label_per_alternative(self) -> None:
        """A binding's keys share a label, and each comma-separated alternative gets its own."""
        self.assertEqual(key_hint_labels('Shift+S,K'), ['Shift+S', 'K'])
        self.assertEqual(key_hint_labels('Shift+S, K'), ['Shift+S', 'K'])
        self.assertEqual(key_hint_labels('Ctrl+Shift+Z'), ['Ctrl+Shift+Z'])
        self.assertEqual(key_hint_labels(''), [])
        self.assertEqual(key_hint_labels(None), [])

    def test_plus_key(self) -> None:
        """A bound plus key stays whole, alone or after modifiers."""
        self.assertEqual(key_hint_labels('+,='), ['+', '='])
        self.assertEqual(key_hint_labels('Ctrl++'), ['Ctrl++'])

    def test_key_names(self) -> None:
        """Modifier spellings are normalized, single keys are upper case, and navigation keys become symbols."""
        self.assertEqual(key_hint_labels('ctrl+control+s'), ['Ctrl+Ctrl+S'])
        self.assertEqual(key_hint_labels('Ctrl+PgDown,Meta+Enter'), ['Ctrl+⇟', '⌘+⏎'])
        self.assertEqual(key_hint_labels('Shift+?'), ['?'])

    def test_other_sources(self) -> None:
        """Key codes, key sequences and modifiers format like the matching config text."""
        self.assertEqual(key_hint_labels(Qt.Key.Key_Delete), ['⌫'])
        self.assertEqual(key_hint_labels(QKeySequence('Ctrl+Up')), ['Ctrl+↑'])
        self.assertEqual(key_hint_labels(Qt.KeyboardModifier.ShiftModifier), ['Shift'])

    def test_compact(self) -> None:
        """Compact labels replace each modifier and its "+" with a symbol, and leave other keys as they are."""
        self.assertEqual(key_hint_labels('Shift+S', compact=True), ['⇧S'])
        self.assertEqual(key_hint_labels('Ctrl+Shift+T', compact=True), ['⌃⇧T'])
        self.assertEqual(key_hint_labels('Alt+F4,Ctrl++', compact=True), ['⎇F4', '⌃+'])
        self.assertEqual(key_hint_labels('Shift', compact=True), ['⇧'])
        self.assertEqual(key_hint_labels('PgUp', compact=True), ['⇞'])

    def test_shortest(self) -> None:
        """The shortest label wins, and the first of those tied for shortest."""
        self.assertEqual(shortest_key_label(['Ctrl+T', 'V', 'W']), ['V'])
        self.assertEqual(shortest_key_label(['Ctrl+T']), ['Ctrl+T'])
        self.assertEqual(shortest_key_label([]), [])

    def test_fitted_labels(self) -> None:
        """Fitting tries all labels, then compact labels, then the shortest compact label."""
        font = keycap_font(QApplication.font())
        keys = 'Shift+S,K'
        full_width = keycap_row_size(key_hint_labels(keys), font).width()
        compact_width = keycap_row_size(key_hint_labels(keys, compact=True), font).width()
        self.assertLess(compact_width, full_width)
        self.assertEqual(fitted_key_hint_labels(keys, font, full_width), ['Shift+S', 'K'])
        self.assertEqual(fitted_key_hint_labels(keys, font, compact_width), ['⇧S', 'K'])
        self.assertEqual(fitted_key_hint_labels(keys, font, 1), ['K'])


class KeyHintFormsTest(IntraPaintTestCase):
    """Tests that every form of a key hint shows the same labels."""

    def test_text_and_rich_text(self) -> None:
        """Plain text joins the labels with a comma, and rich text draws a keycap image per label."""
        self.assertEqual(key_hint_text('Shift+S,K'), 'Shift+S, K')
        self.assertEqual(key_hint_text(''), '')
        self.assertEqual(rich_text_key_hints('Shift+S,K').count('<img'), 2)
        self.assertEqual(rich_text_key_hints(''), '')

    def test_widgets_share_labels(self) -> None:
        """Keycap badges and key hint labels show the same keycaps for a binding, at the same size."""
        badge = KeycapBadge('Shift+S,K')
        label = KeyHintLabel('Shift+S,K')
        label.setFont(badge.font())
        self.assertEqual(badge.labels, ['Shift+S', 'K'])
        self.assertEqual(label.labels, ['Shift+S', 'K'])
        self.assertEqual(badge.sizeHint(), label.sizeHint())
        self.assertGreater(badge.sizeHint().width(), KeycapBadge('Shift+S').sizeHint().width())
