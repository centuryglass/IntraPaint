"""Popup modal window used for entering login information."""
import json
from typing import Callable, Optional

import requests
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QPushButton, QApplication,
                               QSizePolicy)

from src.util.shared_constants import APP_ICON_PATH

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.modal.login_modal'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


LOGIN_TITLE = _tr('Enter image generation server credentials:')
USERNAME_LABEL = _tr('Username:')
PASSWORD_LABEL = _tr('Password:')
LOGIN_BUTTON_TEXT = _tr('Log In')
CANCEL_BUTTON_TEXT = _tr('Cancel')

ERROR_MISSING_INFO = _tr('Username and password cannot be empty.')
ERROR_UNKNOWN = _tr('Unknown error, try again.')


class LoginModal(QDialog):
    """Popup modal window used for entering login information."""

    def __init__(self, try_login: Callable[[str, str], Optional[requests.Response]]) -> None:
        super().__init__()
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.user: Optional[str] = None
        self.pw: Optional[str] = None
        self._res: Optional[requests.Response] = None

        self.setModal(True)

        self._layout = QFormLayout(self)
        self._title = QLabel(self)
        self._title.setText(LOGIN_TITLE)
        self._layout.addRow(self._title)

        self._name_input = QLineEdit(parent=self)
        self._layout.addRow(USERNAME_LABEL, self._name_input)

        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._layout.addRow(PASSWORD_LABEL, self._password_input)

        self._status = QLabel(self)
        self._layout.addRow(self._status)

        self._button_row = QHBoxLayout()
        self._login_button = QPushButton(self)
        self._login_button.setText(LOGIN_BUTTON_TEXT)
        self._button_row.addWidget(self._login_button)
        self._cancel_button = QPushButton(self)
        self._cancel_button.setText(CANCEL_BUTTON_TEXT)
        self._button_row.addWidget(self._cancel_button)
        self._layout.addRow(self._button_row)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        def on_login() -> None:
            """Attempt to log in, show a message on error or set response on success."""
            if self._name_input.text() == '' or self._password_input.text() == '':
                self._status.setText(ERROR_MISSING_INFO)
                return
            self._res = try_login(self._name_input.text(), self._password_input.text())
            assert self._res is not None
            if self._res.status_code == 200:
                self.user = self._name_input.text()
                self.pw = self._password_input.text()
                self.hide()
            else:
                self._password_input.setText('')
                try:
                    self._status.setText(self._res.json()['detail'])
                except json.JSONDecodeError:
                    self._status.setText(ERROR_UNKNOWN)

        self._login_button.clicked.connect(on_login)

        def on_cancel() -> None:
            """Close and set response to none when the cancel button is clicked."""
            self._res = None
            self.hide()

        self._cancel_button.clicked.connect(on_cancel)
        self.setLayout(self._layout)

    def clear_password(self) -> None:
        """Clears the password field."""
        self._password_input.setText('')

    def set_status(self, status: str) -> None:
        """Sets status text shown to the user."""
        self._status.setText(status)

    def show_login_modal(self) -> tuple[str | None, str | None]:
        """Shows the login modal and returns user input on close."""
        self.setMaximumSize(self.sizeHint().width(), self.sizeHint().height())
        self.exec()
        if self._res is not None and self._res.status_code == 200:
            return self.user, self.pw
        return None, None

    def get_login_response(self) -> Optional[requests.Response]:
        """Gets any saved network response from the login attempt."""
        return self._res
