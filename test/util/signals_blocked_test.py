"""Tests the signals_blocked context manager."""
from PySide6.QtCore import QObject

from src.util.signals_blocked import signals_blocked
from test.base_test_case import IntraPaintTestCase


class SignalsBlockedTest(IntraPaintTestCase):
    """Tests that signals_blocked restores the blocked state it found."""

    def test_unblocks_on_exit(self) -> None:
        """A single block leaves the source unblocked on exit."""
        source = QObject()
        with signals_blocked(source):
            self.assertTrue(source.signalsBlocked())
        self.assertFalse(source.signalsBlocked())

    def test_nested_block_keeps_outer_block(self) -> None:
        """An inner block of the same source leaves it blocked until the outer block exits."""
        source = QObject()
        with signals_blocked(source):
            with signals_blocked(source):
                pass
            self.assertTrue(source.signalsBlocked())
        self.assertFalse(source.signalsBlocked())
