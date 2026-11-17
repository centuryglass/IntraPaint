"""The footer button row every dialog shares: secondary actions at the left, then Cancel and the confirm button.

Confirm and cancel sit in a `QDialogButtonBox`, so the platform decides their order. Buttons are sized to their text
and aligned right. The confirm button is the dialog's one primary button and its default, so Enter triggers it.
"""
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QHBoxLayout, QPushButton, QWidget

from src.ui.button_weight import ButtonWeight, set_button_weight

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.modal.dialog_footer'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


CANCEL_BUTTON_LABEL = _tr('Cancel')


class DialogFooter(QWidget):
    """A dialog's footer: optional secondary buttons, then the platform-ordered cancel and confirm buttons.

    `confirm_text` names the action ("Resize canvas"), never "OK". Pass `destructive=True` when confirming discards
    work, which draws the confirm button in the signal color instead of as the primary button. Pass `cancel_text` to
    relabel the cancel button, such as "Close" on a dialog where nothing is pending, or None to omit it.
    """

    accepted = Signal()
    rejected = Signal()

    def __init__(self, confirm_text: str, parent: Optional[QWidget] = None, cancel_text: Optional[str] =
                 CANCEL_BUTTON_LABEL, destructive: bool = False) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addStretch(1)
        self._box = QDialogButtonBox(self)
        self._layout.addWidget(self._box)

        self.confirm_button: QPushButton = self._box.addButton(confirm_text, QDialogButtonBox.ButtonRole.AcceptRole)
        self.confirm_button.setDefault(True)
        set_button_weight(self.confirm_button, ButtonWeight.DANGER if destructive else ButtonWeight.PRIMARY)
        self.cancel_button: Optional[QPushButton] = None
        if cancel_text is not None:
            self.cancel_button = self._box.addButton(cancel_text, QDialogButtonBox.ButtonRole.RejectRole)
        self._secondary_count = 0
        self._box.accepted.connect(self.accepted)
        self._box.rejected.connect(self.rejected)

    def add_secondary_button(self, text: str, destructive: bool = False) -> QPushButton:
        """Adds a button for an action other than confirm and cancel, at the left of the footer.

        Connect the returned button's `clicked` signal. `destructive` draws it in the signal color.
        """
        button = QPushButton(text, self)
        button.setAutoDefault(False)
        if destructive:
            set_button_weight(button, ButtonWeight.DANGER)
        self._layout.insertWidget(self._secondary_count, button)
        self._secondary_count += 1
        return button
