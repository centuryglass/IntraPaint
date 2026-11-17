"""Tests SizeField: changing its orientation keeps its widgets shown."""
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QSpinBox

from src.ui.input_fields.size_field import SizeField
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class SizeFieldTest(IntraPaintTestCase):
    """Tests SizeField layout changes."""

    def test_orientation_change_keeps_boxes_visible(self) -> None:
        """Stacking the boxes and putting them back side by side leaves both spin boxes shown."""
        field = SizeField()
        field.show()
        boxes = field.findChildren(QSpinBox)
        self.assertEqual(len(boxes), 2)
        for orientation in (Qt.Orientation.Vertical, Qt.Orientation.Horizontal):
            field.orientation = orientation
            for box in boxes:
                self.assertTrue(box.isVisible())
                self.assertIs(box.parentWidget(), field)
