"""A push button with a title and a one-line summary beneath it, for a primary action that may grow tall."""
from typing import Optional

from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtGui import QPaintEvent, QPalette
from PySide6.QtWidgets import QPushButton, QSizePolicy, QStyle, QStyleOptionButton, QStylePainter, QWidget

from src.ui.ink_style import STICKER_OFFSET, ink_colors

SUMMARY_FONT_FRACTION = 0.9
MAX_HEIGHT_LINES = 3


class SummaryButton(QPushButton):
    """A push button that draws its text as a bold title over a smaller summary line.

    The summary elides to the button's width and never widens the button. Hints come from the title alone, plus one
    line for the summary, and the height may grow to `MAX_HEIGHT_LINES` text lines (set through
    `setMaximumHeight`). Mark it with `src.ui.ink_style.set_primary_button` to get the primary look.
    """

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self._summary = ''
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._apply_max_height()

    @property
    def summary(self) -> str:
        """The summary line."""
        return self._summary

    def set_summary(self, summary: str) -> None:
        """Changes the summary line."""
        if summary != self._summary:
            self._summary = summary
            self.updateGeometry()
            self.update()

    def _line_height(self) -> int:
        return self.fontMetrics().lineSpacing()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the title's size with room for the summary line."""
        hint = super().sizeHint()
        return QSize(hint.width(), hint.height() + (self._line_height() if self._summary else 0))

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the same size as `sizeHint`."""
        return self.sizeHint()

    def _apply_max_height(self) -> None:
        padding = super().sizeHint().height() - self._line_height()
        self.setMaximumHeight(self._line_height() * MAX_HEIGHT_LINES + padding)

    def changeEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """Re-applies the height cap when the font or style changes."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._apply_max_height()

    def paintEvent(self, _event: QPaintEvent) -> None:  # pylint: disable=invalid-name
        """Draws the button bevel, then the title and summary centered in the body."""
        painter = QStylePainter(self)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        painter.drawControl(QStyle.ControlElement.CE_PushButtonBevel, option)
        primary = ink_colors() is not None and bool(self.property('ink_primary'))
        body = QRect(option.rect)
        if primary:
            body.adjust(0, 0, 0, -STICKER_OFFSET)
            if option.state & QStyle.StateFlag.State_Sunken:
                body.translate(0, STICKER_OFFSET)
        role = QPalette.ColorRole.HighlightedText if primary else QPalette.ColorRole.ButtonText
        group = QPalette.ColorGroup.Disabled if not self.isEnabled() else QPalette.ColorGroup.Active
        color = self.palette().color(group, role)
        painter.setPen(color)
        title_font = painter.font()
        title_font.setWeight(self.font().Weight.DemiBold)
        summary_font = self.font()
        summary_font.setPointSizeF(summary_font.pointSizeF() * SUMMARY_FONT_FRACTION)
        title_height = painter.fontMetrics().lineSpacing()
        painter.setFont(summary_font)
        summary_height = painter.fontMetrics().lineSpacing() if self._summary else 0
        top = body.top() + (body.height() - title_height - summary_height) // 2
        margin = self.style().pixelMetric(QStyle.PixelMetric.PM_ButtonMargin, option, self)
        text_width = max(1, body.width() - 2 * margin)
        painter.setFont(title_font)
        painter.drawText(QRect(body.left() + margin, top, text_width, title_height), Qt.AlignmentFlag.AlignCenter,
                         painter.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, text_width))
        if self._summary:
            painter.setFont(summary_font)
            painter.drawText(QRect(body.left() + margin, top + title_height, text_width, summary_height),
                             Qt.AlignmentFlag.AlignCenter,
                             painter.fontMetrics().elidedText(self._summary, Qt.TextElideMode.ElideRight, text_width))
