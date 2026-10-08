"""Tests for applying the IntraPaint Ink theme and switching between theme options."""
import json
import sys

from PySide6.QtGui import QFont, QFontInfo, QPalette
from PySide6.QtWidgets import QApplication, QPushButton, QStyle

from src.ui.ink_style import InkColors, InkStyle, STICKER_OFFSET, set_primary_button
from src.ui.theme import (INK_THEME_PATH, THEME_INK, THEME_SYSTEM, apply_overlay_scroll_bars, apply_style, apply_theme,
                          load_theme_palette)
from src.util.gc_paused import gc_paused
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

_ALL_ROLES = [role for role in QPalette.ColorRole
              if role not in (QPalette.ColorRole.NoRole, QPalette.ColorRole.NColorRoles)]
_GROUPS = (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled)


def _load_theme_data() -> dict:
    with open(INK_THEME_PATH, encoding='utf-8') as theme_file:
        return json.load(theme_file)


class ThemeTest(IntraPaintTestCase):
    """The test session applies THEME_INK in conftest.py, so each test starts and ends with it applied."""

    def tearDown(self) -> None:
        apply_overlay_scroll_bars(True)
        apply_style('Fusion')
        apply_theme(THEME_INK)
        super().tearDown()

    def test_ink_theme_sets_every_palette_role(self):
        """A role left to the system would make colors depend on the platform again."""
        defined_roles = set(_load_theme_data()['palette']['all'])
        self.assertEqual(set(), {role.name for role in _ALL_ROLES} - defined_roles)

    def test_ink_theme_palette_applied(self):
        palette_data = _load_theme_data()['palette']
        palette = app.palette()
        for role in _ALL_ROLES:
            for group in _GROUPS:
                expected = palette_data['all'][role.name]
                if group == QPalette.ColorGroup.Disabled:
                    expected = palette_data['disabled'].get(role.name, expected)
                self.assertEqual(expected, palette.color(group, role).name(), f'{group.name} {role.name}')

    def test_ink_theme_font_loaded(self):
        """The bundled font must resolve, not fall back to a system font with the same requested family name."""
        font = app.font()
        self.assertEqual('IBM Plex Sans', QFontInfo(font).family())
        self.assertEqual(1, font.featureValue(QFont.Tag('zero')))

    def test_theme_change_keeps_font_size(self):
        point_size = app.font().pointSize()
        apply_theme(THEME_SYSTEM)
        self.assertEqual(point_size, app.font().pointSize())
        apply_theme(THEME_INK)
        self.assertEqual(point_size, app.font().pointSize())

    def test_system_theme_restores_system_look(self):
        apply_theme(THEME_SYSTEM)
        self.assertNotEqual('IBM Plex Sans', app.font().family())
        self.assertNotEqual(_load_theme_data()['palette']['all']['Window'],
                            app.palette().color(QPalette.ColorRole.Window).name())

    def test_ink_theme_clears_stylesheet(self):
        with gc_paused():
            app.setStyleSheet('QWidget { margin: 1px; }')
        apply_theme(THEME_INK)
        self.assertEqual('', app.styleSheet())

    def test_palette_rejects_invalid_names_and_colors(self):
        for palette_data in ({'all': {'Windw': '#000000'}},
                             {'all': {'NoRole': '#000000'}},
                             {'all': {'Window': 'not a color'}},
                             {'inactive': {'Window': '#000000'}}):
            with self.assertRaises(ValueError, msg=str(palette_data)):
                load_theme_palette(palette_data)

    def test_palette_group_overrides_all(self):
        palette = load_theme_palette({'disabled': {'Text': '#ff0000'}, 'all': {'Text': '#00ff00'}})
        self.assertEqual('#00ff00', palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text).name())
        self.assertEqual('#ff0000', palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text).name())

    def test_ink_theme_installs_ink_style(self):
        """The Ink theme wraps the configured style in InkStyle, and other themes use the configured style alone."""
        self.assertIsInstance(app.style(), InkStyle)
        self.assertEqual('fusion', app.style().baseStyle().name().lower())
        apply_theme(THEME_SYSTEM)
        self.assertNotIsInstance(app.style(), InkStyle)
        self.assertEqual('fusion', app.style().name().lower())
        apply_theme(THEME_INK)
        self.assertIsInstance(app.style(), InkStyle)

    def test_style_change_keeps_ink_style_and_palette(self):
        window_color = app.palette().color(QPalette.ColorRole.Window).name()
        apply_style('Windows')
        self.assertIsInstance(app.style(), InkStyle)
        self.assertEqual('windows', app.style().baseStyle().name().lower())
        self.assertEqual(window_color, app.palette().color(QPalette.ColorRole.Window).name())

    def test_unknown_style_falls_back_to_fusion(self):
        with self.assertLogs('src.ui.theme', level='ERROR'):
            apply_style('NotAStyle')
        self.assertEqual('fusion', app.style().baseStyle().name().lower())

    def test_overlay_scroll_bar_option(self):
        transient = QStyle.StyleHint.SH_ScrollBar_Transient
        self.assertTrue(app.style().styleHint(transient))
        apply_overlay_scroll_bars(False)
        self.assertIsInstance(app.style(), InkStyle)
        self.assertFalse(app.style().styleHint(transient))
        apply_overlay_scroll_bars(True)
        self.assertTrue(app.style().styleHint(transient))

    def test_ink_style_colors_parsed(self):
        colors = InkColors.from_theme_data(_load_theme_data()['style_colors'])
        self.assertEqual('#1e4544', colors.accent_wash.name())
        for color_data in ({}, {**_load_theme_data()['style_colors'], 'accent_wash': 'not a color'}):
            with self.assertRaises(ValueError):
                InkColors.from_theme_data(color_data)

    def test_primary_button_makes_room_for_its_offset(self):
        """A primary button is taller by its raised offset, and wide enough for its bolder label."""
        plain = QPushButton('Generate')
        primary = QPushButton('Generate')
        set_primary_button(primary)
        self.assertEqual(plain.sizeHint().height() + STICKER_OFFSET, primary.sizeHint().height())
        self.assertGreaterEqual(primary.sizeHint().width(), plain.sizeHint().width())
