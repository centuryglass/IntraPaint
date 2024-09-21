"""A rotating toolbar button that uses Label for rendering contents."""
from typing import Optional

from PySide6.QtCore import QRect, QPoint, QSize
from PySide6.QtGui import QPixmap, QIcon, Qt, QResizeEvent
from PySide6.QtWidgets import QToolButton

from src.ui.widget.label import Label

LABEL_MARGINS = 4


class RotatingToolbarButton(QToolButton):
    """A rotating toolbar button that uses Label for rendering contents."""

    def __init__(self, text: Optional[str] = None, icon: Optional[QPixmap | QIcon | str] = None) -> None:
        super().__init__()
        if text is None:
            text = ''
        self._orientation = Qt.Orientation.Horizontal
        self._label = Label(text)
        if icon is not None:
            self._label.setIcon(icon)
        self._label.setParent(self)

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Updates the button orientation."""
        self._label.set_orientation(orientation)

    def text(self) -> str:
        """Returns the label's text"""
        return self._label.text()

    def setText(self, text: str) -> None:
        """Apply text changes to the label."""
        self._label.setText(text)

    def setIcon(self, icon: QPixmap | QIcon | str) -> None:
        """Apply icon changes to the label."""
        self._label.setIcon(icon)

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Update the label placement on resize."""
        label_bounds = QRect(QPoint(), self.size()).adjusted(LABEL_MARGINS, LABEL_MARGINS,
                                                             -LABEL_MARGINS, -LABEL_MARGINS)
        self._label.setGeometry(label_bounds)

    def sizeHint(self) -> QSize:
        """Use the label's size hint to determine button size"""
        label_hint = self._label.sizeHint()
        return QSize(label_hint.width() + 2 * LABEL_MARGINS, label_hint.height() + 2 * LABEL_MARGINS)

    def minimumSizeHint(self) -> QSize:
        """Use the label's size hint to determine minimum button size"""
        return self._label.minimumSizeHint()
