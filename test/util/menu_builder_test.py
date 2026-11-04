"""Tests the @menu_action decorator and MenuBuilder."""
from PySide6.QtWidgets import QMainWindow

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
