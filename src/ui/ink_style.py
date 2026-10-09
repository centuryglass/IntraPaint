"""Draws the IntraPaint Ink theme's controls: ink outlines, flat fills, and sticker-style primary actions.

`InkStyle` wraps a base Qt style (Fusion by default) and redraws the controls the Ink design changes. Text, icons and
every control it doesn't override come from the base style. Colors come from the palette the control is drawn with,
plus the few `InkColors` that have no QPalette role, so a palette change restyles every control.

Only push buttons marked with `set_primary_button` get the raised accent "sticker" look, and only those marked with
`set_signal` get it in the signal color. Check boxes, radio buttons and slider handles use a smaller version of the
same raised shadow, and `set_signal` also switches a check box to the signal color.
"""
from dataclasses import dataclass, fields
from typing import Optional

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPalette, QPen, QPolygonF
from PySide6.QtWidgets import (QAbstractItemView, QAbstractSpinBox, QApplication, QCheckBox, QPlainTextEdit,
                               QProxyStyle, QPushButton, QSlider, QStyle, QStyleOption, QStyleOptionButton,
                               QStyleOptionComboBox, QStyleOptionMenuItem, QStyleOptionProgressBar,
                               QStyleOptionSlider, QStyleOptionSpinBox, QStyleOptionTab, QStyleOptionViewItem,
                               QTabBar, QTextEdit, QWidget)

State = QStyle.StateFlag
Primitive = QStyle.PrimitiveElement
Control = QStyle.ControlElement
Complex = QStyle.ComplexControl
SubControl = QStyle.SubControl
Metric = QStyle.PixelMetric
Role = QPalette.ColorRole
Group = QPalette.ColorGroup

PRIMARY_BUTTON_PROPERTY = 'ink_primary'
SIGNAL_PROPERTY = 'ink_signal'

RADIUS = 4.0
STICKER_OFFSET = 3
SMALL_STICKER_OFFSET = 2
INDICATOR_SIZE = 15
SLIDER_GROOVE_THICKNESS = 6
SLIDER_HANDLE_LENGTH = 12
SLIDER_HANDLE_THICKNESS = 16
SLIDER_TICK_LENGTH = 3
SLIDER_TICK_GAP = 6
OVERLAY_SCROLL_BAR_WIDTH = 6
OVERLAY_SCROLL_BAR_HOVER_WIDTH = 9
OVERLAY_SCROLL_BAR_MARGIN = 2
CLASSIC_SCROLL_BAR_EXTENT = 14
CLASSIC_SCROLL_HANDLE_INSET = 3
CHEVRON_WIDTH = 8.0
CHEVRON_HEIGHT = 4.5

# Translucent shading drawn over palette colors:
BEVEL_HIGHLIGHT = QColor(255, 255, 255, 0x12)
SUNKEN_SHADE = QColor(0, 0, 0, 0x55)
FIELD_SHADE = QColor(0, 0, 0, 0x66)
ROW_HOVER = QColor(255, 255, 255, 0x08)
SCROLL_HANDLE = QColor(255, 255, 255, 0x38)
SCROLL_HANDLE_HOVER = QColor(255, 255, 255, 0x5a)
CLASSIC_SCROLL_HANDLE = QColor(255, 255, 255, 0x40)
OVERLAY_SCROLL_HANDLE_OUTLINE = QColor(0, 0, 0, 0x60)
STRIPE_WIDTH = 6

# Unselected tab labels mix this much of the window color into the text color:
DIM_TEXT_WINDOW_FRACTION = 0.4


@dataclass(frozen=True)
class InkColors:
    """Ink theme colors that have no QPalette role, from the theme file's `style_colors`."""
    accent_hover: QColor
    accent_pressed: QColor
    accent_wash: QColor
    accent_stripe: QColor
    field_hover: QColor
    disabled_outline: QColor
    signal: QColor
    signal_hover: QColor
    signal_pressed: QColor
    canvas_surround: QColor

    @staticmethod
    def from_theme_data(color_data: dict[str, str]) -> 'InkColors':
        """Parses the theme file's `style_colors` section.

        Raises
        ------
        ValueError
            If a color is missing, or doesn't parse.
        """
        colors = {}
        for name in (field.name for field in fields(InkColors)):
            if name not in color_data:
                raise ValueError(f'Missing Ink style color "{name}"')
            color = QColor(color_data[name])
            if not color.isValid():
                raise ValueError(f'Invalid color "{color_data[name]}" for Ink style color {name}')
            colors[name] = color
        return InkColors(**colors)


def set_primary_button(button: QPushButton) -> None:
    """Marks a push button as its panel's primary action, which InkStyle draws as a raised accent sticker."""
    button.setProperty(PRIMARY_BUTTON_PROPERTY, True)


def set_signal(widget: QWidget) -> None:
    """Marks a push button or check box as risky, which InkStyle draws in the signal color.

    A push button becomes a raised sticker like a primary button, and a check box fills its checked indicator. Use it
    for actions that discard work, and for options that restrict where changes apply. Other styles ignore the mark.
    """
    widget.setProperty(SIGNAL_PROPERTY, True)


def ink_colors() -> Optional[InkColors]:
    """Returns the Ink colors with no QPalette role if the application style is InkStyle, or None for other styles."""
    style = QApplication.style()
    return style.colors if isinstance(style, InkStyle) else None


def signal_color() -> Optional[QColor]:
    """Returns the signal color if the application style is InkStyle, or None if it has no signal color."""
    colors = ink_colors()
    return None if colors is None else colors.signal


def _is_primary(widget: Optional[QWidget]) -> bool:
    return isinstance(widget, QPushButton) and bool(widget.property(PRIMARY_BUTTON_PROPERTY))


def _is_signal(widget: Optional[QWidget]) -> bool:
    return isinstance(widget, (QPushButton, QCheckBox)) and bool(widget.property(SIGNAL_PROPERTY))


