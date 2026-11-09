"""Pre-save dialog listing everything a save would lose, with a way to save as .ora instead or cancel."""
import html
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.config.application_config import AppConfig
from src.ui.ink_style import set_signal
from src.ui.input_fields.check_box import CheckBox
from src.ui.modal.modal_parent import modal_parent
from src.util.layout import add_layout
from src.util.shared_constants import APP_ICON_PATH

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.save_loss_modal'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


WINDOW_TITLE = _tr('Save will lose data')
INTRO_LABEL = _tr('Saving in this format will lose the following:')
CHECKBOX_LABEL = _tr('Don\'t warn about this again')
BUTTON_SAVE_ORA = _tr('Save as .ora')
BUTTON_SAVE_ANYWAY = _tr('Save anyway')
BUTTON_CANCEL = _tr('Cancel')

SAVE_ORA = 'save_ora'
SAVE_ANYWAY = 'save_anyway'
CANCEL = 'cancel'


@dataclass(frozen=True)
class SaveLoss:
    """One kind of data a save would lose.

    `config_key` is the `AppConfig` boolean that, once false, stops this warning. The dialog's checkbox sets it.
    """
    title: str
    message: str
    config_key: str


class SaveLossModal(QDialog):
    """Lists each `SaveLoss` with its own "don't warn again" checkbox, and offers Save as .ora, Save anyway, Cancel.

    Save as .ora is offered only when `offer_ora` is set, because only the layers loss is fixed by that format.
    """

    def __init__(self, parent: Optional[QWidget], losses: list[SaveLoss], offer_ora: bool) -> None:
        super().__init__(modal_parent(parent))
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setModal(True)
        self.setWindowTitle(WINDOW_TITLE)
        self.choice = CANCEL
        self._checkboxes: list[tuple[SaveLoss, CheckBox]] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(INTRO_LABEL, self))
        for loss in losses:
            title_label = QLabel(f'<b>{html.escape(loss.title)}</b>', self)
            title_label.setTextFormat(Qt.TextFormat.RichText)
            message_label = QLabel(loss.message, self)
            message_label.setWordWrap(True)
            checkbox = CheckBox()
            checkbox.setText(CHECKBOX_LABEL)
            self._checkboxes.append((loss, checkbox))
            layout.addWidget(title_label)
            layout.addWidget(message_label)
            layout.addWidget(checkbox)

        button_row = QHBoxLayout()
        add_layout(layout, button_row)
        button_row.addStretch(1)
        cancel_button = QPushButton(BUTTON_CANCEL, self)
        cancel_button.clicked.connect(self.reject)
        button_row.addWidget(cancel_button)
        if offer_ora:
            ora_button = QPushButton(BUTTON_SAVE_ORA, self)
            ora_button.clicked.connect(lambda: self._finish(SAVE_ORA))
            button_row.addWidget(ora_button)
            ora_button.setDefault(True)
        anyway_button = QPushButton(BUTTON_SAVE_ANYWAY, self)
        set_signal(anyway_button)
        anyway_button.clicked.connect(lambda: self._finish(SAVE_ANYWAY))
        button_row.addWidget(anyway_button)

    def _finish(self, choice: str) -> None:
        self.choice = choice
        self.accept()

    def done(self, result: int) -> None:
        """Stores the "don't warn again" boxes whatever button closed the dialog, then closes."""
        for loss, checkbox in self._checkboxes:
            if checkbox.isChecked():
                AppConfig().set(loss.config_key, False)
        super().done(result)


def request_save_loss_choice(parent: Optional[QWidget], losses: list[SaveLoss], offer_ora: bool) -> str:
    """Asks how to proceed with a lossy save. Returns `SAVE_ORA`, `SAVE_ANYWAY` or `CANCEL`.

    Losses whose `config_key` setting is already false are skipped, and no dialog opens if none remain.
    """
    shown = [loss for loss in losses if AppConfig().get(loss.config_key)]
    if len(shown) == 0:
        return SAVE_ANYWAY
    modal = SaveLossModal(parent, shown, offer_ora and any(loss.config_key == AppConfig.WARN_BEFORE_LAYERLESS_SAVE
                                                           for loss in shown))
    modal.exec()
    choice = modal.choice
    modal.deleteLater()
    return choice
