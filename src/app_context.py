"""Holds the application's global services in one replaceable `AppContext`.

A global service is a class whose metaclass is `AppService` (or `QObjectService` for a `QObject`). Calling the class
with no arguments, as in `AppConfig()`, returns the installed context's instance, which the context constructs on
first use. `IntraPaint.py` installs the application's context at startup, and `IntraPaintTestCase` installs a fresh
one for every test, so no service state carries from one test to the next.

Installing a context closes the one it replaces: each of its services that defines `close()` drops its connections
and stops its timers there. An object that keeps a service instance in an attribute keeps the closed instance, so a
module-level or class-level attribute must never hold one; `test/base_test_case_test.py` checks for them.
"""
import logging
from typing import Any, Mapping, Optional, TypeVar

from PySide6.QtCore import QObject

logger = logging.getLogger(__name__)

ServiceT = TypeVar('ServiceT')


class AppService(type):
    """Metaclass of a global service: calling the class with no arguments returns the installed context's instance.

    Arguments a service's constructor takes come from the `AppContext` that owns it. `create` constructs a separate
    instance that no context owns.
    """

    def __call__(cls, *args, **kwargs):
        if len(args) > 0 or len(kwargs) > 0:
            raise TypeError(f'{cls.__name__}() takes no arguments and returns the installed AppContext\'s instance. '
                            f'Pass constructor arguments through AppContext, or use {cls.__name__}.create(...) for '
                            'an instance no context owns.')
        return current_context().service(cls)

    def create(cls: type[ServiceT], *args: Any, **kwargs: Any) -> ServiceT:
        """Constructs a new instance that no context owns. The caller closes it, if its class defines `close()`."""
        # The next metaclass's __call__ constructs normally: type's, or PySide's for a QObjectService class.
        return super(AppService, cls).__call__(*args, **kwargs)  # type: ignore[misc]


class QObjectService(AppService, type(QObject)):  # type: ignore[misc]
    """`AppService` for a `QObject` subclass, whose metaclass must also derive from PySide's."""


class AppContext:
    """Owns one instance of each global service, constructing each one the first time it is requested.

    Parameters
    ----------
    arguments: Mapping[type, tuple], optional
        Constructor arguments for service classes, such as `{AppConfig: (json_path,)}`. A class with no entry is
        constructed with its defaults.
    """

    def __init__(self, arguments: Optional[Mapping[type, tuple[Any, ...]]] = None) -> None:
        self._arguments = dict(arguments or {})
        self._services: dict[type, Any] = {}
        self._closed = False

    def service(self, service_class: type[ServiceT]) -> ServiceT:
        """Returns this context's instance of a service class, constructing it if this context has none yet."""
        if service_class not in self._services:
            if self._closed:
                raise RuntimeError(f'Requested {service_class.__name__} from a closed AppContext')
            assert isinstance(service_class, AppService), f'{service_class.__name__} is not an AppService class'
            # Construction can request other services, which then precede this one in `_services` and close after it.
            instance = service_class.create(*self._arguments.get(service_class, ()))
            self._services.setdefault(service_class, instance)
        return self._services[service_class]

    def has_service(self, service_class: type) -> bool:
        """Returns whether this context has constructed its instance of a service class."""
        return service_class in self._services

    def close(self) -> None:
        """Closes every service this context constructed, newest first, and refuses to construct more.

        Closing a closed context does nothing.
        """
        if self._closed:
            return
        self._closed = True
        for service in reversed(list(self._services.values())):
            close = getattr(service, 'close', None)
            if close is not None:
                close()


_installed: Optional[AppContext] = None  # pylint: disable=invalid-name  # Reassigned by install_context.


def install_context(context: AppContext) -> None:
    """Makes `context` the one every service accessor reads from, closing the context it replaces."""
    global _installed  # pylint: disable=global-statement
    previous = _installed
    _installed = context
    if previous is not None and previous is not context:
        previous.close()


def installed_context() -> Optional[AppContext]:
    """Returns the installed context, or None if none has been installed or created yet."""
    return _installed


def current_context() -> AppContext:
    """Returns the installed context, installing one with every service's default arguments if there is none."""
    if _installed is None:
        logger.debug('No AppContext installed, creating one with default arguments')
        install_context(AppContext())
    assert _installed is not None
    return _installed
