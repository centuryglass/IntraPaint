"""Convenience function for importing optional dependencies."""
import importlib
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def optional_import(module_name: str, package_name: Optional[str] = None, attr_name: Optional[str] = None) -> Any:
    """Attempts to load an optional module, returning None if the module is not found.

    Parameters
    ----------
    module_name: str
        The name of the module.
    package_name: str
        Optional package name to use for the import
    attr_name: str, optional
        An optional attribute within the module to import. If None, the module itself is returned.
    Return
    ------
    The requested module or module attribute, or None if it could not be imported."""
    try:
        module = importlib.import_module(module_name, package_name)
        if attr_name is None:
            return module
        return getattr(module, attr_name)
    except ImportError as err:
        logger.warning(f'Failed to load optional import from {module_name}: {err}')
        return None
