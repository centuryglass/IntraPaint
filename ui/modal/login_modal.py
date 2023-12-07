from PyQt5.QtWidgets import QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
from PyQt5.QtCore import QSize
from sd_api.login import LoginPost
import base64

class LoginModal(QDialog):
    def __init__(self, tryLogin):
        super().__init__()
        self.user=None
        self.pw=None

        self.setModal(True)

        self._layout = QVBoxLayout()
        self._title = QLabel(self)
        self._title.setText("Enter username and password")
        self._layout.addWidget(self._title)

        self._nameRow = QHBoxLayout()
        self._nameRow.addWidget(QLabel("Username", self))
        self._nameInput = QLineEdit()
        self._nameRow.addWidget(self._nameInput)
        self._layout.addLayout(self._nameRow)

        self._passRow = QHBoxLayout()
        self._passRow.addWidget(QLabel("Password", self))
        self._passInput = QLineEdit()
        self._passInput.setEchoMode(QLineEdit.EchoMode.Password)
        self._passRow.addWidget(self._passInput)
        self._layout.addLayout(self._passRow)

        self._status = QLabel(self)
        self._layout.addWidget(self._status)

        self._buttonRow = QHBoxLayout()
        self._cancelButton = QPushButton(self)
        self._cancelButton.setText("Cancel")
        self._buttonRow.addWidget(self._cancelButton)
        self._loginButton = QPushButton(self)
        self._loginButton.setText("Log In")
        self._buttonRow.addWidget(self._loginButton)
        self._layout.addLayout(self._buttonRow)
        def onLogin():
            if self._nameInput.text() == '' or self._passInput.text() == '':
                self._status.setText('Username and password cannot be empty')
                return

            params = {
                'username': self._nameInput.text(),
                'password': self._passInput.text()
            }
            self._res = tryLogin(self._nameInput.text(), self._passInput.text())
            if self._res.status_code == 200:
                self.user = self._nameInput.text()
                self.pw = self._passInput.text()
                self.hide()
            else:
                self._passInput.setText('')
                try:
                    self._status.setText(self._res.json()['detail'])
                except:
                    self._status.setText('Unknown error, try again')
                
        self._loginButton.clicked.connect(onLogin)

        def onCancel():
            self._res = False
            self.hide()

        self._cancelButton.clicked.connect(onCancel)
        self.setLayout(self._layout)

    def clearPassword(self):
        self._passInput.setText('')

    def setStatus(self, status):
        self._status.setText(status)

    def showLoginModal(self):
        self.exec_()
        if self._res.status_code == 200:
            return (self.user, self.pw)
