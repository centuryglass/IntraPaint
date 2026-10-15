"""A one-line numeric field that scrubs by dragging and types an exact value on click, drawn in the Ink style.

`NumberField` shows a label and a formatted value in a 24 px field, with no fill, for signed or unbounded numbers.
`SliderField` (`slider_field.py`) adds a fill that shows the value's place in a finite range. Both replace the
label + slider + spin box rows.

- Dragging anywhere scrubs the value. A click without a drag opens a text entry. Wheel, arrow keys and Page Up/Down
  step the value. Enter, Return or F2 opens the text entry from the keyboard.
- The stored value and its display are separate: `display_scale`, `suffix` and `zero_text` change what is shown and
  typed, never what `value()` returns.
- The widget holds no config or undo state. The owner connects `valueChanged`, calls `set_value` when the bound value
  changes, and brackets one drag as one undo step with `dragStarted` and `dragFinished`.
- Colors and fonts are cached and rebuilt on palette and font changes.
"""
import math
from typing import Optional

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QFocusEvent, QFont, QFontMetrics, QHelpEvent, QKeyEvent, QMouseEvent, QPainter,
                           QPaintEvent, QPalette, QPen, QResizeEvent, QWheelEvent)
from PySide6.QtWidgets import QApplication, QLineEdit, QSizePolicy, QToolTip, QWidget

from src.ui.ink_style import RADIUS, ink_colors

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.input_fields.number_field'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


PRESSURE_LINK_TOOLTIP = _tr('Pen pressure changes this value')

FIELD_HEIGHT = 24
MIN_WIDTH = 110
PREFERRED_WIDTH = 150
MAX_WIDTH = 300
TEXT_MARGIN = 7
PRESSURE_LINK_WIDTH = 22
PRESSURE_DOT_RADIUS = 4.0
# An unbounded field changes by one step for every this many pixels dragged:
PIXELS_PER_STEP = 4
# A page step is this many single steps, unless set otherwise:
DEFAULT_PAGE_STEPS = 10
# Unfocused label text mixes this much of the background into the text color:
LABEL_DIM_FRACTION = 0.35
FILL_ALPHA = 90


def _mix(color: QColor, other: QColor, other_fraction: float) -> QColor:
    return QColor.fromRgbF(color.redF() + (other.redF() - color.redF()) * other_fraction,
                           color.greenF() + (other.greenF() - color.greenF()) * other_fraction,
                           color.blueF() + (other.blueF() - color.blueF()) * other_fraction)


class _FieldColors:
    """The colors and font a field paints with, read from the palette and the Ink theme."""

    def __init__(self, widget: QWidget) -> None:
        palette = widget.palette()
        enabled = widget.isEnabled()
        group = QPalette.ColorGroup.Active if enabled else QPalette.ColorGroup.Disabled
        self.font = QFont(widget.font())
        self.background = palette.color(group, QPalette.ColorRole.Base)
        self.text = palette.color(group, QPalette.ColorRole.Text)
        self.label = _mix(self.text, self.background, LABEL_DIM_FRACTION)
        self.outline = palette.color(group, QPalette.ColorRole.Mid)
        self.focus = palette.color(group, QPalette.ColorRole.Highlight)
        colors = ink_colors()
        self.hover_outline = colors.accent_hover if colors is not None else self.focus
        self.accent = colors.accent_hover if colors is not None else self.focus
        fill = QColor(self.accent)
        fill.setAlpha(FILL_ALPHA)
        self.fill = fill if enabled else _mix(self.background, self.outline, 0.5)
        if not enabled:
            if colors is not None:
                self.outline = colors.disabled_outline
            self.accent = self.label


