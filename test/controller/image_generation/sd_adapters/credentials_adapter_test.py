"""Tests prompting for WebUI credentials on the main thread, from the main thread or a worker thread."""
import threading
from typing import Optional
from unittest import mock

from sd_backend_client import A1111Webservice

from src.controller.image_generation.sd_adapters import credentials_adapter
from src.controller.image_generation.sd_adapters.credentials_adapter import create_webservice, \
    login_without_prompt, request_credentials
from test.base_test_case import IntraPaintTestCase
from test.controller.image_generation.fake_sd_backend import FakeResponse, FakeSdBackend

SERVER_URL = 'http://sd.invalid:7860'
JOIN_TIMEOUT_SECONDS = 10


class CredentialsAdapterTest(IntraPaintTestCase):
    """Tests prompting for WebUI credentials on the main thread, from the main thread or a worker thread."""

    def setUp(self) -> None:
        super().setUp()
        self.webservice = A1111Webservice(SERVER_URL)
        self.addCleanup(self.webservice.disconnect)

    def test_prompt_on_main_thread(self) -> None:
        """A request from the main thread shows the login modal directly and returns its credentials."""
        with mock.patch.object(credentials_adapter, 'LoginModal') as modal_class:
            modal_class.return_value.show_login_modal.return_value = ('user', 'secret')
            self.assertEqual(request_credentials(self.webservice), ('user', 'secret'))
        modal_class.assert_called_once()

    def test_cancelled_prompt(self) -> None:
        """Cancelling the login modal returns no credentials."""
        with mock.patch.object(credentials_adapter, 'LoginModal') as modal_class:
            modal_class.return_value.show_login_modal.return_value = (None, None)
            self.assertIsNone(request_credentials(self.webservice))

    def test_prompt_from_worker_thread(self) -> None:
        """A request from a worker thread blocks it while the main thread runs the prompt."""
        scheduled: list = []
        scheduled_event = threading.Event()

        def _single_shot(_msec, _context, callback) -> None:
            scheduled.append(callback)
            scheduled_event.set()

        answers: list[Optional[tuple[str, str]]] = []
        prompt_threads: list[threading.Thread] = []

        def _show_modal(_webservice) -> tuple[str, str]:
            prompt_threads.append(threading.current_thread())
            return 'user', 'secret'

        with mock.patch.object(credentials_adapter.QTimer, 'singleShot', _single_shot), \
                mock.patch.object(credentials_adapter, '_show_login_modal', _show_modal):
            worker = threading.Thread(target=lambda: answers.append(request_credentials(self.webservice)))
            worker.start()
            self.assertTrue(scheduled_event.wait(JOIN_TIMEOUT_SECONDS), 'the worker did not schedule the prompt')
            self.assertEqual(answers, [], 'the worker returned before the prompt ran')
            scheduled[0]()
            worker.join(JOIN_TIMEOUT_SECONDS)
        self.assertFalse(worker.is_alive())
        self.assertEqual(answers, [('user', 'secret')])
        self.assertEqual(prompt_threads, [threading.current_thread()], 'the prompt ran on the main thread')

    def test_created_webservice_prompts_on_auth_error(self) -> None:
        """The webservice takes its credentials from the login modal when the server answers 401."""
        webservice = create_webservice(SERVER_URL)
        self.addCleanup(webservice.disconnect)
        with FakeSdBackend() as backend:
            # The library checks new credentials with an authenticated request to the progress endpoint:
            backend.route('GET', A1111Webservice.Endpoints.PROGRESS, {})
            with mock.patch.object(credentials_adapter, '_show_login_modal',
                                   return_value=('user', 'secret')) as show_modal:
                webservice._handle_auth_error()  # pylint: disable=protected-access
        show_modal.assert_called_once_with(webservice)
        self.assertEqual(webservice._session.auth, ('user', 'secret'))  # pylint: disable=protected-access

    def test_login_without_prompt_returns_rejection(self) -> None:
        """A rejected login returns the 401 response without asking for credentials again."""
        with FakeSdBackend() as backend:
            backend.route('POST', A1111Webservice.Endpoints.LOGIN,
                          FakeResponse({'detail': 'Incorrect username or password'}, status_code=401))
            with mock.patch.object(credentials_adapter, '_show_login_modal') as show_modal:
                response = login_without_prompt(self.webservice, 'user', 'wrong')
        self.assertEqual(response.status_code, 401)
        show_modal.assert_not_called()
