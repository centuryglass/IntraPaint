"""A panel header: the panel or active tool's icon, name and key, an optional dim description, a reset-to-defaults
button and a More button.

- The key and description follow the name. When the first line can't fit them, they move to a second line, where the
  description wraps. A name that still doesn't fit ends with an ellipsis.
- The header holds no config. `reset_requested` fires when the reset button is clicked, and the owner restores its
  declared keys (see `src.ui.panel.panel_reset`).
- The More button opens a popover holding the controls a small grid size moved out of the panel, plus panel
  commands. The owner supplies them with `set_popover_content` and refreshes them in a `more_requested` handler.
- In a strip one row tall (Strip Short) the owner hides the header and places `more_button` at the end of the panel's
  row, and `restore_more_button` puts it back.
"""
from typing import Optional

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPalette, QPen, QResizeEvent
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QSizePolicy, QStyle, QStyleOptionToolButton,
                               QToolButton, QVBoxLayout, QWidget)

from src.ui.widget.keycap_badge import KeycapBadge
from src.ui.widget.shortcut_tooltip import shortcut_tooltip_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.panel_header'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


RESET_TOOLTIP = _tr('Reset to defaults')
MORE_TOOLTIP = _tr('More')

ICON_SIZE = 18
BUTTON_SIZE = 24
GLYPH_SIZE = 12.0
HEADER_SPACING = 6
LINE_SPACING = 2
POPOVER_MARGIN = 8


class _GlyphButton(QToolButton):
    """A flat tool button drawing a vector glyph in the palette's text color, so it follows palette changes."""

    RESET = 'reset'
    MORE = 'more'

    def __init__(self, glyph: str, tooltip: str) -> None:
        super().__init__()
        self._glyph = glyph
        self.setAutoRaise(True)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def sizeHint(self) -> QSize:
        """Returns the fixed button size."""
        return QSize(BUTTON_SIZE, BUTTON_SIZE)

    def paintEvent(self, _event) -> None:  # pylint: disable=invalid-name
        """Draws the button's frame with the style, then its glyph."""
        painter = QPainter(self)
        option = QStyleOptionToolButton()
        self.initStyleOption(option)
        option.icon = QIcon()
        option.text = ''
        option.toolButtonStyle = Qt.ToolButtonStyle.ToolButtonIconOnly
        self.style().drawComplexControl(QStyle.ComplexControl.CC_ToolButton, option, painter, self)
        group = QPalette.ColorGroup.Active if self.isEnabled() else QPalette.ColorGroup.Disabled
        color = self.palette().color(group, QPalette.ColorRole.ButtonText)
        center = QPointF(self.width() / 2, self.height() / 2)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._glyph == self.MORE:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            for offset in (-4.0, 0.0, 4.0):
                painter.drawEllipse(center + QPointF(offset, 0), 1.3, 1.3)
        else:
            radius = GLYPH_SIZE / 2 - 1
            arc_rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
            path = QPainterPath()
            path.arcMoveTo(arc_rect, 60)
            path.arcTo(arc_rect, 60, 270)
            painter.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            tip = path.pointAtPercent(0.0)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            arrow = QPainterPath()
            arrow.moveTo(tip + QPointF(-1.5, -3.5))
            arrow.lineTo(tip + QPointF(3.5, -1.0))
            arrow.lineTo(tip + QPointF(-0.5, 2.5))
            arrow.closeSubpath()
            painter.drawPath(arrow)
        painter.end()


class _ElidedLabel(QLabel):
    """A one-line label that ends its text with an ellipsis when it is too narrow, and shows the full text as a
    tooltip then."""

    def __init__(self) -> None:
        super().__init__()
        self._full_text = ''
        self.setMinimumWidth(1)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

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

    def sizeHint(self) -> QSize:
        """Returns the size of the full text."""
        return QSize(self.full_text_width(), super().sizeHint().height())

    def minimumSizeHint(self) -> QSize:
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


