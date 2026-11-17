"""The outline of a floating `PanelDock`, drawn over the dock's content.

Qt paints a floating dock's frame on the dock itself and reserves room for it only when it decides the window manager
draws no frame. With a custom title bar that decision can go either way, and the content then covers the frame. This
overlay draws the same `QStyle.PE_FrameDockWidget` primitive (`InkStyle` outlines it in `InkColors.panel_edge`) above
the content.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPaintEvent, QPainter
from PySide6.QtWidgets import QStyle, QStyleOptionFrame, QWidget


class FloatingEdge(QWidget):
    """Draws a dock frame over its parent's whole area, and ignores the mouse."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    def fit_parent(self) -> None:
        """Covers the parent and rises above its content. Call when the parent resizes or its content changes."""
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
        self.raise_()

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the frame primitive."""
        option = QStyleOptionFrame()
        option.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_FrameDockWidget, option, painter, self)
        painter.end()
