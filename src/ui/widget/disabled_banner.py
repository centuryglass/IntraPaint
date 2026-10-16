"""A banner saying why a panel is inert, with a button that offers the fix.

It replaces greying out a whole panel with no explanation. The owner shows it while the panel is inert, for example
with `"Sky inpaint 3" is locked` and an Unlock button, and handles `fix_requested`.
"""
from typing import Optional

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from src.ui.ink_style import RADIUS, ink_colors

STRIPE_WIDTH = 4
BANNER_MARGIN = 8


class DisabledBanner(QFrame):
    """Explains why a panel can't be used, and offers an action that fixes it."""

    fix_requested = Signal()

    def __init__(self, message: str = '', fix_text: str = '', parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._message = QLabel(message)
        self._message.setWordWrap(True)
        self._message.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._message.setMinimumWidth(1)
        self._fix_button = QPushButton(fix_text)
        self._fix_button.clicked.connect(self.fix_requested)
        self._fix_button.setVisible(fix_text != '')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(BANNER_MARGIN + STRIPE_WIDTH, BANNER_MARGIN // 2, BANNER_MARGIN, BANNER_MARGIN // 2)
        layout.setSpacing(BANNER_MARGIN)
        layout.addWidget(self._message, stretch=1)
        layout.addWidget(self._fix_button)
        self.setAccessibleName(message)

    @property
    def fix_button(self) -> QPushButton:
        """Returns the button that offers the fix."""
        return self._fix_button

    def message(self) -> str:
        """Returns the explanation text."""
        return self._message.text()

    def set_message(self, message: str) -> None:
        """Changes the explanation, such as `"Sky inpaint 3" is locked`."""
        self._message.setText(message)
        self.setAccessibleName(message)

    def set_fix(self, fix_text: str) -> None:
        """Sets the fix button's text, such as "Unlock". With an empty text the button is hidden."""
        self._fix_button.setText(fix_text)
        self._fix_button.setVisible(fix_text != '')

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws a rounded plate with a signal-colored stripe on its left edge, from the current palette."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        colors = ink_colors()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        stripe = colors.signal if colors is not None else palette.color(QPalette.ColorRole.Highlight)
        outline = palette.color(QPalette.ColorRole.Mid)
        painter.setPen(QPen(outline, 1))
        painter.setBrush(palette.color(QPalette.ColorRole.AlternateBase))
        painter.drawRoundedRect(rect, RADIUS, RADIUS)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(stripe)
        painter.setClipRect(QRectF(rect.left(), rect.top(), STRIPE_WIDTH + 1, rect.height()))
        painter.drawRoundedRect(rect, RADIUS, RADIUS)
        painter.end()
