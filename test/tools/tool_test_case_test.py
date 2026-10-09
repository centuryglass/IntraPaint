"""Tests the tool test harness in test/tools/tool_test_case.py."""
import unittest
from typing import Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtWidgets import QFrame

from src.config.key_config import KeyConfig
from src.tools.base_tool import BaseTool
from test.tools.tool_test_case import ToolTestCase


class _RecordingTool(BaseTool):
    """Records the mouse events it receives, along with their image coordinates."""

    def __init__(self) -> None:
        super().__init__(KeyConfig.BRUSH_TOOL_KEY, 'Recording tool', '', QIcon())
        self.calls: list[tuple[str, tuple[int, int], Qt.MouseButton]] = []

    def _record(self, name: str, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        assert event is not None
        self.calls.append((name, image_coordinates.toTuple(), event.buttons()))
        return True

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        return self._record('click', event, image_coordinates)

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        return self._record('move', event, image_coordinates)

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        return self._record('release', event, image_coordinates)


class ToolTestCaseTest(ToolTestCase):
    """Tests that the harness delivers synthetic input to the active tool at the requested image pixels."""

    def setUp(self) -> None:
        super().setUp()
        self.tool = self.activate_tool(_RecordingTool())

    def test_view_scale(self) -> None:
        """The whole image is shown at 1:1 scale."""
        self.assertEqual(self.image_viewer.scene_scale, 1.0)
        self.assertTrue(self.image_viewer.visible_scene_bounds.contains(self.image_stack.bounds.toRectF()))

    def test_image_point_to_widget(self) -> None:
        """Every corner and an interior pixel map back to themselves through the viewer."""
        last = QPoint(self.IMAGE_SIZE.width() - 1, self.IMAGE_SIZE.height() - 1)
        for point in (QPoint(0, 0), QPoint(last.x(), 0), QPoint(0, last.y()), last, QPoint(123, 45)):
            widget_point = self.image_point_to_widget(point)
            scene_point = self.image_viewer.widget_point_to_scene(widget_point)
            self.assertEqual((int(scene_point.x()), int(scene_point.y())), point.toTuple())

    def test_mouse_drag(self) -> None:
        """A drag reaches the tool as a click, moves and a release, each at its image pixel."""
        left = Qt.MouseButton.LeftButton
        self.mouse_drag([QPoint(10, 20), QPoint(11, 22), QPoint(300, 400)])
        self.assertEqual(self.tool.calls, [('click', (10, 20), left), ('move', (11, 22), left),
                                               ('move', (300, 400), left),
                                               ('release', (300, 400), Qt.MouseButton.NoButton)])

    def test_right_button(self) -> None:
        """Mouse helpers pass through the button used."""
        right = Qt.MouseButton.RightButton
        self.mouse_press(QPoint(5, 5), right)
        self.mouse_move(QPoint(6, 6), right)
        self.assertEqual(self.tool.calls, [('click', (5, 5), right), ('move', (6, 6), right)])

    def test_release_delivered_once(self) -> None:
        """Each mouse release reaches the tool once."""
        self.mouse_drag([QPoint(10, 10)])
        self.assertEqual([name for name, _, _ in self.tool.calls], ['click', 'release'])

    def test_framed_viewer(self) -> None:
        """With a frame around the viewport, a press, move and release at one point all reach the same pixel once."""
        self.image_viewer.setFrameShape(QFrame.Shape.Box)
        self.image_viewer.setLineWidth(3)
        self.image_viewer.scene_scale = 1.0
        point = QPoint(100, 100)
        self.mouse_press(point)
        self.mouse_move(point)
        self.mouse_release(point)
        self.assertEqual([(name, pos) for name, pos, _ in self.tool.calls],
                         [('click', (100, 100)), ('move', (100, 100)), ('release', (100, 100))])


if __name__ == '__main__':
    unittest.main()
