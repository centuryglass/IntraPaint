"""Tests the panel component kit: PanelSection, PanelHeader, DisabledBanner, button weights, LabelColumnLayout and
the reset helper. Events are synthesized and nothing waits on the event loop."""
import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QWidget

from src.config.application_config import AppConfig
from src.ui.button_weight import ButtonWeight, button_weight, set_button_weight
from src.ui.ink_style import InkStyle
from src.ui.layout.label_column_layout import LabelColumnLayout, normalize_row_label
from src.ui.panel.panel_reset import reset_config_keys
from src.ui.widget.disabled_banner import DisabledBanner
from src.ui.widget.keycap_badge import KeycapBadge
from src.ui.widget.panel_header import MORE_TOOLTIP, PanelHeader, RESET_TOOLTIP
from src.ui.widget.panel_section import PanelSection
from src.undo_stack import UndoStack
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class _Values(QObject):
    """Stands in for a control with a value-changed signal."""
    changed = Signal(int)


class PanelSectionTest(IntraPaintTestCase):
    """Tests collapsing, remembering state, and the summary."""

    def _section(self, expanded: bool = True) -> PanelSection:
        section = PanelSection('Size', QLabel('body'), expanded=expanded)
        section.resize(240, 80)
        return section

    def test_click_toggles_and_emits(self) -> None:
        """Clicking the header collapses and expands the body, and reports the remembered choice."""
        section = self._section()
        reported: list[bool] = []
        section.expanded_changed.connect(reported.append)
        section.header_button.click()
        self.assertTrue(section.body.isHidden())
        self.assertFalse(section.is_expanded())
        section.header_button.click()
        self.assertFalse(section.body.isHidden())
        self.assertEqual(reported, [False, True])

    def test_restored_state_is_not_reported_twice(self) -> None:
        """Setting the state the section already has emits nothing, and a collapsed start hides the body."""
        section = self._section(expanded=False)
        self.assertTrue(section.body.isHidden())
        reported: list[bool] = []
        section.expanded_changed.connect(reported.append)
        section.set_expanded(False)
        self.assertEqual(reported, [])

    def test_forced_collapse_keeps_remembered_choice(self) -> None:
        """A forced collapse hides the body, ignores header clicks, and leaves the remembered choice alone."""
        section = self._section()
        section.set_forced_collapsed(True)
        self.assertTrue(section.body.isHidden())
        self.assertTrue(section.is_collapsed())
        self.assertTrue(section.is_expanded())
        section.header_button.click()
        self.assertTrue(section.is_expanded())
        self.assertTrue(section.body.isHidden())
        section.set_forced_collapsed(False)
        self.assertFalse(section.body.isHidden())

    def test_summary_follows_bound_signals(self) -> None:
        """A bound summary is computed immediately and again after each change signal."""
        values = _Values()
        state = {'size': 512}
        section = self._section()
        section.bind_summary(lambda: f'{state["size"]} x {state["size"]}', values.changed)
        self.assertEqual(section.summary(), '512 x 512')
        state['size'] = 768
        values.changed.emit(768)
        self.assertEqual(section.summary(), '768 x 768')
        self.assertEqual(section.header_button.accessibleDescription(), '768 x 768')

    def test_header_actions(self) -> None:
        """Header actions and keycaps are added to the header, outside the body."""
        section = self._section()
        button = QPushButton('LoRA')
        section.add_header_widget(button)
        badge = section.add_header_keycap('Q')
        self.assertIsInstance(badge, KeycapBadge)
        self.assertEqual(badge.text, 'Q')
        self.assertFalse(section.body.isAncestorOf(button))
        self.assertIs(button.parentWidget(), section)


class PanelHeaderTest(IntraPaintTestCase):
    """Tests the panel header's buttons, key badge and popover."""

    def test_key_badge_hidden_without_key(self) -> None:
        """The keycap shows only while the header has key text."""
        header = PanelHeader('Brush', key_text='B')
        header.show()
        self.assertTrue(header.key_badge.isVisible())
        self.assertEqual(header.key_badge.text, 'B')
        header.set_key_text('')
        self.assertFalse(header.key_badge.isVisible())

    def test_reset_signal_and_tooltips(self) -> None:
        """The reset button emits reset_requested, and both icon-only buttons have tooltips."""
        header = PanelHeader('Brush')
        resets: list[bool] = []
        header.reset_requested.connect(lambda: resets.append(True))
        header.reset_button.click()
        self.assertEqual(resets, [True])
        self.assertEqual(header.reset_button.toolTip(), RESET_TOOLTIP)
        self.assertEqual(header.more_button.toolTip(), MORE_TOOLTIP)
        header.set_reset_tooltip('Ctrl+R')
        self.assertIn('Ctrl+R', header.reset_button.toolTip())
        header.set_reset_tooltip()
        self.assertEqual(header.reset_button.toolTip(), RESET_TOOLTIP)

    def test_more_button_follows_popover_content(self) -> None:
        """The More button is visible only while the popover has content, and clicking it asks the owner first."""
        header = PanelHeader('Brush')
        header.show()
        self.assertFalse(header.more_button.isVisible())
        content = QLabel('extra')
        header.set_popover_content(content)
        self.assertTrue(header.more_button.isVisible())
        self.assertIs(header.popover.content, content)
        requests: list[bool] = []
        header.more_requested.connect(lambda: requests.append(True))
        header.more_button.click()
        self.assertEqual(requests, [True])
        self.assertTrue(header.popover.isVisible())
        header.popover.hide()
        header.set_popover_content(None)
        self.assertFalse(header.more_button.isVisible())

    def test_set_name(self) -> None:
        """set_name changes the shown name."""
        header = PanelHeader('Brush')
        header.set_name('Eraser')
        self.assertEqual(header.name(), 'Eraser')


