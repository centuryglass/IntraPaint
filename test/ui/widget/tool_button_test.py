"""Tests how ToolButton draws its tool's icon tile in each state."""
import sys
from unittest.mock import MagicMock

from PySide6.QtCore import QPoint, QSize
from PySide6.QtGui import QColor, QIcon, QImage, QPalette, QPixmap
from PySide6.QtWidgets import QApplication

from src.config.key_config import KeyConfig
from src.tools.base_tool import BaseTool
from src.ui.widget.key_hint_label import compact_key_text
from src.ui.widget.tool_button import ToolButton, TOOL_ICON_SIZE, PLATE_MARGIN, PLATE_SHADOW_OFFSET, MAX_KEY_HINT_SHARE
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class ToolButtonTest(IntraPaintTestCase):
    """Renders a ToolButton for a tool with a blank icon and no activation key."""

    def setUp(self) -> None:
        super().setUp()
        tool = MagicMock(spec=BaseTool)
        icon_pixmap = QPixmap(QSize(16, 16))
        icon_pixmap.fill(QColor(0, 0, 0, 0))
        tool.get_icon.return_value = QIcon(icon_pixmap)
        tool.label = 'Test tool'
        tool.get_activation_config_key.return_value = None
        self.button = ToolButton(tool)
        self.button.resize(self.button.sizeHint())
        self.button.resizeEvent(None)

    def _plate_points(self) -> tuple[QPoint, QPoint]:
        """Returns a point just inside the plate's left edge, and a point in the shadow below the plate."""
        icon_bounds = self.button._icon_bounds  # pylint: disable=protected-access
        center_x = icon_bounds.center().x()
        inside = QPoint(icon_bounds.left() - PLATE_MARGIN + 2, icon_bounds.center().y())
        shadow = QPoint(center_x, icon_bounds.bottom() + PLATE_MARGIN + PLATE_SHADOW_OFFSET)
        return inside, shadow

    def _render(self) -> QImage:
        return self.button.grab().toImage()

    def test_size(self) -> None:
        """The button is a fixed square, with room for the active plate's shadow inside it."""
        self.assertEqual(self.button.size(), QSize(TOOL_ICON_SIZE, TOOL_ICON_SIZE))
        _, shadow = self._plate_points()
        self.assertLess(shadow.y(), TOOL_ICON_SIZE)

    def test_active_tool_draws_accent_plate(self) -> None:
        """The active tool's icon sits on an accent plate with an ink shadow below it."""
        self.button.is_active = True
        palette = self.button.palette()
        image = self._render()
        inside, shadow = self._plate_points()
        self.assertEqual(image.pixelColor(inside), palette.color(QPalette.ColorRole.Highlight))
        self.assertEqual(image.pixelColor(shadow), palette.color(QPalette.ColorRole.Shadow))

    def test_inactive_tool_draws_no_plate(self) -> None:
        """An inactive, unhovered tool draws no plate."""
        self.button.is_active = False
        image = self._render()
        inside, shadow = self._plate_points()
        highlight = self.button.palette().color(QPalette.ColorRole.Highlight)
        ink = self.button.palette().color(QPalette.ColorRole.Shadow)
        self.assertNotEqual(image.pixelColor(inside), highlight)
        self.assertNotEqual(image.pixelColor(shadow), ink)


class ToolButtonKeyHintTest(IntraPaintTestCase):
    """Checks where a smaller ToolButton puts its key hint."""

    def _button(self, config_key: str) -> ToolButton:
        tool = MagicMock(spec=BaseTool)
        tool.get_icon.return_value = QIcon()
        tool.label = 'Test tool'
        tool.get_activation_config_key.return_value = config_key
        tool.get_tooltip_text.return_value = ''
        return ToolButton(tool)

    def test_key_hint_hidden_unless_requested(self) -> None:
        """Below `TOOL_ICON_SIZE`, the key hint shows only when `set_edge_length` asks for it."""
        button = self._button(KeyConfig.TEXT_TOOL_KEY)
        button.set_edge_length(40)
        self.assertFalse(button._key_hint.isVisibleTo(button))  # pylint: disable=protected-access
        button.set_edge_length(40, show_key_hint=True)
        self.assertTrue(button._key_hint.isVisibleTo(button))  # pylint: disable=protected-access

    def test_icon_leaves_most_of_the_key_hint_clear(self) -> None:
        """With the key hint, the icon moves to the top left and covers at most a quarter of the hint."""
        button = self._button(KeyConfig.TEXT_TOOL_KEY)
        button.set_edge_length(40, show_key_hint=True)
        # pylint: disable=protected-access
        hint = button._key_hint.geometry()
        overlap = button._icon_bounds.intersected(hint)
        self.assertLessEqual(overlap.width() * overlap.height(), hint.width() * hint.height() / 4)
        self.assertTrue(button.rect().contains(hint))

    def test_wide_key_hint_switches_to_modifier_symbols(self) -> None:
        """A key hint too wide for the button shows its modifiers as symbols, and switches back when the button is
        large enough for the full text."""
        KeyConfig().set(KeyConfig.TEXT_TOOL_KEY, 'Shift+S')
        button = self._button(KeyConfig.TEXT_TOOL_KEY)
        button.set_edge_length(40, show_key_hint=True)
        # pylint: disable=protected-access
        self.assertTrue(button._key_hint.compact)
        self.assertTrue(button._key_hint.isVisibleTo(button))
        self.assertLessEqual(button._key_hint.width(), round(40 * MAX_KEY_HINT_SHARE))
        button.set_edge_length(TOOL_ICON_SIZE, show_key_hint=True)
        self.assertFalse(button._key_hint.compact)

    def test_key_hint_too_wide_even_with_symbols_stays_hidden(self) -> None:
        """A key hint still too wide with modifier symbols is hidden."""
        KeyConfig().set(KeyConfig.TEXT_TOOL_KEY, 'Ctrl+Shift+PgDown')
        button = self._button(KeyConfig.TEXT_TOOL_KEY)
        button.set_edge_length(40, show_key_hint=True)
        self.assertFalse(button._key_hint.isVisibleTo(button))  # pylint: disable=protected-access


class CompactKeyTextTest(IntraPaintTestCase):
    """Tests modifier symbol substitution."""

    def test_modifiers_become_symbols(self) -> None:
        """Each modifier name and its "+" become one symbol, and other keys stay as they are."""
        self.assertEqual(compact_key_text('Shift+S'), '⇧S')
        self.assertEqual(compact_key_text('Ctrl+Shift+T'), '⌃⇧T')
        self.assertEqual(compact_key_text('Alt+F4, Ctrl++'), '⎇F4, ⌃+')
        self.assertEqual(compact_key_text('Shift'), '⇧')
        self.assertEqual(compact_key_text('PgUp'), 'PgUp')