class PanelPopover(QFrame):
    """A frameless popup window holding one widget, which closes on any click outside it."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAutoFillBackground(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(POPOVER_MARGIN, POPOVER_MARGIN, POPOVER_MARGIN, POPOVER_MARGIN)
        self._content: Optional[QWidget] = None

    @property
    def content(self) -> Optional[QWidget]:
        """Returns the hosted widget, if any."""
        return self._content

    def set_content(self, content: Optional[QWidget]) -> None:
        """Replaces the hosted widget. The popover takes ownership of the new one and detaches the old one."""
        if self._content is not None:
            self.layout().removeWidget(self._content)
            self._content.setParent(None)
        self._content = content
        if content is not None:
            self.layout().addWidget(content)
            content.show()

    def popup_below(self, anchor: QWidget) -> None:
        """Shows the popover under `anchor`, with its right edge aligned to the anchor's."""
        self.adjustSize()
        corner = anchor.mapToGlobal(anchor.rect().bottomRight())
        self.move(corner.x() - self.width() + 1, corner.y() + 2)
        self.show()


class PanelHeader(QWidget):
    """Shows what a panel is for and offers its reset and overflow commands."""

    reset_requested = Signal()
    more_requested = Signal()

    def __init__(self, name: str, icon: Optional[QIcon] = None, key_text: str = '',
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(ICON_SIZE, ICON_SIZE)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label = _ElidedLabel()
        self._key_badge = self._make_key_badge()
        self._description_label = QLabel()
        self._description_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._description_label.setMinimumWidth(1)
        self._description_label.hide()
        # The key and description, which move to their own line when the first line can't fit them:
        self._details = QWidget()
        details_layout = QHBoxLayout(self._details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(HEADER_SPACING)
        details_layout.addWidget(self._key_badge)
        details_layout.addWidget(self._description_label, stretch=1)
        self._wrapped = False
        self._reset_button = _GlyphButton(_GlyphButton.RESET, RESET_TOOLTIP)
        self._more_button = _GlyphButton(_GlyphButton.MORE, MORE_TOOLTIP)
        self._more_button.hide()
        self._popover = PanelPopover(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(LINE_SPACING)
        self._first_line = QHBoxLayout()
        self._first_line.setSpacing(HEADER_SPACING)
        self._first_line.addWidget(self._icon_label)
        self._first_line.addWidget(self._name_label)
        self._first_line.addWidget(self._details, stretch=1)
        self._first_line.addWidget(self._reset_button)
        self._first_line.addWidget(self._more_button)
        self._second_line = QHBoxLayout()
        self._second_line.setSpacing(HEADER_SPACING)
        layout.addLayout(self._first_line)
        layout.addLayout(self._second_line)
        self._reset_button.clicked.connect(self.reset_requested)
        self._more_button.clicked.connect(self.show_popover)
        self._icon = icon if icon is not None else QIcon()
        self._name_label.set_full_text(name)
        self.set_key_text(key_text)
        self._refresh_icon()

    def _make_key_badge(self) -> KeycapBadge:
        return KeycapBadge()

    @property
    def reset_button(self) -> QToolButton:
        """Returns the reset-to-defaults button."""
        return self._reset_button

    @property
    def more_button(self) -> QToolButton:
        """Returns the More button, which the owner can move to another layout when it hides the header."""
        return self._more_button

    @property
    def key_badge(self) -> KeycapBadge:
        """Returns the keycap showing the panel's key."""
        return self._key_badge

    @property
    def popover(self) -> PanelPopover:
        """Returns the popover the More button opens."""
        return self._popover

    def name(self) -> str:
        """Returns the panel or tool name, in full even while it is elided."""
        return self._name_label.full_text

    @property
    def is_wrapped(self) -> bool:
        """Whether the key and description are on their own line."""
        return self._wrapped

    def set_name(self, name: str, icon: Optional[QIcon] = None) -> None:
        """Changes the shown name, and the icon if one is given, for example when the active tool changes."""
        self._name_label.set_full_text(name)
        if icon is not None:
            self._icon = icon
            self._refresh_icon()
        self._fit_lines()

    def set_icon_width(self, width: int) -> None:
        """Centers the icon in a column `width` pixels wide, to line it up with a column of buttons below or above."""
        self._icon_label.setFixedWidth(max(width, ICON_SIZE))
        self._fit_lines()

    def restore_more_button(self) -> None:
        """Puts the More button back at the end of the first line, after its owner moved it elsewhere."""
        self._first_line.addWidget(self._more_button)

    def set_key_text(self, key_text: str) -> None:
        """Shows `key_text` on a keycap after the name, or hides the keycap if it is empty."""
        self._key_badge.set_text(key_text)
        self._key_badge.setVisible(key_text != '')
        self._fit_lines()

    def description(self) -> str:
        """Returns the description shown after the key, or the empty string if none is shown."""
        return self._description_label.text()

    def set_description(self, description: str) -> None:
        """Shows a dim description after the key, or hides it if `description` is empty."""
        self._description_label.setText(description)
        self._description_label.setVisible(description != '')
        self._fit_lines()

    def set_reset_tooltip(self, key_text: str = '') -> None:
        """Adds a key binding to the reset button's tooltip, or restores the plain tooltip if `key_text` is empty."""
        self._reset_button.setToolTip(shortcut_tooltip_text(RESET_TOOLTIP, key_text))

    def set_popover_content(self, content: Optional[QWidget]) -> None:
        """Sets the widget the More button shows. With None, the More button is hidden."""
        self._popover.set_content(content)
        self._more_button.setVisible(content is not None)

    def show_popover(self) -> None:
        """Emits `more_requested` so the owner can refresh the content, then shows the popover under the button."""
        self.more_requested.emit()
        if self._popover.content is not None:
            self._popover.popup_below(self._more_button)

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Moves the key and description to their own line if the first line can't fit them."""
        super().resizeEvent(event)
        self._fit_lines()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the size with the key and description on the first line."""
        return QSize(self._one_line_width(), self._first_line_height())

    def _first_line_height(self) -> int:
        widgets = [self._icon_label, self._name_label, self._key_badge, self._reset_button, self._more_button]
        return max(widget.sizeHint().height() for widget in widgets)

    def _second_line_indent(self) -> int:
        return self._icon_label.width() + HEADER_SPACING if not self._icon_label.isHidden() else 0

    def _needs_second_line(self, width: int) -> bool:
        has_details = not self._key_badge.isHidden() or not self._description_label.isHidden()
        return has_details and width < self._one_line_width()

    def _one_line_width(self) -> int:
        """Returns the width the first line needs with the key and description on it."""
        widgets = [self._icon_label, self._key_badge, self._reset_button, self._more_button]
        shown = [widget for widget in widgets if not widget.isHidden()]
        width = sum(widget.sizeHint().width() for widget in shown) + self._name_label.full_text_width()
        if not self._description_label.isHidden():
            # A pixel to spare on each side for rounding, as `_ElidedLabel.full_text_width` has:
            width += self._description_label.fontMetrics().horizontalAdvance(self._description_label.text()) + 2
            width += HEADER_SPACING
        return width + HEADER_SPACING * len(shown)

    def _fit_lines(self) -> None:
        self.updateGeometry()
        wrap = self._needs_second_line(self.width())
        if wrap == self._wrapped:
            return
        self._wrapped = wrap
        if wrap:
            self._first_line.removeWidget(self._details)
            self._second_line.setContentsMargins(self._second_line_indent(), 0, 0, 0)
            self._second_line.addWidget(self._details)
            self._first_line.insertStretch(2, 1)
        else:
            self._second_line.removeWidget(self._details)
            stretch = self._first_line.itemAt(2)
            if stretch is not None and stretch.spacerItem() is not None:
                self._first_line.removeItem(stretch)
            self._first_line.insertWidget(2, self._details, stretch=1)
        self._description_label.setWordWrap(wrap)
        self._details.show()

    def _refresh_icon(self) -> None:
        if not self._icon.isNull():
            self._icon_label.setPixmap(self._icon.pixmap(QSize(ICON_SIZE, ICON_SIZE)))
        self._icon_label.setVisible(not self._icon.isNull())

    def changeEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """Rebuilds the icon pixmap when the palette changes, for icons that recolor themselves."""
        if event.type() == QEvent.Type.PaletteChange:
            self._refresh_icon()
        super().changeEvent(event)
