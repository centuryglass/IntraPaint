"""Tests `AppContext`, the `AppService` accessors, and replacing the installed context."""
import os
import shutil
import tempfile
from unittest.mock import patch

from src import app_context
from src.app_context import AppContext, AppService, current_context, install_context, installed_context
from src.config.application_config import AppConfig
from test.base_test_case import IntraPaintTestCase, TEST_RESOURCE_DIR

# Each `_RecordingService` close, by the instance's `name`, in the order they happened:
_closed: list[str] = []


class _RecordingService(metaclass=AppService):
    """A service that records when it closes."""

    def __init__(self, name: str = 'default') -> None:
        self.name = name

    def close(self) -> None:
        """Records the close."""
        _closed.append(self.name)


class _DependentService(metaclass=AppService):
    """A service whose construction requests `_RecordingService`."""

    def __init__(self) -> None:
        self.dependency = _RecordingService()

    def close(self) -> None:
        """Records the close."""
        _closed.append('dependent')


class AppContextTest(IntraPaintTestCase):
    """Tests `AppContext` and the `AppService` metaclass."""

    def setUp(self) -> None:
        super().setUp()
        _closed.clear()

    def test_accessor_returns_installed_context_instance(self) -> None:
        """Calling a service class returns one instance per context, constructed on first use."""
        context = AppContext()
        install_context(context)
        self.assertFalse(context.has_service(_RecordingService))
        service = _RecordingService()
        self.assertTrue(context.has_service(_RecordingService))
        self.assertIs(_RecordingService(), service)
        self.assertIs(context.service(_RecordingService), service)
        install_context(AppContext())
        self.assertIsNot(_RecordingService(), service)

    def test_accessor_rejects_arguments(self) -> None:
        """Arguments go through the context, so passing them to the accessor raises."""
        with self.assertRaises(TypeError):
            _RecordingService('other')

    def test_context_passes_constructor_arguments(self) -> None:
        """A context constructs a service with the arguments it was given for that class."""
        install_context(AppContext({_RecordingService: ('configured',)}))
        self.assertEqual(_RecordingService().name, 'configured')
        temp_dir = tempfile.mkdtemp(prefix='intrapaint-app-context-test-')
        self.addCleanup(shutil.rmtree, temp_dir, ignore_errors=True)
        json_path = os.path.join(temp_dir, 'app_config.json')
        shutil.copyfile(os.path.join(TEST_RESOURCE_DIR, 'app_config_test.json'), json_path)
        install_context(AppContext({AppConfig: (json_path,)}))
        self.assertEqual(AppConfig().json_path, json_path)

    def test_create_makes_an_instance_no_context_owns(self) -> None:
        """`create` constructs a separate instance, which the installed context never returns."""
        separate = _RecordingService.create('separate')
        self.assertEqual(separate.name, 'separate')
        self.assertIsNot(_RecordingService(), separate)
        self.assertIsNot(current_context().service(_RecordingService), separate)

    def test_install_closes_replaced_context_newest_first(self) -> None:
        """Installing a context closes each service of the one it replaces, newest first, and only once."""
        context = AppContext()
        install_context(context)
        _DependentService()
        self.assertEqual(_closed, [])
        install_context(AppContext())
        self.assertEqual(_closed, ['dependent', 'default'])
        install_context(context)  # A closed context isn't closed again when it's replaced.
        install_context(AppContext())
        self.assertEqual(_closed, ['dependent', 'default'])

    def test_closed_context_refuses_new_services(self) -> None:
        """A closed context still returns the services it built, but constructs no new ones."""
        context = AppContext()
        service = context.service(_RecordingService)
        context.close()
        self.assertIs(context.service(_RecordingService), service)
        with self.assertRaises(RuntimeError):
            context.service(_DependentService)

    def test_reinstalling_the_same_context_keeps_it_open(self) -> None:
        """Installing the context that is already installed doesn't close it."""
        context = AppContext()
        install_context(context)
        service = _RecordingService()
        install_context(context)
        self.assertEqual(_closed, [])
        self.assertIs(_RecordingService(), service)

    def test_default_context_created_when_none_installed(self) -> None:
        """With no context installed, the first service request installs one with default arguments."""
        with patch.object(app_context, '_installed', None):
            self.assertIsNone(installed_context())
            self.assertEqual(_RecordingService().name, 'default')
            created = installed_context()
            self.assertIsNotNone(created)
            assert created is not None
            created.close()
