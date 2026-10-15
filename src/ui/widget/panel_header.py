"""A panel header: the panel or active tool's icon, name and key, a reset-to-defaults button and a More button.

- The header holds no config. `reset_requested` fires when the reset button is clicked, and the owner restores its
  declared keys (see `src.ui.panel.panel_reset`).
- The More button opens a popover holding the controls a size class moved out of the panel, plus panel commands. The
  owner supplies them with `set_popover_content` and refreshes them in a `more_requested` handler.
- In the Strip Short size class the owner hides the header and places `more_button` at the end of the panel's row.
"""
from typing import Optional

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPalette, QPen
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
        self._name_label = QLabel()
        self._name_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._name_label.setMinimumWidth(1)
        self._key_badge = self._make_key_badge()
        self._reset_button = _GlyphButton(_GlyphButton.RESET, RESET_TOOLTIP)
        self._more_button = _GlyphButton(_GlyphButton.MORE, MORE_TOOLTIP)
        self._more_button.hide()
        self._popover = PanelPopover(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(HEADER_SPACING)
        layout.addWidget(self._icon_label)
        layout.addWidget(self._name_label, stretch=1)
        layout.addWidget(self._key_badge)
        layout.addWidget(self._reset_button)
        layout.addWidget(self._more_button)
        self._reset_button.clicked.connect(self.reset_requested)
        self._more_button.clicked.connect(self.show_popover)
        self._icon = icon if icon is not None else QIcon()
        self._name_label.setText(name)
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
        """Returns the panel or tool name."""
        return self._name_label.text()

    def set_name(self, name: str, icon: Optional[QIcon] = None) -> None:
        """Changes the shown name, and the icon if one is given, for example when the active tool changes."""
        self._name_label.setText(name)
        if icon is not None:
            self._icon = icon
            self._refresh_icon()

    def set_key_text(self, key_text: str) -> None:
        """Shows `key_text` on a keycap after the name, or hides the keycap if it is empty."""
        self._key_badge.set_text(key_text)
        self._key_badge.setVisible(key_text != '')

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

    def _refresh_icon(self) -> None:
        if not self._icon.isNull():
            self._icon_label.setPixmap(self._icon.pixmap(QSize(ICON_SIZE, ICON_SIZE)))
        self._icon_label.setVisible(not self._icon.isNull())

    def changeEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """Rebuilds the icon pixmap when the palette changes, for icons that recolor themselves."""
        if event.type() == QEvent.Type.PaletteChange:
            self._refresh_icon()
        super().changeEvent(event)
