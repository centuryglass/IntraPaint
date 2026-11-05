"""Tests for ActiveTextFieldTracker: how long its connections last, and paste availability."""
import sys
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication, QLineEdit
from shiboken6 import delete, isValid

from src.util.active_text_field_tracker import ActiveTextFieldTracker
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class ActiveTextFieldTrackerTest(IntraPaintTestCase):
    """Tests for ActiveTextFieldTracker."""

    def test_tracker_is_deleted_with_its_parent(self) -> None:
        """Deleting the parent deletes the tracker, which ends its focus and clipboard connections."""
        parent = QObject()
        tracker = ActiveTextFieldTracker(parent)
        delete(parent)
        self.assertFalse(isValid(tracker))

    def test_paste_unavailable_without_clipboard_data(self) -> None:
        """A focused text field can't paste when the clipboard has no data for the platform to offer."""
        tracker = ActiveTextFieldTracker()
        line_edit = QLineEdit()
        tracker._update_active_widget(None, line_edit)  # pylint: disable=protected-access
        clipboard = MagicMock()
        clipboard.mimeData.return_value = None
        with patch.object(QApplication, 'clipboard', return_value=clipboard):
            self.assertFalse(tracker.focused_can_paste())
        tracker._update_active_widget(None, None)  # pylint: disable=protected-access
        delete(tracker)