def _is_sticker(widget: Optional[QWidget]) -> bool:
    """Whether a push button is drawn as a raised sticker, which makes it taller and its label bolder."""
    return isinstance(widget, QPushButton) and (_is_primary(widget) or _is_signal(widget))


def _keyboard_focus(option: QStyleOption) -> bool:
    """Whether a control shows a focus ring: it has focus, and focus last moved by keyboard."""
    return bool(option.state & State.State_HasFocus) and bool(option.state & State.State_KeyboardFocusChange)


def _mix(color: QColor, other: QColor, other_fraction: float) -> QColor:
    return QColor.fromRgbF(color.redF() + (other.redF() - color.redF()) * other_fraction,
                           color.greenF() + (other.greenF() - color.greenF()) * other_fraction,
                           color.blueF() + (other.blueF() - color.blueF()) * other_fraction)


def _line_rect(rect: QRect | QRectF) -> QRectF:
    """Returns the rectangle a 1px pen follows to stay inside `rect`."""
    return QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)


def _draw_box(painter: QPainter, rect: QRect | QRectF, fill: Optional[QColor | QBrush], outline: Optional[QColor],
              radius: float = RADIUS) -> None:
    """Draws a rounded rectangle inside `rect`, with an optional 1px outline."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(outline, 1) if outline is not None else Qt.PenStyle.NoPen)
    painter.setBrush(fill if fill is not None else Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(_line_rect(rect), radius, radius)
    painter.restore()


def _draw_inset_line(painter: QPainter, rect: QRect, color: QColor, radius: float = RADIUS) -> None:
    """Draws a 1px line just inside the top outline of a rounded box."""
    painter.save()
    painter.setPen(QPen(color, 1))
    y = rect.y() + 1.5
    painter.drawLine(QPointF(rect.x() + radius, y), QPointF(rect.x() + rect.width() - radius, y))
    painter.restore()


def _draw_focus_ring(painter: QPainter, rect: QRect, color: QColor, radius: float = RADIUS) -> None:
    """Draws a 2px ring just inside `rect`."""
    _draw_box(painter, rect, None, color, radius)
    _draw_box(painter, rect.adjusted(1, 1, -1, -1), None, color, max(radius - 1, 0.0))


def _draw_chevron(painter: QPainter, center: QPointF, color: QColor, pointing_down: bool) -> None:
    half_width = CHEVRON_WIDTH / 2
    half_height = CHEVRON_HEIGHT / 2
    direction = 1 if pointing_down else -1
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color, 1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawPolyline(QPolygonF([QPointF(center.x() - half_width, center.y() - half_height * direction),
                                    QPointF(center.x(), center.y() + half_height * direction),
                                    QPointF(center.x() + half_width, center.y() - half_height * direction)]))
    painter.restore()


class InkStyle(QProxyStyle):
    """Draws controls in the IntraPaint Ink look, on top of a base Qt style.

    Parameters
    ----------
    base_style_name: str
        Name of the Qt style to draw everything else with, as QStyleFactory knows it.
    colors: InkColors
        Theme colors with no QPalette role.
    overlay_scroll_bars: bool
        If true, scroll bars are thin handles drawn over their scroll area's content, which grow when hovered. If
        false, they take their own space beside the content, with a track.
    """

    # The QStyle overrides keep Qt's camelCase method names:
    # pylint: disable=invalid-name

    def __init__(self, base_style_name: str, colors: InkColors, overlay_scroll_bars: bool = True) -> None:
        super().__init__(base_style_name)
        self._colors = colors
        self._overlay_scroll_bars = overlay_scroll_bars

    @property
    def colors(self) -> InkColors:
        """The theme colors with no QPalette role."""
        return self._colors

    @property
    def overlay_scroll_bars(self) -> bool:
        """Whether scroll bars are drawn over their scroll area's content."""
        return self._overlay_scroll_bars

    # -----------------------------------------------------------------------------------------------------------------
    # Metrics and hints
    # -----------------------------------------------------------------------------------------------------------------

    def pixelMetric(self, metric: Metric, option: Optional[QStyleOption] = None,
                    widget: Optional[QWidget] = None) -> int:
        """Sizes indicators, slider handles and scroll bars for the Ink look."""
        if metric in (Metric.PM_IndicatorWidth, Metric.PM_ExclusiveIndicatorWidth):
            return INDICATOR_SIZE
        if metric in (Metric.PM_IndicatorHeight, Metric.PM_ExclusiveIndicatorHeight):
            return INDICATOR_SIZE + SMALL_STICKER_OFFSET
        if metric == Metric.PM_SliderLength:
            return SLIDER_HANDLE_LENGTH
        if metric in (Metric.PM_SliderThickness, Metric.PM_SliderControlThickness):
            return SLIDER_HANDLE_THICKNESS + SMALL_STICKER_OFFSET
        if metric == Metric.PM_ScrollBarExtent:
            if self._overlay_scroll_bars:
                return OVERLAY_SCROLL_BAR_HOVER_WIDTH + OVERLAY_SCROLL_BAR_MARGIN
            return CLASSIC_SCROLL_BAR_EXTENT
        return super().pixelMetric(metric, option, widget)

    def styleHint(self, hint: QStyle.StyleHint, option: Optional[QStyleOption] = None,
                  widget: Optional[QWidget] = None, return_data: Optional[object] = None) -> int:
        """Makes scroll bars overlay their content when overlay_scroll_bars is set."""
        if hint == QStyle.StyleHint.SH_ScrollBar_Transient:
            return int(self._overlay_scroll_bars)
        return super().styleHint(hint, option, widget, return_data)

    def sizeFromContents(self, content_type: QStyle.ContentsType, option: Optional[QStyleOption],
                         contents_size: QSize, widget: Optional[QWidget] = None) -> QSize:
        """Makes room for a sticker button's raised offset and bolder label."""
        size = super().sizeFromContents(content_type, option, contents_size, widget)
        if (content_type == QStyle.ContentsType.CT_PushButton and _is_sticker(widget)
                and isinstance(option, QStyleOptionButton)):
            assert widget is not None
            bold_metrics = QFontMetrics(self._primary_font(widget.font()))
            extra_width = bold_metrics.horizontalAdvance(option.text) - option.fontMetrics.horizontalAdvance(
                option.text)
            size += QSize(max(extra_width, 0), STICKER_OFFSET)
        return size

    def subControlRect(self, control: Complex, option: QStyleOption, sub_control: SubControl,
                       widget: Optional[QWidget] = None) -> QRect:
        """Removes scroll bar arrow buttons, and sizes slider handles to include their raised offset."""
        if control == Complex.CC_ScrollBar and isinstance(option, QStyleOptionSlider):
            return self._scroll_bar_rect(option, sub_control)
        rect = super().subControlRect(control, option, sub_control, widget)
        if (control == Complex.CC_Slider and sub_control == SubControl.SC_SliderHandle
                and isinstance(option, QStyleOptionSlider)):
            center = rect.center()
            if option.orientation == Qt.Orientation.Horizontal:
                size = QSize(SLIDER_HANDLE_LENGTH, SLIDER_HANDLE_THICKNESS)
            else:
                size = QSize(SLIDER_HANDLE_THICKNESS, SLIDER_HANDLE_LENGTH)
            rect = QRect(center.x() - size.width() // 2 + 1, center.y() - size.height() // 2 + 1, size.width(),
                         size.height() + SMALL_STICKER_OFFSET)
        return rect

    def _scroll_bar_rect(self, option: QStyleOptionSlider, sub_control: SubControl) -> QRect:
        """Places scroll bar parts with no arrow buttons: the groove is the whole bar."""
        rect = QRect(option.rect)
        horizontal = option.orientation == Qt.Orientation.Horizontal
        length = rect.width() if horizontal else rect.height()
        value_range = option.maximum - option.minimum
        if value_range <= 0:
            slider_length = length
        else:
            slider_length = int(length * option.pageStep / (value_range + option.pageStep))
            slider_length = max(slider_length, self.pixelMetric(Metric.PM_ScrollBarSliderMin, option))
            slider_length = min(slider_length, length)
        slider_start = QStyle.sliderPositionFromValue(option.minimum, option.maximum, option.sliderPosition,
                                                      length - slider_length, option.upsideDown)

        def _span(start: int, span_length: int) -> QRect:
            if horizontal:
                return QRect(rect.x() + start, rect.y(), span_length, rect.height())
            return QRect(rect.x(), rect.y() + start, rect.width(), span_length)

        if sub_control == SubControl.SC_ScrollBarGroove:
            result = QRect(rect)
        elif sub_control == SubControl.SC_ScrollBarSlider:
            result = _span(slider_start, slider_length)
        elif sub_control == SubControl.SC_ScrollBarSubPage:
            result = _span(0, slider_start)
        elif sub_control == SubControl.SC_ScrollBarAddPage:
            result = _span(slider_start + slider_length, length - slider_start - slider_length)
        else:
            result = QRect()
        return QStyle.visualRect(option.direction, option.rect, result)

    # -----------------------------------------------------------------------------------------------------------------
    # Primitives
    # -----------------------------------------------------------------------------------------------------------------

    def drawPrimitive(self, element: Primitive, option: QStyleOption, painter: QPainter,
                      widget: Optional[QWidget] = None) -> None:
        """Draws button panels, fields, indicators, menus, tooltips and item view rows."""
        if element in (Primitive.PE_PanelButtonCommand, Primitive.PE_PanelButtonTool,
                       Primitive.PE_IndicatorButtonDropDown):
            self._draw_bevel(painter, option)
        elif element in (Primitive.PE_FrameDefaultButton, Primitive.PE_FrameButtonTool):
            return
        elif element == Primitive.PE_FrameFocusRect:
            # Ink controls draw their own focus rings. Item views keep the base style's current-item frame:
            if isinstance(widget, QAbstractItemView):
                super().drawPrimitive(element, option, painter, widget)
        elif element == Primitive.PE_Frame and isinstance(widget, (QTextEdit, QPlainTextEdit)):
            self._draw_text_area_frame(painter, option)
        elif element == Primitive.PE_PanelLineEdit:
            self._draw_line_edit(painter, option)
        elif element == Primitive.PE_FrameLineEdit:
            self._draw_field(painter, option, option.rect, fill=False)
        elif element == Primitive.PE_IndicatorCheckBox:
            self._draw_indicator(painter, option, round_indicator=False, signal=_is_signal(widget))
        elif element == Primitive.PE_IndicatorRadioButton:
            self._draw_indicator(painter, option, round_indicator=True)
        elif element == Primitive.PE_PanelTipLabel:
            painter.fillRect(option.rect, option.palette.toolTipBase())
            _draw_box(painter, option.rect, None, option.palette.color(Role.Mid), 0)
        elif element == Primitive.PE_PanelMenu:
            painter.fillRect(option.rect, option.palette.window())
            _draw_box(painter, option.rect, None, option.palette.color(Role.Shadow), 0)
        elif element == Primitive.PE_FrameMenu:
            _draw_box(painter, option.rect, None, option.palette.color(Role.Shadow), 0)
        elif element == Primitive.PE_PanelItemViewItem and isinstance(option, QStyleOptionViewItem):
            self._draw_item_view_row(painter, option)
        else:
            super().drawPrimitive(element, option, painter, widget)

    def _draw_bevel(self, painter: QPainter, option: QStyleOption) -> None:
        """Draws a button panel: a flat fill in an ink outline, lit along the top edge unless pressed or checked."""
        palette = option.palette
        rect = option.rect
        if not option.state & State.State_Enabled:
            _draw_box(painter, rect, palette.color(Group.Disabled, Role.Button), self._colors.disabled_outline)
            return
        pressed = bool(option.state & State.State_Sunken)
        checked = bool(option.state & State.State_On)
        if pressed:
            fill = palette.color(Role.AlternateBase)
        elif checked:
            fill = self._colors.accent_wash
        elif option.state & State.State_MouseOver:
            fill = palette.color(Role.Midlight)
        else:
            fill = palette.color(Role.Button)
        is_default = (isinstance(option, QStyleOptionButton)
                      and bool(option.features & QStyleOptionButton.ButtonFeature.DefaultButton))
        outline = palette.color(Role.Highlight) if is_default else palette.color(Role.Shadow)
        _draw_box(painter, rect, fill, outline)
        _draw_inset_line(painter, rect, SUNKEN_SHADE if (pressed or checked) else BEVEL_HIGHLIGHT)
        if _keyboard_focus(option):
            _draw_focus_ring(painter, rect, palette.color(Role.Highlight))

    def _draw_field(self, painter: QPainter, option: QStyleOption, rect: QRect, fill: bool = True) -> None:
        """Draws a text field box: a sunken base fill in an ink outline, which turns accent with focus."""
        palette = option.palette
        if not option.state & State.State_Enabled:
            _draw_box(painter, rect, palette.color(Group.Disabled, Role.Base) if fill else None,
                      self._colors.disabled_outline)
            return
        hovered = bool(option.state & State.State_MouseOver) and not option.state & State.State_ReadOnly
        fill_color: Optional[QColor] = None
        if fill:
            fill_color = self._colors.field_hover if hovered else palette.color(Role.Base)
        _draw_box(painter, rect, fill_color, palette.color(Role.Shadow))
        _draw_inset_line(painter, rect, FIELD_SHADE)
        if option.state & State.State_HasFocus:
            _draw_focus_ring(painter, rect, palette.color(Role.Highlight))

    def _draw_text_area_frame(self, painter: QPainter, option: QStyleOption) -> None:
        """Outlines a multi-line text field in ink, or accent while it has focus. Its viewport paints the fill."""
        palette = option.palette
        if not option.state & State.State_Enabled:
            outline = self._colors.disabled_outline
        elif option.state & State.State_HasFocus:
            outline = palette.color(Role.Highlight)
        else:
            outline = palette.color(Role.Shadow)
        _draw_box(painter, option.rect, None, outline, 0)

    def _draw_line_edit(self, painter: QPainter, option: QStyleOption) -> None:
        line_width = getattr(option, 'lineWidth', 1)
        if line_width > 0:
            self._draw_field(painter, option, option.rect)
        else:
            painter.fillRect(option.rect, option.palette.base())

    def _draw_indicator(self, painter: QPainter, option: QStyleOption, round_indicator: bool,
                        signal: bool = False) -> None:
        """Draws a check box or radio button indicator, raised on an ink shadow and filled with accent (or the signal
        color) when on."""
        palette = option.palette
        rect = option.rect
        size = min(rect.width(), rect.height() - SMALL_STICKER_OFFSET)
        box = QRect(rect.x() + (rect.width() - size) // 2, rect.y(), size, size)
        radius = size / 2 if round_indicator else 3.0
        enabled = bool(option.state & State.State_Enabled)
        marked = bool(option.state & (State.State_On | State.State_NoChange))
        if not enabled:
            _draw_box(painter, box, palette.color(Group.Disabled, Role.Base), self._colors.disabled_outline, radius)
            mark_color = palette.color(Group.Disabled, Role.Text)
        elif marked:
            ink = palette.color(Role.Shadow)
            _draw_box(painter, box.translated(0, SMALL_STICKER_OFFSET), ink, ink, radius)
            _draw_box(painter, box, self._colors.signal if signal else palette.color(Role.Highlight), ink, radius)
            mark_color = palette.color(Role.HighlightedText)
        else:
            fill = self._colors.field_hover if option.state & State.State_MouseOver else palette.color(Role.Base)
            _draw_box(painter, box, fill, palette.color(Role.Shadow), radius)
            if not round_indicator:
                _draw_inset_line(painter, box, FIELD_SHADE, radius)
            mark_color = palette.color(Role.HighlightedText)
        if enabled and _keyboard_focus(option):
            _draw_box(painter, box, None, palette.color(Role.Highlight), radius)
        if not marked:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QRectF(box).center()
        if round_indicator:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(mark_color)
            painter.drawEllipse(center, 2.5, 2.5)
        else:
            pen = QPen(mark_color, 2.2)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
            painter.setPen(pen)
            scale = size / INDICATOR_SIZE
            if option.state & State.State_NoChange:
                painter.drawLine(QPointF(center.x() - 4 * scale, center.y()), QPointF(center.x() + 4 * scale,
                                                                                      center.y()))
            else:
                painter.drawPolyline(QPolygonF([QPointF(center.x() - 4 * scale, center.y() - 0.5 * scale),
                                                QPointF(center.x() - 1.5 * scale, center.y() + 2 * scale),
                                                QPointF(center.x() + 4 * scale, center.y() - 3.5 * scale)]))
        painter.restore()

    def _draw_item_view_row(self, painter: QPainter, option: QStyleOptionViewItem) -> None:
        if option.features & QStyleOptionViewItem.ViewItemFeature.Alternate:
            painter.fillRect(option.rect, option.palette.alternateBase())
        if option.state & State.State_Selected:
            painter.fillRect(option.rect, self._colors.accent_wash)
        elif option.state & State.State_MouseOver and option.state & State.State_Enabled:
            painter.fillRect(option.rect, ROW_HOVER)

    # -----------------------------------------------------------------------------------------------------------------
    # Controls
    # -----------------------------------------------------------------------------------------------------------------

    def drawControl(self, element: Control, option: QStyleOption, painter: QPainter,
                    widget: Optional[QWidget] = None) -> None:
        """Draws sticker buttons, progress bars, tabs, menu items and item view text in the Ink look."""
        if element == Control.CE_PushButtonBevel and _is_sticker(widget):
            self._draw_sticker_bevel(painter, option, _is_signal(widget))
        elif element == Control.CE_PushButtonLabel and _is_sticker(widget) and isinstance(option,
                                                                                           QStyleOptionButton):
            assert widget is not None
            self._draw_sticker_label(painter, option, widget)
        elif element == Control.CE_ProgressBarGroove:
            self._draw_field(painter, option, option.rect)
        elif element == Control.CE_ProgressBarContents and isinstance(option, QStyleOptionProgressBar):
            self._draw_progress(painter, option, widget)
        elif element == Control.CE_TabBarTabShape and isinstance(option, QStyleOptionTab) \
                and option.shape == QTabBar.Shape.RoundedNorth:
            self._draw_tab_shape(painter, option)
        elif element == Control.CE_TabBarTabLabel and isinstance(option, QStyleOptionTab):
            # The tab shape draws the focus ring, and the base style would add a filled focus frame:
            label_option = QStyleOptionTab(option)
            label_option.state &= ~State.State_HasFocus
            if not option.state & State.State_Selected:
                palette = QPalette(option.palette)
                for group in (Group.Active, Group.Inactive):
                    palette.setColor(group, Role.WindowText, _mix(palette.color(group, Role.WindowText),
                                                                  palette.color(group, Role.Window),
                                                                  DIM_TEXT_WINDOW_FRACTION))
                label_option.palette = palette
            super().drawControl(element, label_option, painter, widget)
        elif element == Control.CE_MenuItem and isinstance(option, QStyleOptionMenuItem):
            self._draw_menu_item(painter, option, widget)
        elif element == Control.CE_MenuBarItem and isinstance(option, QStyleOptionMenuItem):
            self._draw_menu_bar_item(painter, option, widget)
        elif element == Control.CE_ItemViewItem and isinstance(option, QStyleOptionViewItem):
            # Selected rows have a dark accent wash behind them, so their text keeps the normal text color:
            row_option = QStyleOptionViewItem(option)
            palette = QPalette(option.palette)
            for group in (Group.Active, Group.Inactive, Group.Disabled):
                palette.setColor(group, Role.HighlightedText, palette.color(group, Role.Text))
            row_option.palette = palette
            super().drawControl(element, row_option, painter, widget)
        else:
            super().drawControl(element, option, painter, widget)

    @staticmethod
    def _primary_font(font: QFont) -> QFont:
        bold_font = QFont(font)
        bold_font.setWeight(QFont.Weight.DemiBold)
        return bold_font

    def _draw_sticker_bevel(self, painter: QPainter, option: QStyleOption, signal: bool) -> None:
        """Draws a button as a sticker on an ink shadow, in accent or signal color. Pressing it moves it onto its
        shadow."""
        palette = option.palette
        body = option.rect.adjusted(0, 0, 0, -STICKER_OFFSET)
        if not option.state & State.State_Enabled:
            _draw_box(painter, body, palette.color(Group.Disabled, Role.Button), self._colors.disabled_outline)
            return
        ink = palette.color(Role.Shadow)
        if option.state & State.State_Sunken:
            _draw_box(painter, body.translated(0, STICKER_OFFSET),
                      self._colors.signal_pressed if signal else self._colors.accent_pressed, ink)
            return
        _draw_box(painter, body.translated(0, STICKER_OFFSET), ink, ink)
        if signal:
            fill = self._colors.signal_hover if option.state & State.State_MouseOver else self._colors.signal
        else:
            fill = self._colors.accent_hover if option.state & State.State_MouseOver else palette.color(Role.Highlight)
        _draw_box(painter, body, fill, ink)
        if _keyboard_focus(option):
            _draw_focus_ring(painter, body, palette.color(Role.Text))

    def _draw_sticker_label(self, painter: QPainter, option: QStyleOptionButton, widget: QWidget) -> None:
        label_option = QStyleOptionButton(option)
        label_rect = option.rect.adjusted(0, 0, 0, -STICKER_OFFSET)
        if option.state & State.State_Sunken:
            label_rect.translate(0, STICKER_OFFSET)
        label_option.rect = label_rect
        palette = QPalette(option.palette)
        for group in (Group.Active, Group.Inactive):
            palette.setColor(group, Role.ButtonText, palette.color(group, Role.HighlightedText))
        label_option.palette = palette
        painter.save()
        painter.setFont(self._primary_font(widget.font()))
        label_option.fontMetrics = painter.fontMetrics()
        super().drawControl(Control.CE_PushButtonLabel, label_option, painter, widget)
        painter.restore()

    def _draw_progress(self, painter: QPainter, option: QStyleOptionProgressBar, widget: Optional[QWidget]) -> None:
        """Fills the done part of a horizontal progress bar with diagonal accent stripes."""
        if not option.state & State.State_Horizontal:
            super().drawControl(Control.CE_ProgressBarContents, option, painter, widget)
            return
        inner = QRectF(option.rect).adjusted(1, 1, -1, -1)
        value_range = option.maximum - option.minimum
        if value_range <= 0:
            fraction = 1.0
        else:
            fraction = min(max((option.progress - option.minimum) / value_range, 0.0), 1.0)
        if fraction <= 0:
            return
        filled = QRectF(inner)
        filled.setWidth(inner.width() * fraction)
        if option.invertedAppearance:
            filled.moveRight(inner.right())
        clip = QPainterPath()
        clip.addRoundedRect(inner, RADIUS - 1, RADIUS - 1)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipPath(clip)
        painter.setClipRect(filled, Qt.ClipOperation.IntersectClip)
        enabled = bool(option.state & State.State_Enabled)
        accent = option.palette.color(Role.Highlight)
        painter.fillRect(filled, accent)
        if enabled:
            stripes = QPainterPath()
            height = inner.height()
            x = inner.left() - height
            while x < filled.right():
                stripes.addPolygon(QPolygonF([QPointF(x + height, inner.top()),
                                              QPointF(x + height + STRIPE_WIDTH, inner.top()),
                                              QPointF(x + STRIPE_WIDTH, inner.bottom()),
                                              QPointF(x, inner.bottom())]))
                x += STRIPE_WIDTH * 2
            painter.fillPath(stripes, self._colors.accent_stripe)
        if fraction < 1:
            painter.setPen(QPen(option.palette.color(Role.Shadow), 1))
            edge_x = filled.left() + 0.5 if option.invertedAppearance else filled.right() - 0.5
            painter.drawLine(QPointF(edge_x, inner.top()), QPointF(edge_x, inner.bottom()))
        painter.restore()

    def _draw_tab_shape(self, painter: QPainter, option: QStyleOptionTab) -> None:
        """Draws a selected tab as an ink-outlined window-colored tab with an accent top line, others flat."""
        rect = QRectF(option.rect)
        if option.state & State.State_Selected:
            outline = QPainterPath()
            left = rect.left() + 0.5
            right = rect.right() - 0.5
            top = rect.top() + 0.5
            bottom = rect.bottom()
            outline.moveTo(left, bottom)
            outline.lineTo(left, top + RADIUS)
            outline.quadTo(left, top, left + RADIUS, top)
            outline.lineTo(right - RADIUS, top)
            outline.quadTo(right, top, right, top + RADIUS)
            outline.lineTo(right, bottom)
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(option.palette.window())
            painter.drawPath(outline)
            painter.setPen(QPen(option.palette.color(Role.Shadow), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(outline)
            if option.state & State.State_Enabled:
                painter.setPen(QPen(option.palette.color(Role.Highlight), 2))
                painter.drawLine(QPointF(left + RADIUS - 1, top + 1.5), QPointF(right - RADIUS + 1, top + 1.5))
            painter.restore()
        elif option.state & State.State_MouseOver and option.state & State.State_Enabled:
            _draw_box(painter, rect.adjusted(0, 0, 0, RADIUS), ROW_HOVER, None)
        if _keyboard_focus(option):
            _draw_box(painter, rect.adjusted(1, 1, -1, 0), None, option.palette.color(Role.Highlight))

    def _draw_menu_item(self, painter: QPainter, option: QStyleOptionMenuItem, widget: Optional[QWidget]) -> None:
        """Highlights the selected menu item with a rounded accent box inside the menu's padding."""
        item_option = QStyleOptionMenuItem(option)
        selected = (option.state & State.State_Selected and option.state & State.State_Enabled
                    and option.menuItemType != QStyleOptionMenuItem.MenuItemType.Separator)
        if selected:
            # The base style would fill the whole row, so it draws this item unselected, in selected text colors:
            _draw_box(painter, option.rect.adjusted(2, 0, -2, 0), option.palette.color(Role.Highlight), None)
            palette = QPalette(option.palette)
            for group in (Group.Active, Group.Inactive):
                for role in (Role.Text, Role.WindowText, Role.ButtonText):
                    palette.setColor(group, role, palette.color(group, Role.HighlightedText))
            item_option.palette = palette
            item_option.state &= ~State.State_Selected
        super().drawControl(Control.CE_MenuItem, item_option, painter, widget)

    def _draw_menu_bar_item(self, painter: QPainter, option: QStyleOptionMenuItem,
                            widget: Optional[QWidget]) -> None:
        """Marks the hovered or open menu bar item with the accent wash, keeping its normal text color."""
        painter.fillRect(option.rect, option.palette.window())
        active = (option.state & (State.State_Selected | State.State_Sunken)
                  and option.state & State.State_Enabled)
        if active:
            _draw_box(painter, option.rect.adjusted(1, 3, -1, -3), self._colors.accent_wash, None)
        alignment = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextShowMnemonic | Qt.TextFlag.TextDontClip \
            | Qt.TextFlag.TextSingleLine
        if not self.styleHint(QStyle.StyleHint.SH_UnderlineShortcut, option, widget):
            alignment |= Qt.TextFlag.TextHideMnemonic
        self.drawItemText(painter, option.rect, int(alignment), option.palette,
                          bool(option.state & State.State_Enabled), option.text, Role.ButtonText)

    # -----------------------------------------------------------------------------------------------------------------
    # Complex controls
    # -----------------------------------------------------------------------------------------------------------------

    def drawComplexControl(self, control: Complex, option: QStyleOption, painter: QPainter,
                           widget: Optional[QWidget] = None) -> None:
        """Draws sliders, scroll bars, spin boxes and combo boxes in the Ink look."""
        if control == Complex.CC_Slider and isinstance(option, QStyleOptionSlider):
            self._draw_slider(painter, option, widget)
        elif control == Complex.CC_ScrollBar and isinstance(option, QStyleOptionSlider):
            self._draw_scroll_bar(painter, option, widget)
        elif control == Complex.CC_SpinBox and isinstance(option, QStyleOptionSpinBox):
            self._draw_spin_box(painter, option, widget)
        elif control == Complex.CC_ComboBox and isinstance(option, QStyleOptionComboBox):
            self._draw_combo_box(painter, option, widget)
        else:
            super().drawComplexControl(control, option, painter, widget)
            # An auto-raise tool button draws no panel until hovered, so it needs its own focus ring:
            if (control == Complex.CC_ToolButton and option.state & State.State_AutoRaise
                    and not option.state & (State.State_Raised | State.State_Sunken | State.State_On)
                    and option.state & State.State_Enabled and _keyboard_focus(option)):
                _draw_focus_ring(painter, option.rect, option.palette.color(Role.Highlight))

    def _draw_slider(self, painter: QPainter, option: QStyleOptionSlider, widget: Optional[QWidget]) -> None:
        """Draws a sunken groove filled with accent up to the handle, and a raised light handle."""
        palette = option.palette
        enabled = bool(option.state & State.State_Enabled)
        horizontal = option.orientation == Qt.Orientation.Horizontal
        groove = self.subControlRect(Complex.CC_Slider, option, SubControl.SC_SliderGroove, widget)
        handle = self.subControlRect(Complex.CC_Slider, option, SubControl.SC_SliderHandle, widget)
        handle_body = handle.adjusted(0, 0, 0, -SMALL_STICKER_OFFSET)
        handle_center = handle_body.center()
        half_groove = SLIDER_GROOVE_THICKNESS // 2
        if horizontal:
            track = QRect(groove.x(), handle_center.y() - half_groove + 1, groove.width(), SLIDER_GROOVE_THICKNESS)
        else:
            track = QRect(handle_center.x() - half_groove + 1, groove.y(), SLIDER_GROOVE_THICKNESS, groove.height())
        track_radius = SLIDER_GROOVE_THICKNESS / 2
        if option.subControls & SubControl.SC_SliderTickmarks:
            self._draw_slider_ticks(painter, option, groove, track)
        if option.subControls & SubControl.SC_SliderGroove:
            if not enabled:
                _draw_box(painter, track, palette.color(Group.Disabled, Role.Base), self._colors.disabled_outline,
                          track_radius)
            else:
                _draw_box(painter, track, palette.color(Role.Base), None, track_radius)
                filled = QRect(track)
                if horizontal:
                    if option.upsideDown:
                        filled.setLeft(handle_center.x())
                    else:
                        filled.setRight(handle_center.x())
                elif option.upsideDown:
                    filled.setTop(handle_center.y())
                else:
                    filled.setBottom(handle_center.y())
                _draw_box(painter, filled, palette.color(Role.Highlight), None, track_radius)
                _draw_box(painter, track, None, palette.color(Role.Shadow), track_radius)
        if not option.subControls & SubControl.SC_SliderHandle:
            return
        if not enabled:
            _draw_box(painter, handle_body, palette.color(Group.Disabled, Role.Button), self._colors.disabled_outline,
                      3)
            return
        ink = palette.color(Role.Shadow)
        _draw_box(painter, handle_body.translated(0, SMALL_STICKER_OFFSET), ink, ink, 3)
        handle_active = bool(option.activeSubControls & SubControl.SC_SliderHandle) and bool(
            option.state & (State.State_MouseOver | State.State_Sunken))
        fill = palette.color(Role.BrightText) if handle_active else palette.color(Role.WindowText)
        outline = palette.color(Role.Highlight) if _keyboard_focus(option) else ink
        _draw_box(painter, handle_body, fill, outline, 3)

    @staticmethod
    def _draw_slider_ticks(painter: QPainter, option: QStyleOptionSlider, groove: QRect, track: QRect) -> None:
        """Draws tick marks beside the slider track, one per tick interval, centered on the handle positions."""
        if option.tickPosition == QSlider.TickPosition.NoTicks:
            return
        interval = option.tickInterval if option.tickInterval > 0 else option.singleStep
        if interval <= 0 or option.maximum <= option.minimum:
            return
        horizontal = option.orientation == Qt.Orientation.Horizontal
        groove_length = groove.width() if horizontal else groove.height()
        available = groove_length - SLIDER_HANDLE_LENGTH
        start = (groove.x() if horizontal else groove.y()) + SLIDER_HANDLE_LENGTH // 2
        sides = []
        if option.tickPosition in (QSlider.TickPosition.TicksAbove, QSlider.TickPosition.TicksBothSides):
            sides.append(-1)
        if option.tickPosition in (QSlider.TickPosition.TicksBelow, QSlider.TickPosition.TicksBothSides):
            sides.append(1)
        enabled = bool(option.state & State.State_Enabled)
        painter.save()
        painter.setPen(QPen(option.palette.color(Group.Active if enabled else Group.Disabled, Role.PlaceholderText),
                            1))
        value = option.minimum
        while value <= option.maximum:
            offset = start + QStyle.sliderPositionFromValue(option.minimum, option.maximum, value, available,
                                                            option.upsideDown) + 0.5
            for side in sides:
                if horizontal:
                    edge = track.bottom() + 1 + SLIDER_TICK_GAP if side > 0 else track.top() - SLIDER_TICK_GAP
                    painter.drawLine(QPointF(offset, edge), QPointF(offset, edge + SLIDER_TICK_LENGTH * side))
                else:
                    edge = track.right() + 1 + SLIDER_TICK_GAP if side > 0 else track.left() - SLIDER_TICK_GAP
                    painter.drawLine(QPointF(edge, offset), QPointF(edge + SLIDER_TICK_LENGTH * side, offset))
            value += interval
        painter.restore()

    def _draw_scroll_bar(self, painter: QPainter, option: QStyleOptionSlider, widget: Optional[QWidget]) -> None:
        """Draws a thin overlay handle that grows when hovered, or a classic track and handle."""
        slider = self.subControlRect(Complex.CC_ScrollBar, option, SubControl.SC_ScrollBarSlider, widget)
        horizontal = option.orientation == Qt.Orientation.Horizontal
        enabled = bool(option.state & State.State_Enabled)
        hovered = enabled and bool(option.state & (State.State_MouseOver | State.State_Sunken))
        if self._overlay_scroll_bars:
            width = OVERLAY_SCROLL_BAR_HOVER_WIDTH if hovered else OVERLAY_SCROLL_BAR_WIDTH
            if horizontal:
                handle = QRect(slider.x(), option.rect.bottom() + 1 - OVERLAY_SCROLL_BAR_MARGIN - width,
                               slider.width(), width)
            else:
                handle = QRect(option.rect.right() + 1 - OVERLAY_SCROLL_BAR_MARGIN - width, slider.y(), width,
                               slider.height())
            fill = SCROLL_HANDLE_HOVER if hovered else SCROLL_HANDLE
            if not enabled:
                fill = QColor(fill)
                fill.setAlpha(fill.alpha() // 2)
            _draw_box(painter, handle, fill, OVERLAY_SCROLL_HANDLE_OUTLINE, width / 2)
            return
        palette = option.palette
        track_outline = palette.color(Role.Shadow) if enabled else self._colors.disabled_outline
        extent = option.rect.height() if horizontal else option.rect.width()
        _draw_box(painter, option.rect, palette.color(Group.Active if enabled else Group.Disabled, Role.Base),
                  track_outline, extent / 2)
        handle = slider.adjusted(CLASSIC_SCROLL_HANDLE_INSET, CLASSIC_SCROLL_HANDLE_INSET,
                                 -CLASSIC_SCROLL_HANDLE_INSET, -CLASSIC_SCROLL_HANDLE_INSET)
        fill = SCROLL_HANDLE_HOVER if hovered else CLASSIC_SCROLL_HANDLE
        _draw_box(painter, handle, fill if enabled else palette.color(Group.Disabled, Role.Button), None,
                  (extent - CLASSIC_SCROLL_HANDLE_INSET * 2) / 2)

    def _draw_spin_box(self, painter: QPainter, option: QStyleOptionSpinBox, widget: Optional[QWidget]) -> None:
        """Draws a text field with up and down buttons stacked inside its right edge."""
        palette = option.palette
        enabled = bool(option.state & State.State_Enabled)
        if option.frame:
            self._draw_field(painter, option, option.rect)
        else:
            painter.fillRect(option.rect, palette.base())
        if option.buttonSymbols == QAbstractSpinBox.ButtonSymbols.NoButtons:
            return
        up_rect = self.subControlRect(Complex.CC_SpinBox, option, SubControl.SC_SpinBoxUp, widget)
        down_rect = self.subControlRect(Complex.CC_SpinBox, option, SubControl.SC_SpinBoxDown, widget)
        buttons = up_rect.united(down_rect)
        frame_inset = 1 if option.frame else 0
        buttons.setTop(option.rect.top() + frame_inset)
        buttons.setBottom(option.rect.bottom() - frame_inset)
        buttons.setRight(option.rect.right() - frame_inset)
        split_y = up_rect.bottom() + 1 if up_rect.isValid() else buttons.center().y()
        step = QAbstractSpinBox.StepEnabledFlag
        parts = ((SubControl.SC_SpinBoxUp, QRect(buttons.x(), buttons.y(), buttons.width(), split_y - buttons.y()),
                  step.StepUpEnabled, False),
                 (SubControl.SC_SpinBoxDown, QRect(buttons.x(), split_y, buttons.width(),
                                                   buttons.bottom() + 1 - split_y), step.StepDownEnabled, True))
        ink = palette.color(Role.Shadow) if enabled else self._colors.disabled_outline
        painter.save()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(option.rect).adjusted(frame_inset, frame_inset, -frame_inset, -frame_inset),
                            RADIUS - 1, RADIUS - 1)
        painter.setClipPath(clip)
        for part, part_rect, step_flag, pointing_down in parts:
            part_enabled = enabled and bool(option.stepEnabled & step_flag)
            if not enabled:
                fill = palette.color(Group.Disabled, Role.Button)
            elif part_enabled and option.activeSubControls & part and option.state & State.State_Sunken:
                fill = palette.color(Role.AlternateBase)
            elif part_enabled and option.activeSubControls & part and option.state & State.State_MouseOver:
                fill = palette.color(Role.Midlight)
            else:
                fill = palette.color(Role.Button)
            painter.fillRect(part_rect, fill)
            arrow_color = palette.color(Group.Active if part_enabled else Group.Disabled, Role.ButtonText)
            _draw_chevron(painter, QRectF(part_rect).center(), arrow_color, pointing_down)
        painter.setPen(QPen(ink, 1))
        painter.drawLine(QPointF(buttons.x() - 0.5, buttons.top()), QPointF(buttons.x() - 0.5, buttons.bottom() + 1))
        painter.drawLine(QPointF(buttons.x(), split_y - 0.5), QPointF(buttons.right() + 1, split_y - 0.5))
        painter.restore()
        if option.frame:
            # Redraw the outline over the buttons, so they sit inside it:
            outline_option = QStyleOption(option)
            outline_option.state &= ~State.State_MouseOver
            self._draw_field(painter, outline_option, option.rect, fill=False)

    def _draw_combo_box(self, painter: QPainter, option: QStyleOptionComboBox, widget: Optional[QWidget]) -> None:
        """Draws a combo box as a text field with a chevron at its right edge."""
        if option.frame:
            field_option = QStyleOption(option)
            if not option.editable:
                # A non-editable combo box only shows a focus ring when focus came from the keyboard:
                if not _keyboard_focus(option):
                    field_option.state &= ~State.State_HasFocus
            self._draw_field(painter, field_option, option.rect)
        else:
            painter.fillRect(option.rect, option.palette.base())
        if option.subControls & SubControl.SC_ComboBoxArrow:
            arrow_rect = self.subControlRect(Complex.CC_ComboBox, option, SubControl.SC_ComboBoxArrow, widget)
            enabled = bool(option.state & State.State_Enabled)
            arrow_color = option.palette.color(Group.Active if enabled else Group.Disabled, Role.ButtonText)
            _draw_chevron(painter, QRectF(arrow_rect).center(), arrow_color, True)
