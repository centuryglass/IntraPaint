"""A panel section: a short header over a body, collapsible to one line that still summarizes its values.

- The header shows a chevron, the title, and small actions on its right. While collapsed it also shows a summary of
  the section's values, such as "512 x 512, batch 4". The owner supplies the summary text with `set_summary`, or with
  `bind_summary`, which recomputes it when a bound value changes.
- Two states decide whether the body shows: the remembered choice (`is_expanded`) and a forced collapse
  (`set_forced_collapsed`) that a panel without room uses without changing the remembered choice.
- The section holds no config. The owner stores `is_expanded` per section by connecting `expanded_changed`, and calls
  `set_expanded` to restore it.
"""
from typing import Callable, Optional

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics, QKeyEvent, QPainter, QPainterPath, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from src.ui.widget.keycap_badge import KeycapBadge

HEADER_HEIGHT = 26
CHEVRON_SIZE = 8.0
CHEVRON_MARGIN = 4
TEXT_GAP = 8
# The summary mixes this much of the background into the text color:
SUMMARY_DIM_FRACTION = 0.4
ACTION_SPACING = 4


def _mix(color, other, other_fraction: float):
    return type(color).fromRgbF(*(color.getRgbF()[i] + (other.getRgbF()[i] - color.getRgbF()[i]) * other_fraction
                                  for i in range(3)))


class _HeaderButton(QAbstractButton):
    """The clickable part of a section header: chevron, title and, while collapsed, the summary."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.setText(title)
        self.setAccessibleName(title)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._summary = ''
        self._expanded = True

    def set_summary(self, summary: str, expanded: bool) -> None:
        """Changes the summary text and whether the section looks expanded."""
        self._summary = summary
        self._expanded = expanded
        self.update()

    def _title_font(self) -> QFont:
        font = QFont(self.font())
        font.setWeight(QFont.Weight.DemiBold)
        return font

    def sizeHint(self) -> QSize:
        """Returns the chevron and title width at the header height."""
        title_width = QFontMetrics(self._title_font()).horizontalAdvance(self.text())
        return QSize(int(CHEVRON_MARGIN * 2 + CHEVRON_SIZE + TEXT_GAP + title_width), HEADER_HEIGHT)

    def minimumSizeHint(self) -> QSize:
        """Returns room for the chevron alone, so a narrow panel can clip the title instead of widening."""
        return QSize(int(CHEVRON_MARGIN * 2 + CHEVRON_SIZE), HEADER_HEIGHT)

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the chevron, title and summary in palette colors, with a focus underline for keyboard focus."""
        painter = QPainter(self)
        palette = self.palette()
        group = QPalette.ColorGroup.Active if self.isEnabled() else QPalette.ColorGroup.Disabled
        text = palette.color(group, QPalette.ColorRole.WindowText)
        background = palette.color(group, QPalette.ColorRole.Window)
        if self.underMouse():
            text = palette.color(group, QPalette.ColorRole.Highlight).lighter(130)
        center_y = self.height() / 2
        left = float(CHEVRON_MARGIN)
        chevron = QPainterPath()
        half = CHEVRON_SIZE / 2
        if self._expanded:
            chevron.moveTo(left, center_y - half / 2)
            chevron.lineTo(left + half, center_y + half / 2)
            chevron.lineTo(left + CHEVRON_SIZE, center_y - half / 2)
        else:
            chevron.moveTo(left + half / 2, center_y - half)
            chevron.lineTo(left + half * 1.5, center_y)
            chevron.lineTo(left + half / 2, center_y + half)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(text, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(chevron)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        title_font = self._title_font()
        painter.setFont(title_font)
        title_x = int(left + CHEVRON_SIZE + TEXT_GAP)
        title_rect = self.rect().adjusted(title_x, 0, 0, 0)
        painter.setPen(text)
        title_width = QFontMetrics(title_font).horizontalAdvance(self.text())
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         QFontMetrics(title_font).elidedText(self.text(), Qt.TextElideMode.ElideRight,
                                                             max(0, title_rect.width())))
        summary_x = title_x + title_width + TEXT_GAP
        if not self._expanded and self._summary != '' and summary_x < self.width():
            painter.setFont(self.font())
            painter.setPen(_mix(palette.color(group, QPalette.ColorRole.WindowText), background,
                                SUMMARY_DIM_FRACTION))
            summary_rect = self.rect().adjusted(summary_x, 0, 0, 0)
            painter.drawText(summary_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             QFontMetrics(self.font()).elidedText(self._summary, Qt.TextElideMode.ElideRight,
                                                                  summary_rect.width()))
        if self.hasFocus() and self.isEnabled():
            painter.setPen(QPen(palette.color(group, QPalette.ColorRole.Highlight), 1))
            painter.drawLine(CHEVRON_MARGIN, self.height() - 1, self.width() - CHEVRON_MARGIN, self.height() - 1)
        painter.end()

    def enterEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Repaints the hover color."""
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """Repaints without the hover color."""
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # pylint: disable=invalid-name
        """Toggles on Enter and Return, which buttons ignore by default."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            return
        super().keyPressEvent(event)


