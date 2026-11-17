"""Supplies the `credentials_provider` the library's `A1111Webservice` calls when the server answers 401.

The library calls the provider on whichever thread sent the request, which is a worker thread during generation.
`create_webservice` builds a client whose provider shows `LoginModal` on the main thread and blocks the calling thread
until it closes.
"""
import threading
from typing import Optional

import requests
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication
from sd_backend_client import A1111Webservice

from src.ui.modal.login_modal import LoginModal


def login_without_prompt(webservice: A1111Webservice, username: str, password: str) -> requests.Response:
    """Posts a username and password to the WebUI's login endpoint.

    A 401 response is returned, not handled. `A1111Webservice.login` would ask the credentials provider for new
    credentials on a 401, which opens a second login prompt while the first one is checking its input.
    """
    return webservice.post(A1111Webservice.Endpoints.LOGIN, {'username': username, 'password': password},
                           'x-www-form-urlencoded', fail_on_auth_error=True, throw_on_failure=False)


def _show_login_modal(webservice: A1111Webservice) -> Optional[tuple[str, str]]:
    """Shows `LoginModal` until the user logs in or cancels. Call this on the main thread."""
    login_modal = LoginModal(lambda username, password: login_without_prompt(webservice, username, password))
    username, password = login_modal.show_login_modal()
    if username is None or password is None:
        return None
    return username, password


def request_credentials(webservice: A1111Webservice) -> Optional[tuple[str, str]]:
    """Asks the user for server credentials, returning a (username, password) pair or None if they cancel.

    Runs the prompt on the main thread. When called from another thread, blocks that thread until the prompt closes,
    so the main thread must keep running its event loop.
    """
    app = QApplication.instance()
    assert app is not None
    if QThread.currentThread() == app.thread():
        return _show_login_modal(webservice)
    answer: list[Optional[tuple[str, str]]] = [None]
    done = threading.Event()

    def _prompt() -> None:
        try:
            answer[0] = _show_login_modal(webservice)
        finally:
            done.set()

    QTimer.singleShot(0, app, _prompt)
    done.wait()
    return answer[0]


def create_webservice(url: str) -> A1111Webservice:
    """Returns an `A1111Webservice` that asks the user for credentials through `request_credentials`."""
    webservice = A1111Webservice(url, credentials_provider=lambda: request_credentials(webservice))
    return webservice
