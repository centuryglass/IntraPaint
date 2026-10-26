"""A row of 2-5 mutually exclusive segments, for short choices that change often, drawn in the Ink style.

`SegmentedControl` replaces `DualToggle` and `SelectionModeToggle` (`option_toggle.py`).

- Each `Segment` pairs a raw option string with the label shown for it. `value()` and `valueChanged` carry the raw
  option string, so translating or renaming a label never changes what is stored or compared.
- `DisplayMode` picks icon plus label, label only, or icon only. Icon-only segments show their label as the tooltip.
- With `combo_fallback`, a control too narrow for its labels shows a combo box with the same options.
- `set_hint_value` highlights the segment a temporary state, such as a held modifier, would pick. It never changes
  the value.
- The control is one focus stop. Arrow keys move the selection between segments.
- The widget holds no config state. The owner connects `valueChanged` and calls `set_value` when the bound value
  changes. Colors and fonts are cached and rebuilt on palette and font changes.
"""
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QFocusEvent, QFont, QFontMetrics, QFontMetricsF, QHelpEvent, QHoverEvent, QIcon,
                           QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPaintEvent, QPalette, QPen, QResizeEvent)
from PySide6.QtWidgets import QComboBox, QSizePolicy, QToolTip, QWidget

from src.ui.ink_style import RADIUS, ink_colors

MIN_SEGMENTS = 2
MAX_SEGMENTS = 5
CONTROL_HEIGHT = 24
SEGMENT_PADDING = 8
ICON_SIZE = 16
ICON_TEXT_SPACING = 4
# The text color mixes this much of the background in while the control is disabled:
DISABLED_TEXT_FRACTION = 0.5
WASH_FALLBACK_ALPHA = 90
HOVER_ALPHA = 40


class DisplayMode(Enum):
    """What each segment shows."""
    ICON_AND_LABEL = 'icon_and_label'
    LABEL = 'label'
    ICON = 'icon'


@dataclass(frozen=True)
class Segment:
    """One choice.

    Parameters
    ----------
    value: str
        The raw option string that `SegmentedControl.value` returns. Never translated.
    label: str
        The translated text shown for the option.
    icon: QIcon or str, optional
        Icon, or the path of an image file. Required for `DisplayMode.ICON`.
    tooltip: str, optional
        Tooltip text. Defaults to the label.
    """
    value: str
    label: str
    icon: Optional[QIcon | str] = None
    tooltip: Optional[str] = None

    def qicon(self) -> QIcon:
        """Returns the icon as a QIcon, empty if there is none."""
        if self.icon is None:
            return QIcon()
        return self.icon if isinstance(self.icon, QIcon) else QIcon(self.icon)


def _mix(color: QColor, other: QColor, other_fraction: float) -> QColor:
    return QColor.fromRgbF(color.redF() + (other.redF() - color.redF()) * other_fraction,
                           color.greenF() + (other.greenF() - color.greenF()) * other_fraction,
                           color.blueF() + (other.blueF() - color.blueF()) * other_fraction)


class _Colors:
    """The colors and font a control paints with, read from the palette and the Ink theme."""

    def __init__(self, widget: QWidget) -> None:
        enabled = widget.isEnabled()
        group = QPalette.ColorGroup.Active if enabled else QPalette.ColorGroup.Disabled

        def _color(role: QPalette.ColorRole) -> QColor:
            return widget.palette().color(group, role)

        self.font = QFont(widget.font())
        self.background = _color(QPalette.ColorRole.Base)
        self.text = _color(QPalette.ColorRole.Text)
        self.outline = _color(QPalette.ColorRole.Mid)
        self.focus = _color(QPalette.ColorRole.Highlight)
        colors = ink_colors()
        accent = colors.accent_hover if colors is not None else self.focus
        if colors is not None:
            self.checked = QColor(colors.accent_wash)
        else:
            self.checked = QColor(accent)
            self.checked.setAlpha(WASH_FALLBACK_ALPHA)
        self.hover = QColor(accent)
        self.hover.setAlpha(HOVER_ALPHA)
        self.hover_outline = accent
        self.hint = accent
        if not enabled:
            # A disabled control stays distinguishable from a disabled checked state by keeping its wash, dimmed.
            self.text = _mix(self.text, self.background, DISABLED_TEXT_FRACTION)
            self.checked = _mix(self.background, self.outline, 0.5)
            self.hover = QColor(Qt.GlobalColor.transparent)
            self.hover_outline = self.outline
            self.hint = self.outline
            if colors is not None:
                self.outline = colors.disabled_outline


