"""Tests for GenerationAreaToolPanel's sync with the generation area."""
import sys
from typing import cast

from PySide6.QtCore import QSize, QRect
from PySide6.QtWidgets import QApplication, QSlider, QSpinBox

from src.controller.generation_area_controller import apply_generation_area_frame
from src.image.layers.image_stack import ImageStack
from src.ui.panel.tool_control_panels.generation_area_tool_panel import GenerationAreaToolPanel
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

IMAGE_SIZE = QSize(1024, 640)
MAX_AREA_SIZE = QSize(10240, 10240)


class GenerationAreaToolPanelTest(IntraPaintTestCase):
    """Tests that the panel's coordinate controls follow generation area changes."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(IMAGE_SIZE, QSize(384, 384), QSize(8, 8), MAX_AREA_SIZE)
        self.panel = GenerationAreaToolPanel(self.image_stack)

    def _assert_controls_match_area(self) -> None:
        area = self.image_stack.generation_area
        for ctrl, value in ((self.panel._x_spinbox, area.x()), (self.panel._y_spinbox, area.y()),
                            (self.panel._w_spinbox, area.width()), (self.panel._h_spinbox, area.height()),
                            (self.panel._x_slider, area.x()), (self.panel._y_slider, area.y()),
                            (self.panel._w_slider, area.width()), (self.panel._h_slider, area.height())):
            self.assertEqual(cast(QSpinBox | QSlider, ctrl).value(), value)

    def test_centered_shrink_past_old_range(self) -> None:
        """Shrinking around the center moves x and y past the old control ranges, and the controls still follow."""
        self.image_stack.generation_area = QRect(320, 192, 384, 384)
        apply_generation_area_frame(self.image_stack, QSize(128, 128))
        self.assertEqual(self.image_stack.generation_area, QRect(448, 320, 128, 128))
        self._assert_controls_match_area()

    def test_growth_below_old_value(self) -> None:
        """Growing the area lowers the coordinate ranges below the old values, and the controls still follow."""
        self.image_stack.generation_area = QRect(800, 500, 128, 128)
        apply_generation_area_frame(self.image_stack, QSize(512, 512))
        self.assertEqual(self.image_stack.generation_area, QRect(512, 128, 512, 512))
        self._assert_controls_match_area()

    def test_oversized_typed_frame(self) -> None:
        """A typed size too large for a C int selects the largest area that fits."""
        self.panel._custom_frame_input.setText('99999999999999999')
        self.panel._custom_frame_input.returnPressed.emit()
        self.assertEqual(self.image_stack.generation_area, QRect(0, 0, 1024, 640))
        self._assert_controls_match_area()
