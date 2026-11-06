"""A push button with a title and a one-line summary beneath it, for a primary action that may grow tall."""
from typing import Optional

from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtGui import QPaintEvent, QPalette
from PySide6.QtWidgets import QPushButton, QSizePolicy, QStyle, QStyleOptionButton, QStylePainter, QWidget

from src.ui.ink_style import STICKER_OFFSET, ink_colors

SUMMARY_FONT_FRACTION = 0.9
DEFAULT_MAX_LINES = 2


class SummaryButton(QPushButton):
    """A push button that draws its text as a bold title over a smaller summary line.

    - The minimum size is the title's, so the button never needs more room than a plain button. The summary draws
      only while the button is tall enough for both lines, and elides to the button's width.
    - The preferred height has room for both lines. `set_max_lines` sets how tall it grows past that: with more than
      two lines it stretches to take spare height, and with two it takes none.
    - Mark it with `src.ui.ink_style.set_primary_button` to get the primary look.
    """

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self._summary = ''
        self._max_lines = DEFAULT_MAX_LINES
        self._apply_max_lines()

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

    def set_max_lines(self, lines: int) -> None:
        """Sets the most text lines of height the button grows to. Values above two let it stretch."""
        self._max_lines = max(1, lines)
        self._apply_max_lines()

    def _line_height(self) -> int:
        return self.fontMetrics().lineSpacing()

    def _padding(self) -> int:
        return super().sizeHint().height() - self._line_height()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the title's size with room for the summary line."""
        hint = super().sizeHint()
        return QSize(hint.width(), hint.height() + (self._line_height() if self._summary else 0))

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the size of the title alone."""
        return super().sizeHint()

    def _apply_max_lines(self) -> None:
        stretches = self._max_lines > DEFAULT_MAX_LINES
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Expanding if stretches else QSizePolicy.Policy.Preferred)
        self.setMaximumHeight(self._line_height() * self._max_lines + self._padding())
        self.updateGeometry()

    def changeEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """Re-applies the height cap when the font or style changes."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._apply_max_lines()

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
        summary_height = painter.fontMetrics().lineSpacing()
        show_summary = self._summary != '' and self.height() >= title_height + summary_height + self._padding()
        if not show_summary:
            summary_height = 0
        top = body.top() + (body.height() - title_height - summary_height) // 2
        margin = self.style().pixelMetric(QStyle.PixelMetric.PM_ButtonMargin, option, self)
        text_width = max(1, body.width() - 2 * margin)
        painter.setFont(title_font)
        painter.drawText(QRect(body.left() + margin, top, text_width, title_height), Qt.AlignmentFlag.AlignCenter,
                         painter.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, text_width))
        if show_summary:
            painter.setFont(summary_font)
            painter.drawText(QRect(body.left() + margin, top + title_height, text_width, summary_height),
                             Qt.AlignmentFlag.AlignCenter,
                             painter.fontMetrics().elidedText(self._summary, Qt.TextElideMode.ElideRight, text_width))
