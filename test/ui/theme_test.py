"""Tests for applying the IntraPaint Ink theme and switching between theme options."""
import json
import sys

from PySide6.QtGui import QFont, QFontInfo, QPalette
from PySide6.QtWidgets import QApplication

from src.ui.theme import INK_THEME_PATH, THEME_INK, THEME_SYSTEM, apply_theme, load_theme_palette
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