class SegmentedControl(QWidget):
    """A row of 2-5 mutually exclusive segments.

    Parameters
    ----------
    segments: list[Segment]
        2-5 choices, with distinct values.
    display_mode: DisplayMode
        What each segment shows.
    combo_fallback: bool
        If true, a combo box replaces the segments while the control is narrower than its segments need.
    parent: QWidget, optional
        Optional parent widget.
    """

    valueChanged = Signal(str)

    def __init__(self, segments: list[Segment], display_mode: DisplayMode = DisplayMode.ICON_AND_LABEL,
                 combo_fallback: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        if not MIN_SEGMENTS <= len(segments) <= MAX_SEGMENTS:
            raise ValueError(f'SegmentedControl needs {MIN_SEGMENTS}-{MAX_SEGMENTS} segments, got {len(segments)}')
        if len({segment.value for segment in segments}) != len(segments):
            raise ValueError(f'SegmentedControl needs distinct values, got {[s.value for s in segments]}')
        self._segments = list(segments)
        self._display_mode = display_mode
        self._check_icons(display_mode)
        self._combo_fallback = combo_fallback
        self._index = 0
        self._hint_index: Optional[int] = None
        self._hover_index: Optional[int] = None
        self._keyboard_focus = False
        self._combo: Optional[QComboBox] = None
        if combo_fallback:
            self._combo = QComboBox(self)
            for segment in self._segments:
                self._combo.addItem(segment.qicon(), segment.label, segment.value)
            self._combo.currentIndexChanged.connect(self._combo_index_changed)
            self._combo.hide()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed))
        self._colors = _Colors(self)
        self._update_accessibility()

    @classmethod
    def from_enum(cls, options: type[Enum], labels: dict[Enum, str], icons: Optional[dict[Enum, QIcon | str]] = None,
                  tooltips: Optional[dict[Enum, str]] = None, **kwargs) -> 'SegmentedControl':
        """Creates a control over a `str` Enum's members, in definition order.

        The stored values are the members' values. `labels` gives each member's translated label. `icons` and
        `tooltips` are optional per member. `kwargs` are the remaining constructor options.
        """
        segments = [Segment(str(member.value), labels[member], None if icons is None else icons.get(member),
                            None if tooltips is None else tooltips.get(member)) for member in options]
        return cls(segments, **kwargs)

    # -----------------------------------------------------------------------------------------------------------------
    # Value
    # -----------------------------------------------------------------------------------------------------------------

    @property
    def segments(self) -> list[Segment]:
        """Returns the control's segments."""
        return list(self._segments)

    @property
    def display_mode(self) -> DisplayMode:
        """Returns what each segment shows."""
        return self._display_mode

    def set_display_mode(self, display_mode: DisplayMode) -> None:
        """Changes what each segment shows, so a panel can pick the mode that fits its space."""
        if display_mode == self._display_mode:
            return
        self._check_icons(display_mode)
        self._display_mode = display_mode
        self.updateGeometry()
        self._update_fallback()
        self.update()

    def _check_icons(self, display_mode: DisplayMode) -> None:
        if display_mode == DisplayMode.ICON and any(segment.icon is None for segment in self._segments):
            raise ValueError('Icon-only display needs an icon on every segment')

    def value(self) -> str:
        """Returns the raw option string of the checked segment."""
        return self._segments[self._index].value

    def set_value(self, value: str) -> None:
        """Checks the segment with an option string, emitting `valueChanged` if that changes the value.

        Raises
        ------
        ValueError
            If no segment has the value.
        """
        self._select(self._index_of(value))

    def set_segment_tooltip(self, value: str, tooltip: Optional[str]) -> None:
        """Replaces the tooltip of the segment with an option string. None restores its label."""
        index = self._index_of(value)
        segment = self._segments[index]
        self._segments[index] = Segment(segment.value, segment.label, segment.icon, tooltip)

    def set_segment_label(self, value: str, label: str) -> None:
        """Replaces the label of the segment with an option string, such as a shorter label that fits a panel's
        space."""
        index = self._index_of(value)
        segment = self._segments[index]
        if segment.label == label:
            return
        self._segments[index] = Segment(segment.value, label, segment.icon, segment.tooltip)
        if self._combo is not None:
            self._combo.setItemText(index, label)
        self._update_accessibility()
        self.updateGeometry()
        self._update_fallback()
        self.update()

    def set_segment_icon(self, value: str, icon: Optional[QIcon | str]) -> None:
        """Replaces the icon of the segment with an option string, such as a preview redrawn in new colors."""
        index = self._index_of(value)
        segment = self._segments[index]
        self._segments[index] = Segment(segment.value, segment.label, icon, segment.tooltip)
        if self._combo is not None:
            self._combo.setItemIcon(index, self._segments[index].qicon())
        self.update()

    def _index_of(self, value: str) -> int:
        for i, segment in enumerate(self._segments):
            if segment.value == value:
                return i
        raise ValueError(f'No segment with value {value!r}, expected one of {[s.value for s in self._segments]}')

    def _select(self, index: int) -> None:
        if index == self._index:
            return
        self._index = index
        if self._combo is not None:
            self._combo.blockSignals(True)
            self._combo.setCurrentIndex(index)
            self._combo.blockSignals(False)
        self._update_accessibility()
        self.update()
        self.valueChanged.emit(self._segments[index].value)

    def _combo_index_changed(self, index: int) -> None:
        self._select(index)

    def hint_value(self) -> Optional[str]:
        """Returns the option string of the hinted segment, or None."""
        return None if self._hint_index is None else self._segments[self._hint_index].value

    def set_hint_value(self, value: Optional[str]) -> None:
        """Highlights the segment a temporary state would pick, or clears the highlight with None. Does not change
        the value."""
        index = None if value is None else self._index_of(value)
        if index != self._hint_index:
            self._hint_index = index
            self.update()

    def _update_accessibility(self) -> None:
        self.setAccessibleDescription(self._segments[self._index].label)

    # -----------------------------------------------------------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------------------------------------------------------

    def _content_width(self, segment: Segment) -> int:
        # Painting elides against the unrounded advance, so a rounded-down width would elide the label at this size:
        metrics = QFontMetricsF(self.font())
        show_text = self._display_mode != DisplayMode.ICON
        show_icon = self._display_mode != DisplayMode.LABEL and segment.icon is not None
        width = 0
        if show_icon:
            width += ICON_SIZE
        if show_text:
            width += math.ceil(metrics.horizontalAdvance(segment.label)) + (ICON_TEXT_SPACING if show_icon else 0)
        return width + 2 * SEGMENT_PADDING

    def _segment_width_hint(self) -> int:
        return max(self._content_width(segment) for segment in self._segments)

    def _segments_width(self) -> int:
        """Returns the width at which every segment fits its content."""
        return self._segment_width_hint() * len(self._segments)

    def sizeHint(self) -> QSize:
        """Returns room for equal segments, each as wide as the widest."""
        return QSize(self._segments_width(), CONTROL_HEIGHT)

    def minimumSizeHint(self) -> QSize:
        """Returns the smallest size that fits the segments, or a combo box if there is a fallback."""
        if self._combo is not None:
            return QSize(self._combo.minimumSizeHint().width(), CONTROL_HEIGHT)
        return self.sizeHint()

    def uses_combo_fallback(self) -> bool:
        """Returns whether the combo box is replacing the segments."""
        return self._combo is not None and self.width() < self._segments_width()

    def _update_fallback(self) -> None:
        if self._combo is None:
            return
        use_combo = self.uses_combo_fallback()
        self._combo.setGeometry(self.rect())
        self._combo.setVisible(use_combo)

    def resizeEvent(self, event: QResizeEvent) -> None:  # pylint: disable=invalid-name
        """Switches between the segments and the combo box fallback."""
        super().resizeEvent(event)
        self._update_fallback()

    def showEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Applies the fallback for the size the control is shown at."""
        super().showEvent(event)
        self._update_fallback()

    def segment_rect(self, index: int) -> QRect:
        """Returns the area of one segment. Segment widths differ by at most one pixel."""
        count = len(self._segments)
        left = self.width() * index // count
        right = self.width() * (index + 1) // count
        return QRect(left, 0, right - left, self.height())

    def _index_at(self, pos: QPoint) -> Optional[int]:
        if not self.rect().contains(pos):
            return None
        return min(pos.x() * len(self._segments) // max(self.width(), 1), len(self._segments) - 1)

    # -----------------------------------------------------------------------------------------------------------------
    # Painting
    # -----------------------------------------------------------------------------------------------------------------

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the box, the checked and hovered segments, the dividers, the hint and the focus ring."""
        if self.uses_combo_fallback():
            return
        colors = self._colors
        box = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(colors.background)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(box, RADIUS, RADIUS)
        painter.save()
        painter.setClipPath(self._box_path(box))
        for i in range(len(self._segments)):
            rect = QRectF(self.segment_rect(i))
            if i == self._index:
                painter.fillRect(rect, colors.checked)
            elif i == self._hover_index and self.isEnabled():
                painter.fillRect(rect, colors.hover)
        painter.restore()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(colors.outline, 1))
        for i in range(1, len(self._segments)):
            x = self.segment_rect(i).left() + 0.5
            painter.drawLine(x, 1, x, self.height() - 1)
        painter.drawRoundedRect(box, RADIUS, RADIUS)
        if self._hint_index is not None:
            painter.setPen(QPen(colors.hint, 2))
            rect = QRectF(self.segment_rect(self._hint_index)).adjusted(1.5, 1.5, -1.5, -1.5)
            painter.drawRoundedRect(rect, max(RADIUS - 1, 0), max(RADIUS - 1, 0))
        if self._keyboard_focus and self.isEnabled():
            painter.setPen(QPen(colors.focus, 1))
            painter.drawRoundedRect(box, RADIUS, RADIUS)
            painter.drawRoundedRect(box.adjusted(1, 1, -1, -1), max(RADIUS - 1, 0), max(RADIUS - 1, 0))
        painter.setFont(colors.font)
        for i, segment in enumerate(self._segments):
            self._paint_segment(painter, segment, self.segment_rect(i))
        painter.end()

    @staticmethod
    def _box_path(box: QRectF) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(box, RADIUS, RADIUS)
        return path

    def _paint_segment(self, painter: QPainter, segment: Segment, rect: QRect) -> None:
        """Draws a segment's icon and label, centered in its area."""
        colors = self._colors
        metrics = QFontMetrics(colors.font)
        show_text = self._display_mode != DisplayMode.ICON
        icon = segment.qicon()
        show_icon = self._display_mode != DisplayMode.LABEL and not icon.isNull()
        available = rect.width() - 2 * SEGMENT_PADDING
        text = metrics.elidedText(segment.label, Qt.TextElideMode.ElideRight,
                                  max(available - (ICON_SIZE + ICON_TEXT_SPACING if show_icon else 0), 0)) \
            if show_text else ''
        content_width = (ICON_SIZE if show_icon else 0) + (metrics.horizontalAdvance(text) if text else 0) \
            + (ICON_TEXT_SPACING if show_icon and text else 0)
        x = rect.left() + (rect.width() - content_width) // 2
        if show_icon:
            mode = QIcon.Mode.Normal if self.isEnabled() else QIcon.Mode.Disabled
            icon.paint(painter, QRect(x, rect.top() + (rect.height() - ICON_SIZE) // 2, ICON_SIZE, ICON_SIZE),
                       Qt.AlignmentFlag.AlignCenter, mode)
            x += ICON_SIZE + (ICON_TEXT_SPACING if text else 0)
        if text:
            self._paint_text(painter, text, QRect(x, rect.top(), metrics.horizontalAdvance(text) + 1, rect.height()))

    def _paint_text(self, painter: QPainter, text: str, rect: QRect) -> None:
        painter.setPen(self._colors.text)
        painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

    def changeEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """Rebuilds the cached colors and font when the palette, font or enabled state changes."""
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.FontChange, QEvent.Type.EnabledChange,
                            QEvent.Type.StyleChange):
            self._colors = _Colors(self)
            if event.type() == QEvent.Type.FontChange:
                self.updateGeometry()
            self.update()
        super().changeEvent(event)

    # -----------------------------------------------------------------------------------------------------------------
    # Input
    # -----------------------------------------------------------------------------------------------------------------

    def event(self, event: QEvent) -> bool:
        """Tracks the hovered segment, and shows each segment's tooltip."""
        if isinstance(event, QHoverEvent) and event.type() in (QEvent.Type.HoverMove, QEvent.Type.HoverEnter):
            index = self._index_at(event.position().toPoint())
            if index != self._hover_index:
                self._hover_index = index
                self.update()
        elif event.type() == QEvent.Type.HoverLeave:
            self._hover_index = None
            self.update()
        elif event.type() == QEvent.Type.ToolTip and isinstance(event, QHelpEvent):
            index = self._index_at(event.pos())
            if index is None:
                QToolTip.hideText()
            else:
                QToolTip.showText(event.globalPos(), self.segment_tooltip(index), self)
            return True
        return super().event(event)

    def segment_tooltip(self, index: int) -> str:
        """Returns a segment's tooltip: its own, or its label."""
        segment = self._segments[index]
        return segment.tooltip if segment.tooltip is not None else segment.label

    def mousePressEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """Checks the segment under a left click."""
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        self._keyboard_focus = False
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        index = self._index_at(event.position().toPoint())
        if index is not None:
            self._select(index)
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # pylint: disable=invalid-name
        """Left and Up check the previous segment, Right and Down the next, Home and End the first and last."""
        key = event.key()
        count = len(self._segments)
        target = None
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            target = max(self._index - 1, 0)
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            target = min(self._index + 1, count - 1)
        elif key == Qt.Key.Key_Home:
            target = 0
        elif key == Qt.Key.Key_End:
            target = count - 1
        if target is None:
            super().keyPressEvent(event)
            return
        self._select(target)
        event.accept()

    def focusInEvent(self, event: QFocusEvent) -> None:  # pylint: disable=invalid-name
        """Shows the focus ring when focus arrives from the keyboard."""
        self._keyboard_focus = event.reason() in (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
                                                  Qt.FocusReason.ShortcutFocusReason)
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event: QFocusEvent) -> None:  # pylint: disable=invalid-name
        """Hides the focus ring."""
        self._keyboard_focus = False
        super().focusOutEvent(event)
        self.update()
