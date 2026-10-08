"""Displays a tool icon and label, indicates if the tool is selected, and can be clicked to select its tool.

The active tool's icon sits on a raised accent plate, the small version of InkStyle's sticker look.
"""
from typing import Optional

from PySide6.QtCore import Signal, QObject, Qt, QRect, QRectF, QSize, QPoint
from PySide6.QtGui import QColor, QResizeEvent, QPaintEvent, QPainter, QPalette, QPen
from PySide6.QtWidgets import QToolButton, QSizePolicy

from src.tools.base_tool import BaseTool
from src.ui.widget.key_hint_label import KeyHintLabel
from src.util.visual.geometry_utils import get_scaled_placement

TOOL_ICON_SIZE = 48
# Space between the icon and the edge of the plate drawn behind it:
PLATE_MARGIN = 4
PLATE_RADIUS = 7.0
# The active plate's ink shadow drops this far below it. It has to fit inside the button's margin around the icon:
PLATE_SHADOW_OFFSET = 2


class ToolButton(QToolButton):
    """Displays a tool icon and label, indicates if the tool is selected, and can be clicked to select its tool."""

    tool_selected = Signal(QObject)

    def __init__(self, connected_tool: BaseTool) -> None:
        super().__init__()
        self.setAutoRaise(True)
        self._tool = connected_tool
        self._icon = connected_tool.get_icon()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed))
        self.setContentsMargins(2, 2, 2, 2)
        label_text = connected_tool.label
        self._key_hint = KeyHintLabel(None, connected_tool.get_activation_config_key(), parent=self)
        self._key_hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._key_hint.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self._key_hint.setMinimumSize(self._key_hint.sizeHint())
        self.setToolTip(label_text)
        self._icon_bounds = QRect()
        self._active = False
        self.clicked.connect(self._activate_tool)

    @property
    def connected_tool(self) -> BaseTool:
        """Accesses the tool connected to this button."""
        return self._tool

    def sizeHint(self) -> QSize:
        """Returns ideal size as TOOL_ICON_SIZExTOOL_ICON_SIZE."""
        return QSize(TOOL_ICON_SIZE, TOOL_ICON_SIZE)

    def minimumSizeHint(self) -> QSize:
        """Returns ideal size as TOOL_ICON_SIZExTOOL_ICON_SIZE."""
        return self.sizeHint()

    def resizeEvent(self, unused_event: Optional[QResizeEvent]):
        """Recalculate and cache icon bounds on size change."""
        self._icon_bounds = get_scaled_placement(self.size(), QSize(1, 1), 8)
        hint_size = self._key_hint.sizeHint()
        width = hint_size.width()
        height = hint_size.height()
        x = self.width() - width
        y = self.height() - height
        self._key_hint.setGeometry(QRect(QPoint(x, y), hint_size))

    @property
    def is_active(self) -> bool:
        """Checks whether the associated tool is shown as active."""
        return self._active

    @is_active.setter
    def is_active(self, active: bool) -> None:
        """Sets whether the associated tool is shown as active."""
        self._active = active
        self.update()

    def _activate_tool(self) -> None:
        """Trigger tool change if clicked when not selected."""
        if not self.is_active:
            self.tool_selected.emit(self._tool)

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws the icon on an accent plate if its tool is active, or a lighter plate while hovered or pressed."""
        painter = QPainter(self)
        palette = self.palette()
        ink = palette.color(QPalette.ColorRole.Shadow)
        plate = QRectF(self._icon_bounds.adjusted(-PLATE_MARGIN, -PLATE_MARGIN, PLATE_MARGIN, PLATE_MARGIN))
        if self.is_active:
            self._draw_plate(painter, plate.translated(0, PLATE_SHADOW_OFFSET), ink, ink)
            self._draw_plate(painter, plate, palette.color(QPalette.ColorRole.Highlight), ink)
        elif self.isDown():
            self._draw_plate(painter, plate, palette.color(QPalette.ColorRole.Button), ink)
        elif self.underMouse():
            self._draw_plate(painter, plate, palette.color(QPalette.ColorRole.Midlight), ink)
        self._icon.paint(painter, self._icon_bounds)

    @staticmethod
    def _draw_plate(painter: QPainter, plate: QRectF, fill: QColor, outline: QColor) -> None:
        """Draws a rounded plate with a 1px outline inside `plate`."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(outline, 1))
        painter.setBrush(fill)
        painter.drawRoundedRect(plate.adjusted(0.5, 0.5, -0.5, -0.5), PLATE_RADIUS, PLATE_RADIUS)
        painter.restore()