class NumberField(QWidget):
    """A labeled numeric field with drag-to-scrub, click-to-type, wheel and key stepping, and an optional pen
    pressure link.

    Parameters
    ----------
    label: str
        Text on the left of the field. Also the accessible name.
    value: int | float
        Initial value. The field is an integer field if value, step, minimum and maximum are all ints, and a float
        field otherwise.
    minimum: Optional[int | float]
        Smallest accepted value, or None for no lower limit.
    maximum: Optional[int | float]
        Largest accepted value, or None for no upper limit.
    step: int | float
        Change made by one arrow key press or wheel notch, and the grid scrubbed and typed values snap to.
    suffix: str
        Text shown after the displayed value, such as ' px' or '%'.
    display_scale: float
        The shown number is the stored value times this, so a 0.0-1.0 opacity can display as a percentage with
        `display_scale=100`. Typed entry is divided by it again.
    decimals: Optional[int]
        Digits after the decimal point in the displayed number. Defaults to 0 for integer fields.
    zero_text: Optional[str]
        If set, the text shown in place of the number when the value is 0, such as 'none' or 'Off'.
    page_step: Optional[int | float]
        Change made by Page Up and Page Down. Defaults to ten steps.
    parent: Optional[QWidget]
        Optional parent widget.
    """

    valueChanged = Signal(object)
    dragStarted = Signal()
    dragFinished = Signal()
    pressureLinkToggled = Signal(bool)

    def __init__(self, label: str, value: int | float = 0, minimum: Optional[int | float] = None,
                 maximum: Optional[int | float] = None, step: int | float = 1, suffix: str = '',
                 display_scale: float = 1.0, decimals: Optional[int] = None, zero_text: Optional[str] = None,
                 page_step: Optional[int | float] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        if step <= 0:
            raise ValueError(f'step must be positive, got {step}')
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError(f'minimum {minimum} is greater than maximum {maximum}')
        self._integer = all(isinstance(number, int) for number in (value, step, minimum, maximum) if number is not None)
        self._label = label
        self._minimum = minimum
        self._maximum = maximum
        self._step = step
        self._page_step = page_step if page_step is not None else step * DEFAULT_PAGE_STEPS
        self._suffix = suffix
        self._display_scale = display_scale
        self._decimals = decimals if decimals is not None else (0 if self._integer else 2)
        self._zero_text = zero_text
        self._value: int | float = self._snap(self._clamp(value))

        self._pressure_available = False
        self._pressure_enabled = False
        self._pressure_tooltip = PRESSURE_LINK_TOOLTIP
        self._hovered = False
        self._keyboard_focus = False
        self._press_pos: Optional[QPoint] = None
        self._press_value: int | float = self._value
        self._scrubbing = False
        self._editor: Optional[QLineEdit] = None
        self._colors = _FieldColors(self)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(FIELD_HEIGHT)
        self.setMinimumWidth(MIN_WIDTH)
        self.setMaximumWidth(MAX_WIDTH)
        self.setAccessibleName(label)
        self._update_accessible_description()

    # -----------------------------------------------------------------------------------------------------------------
    # Value and display
    # -----------------------------------------------------------------------------------------------------------------

    def value(self) -> int | float:
        """Returns the stored value, an int for integer fields."""
        return self._value

    def set_value(self, value: int | float) -> None:
        """Sets the value, clamped to the range and snapped to the step. Emits `valueChanged` if it changed."""
        new_value = self._snap(self._clamp(value))
        if new_value == self._value:
            return
        self._value = new_value
        self._value_changed()
        self.valueChanged.emit(new_value)

    def minimum(self) -> Optional[int | float]:
        """Returns the smallest accepted value, or None if there is none."""
        return self._minimum

    def maximum(self) -> Optional[int | float]:
        """Returns the largest accepted value, or None if there is none."""
        return self._maximum

    def set_range(self, minimum: Optional[int | float], maximum: Optional[int | float]) -> None:
        """Sets the accepted range, re-clamping the value."""
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError(f'minimum {minimum} is greater than maximum {maximum}')
        self._minimum = minimum
        self._maximum = maximum
        self.set_value(self._value)
        self._value_changed()

    def step(self) -> int | float:
        """Returns the change made by one arrow key press or wheel notch."""
        return self._step

    def label(self) -> str:
        """Returns the label text."""
        return self._label

    def set_label(self, label: str) -> None:
        """Changes the label text."""
        self._label = label
        self.setAccessibleName(label)
        self.update()

    def value_text(self, value: Optional[int | float] = None) -> str:
        """Returns the text shown for a value (the current value by default), including the suffix."""
        if value is None:
            value = self._value
        if value == 0 and self._zero_text is not None:
            return self._zero_text
        shown = value * self._display_scale
        number = f'{shown:.{self._decimals}f}'
        if '.' in number and self._decimals > 0:
            number = number.rstrip('0').rstrip('.')
        if number in ('-0', ''):
            number = '0'
        return f'{number}{self._suffix}'

    def _clamp(self, value: int | float) -> int | float:
        if self._minimum is not None and value < self._minimum:
            value = self._minimum
        if self._maximum is not None and value > self._maximum:
            value = self._maximum
        return value

    def _snap(self, value: int | float) -> int | float:
        """Rounds a value to the step grid, which starts at the minimum if there is one, otherwise at 0."""
        origin = self._minimum if self._minimum is not None else 0
        steps = round((value - origin) / self._step)
        snapped = origin + steps * self._step
        if self._integer:
            return int(round(snapped))
        digits = max(self._decimals + 2, 6)
        snapped = round(float(snapped), digits)
        return float(self._clamp(snapped))

    def _step_by(self, amount: int | float) -> None:
        self.set_value(self._value + amount)

    def _value_changed(self) -> None:
        self._update_accessible_description()
        self.update()

    def _update_accessible_description(self) -> None:
        description = self.value_text()
        if self._minimum is not None and self._maximum is not None:
            description += f' ({self.value_text(self._minimum)} - {self.value_text(self._maximum)})'
        self.setAccessibleDescription(description)

    # -----------------------------------------------------------------------------------------------------------------
    # Pen pressure link
    # -----------------------------------------------------------------------------------------------------------------

    def set_pressure_link_available(self, available: bool) -> None:
        """Shows or hides the pen pressure link at the right end. Its space is part of the field, so showing it does
        not change the field's size."""
        if available != self._pressure_available:
            self._pressure_available = available
            self.update()

    def pressure_link_available(self) -> bool:
        """Returns whether the pen pressure link is shown."""
        return self._pressure_available

    def set_pressure_link_enabled(self, enabled: bool) -> None:
        """Lights or dims the pen pressure link. Emits `pressureLinkToggled` if it changed."""
        if enabled != self._pressure_enabled:
            self._pressure_enabled = enabled
            self.update()
            self.pressureLinkToggled.emit(enabled)

    def pressure_link_enabled(self) -> bool:
        """Returns whether pen pressure drives the value."""
        return self._pressure_enabled

    def set_pressure_link_tooltip(self, tooltip: str) -> None:
        """Sets the tooltip shown over the pressure link."""
        self._pressure_tooltip = tooltip

    def _pressure_link_rect(self) -> QRect:
        if not self._pressure_available:
            return QRect()
        return QRect(self.width() - PRESSURE_LINK_WIDTH, 0, PRESSURE_LINK_WIDTH, self.height())

    # -----------------------------------------------------------------------------------------------------------------
    # Sizing and painting
    # -----------------------------------------------------------------------------------------------------------------

    def sizeHint(self) -> QSize:
        """Returns the preferred size."""
        return QSize(PREFERRED_WIDTH, FIELD_HEIGHT)

    def minimumSizeHint(self) -> QSize:
        """Returns the smallest size that shows the value."""
        return QSize(MIN_WIDTH, FIELD_HEIGHT)

    def _fill_fraction(self) -> Optional[float]:
        """Returns how much of the field the fill covers, or None to draw no fill. Subclasses with a fill override."""
        return None

    def _text_rect(self) -> QRect:
        return self.rect().adjusted(TEXT_MARGIN, 0, -TEXT_MARGIN - (PRESSURE_LINK_WIDTH if self._pressure_available
                                                                     else 0), 0)

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the field box, fill, label, value and pressure link."""
        colors = self._colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        box = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colors.background)
        painter.drawRoundedRect(box, RADIUS, RADIUS)
        fraction = self._fill_fraction()  # pylint: disable=assignment-from-none  # SliderField overrides it
        if fraction is not None and fraction > 0:
            painter.save()
            clip = QRectF(box)
            clip.setWidth(box.width() * fraction)
            painter.setClipRect(clip)
            painter.setBrush(colors.fill)
            painter.drawRoundedRect(box, RADIUS, RADIUS)
            painter.restore()
        editing = self._editor is not None
        outline = colors.hover_outline if (self._hovered or self._scrubbing) and self.isEnabled() else colors.outline
        if editing:
            outline = colors.focus
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(outline, 1))
        painter.drawRoundedRect(box, RADIUS, RADIUS)
        if self._keyboard_focus and not editing:
            painter.setPen(QPen(colors.focus, 1))
            painter.drawRoundedRect(box.adjusted(1, 1, -1, -1), max(RADIUS - 1, 0), max(RADIUS - 1, 0))
            painter.drawRoundedRect(box, RADIUS, RADIUS)
        painter.setFont(colors.font)
        if not editing:
            self._paint_text(painter)
        if self._pressure_available:
            self._paint_pressure_link(painter)
        painter.end()

    def _paint_text(self, painter: QPainter) -> None:
        colors = self._colors
        metrics = QFontMetrics(colors.font)
        text_rect = self._text_rect()
        value_text = metrics.elidedText(self.value_text(), Qt.TextElideMode.ElideRight, text_rect.width())
        value_width = metrics.horizontalAdvance(value_text)
        painter.setPen(colors.text)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, value_text)
        label_width = text_rect.width() - value_width - TEXT_MARGIN
        if label_width > 0 and self._label != '':
            label_text = metrics.elidedText(self._label, Qt.TextElideMode.ElideRight, label_width)
            painter.setPen(colors.label)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label_text)

    def _paint_pressure_link(self, painter: QPainter) -> None:
        colors = self._colors
        link_rect = self._pressure_link_rect()
        center = QPointF(link_rect.center()) + QPointF(0.5, 0.5)
        painter.setPen(QPen(colors.outline, 1))
        painter.drawLine(QPointF(link_rect.left() + 0.5, 4.0), QPointF(link_rect.left() + 0.5, self.height() - 4.0))
        if self._pressure_enabled:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colors.accent)
        else:
            painter.setPen(QPen(colors.label, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, PRESSURE_DOT_RADIUS, PRESSURE_DOT_RADIUS)

    def changeEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """Rebuilds the cached colors and font when the palette, font or enabled state changes."""
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.FontChange, QEvent.Type.EnabledChange,
                            QEvent.Type.StyleChange):
            self._colors = _FieldColors(self)
            self.update()
        super().changeEvent(event)

    # -----------------------------------------------------------------------------------------------------------------
    # Mouse
    # -----------------------------------------------------------------------------------------------------------------

    def event(self, event: QEvent) -> bool:
        """Tracks hover, and shows the pressure link's tooltip over the link."""
        if event.type() == QEvent.Type.HoverEnter:
            self._hovered = True
            self.update()
        elif event.type() == QEvent.Type.HoverLeave:
            self._hovered = False
            self.update()
        elif event.type() == QEvent.Type.ToolTip and isinstance(event, QHelpEvent) and self._pressure_available \
                and self._pressure_link_rect().contains(event.pos()):
            QToolTip.showText(event.globalPos(), self._pressure_tooltip, self)
            return True
        return super().event(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """Starts a possible drag. A press on the pressure link toggles it instead."""
        if event.button() != Qt.MouseButton.LeftButton or self._editor is not None:
            event.ignore()
            return
        if self._pressure_available and self._pressure_link_rect().contains(event.position().toPoint()):
            self.set_pressure_link_enabled(not self._pressure_enabled)
            event.accept()
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self._press_pos = event.position().toPoint()
        self._press_value = self._value
        self._scrubbing = False
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """Scrubs the value once the pointer moves past the drag threshold."""
        if self._press_pos is None:
            return
        delta_x = event.position().toPoint().x() - self._press_pos.x()
        if not self._scrubbing:
            if abs(delta_x) < QApplication.startDragDistance():
                return
            self._scrubbing = True
            self.dragStarted.emit()
        self.set_value(self._press_value + self._scrub_delta(delta_x))
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """Ends a drag, or opens the text entry if the press wasn't a drag."""
        if event.button() != Qt.MouseButton.LeftButton or self._press_pos is None:
            return
        was_scrubbing = self._scrubbing
        self._press_pos = None
        self._scrubbing = False
        if was_scrubbing:
            self.update()
            self.dragFinished.emit()
        else:
            self.begin_edit()
        event.accept()

    def _scrub_delta(self, delta_x: int) -> int | float:
        """Returns the value change for a horizontal drag distance in pixels. Subclasses with a finite range override
        this to scale by the field's width."""
        return delta_x / PIXELS_PER_STEP * self._step

    # -----------------------------------------------------------------------------------------------------------------
    # Wheel and keys
    # -----------------------------------------------------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:  # pylint: disable=invalid-name
        """Steps the value by one step per wheel notch."""
        notches = event.angleDelta().y() / 120
        if notches == 0 or self._editor is not None:
            event.ignore()
            return
        self._step_by(notches * self._step)
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # pylint: disable=invalid-name
        """Steps the value with arrow and page keys, jumps to the limits with Home and End, opens the text entry
        with Enter, Return or F2, and toggles the pressure link with Space."""
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Down):
            self._step_by(-self._step)
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Up):
            self._step_by(self._step)
        elif key == Qt.Key.Key_PageDown:
            self._step_by(-self._page_step)
        elif key == Qt.Key.Key_PageUp:
            self._step_by(self._page_step)
        elif key == Qt.Key.Key_Home and self._minimum is not None:
            self.set_value(self._minimum)
        elif key == Qt.Key.Key_End and self._maximum is not None:
            self.set_value(self._maximum)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_F2):
            self.begin_edit()
        elif key == Qt.Key.Key_Space and self._pressure_available:
            self.set_pressure_link_enabled(not self._pressure_enabled)
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def focusInEvent(self, event: QFocusEvent) -> None:  # pylint: disable=invalid-name
        """Shows the focus ring when focus arrived by keyboard."""
        self._keyboard_focus = event.reason() != Qt.FocusReason.MouseFocusReason
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # pylint: disable=invalid-name
        """Hides the focus ring."""
        self._keyboard_focus = False
        self.update()
        super().focusOutEvent(event)

    # -----------------------------------------------------------------------------------------------------------------
    # Text entry
    # -----------------------------------------------------------------------------------------------------------------

    def editing(self) -> bool:
        """Returns whether the text entry is open."""
        return self._editor is not None

    def begin_edit(self) -> None:
        """Opens the text entry over the field, with the current value selected."""
        if self._editor is not None or not self.isEnabled():
            return
        editor = QLineEdit(self)
        editor.setFrame(False)
        editor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        editor.setAccessibleName(self._label)
        palette = editor.palette()
        palette.setColor(QPalette.ColorRole.Base, self._colors.background)
        editor.setPalette(palette)
        text = self.value_text()
        if self._zero_text is not None and self._value == 0:
            text = f'0{self._suffix}'
        editor.setText(text)
        editor.setGeometry(self._editor_rect())
        editor.editingFinished.connect(self._finish_edit)
        editor.installEventFilter(self)
        self._editor = editor
        editor.show()
        editor.setFocus(Qt.FocusReason.OtherFocusReason)
        editor.selectAll()
        self.update()

    def eventFilter(self, watched: object, event: QEvent) -> bool:  # pylint: disable=invalid-name
        """Cancels the text entry on Escape."""
        if watched is self._editor and event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent) \
                and event.key() == Qt.Key.Key_Escape:
            self.cancel_edit()
            return True
        return super().eventFilter(watched, event)  # type: ignore[arg-type]

    def cancel_edit(self) -> None:
        """Closes the text entry without changing the value."""
        self._close_editor(None)

    def commit_edit(self) -> None:
        """Closes the text entry, applying the typed value if it parses."""
        if self._editor is not None:
            self._finish_edit()

    def _finish_edit(self) -> None:
        if self._editor is not None:
            self._close_editor(self._editor.text())

    def _close_editor(self, text: Optional[str]) -> None:
        editor = self._editor
        if editor is None:
            return
        self._editor = None
        editor.removeEventFilter(self)
        had_focus = editor.hasFocus()
        editor.blockSignals(True)
        editor.hide()
        editor.setParent(None)  # type: ignore[call-overload]
        editor.deleteLater()
        if had_focus:
            self.setFocus(Qt.FocusReason.OtherFocusReason)
        if text is not None:
            typed = self.parse_text(text)
            if typed is not None:
                self.set_value(typed)
        self.update()

    def parse_text(self, text: str) -> Optional[int | float]:
        """Returns the stored value a typed string means, or None if it isn't a number. The suffix is optional."""
        text = text.strip()
        suffix = self._suffix.strip()
        if suffix != '' and text.endswith(suffix):
            text = text[:-len(suffix)].strip()
        if self._zero_text is not None and text.lower() == self._zero_text.lower():
            return 0
        try:
            shown = float(text)
        except ValueError:
            return None
        if not math.isfinite(shown) or self._display_scale == 0:
            return None
        return shown / self._display_scale

    def resizeEvent(self, event: QResizeEvent) -> None:  # pylint: disable=invalid-name
        """Keeps the text entry over the field."""
        super().resizeEvent(event)
        if self._editor is not None:
            self._editor.setGeometry(self._editor_rect())

    def _editor_rect(self) -> QRect:
        return self.rect().adjusted(2, 2, -2 - (PRESSURE_LINK_WIDTH if self._pressure_available else 0), -2)
