"""Tests how ToolButton draws its tool's icon tile in each state."""
import sys
from unittest.mock import MagicMock

from PySide6.QtCore import QPoint, QSize
from PySide6.QtGui import QColor, QIcon, QImage, QPalette, QPixmap
from PySide6.QtWidgets import QApplication

from src.tools.base_tool import BaseTool
from src.ui.widget.tool_button import ToolButton, TOOL_ICON_SIZE, PLATE_MARGIN, PLATE_SHADOW_OFFSET
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class ToolButtonTest(IntraPaintTestCase):
    """Renders a ToolButton for a tool with a blank icon and no activation key."""

    def setUp(self) -> None:
        super().setUp()
        tool = MagicMock(spec=BaseTool)
        icon_pixmap = QPixmap(QSize(16, 16))
        icon_pixmap.fill(QColor(0, 0, 0, 0))
        tool.get_icon.return_value = QIcon(icon_pixmap)
        tool.label = 'Test tool'
        tool.get_activation_config_key.return_value = None
        self.button = ToolButton(tool)
        self.button.resize(self.button.sizeHint())
        self.button.resizeEvent(None)

    def _plate_points(self) -> tuple[QPoint, QPoint]:
        """Returns a point just inside the plate's left edge, and a point in the shadow below the plate."""
        icon_bounds = self.button._icon_bounds  # pylint: disable=protected-access
        center_x = icon_bounds.center().x()
        inside = QPoint(icon_bounds.left() - PLATE_MARGIN + 2, icon_bounds.center().y())
        shadow = QPoint(center_x, icon_bounds.bottom() + PLATE_MARGIN + PLATE_SHADOW_OFFSET)
        return inside, shadow

    def _render(self) -> QImage:
        return self.button.grab().toImage()

    def test_size(self) -> None:
        """The button is a fixed square, with room for the active plate's shadow inside it."""
        self.assertEqual(self.button.size(), QSize(TOOL_ICON_SIZE, TOOL_ICON_SIZE))
        _, shadow = self._plate_points()
        self.assertLess(shadow.y(), TOOL_ICON_SIZE)

    def test_active_tool_draws_accent_plate(self) -> None:
        """The active tool's icon sits on an accent plate with an ink shadow below it."""
        self.button.is_active = True
        palette = self.button.palette()
        image = self._render()
        inside, shadow = self._plate_points()
        self.assertEqual(image.pixelColor(inside), palette.color(QPalette.ColorRole.Highlight))
        self.assertEqual(image.pixelColor(shadow), palette.color(QPalette.ColorRole.Shadow))

    def test_inactive_tool_draws_no_plate(self) -> None:
        """An inactive, unhovered tool draws no plate."""
        self.button.is_active = False
        image = self._render()
        inside, shadow = self._plate_points()
        highlight = self.button.palette().color(QPalette.ColorRole.Highlight)
        ink = self.button.palette().color(QPalette.ColorRole.Shadow)
        self.assertNotEqual(image.pixelColor(inside), highlight)
        self.assertNotEqual(image.pixelColor(shadow), ink)
