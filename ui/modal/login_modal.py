from PyQt5.QtWidgets import QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
from PyQt5.QtCore import QSize
from data_model.stable_diffusion_api import *
import requests, json

class LoginModal(QDialog):
    def __init__(self, server_url):
        super().__init__()

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

        self._buttonRow = QHBoxLayout()
        self._cancelButton = QPushButton(self)
        self._cancelButton.setText("Cancel")
        self._buttonRow.addWidget(self._cancelButton)
        self._loginButton = QPushButton(self)
        self._loginButton.setText("Log In")
        self._buttonRow.addWidget(self._loginButton)
        self._layout.addLayout(self._buttonRow)
        def onLogin():
            body = {
                'username': self._nameInput.text(),
                'password': self._passInput.text()
            }
            url = f"{server_url}{API_ENDPOINTS['LOGIN']}"
            self._res = requests.post(url, json=body)
            self.hide()
        self._loginButton.clicked.connect(onLogin)

        def onCancel():
            self._res = False
            self.hide()

        self._cancelButton.clicked.connect(onCancel)
        self.setLayout(self._layout)

    def showLoginModal(self):
        self.exec_()
        if self._res:
            print(f"{self._res.status_code} : {self._res.text}")
