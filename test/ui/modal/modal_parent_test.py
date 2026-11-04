"""Tests that modal dialogs sit above the windows they block."""
from PySide6.QtWidgets import QDialog, QMainWindow, QMessageBox, QWidget

from src.ui.modal.color_dialog import ColorDialog
from src.ui.modal.modal_parent import modal_parent
from src.ui.modal.modal_utils import _new_message_box
from src.ui.modal.new_image_modal import NewImageModal
from test.base_test_case import IntraPaintTestCase


class ModalParentTest(IntraPaintTestCase):
    """Dialogs opened without an explicit parent become children of the window they block."""

    def setUp(self) -> None:
        super().setUp()
        self.main_window = QMainWindow()
        self.main_window.show()

    def tearDown(self) -> None:
        self.main_window.close()
        self.main_window.deleteLater()
        super().tearDown()

    def test_explicit_parent_wins(self) -> None:
        """A parent passed by the caller is used as given."""
        other = QWidget()
        self.assertIs(modal_parent(other), other)

    def test_falls_back_to_visible_main_window(self) -> None:
        """With no active window or modal, the visible main window is the parent."""
        self.assertIs(modal_parent(), self.main_window)

    def test_no_main_window_gives_no_parent(self) -> None:
        """Before any main window shows, there is nothing to parent to."""
        self.main_window.hide()
        self.assertIsNone(modal_parent())

    def test_open_modal_is_preferred(self) -> None:
        """A dialog opened while another modal is showing stacks over that modal, not the main window."""
        first = QDialog(self.main_window)
        first.setModal(True)
        first.show()
        self.assertIs(modal_parent(), first)

    def test_message_box_has_main_window_parent(self) -> None:
        """Message boxes without a parent, like the editing-failed errors, are parented to the main window."""
        box = _new_message_box(None)
        self.assertIsInstance(box, QMessageBox)
        self.assertIs(box.parent(), self.main_window)

    def test_modals_have_main_window_parent(self) -> None:
        """The modals that used to be parentless are children of the main window."""
        self.assertIs(NewImageModal(512, 512).parent(), self.main_window)
        self.assertIs(ColorDialog().parent(), self.main_window)
