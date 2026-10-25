"""A one-line label that elides its text to fit, for names and paths that must not widen a panel."""
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class ElidedLabel(QLabel):
    """A one-line label that ends its text with an ellipsis when it is too narrow, and shows the full text as a
    tooltip then."""

    def __init__(self, text: str = '', parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._full_text = ''
        self.setMinimumWidth(1)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.set_full_text(text)

    @property
    def full_text(self) -> str:
        """Returns the text before eliding."""
        return self._full_text

    def set_full_text(self, text: str) -> None:
        """Changes the text, eliding it to the current width."""
        self._full_text = text
        self.updateGeometry()
        self._elide()

    def full_text_width(self) -> int:
        """Returns the width the full text needs, with a pixel to spare on each side for rounding."""
        return self.fontMetrics().horizontalAdvance(self._full_text) + 2

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the size of the full text."""
        return QSize(self.full_text_width(), super().sizeHint().height())

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns a width of one pixel, since the text elides to fit."""
        return QSize(1, super().minimumSizeHint().height())

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Elides the text to the new width."""
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        shown = self._full_text if self.width() >= self.full_text_width() \
            else self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideRight, self.width())
        self.setText(shown)
        self.setToolTip(self._full_text if shown != self._full_text else '')
