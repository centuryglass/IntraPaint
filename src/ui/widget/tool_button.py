"""Displays a tool icon and label, indicates if the tool is selected, and can be clicked to select its tool."""
from typing import Optional

from PySide6.QtCore import Signal, QObject, Qt, QRect, QSize, QPoint
from PySide6.QtGui import QResizeEvent, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import QToolButton, QSizePolicy

from src.tools.base_tool import BaseTool
from src.ui.widget.key_hint_label import KeyHintLabel
from src.util.visual.geometry_utils import get_scaled_placement

TOOL_ICON_SIZE = 48


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
        """Highlight when selected."""
        painter = QPainter(self)
        if self.is_active:
            pen = QPen(self.palette().color(self.foregroundRole()), 2)
        else:
            pen = QPen(self.palette().color(self.backgroundRole()).lighter(), 2)

        painter.setPen(pen)
        painter.drawRect(self._icon_bounds.adjusted(-4, -4, 4, 4))
        self._icon.paint(painter, self._icon_bounds)
