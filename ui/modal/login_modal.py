"""Popup modal window used for entering login information."""
import json
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton


class LoginModal(QDialog):
    """Popup modal window used for entering login information."""

    def __init__(self, try_login):
        super().__init__()
        self.user=None
        self.pw=None
        self._res=None

        self.setModal(True)

        self._layout = QVBoxLayout()
        self._title = QLabel(self)
        self._title.setText('Enter username and password')
        self._layout.addWidget(self._title)

        self._name_row = QHBoxLayout()
        self._name_row.addWidget(QLabel('Username', self))
        self._name_input = QLineEdit()
        self._name_row.addWidget(self._name_input)
        self._layout.addLayout(self._name_row)

        self._password_row = QHBoxLayout()
        self._password_row.addWidget(QLabel('Password', self))
        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_row.addWidget(self._password_input)
        self._layout.addLayout(self._password_row)

        self._status = QLabel(self)
        self._layout.addWidget(self._status)

        self._button_row = QHBoxLayout()
        self._login_button = QPushButton(self)
        self._login_button.setText('Log In')
        self._button_row.addWidget(self._login_button)
        self._cancel_button = QPushButton(self)
        self._cancel_button.setText('Cancel')
        self._button_row.addWidget(self._cancel_button)
        self._layout.addLayout(self._button_row)
        def on_login():
            if self._name_input.text() == '' or self._password_input.text() == '':
                self._status.setText('Username and password cannot be empty')
                return
            self._res = try_login(self._name_input.text(), self._password_input.text())
            if self._res.status_code == 200:
                self.user = self._name_input.text()
                self.pw = self._password_input.text()
                self.hide()
            else:
                self._password_input.setText('')
                try:
                    self._status.setText(self._res.json()['detail'])
                except json.JSONDecodeError:
                    self._status.setText('Unknown error, try again')

        self._login_button.clicked.connect(on_login)

        def on_cancel():
            self._res=None
            self.hide()

        self._cancel_button.clicked.connect(on_cancel)
        self.setLayout(self._layout)

    def clear_password(self):
        """Clears the password field."""
        self._password_input.setText('')

    def set_status(self, status):
        """Sets status text shown to the user."""
        self._status.setText(status)

    def show_login_modal(self):
        """Shows the login modal and returns user input on close."""
        self.exec_()
        if self._res is not None and self._res.status_code == 200:
            return (self.user, self.pw)
        return (None, None)

    def get_login_response(self):
        """Gets any saved network response from the login attempt."""
        return self._res
