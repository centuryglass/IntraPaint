"""Tests the @menu_action decorator and MenuBuilder."""
from PySide6.QtWidgets import QMainWindow

from src.config.key_config import KeyConfig
from src.util.menu_builder import MenuBuilder, menu_action
from test.base_test_case import IntraPaintTestCase

MENU = 'Test menu'


class _Builder(MenuBuilder):
    @menu_action(MENU, 'undo_shortcut', 0)
    def first(self) -> None:
        """First group's first item."""

    @menu_action(MENU, 'redo_shortcut', 1)
    def second(self) -> None:
        """Same group as the first item."""

    @menu_action(MENU, 'cut_shortcut', 2, separator_before=True)
    def third(self) -> None:
        """Starts a second group."""

    @menu_action(MENU, 'copy_shortcut', 3)
    def fourth(self) -> None:
        """Same group as the third item."""


class MenuBuilderTest(IntraPaintTestCase):
    """Tests separator placement."""

    def test_separator_before(self) -> None:
        """A separator appears only before items that request it, and not again when menus are rebuilt."""
        window = QMainWindow()
        builder = _Builder()
        builder.menu_window = window
        for _ in range(2):
            builder.build_menus()
            layout = [action.isSeparator() for action in builder.menu_actions(MENU)]
            self.assertEqual(layout, [False, False, True, False, False])

    def test_separator_not_first(self) -> None:
        """A separator is never placed at the top of a menu."""
        class _FirstBuilder(MenuBuilder):
            @menu_action(MENU, 'undo_shortcut', 0, separator_before=True)
            def only(self) -> None:
                """The only item."""
        window = QMainWindow()
        builder = _FirstBuilder()
        builder.menu_window = window
        builder.build_menus()
        self.assertEqual([action.isSeparator() for action in builder.menu_actions(MENU)], [False])

    def test_priority_order_across_builders(self) -> None:
        """Actions from a second builder slot in by priority, and leave and return without leaving stray entries."""
        class _Late(MenuBuilder):
            @menu_action(MENU, 'paste_shortcut', 1)
            def late(self) -> None:
                """Sorts between the first builder's first two items."""
        window = QMainWindow()
        main = _Builder()
        main.menu_window = window
        main.build_menus()
        main.add_menu_separator(MENU, 10)
        late = _Late()
        late.menu_window = window
        late.build_menus()
        def _names() -> list[str]:
            return [action.text() if not action.isSeparator() else '----' for action in main.menu_actions(MENU)
                    if action.isVisible()]
        first, second, third, fourth = (KeyConfig().get_label(key) for key in
                                        ('undo_shortcut', 'redo_shortcut', 'cut_shortcut', 'copy_shortcut'))
        late_label = KeyConfig().get_label('paste_shortcut')
        self.assertEqual(_names(), [first, second, late_label, '----', third, fourth, '----'])
        late.clear_menus()
        self.assertEqual(_names(), [first, second, '----', third, fourth, '----'])
        late.build_menus()
        self.assertEqual(_names(), [first, second, late_label, '----', third, fourth, '----'])
