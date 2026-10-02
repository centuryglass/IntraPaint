"""Shared harness for tool tests: an ImageStack, an ImagePanel's ImageViewer and a ToolController, without the
   AppController and main window."""
import math
from typing import Sequence, TypeVar

from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QFrame

from src.controller.tool_controller import ToolController
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.ui.image_viewer import MIN_OUTLINE_PIXEL_SIZE
from src.ui.panel.image_panel import ImagePanel
from test.base_test_case import IntraPaintTestCase

ToolT = TypeVar('ToolT', bound=BaseTool)

# Room around the image inside the panel, so the whole image is visible at 1:1 scale:
VIEW_MARGIN = 64


class ToolTestCase(IntraPaintTestCase):
    """Base class for tool tests.

    setUp builds an image stack, an image panel showing it at 1:1 scale, and a tool controller with no tools loaded.
    Tests add the tool under test with `activate_tool`, then drive it with the mouse helpers, which send synthetic
    mouse events to the image viewer. Those events reach the tool through the same viewer and controller code that
    handles real input, including the mapping from widget to image coordinates. Tests never wait on the event loop.
    """

    IMAGE_SIZE = QSize(512, 512)

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(self.IMAGE_SIZE, self.IMAGE_SIZE, self.IMAGE_SIZE, self.IMAGE_SIZE)
        self.image_panel = ImagePanel(self.image_stack, include_zoom_controls=False, use_keybindings=False)
        self.image_viewer = self.image_panel.image_viewer
        # A frameless viewer keeps mouse presses and moves on the same pixel. With a frame, ToolController maps them
        # one frame width apart (#76).
        self.image_viewer.setFrameShape(QFrame.Shape.NoFrame)
        self.image_panel.resize(self.IMAGE_SIZE.width() + VIEW_MARGIN * 2, self.IMAGE_SIZE.height() + VIEW_MARGIN * 2)
        self.image_panel.show()
        self.image_viewer.scene_scale = 1.0
        self.tool_controller = ToolController(self.image_stack, self.image_viewer, load_all_tools=False,
                                              use_hotkeys=False)

    def tearDown(self) -> None:
        self.image_panel.close()
        super().tearDown()

    def activate_tool(self, tool: ToolT) -> ToolT:
        """Adds a tool to the tool controller if it isn't there already, makes it the active tool, and returns it."""
        self.tool_controller.active_tool = tool
        assert tool.is_active
        return tool

    def image_point_to_widget(self, image_point: QPoint) -> QPoint:
        """Returns a point in image viewer widget coordinates that ToolController maps to the given image pixel."""
        viewer = self.image_viewer
        pixel_center = viewer.mapFromScene(QPointF(image_point.x() + 0.5, image_point.y() + 0.5))
        widget_center = viewer.viewport().mapToParent(pixel_center)

        def _maps_to_pixel(widget_point: QPoint) -> bool:
            # Matches ToolController.eventFilter's find_image_coordinates:
            scene_point = viewer.widget_point_to_scene(widget_point)
            if viewer.scene_scale >= MIN_OUTLINE_PIXEL_SIZE:
                return QPoint(math.floor(scene_point.x()), math.floor(scene_point.y())) == image_point
            return scene_point.toPoint() == image_point
        for dy in (0, -1, 1):
            for dx in (0, -1, 1):
                widget_point = QPoint(widget_center.x() + dx, widget_center.y() + dy)
                if _maps_to_pixel(widget_point):
                    return widget_point
        raise ValueError(f'No widget point maps to image point {image_point.toTuple()} at scale '
                         f'{viewer.scene_scale}')

    def send_mouse_event(self, event_type: QEvent.Type, image_point: QPoint, button: Qt.MouseButton,
                         buttons: Qt.MouseButton,
                         modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
        """Sends a synthetic mouse event at an image pixel to the image viewer's viewport, where real mouse input
           arrives."""
        viewport = self.image_viewer.viewport()
        assert viewport is not None
        viewport_point = viewport.mapFromParent(self.image_point_to_widget(image_point))
        event = QMouseEvent(event_type, QPointF(viewport_point), QPointF(viewport.mapToGlobal(viewport_point)),
                            button, buttons, modifiers)
        QApplication.sendEvent(viewport, event)

    def mouse_press(self, image_point: QPoint, button: Qt.MouseButton = Qt.MouseButton.LeftButton,
                    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
        """Presses a mouse button over an image pixel."""
        self.send_mouse_event(QEvent.Type.MouseButtonPress, image_point, button, button, modifiers)

    def mouse_move(self, image_point: QPoint, buttons: Qt.MouseButton = Qt.MouseButton.LeftButton,
                   modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
        """Moves the mouse to an image pixel with the given buttons held. Pass Qt.MouseButton.NoButton to hover."""
        self.send_mouse_event(QEvent.Type.MouseMove, image_point, Qt.MouseButton.NoButton, buttons, modifiers)

    def mouse_release(self, image_point: QPoint, button: Qt.MouseButton = Qt.MouseButton.LeftButton,
                      modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
        """Releases a mouse button over an image pixel. No buttons are held afterward."""
        self.send_mouse_event(QEvent.Type.MouseButtonRelease, image_point, button, Qt.MouseButton.NoButton,
                              modifiers)

    def mouse_drag(self, image_points: Sequence[QPoint], button: Qt.MouseButton = Qt.MouseButton.LeftButton,
                   modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
        """Presses at the first point, moves through the rest in order, and releases at the last: one brush stroke,
           drag, or click if only one point is given."""
        if len(image_points) == 0:
            raise ValueError('mouse_drag needs at least one point')
        self.mouse_press(image_points[0], button, modifiers)
        for point in image_points[1:]:
            self.mouse_move(point, button, modifiers)
        self.mouse_release(image_points[-1], button, modifiers)
