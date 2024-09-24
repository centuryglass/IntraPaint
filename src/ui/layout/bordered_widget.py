"""
A QFrame with minor adjustments to default properties and interface.
"""
from typing import Optional

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QFrame, QWidget

DEFAULT_LINE_WIDTH = 3


class BorderedWidget(QFrame):
    """A QFrame with minor adjustments to default properties and interface."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the widget, optionally adding it to a parent."""
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Raised)
        self.setLineWidth(DEFAULT_LINE_WIDTH)
        self.setAutoFillBackground(True)

    @property
    def frame_color(self) -> QColor:
        """Returns the drawn border color."""
        return self.palette().color(QPalette.ColorRole.Mid)

    @frame_color.setter
    def frame_color(self, new_color: QColor) -> None:
        """Updates the drawn border color."""
        if new_color != self.frame_color:
            palette = self.palette()
            palette.setColor(QPalette.ColorRole.Mid, new_color)
            self.setPalette(palette)
            self.update()

    @property
    def line_width(self) -> int:
        """Returns the line width of the drawn border."""
        return self.lineWidth()

    @line_width.setter
    def line_width(self, new_width: int) -> None:
        """Updates the line width of the drawn border."""
        self.setLineWidth(new_width)