class PanelSection(QWidget):
    """A titled group of controls that collapses to its header line."""

    expanded_changed = Signal(bool)

    def __init__(self, title: str, body: QWidget, expanded: bool = True, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._title = title
        self._body = body
        self._expanded = expanded
        self._forced_collapsed = False
        self._summary = ''
        self._summary_fn: Optional[Callable[[], str]] = None
        self._header_button = _HeaderButton(title)
        self._header_button.clicked.connect(self._toggle)
        self._actions = QHBoxLayout()
        self._actions.setContentsMargins(0, 0, CHEVRON_MARGIN, 0)
        self._actions.setSpacing(ACTION_SPACING)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(0)
        header.addWidget(self._header_button, stretch=1)
        header.addLayout(self._actions)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(body)
        self._apply_state()

    @property
    def title(self) -> str:
        """Returns the section title."""
        return self._title

    def set_title(self, title: str) -> None:
        """Changes the title shown in the header."""
        self._title = title
        self._header_button.setText(title)
        self._header_button.setAccessibleName(title)
        self._header_button.updateGeometry()
        self._header_button.update()

    @property
    def body(self) -> QWidget:
        """Returns the widget holding the section's controls."""
        return self._body

    @property
    def header_button(self) -> QAbstractButton:
        """Returns the header's toggle button."""
        return self._header_button

    def is_expanded(self) -> bool:
        """Returns the remembered choice: whether the user wants the body shown. A forced collapse doesn't change it."""
        return self._expanded

    def is_collapsed(self) -> bool:
        """Returns whether the body is hidden now, from a collapsed choice or a forced collapse."""
        return self._forced_collapsed or not self._expanded

    def set_expanded(self, expanded: bool) -> None:
        """Sets the remembered choice, and emits `expanded_changed` if it changed."""
        if expanded != self._expanded:
            self._expanded = expanded
            self._apply_state()
            self.expanded_changed.emit(expanded)

    def set_forced_collapsed(self, forced: bool) -> None:
        """Collapses the section regardless of the remembered choice, or lifts that. Header clicks do nothing while
        forced."""
        if forced != self._forced_collapsed:
            self._forced_collapsed = forced
            self._apply_state()

    def summary(self) -> str:
        """Returns the summary text shown while the section is collapsed."""
        return self._summary

    def set_summary(self, summary: str) -> None:
        """Sets the one-line summary of the section's values, such as "Euler a, 30 steps, CFG 7"."""
        self._summary = summary
        self._apply_state()

    def bind_summary(self, summary_fn: Callable[[], str], *change_signals) -> None:
        """Sets the summary from `summary_fn()` now, and again whenever any of the signals is emitted.

        The signals are the controls' value-changed signals, and are emitted on the main thread.
        """
        self._summary_fn = summary_fn
        for signal in change_signals:
            signal.connect(self._refresh_summary)
        self._refresh_summary()

    def add_header_widget(self, widget: QWidget) -> None:
        """Adds a small action, such as a flat button, to the right of the header."""
        self._actions.addWidget(widget)

    def add_header_keycap(self, key_text: str) -> KeycapBadge:
        """Adds a keycap with `key_text` to the right of the header and returns it."""
        badge = KeycapBadge(key_text)
        self.add_header_widget(badge)
        return badge

    def _refresh_summary(self, *_args) -> None:
        if self._summary_fn is not None:
            self.set_summary(self._summary_fn())

    def _toggle(self) -> None:
        if not self._forced_collapsed:
            self.set_expanded(not self._expanded)

    def _apply_state(self) -> None:
        collapsed = self.is_collapsed()
        self._body.setVisible(not collapsed)
        self._header_button.set_summary(self._summary, not collapsed)
        self._header_button.setAccessibleDescription(self._summary)