class DisabledBannerTest(IntraPaintTestCase):
    """Tests the disabled banner's message and fix button."""

    def test_fix_button(self) -> None:
        """The fix button emits fix_requested, and an empty fix text hides it."""
        banner = DisabledBanner('"Sky inpaint 3" is locked', 'Unlock')
        banner.show()
        fixes: list[bool] = []
        banner.fix_requested.connect(lambda: fixes.append(True))
        self.assertTrue(banner.fix_button.isVisible())
        banner.fix_button.click()
        self.assertEqual(fixes, [True])
        banner.set_fix('')
        self.assertFalse(banner.fix_button.isVisible())
        banner.set_message('Other')
        self.assertEqual(banner.message(), 'Other')


class ButtonWeightTest(IntraPaintTestCase):
    """Tests the four button weights."""

    def test_weights_replace_each_other(self) -> None:
        """Each weight reads back as set, and setting one clears the previous."""
        button = QPushButton('Go')
        for weight in (ButtonWeight.PRIMARY, ButtonWeight.DANGER, ButtonWeight.FLAT, ButtonWeight.STANDARD,
                       ButtonWeight.DANGER):
            set_button_weight(button, weight)
            self.assertEqual(button_weight(button), weight)
        self.assertFalse(button.isFlat())

    def test_danger_text_uses_signal_color(self) -> None:
        """A danger button's text is drawn in the signal color, and a standard button's is not."""
        style = QApplication.style()
        if not isinstance(style, InkStyle):
            self.skipTest('Requires the Ink style')
        signal = style.colors.signal

        def _has_signal_pixels(weight: ButtonWeight) -> bool:
            button = QPushButton('Delete everything')
            set_button_weight(button, weight)
            button.resize(160, 32)
            image = button.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)
            for y in range(image.height()):
                for x in range(image.width()):
                    color = QColor(image.pixel(x, y))
                    if abs(color.red() - signal.red()) < 8 and abs(color.green() - signal.green()) < 8 \
                            and abs(color.blue() - signal.blue()) < 8:
                        return True
            return False
        self.assertTrue(_has_signal_pixels(ButtonWeight.DANGER))
        self.assertFalse(_has_signal_pixels(ButtonWeight.STANDARD))


class LabelColumnLayoutTest(IntraPaintTestCase):
    """Tests the shared label column."""

    def test_labels_are_normalized(self) -> None:
        """Trailing colons and whitespace are removed from row labels."""
        self.assertEqual(normalize_row_label(' Sampling method: '), 'Sampling method')
        self.assertEqual(normalize_row_label('Seed'), 'Seed')

    def test_rows_share_a_label_column(self) -> None:
        """Fields of different rows start at the same x position, whatever their label widths."""
        host = QWidget()
        layout = LabelColumnLayout(host)
        short_field, long_field = QLineEdit(), QLineEdit()
        label = layout.add_row('Seed:', short_field)
        layout.add_row('Sampling method', long_field)
        host.resize(300, 100)
        host.show()
        layout.activate()
        self.assertEqual(label.text(), 'Seed')
        self.assertIs(label.buddy(), short_field)
        self.assertEqual(short_field.x(), long_field.x())
        self.assertGreater(short_field.x(), label.width() - 1)


class ResetConfigKeysTest(IntraPaintTestCase):
    """Tests restoring declared config keys to their defaults."""

    def test_reset_restores_declared_keys_only(self) -> None:
        """Declared keys return to their defaults, and other keys keep their values."""
        config = AppConfig()
        declared, other = self._two_int_keys(config)
        for key in (declared, other):
            config.set(key, config.get_default(key) + 1)
        self.assertTrue(reset_config_keys(config, [declared]))
        self.assertEqual(config.get(declared), config.get_default(declared))
        self.assertEqual(config.get(other), config.get_default(other) + 1)

    def test_reset_without_changes_does_nothing(self) -> None:
        """Keys already at their defaults report no change and record no undo step."""
        config = AppConfig()
        declared, _ = self._two_int_keys(config)
        undo_count = UndoStack().undo_count()
        self.assertFalse(reset_config_keys(config, [declared], UndoStack()))
        self.assertEqual(UndoStack().undo_count(), undo_count)

    def test_reset_is_one_undo_step(self) -> None:
        """With an undo stack, resetting several keys is one step that undo and redo both apply fully."""
        config = AppConfig()
        first, second = self._two_int_keys(config)
        for key in (first, second):
            config.set(key, config.get_default(key) + 1)
        undo_count = UndoStack().undo_count()
        self.assertTrue(reset_config_keys(config, [first, second], UndoStack()))
        self.assertEqual(UndoStack().undo_count(), undo_count + 1)
        UndoStack().undo()
        self.assertEqual(config.get(first), config.get_default(first) + 1)
        self.assertEqual(config.get(second), config.get_default(second) + 1)
        UndoStack().redo()
        self.assertEqual(config.get(first), config.get_default(first))
        self.assertEqual(config.get(second), config.get_default(second))

    def test_unknown_key(self) -> None:
        """An undeclared key raises KeyError."""
        with self.assertRaises(KeyError):
            reset_config_keys(AppConfig(), ['no such key'])

    @staticmethod
    def _two_int_keys(config: AppConfig) -> tuple[str, str]:
        keys = [key for key in config.get_keys() if config.get_data_type(key) == 'int'
                and isinstance(config.get_default(key), int) and not isinstance(config.get_default(key), bool)
                and not _has_options(config, key)]
        return keys[0], keys[1]


def _has_options(config: AppConfig, key: str) -> bool:
    try:
        return len(config.get_options(key)) > 0
    except RuntimeError:
        return False
