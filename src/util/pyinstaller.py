"""Utility functions related to pyinstaller bundles."""
import sys


def is_pyinstaller_bundle() -> bool:
    """Returns whether the application is running from a pyinstaller bundle."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
