"""Renders the Qt style's controls in every state, for tests and screenshots.

`style_gallery_test.py` compares these renders with committed goldens, and `scripts/capture_ui.py` saves them as images
for review. Both go through the same functions, so a screenshot shows what a test checked. Panel captures are in
`test/ui/panel_capture.py`.

Style gallery images draw each control through `QStyle` with hand-built options, one cell per state. They contain no
text: Qt rasterizes glyphs with the system's FreeType and fontconfig, so text pixels differ between machines.
"""
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QFocusEvent, QFontMetrics, QHoverEvent, QIcon, QImage, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QCheckBox, QPushButton, QStyle, QStyleOption,
                               QStyleOptionButton, QStyleOptionComboBox, QStyleOptionComplex, QStyleOptionFrame,
                               QStyleOptionGroupBox, QStyleOptionMenuItem, QStyleOptionProgressBar, QStyleOptionSlider,
                               QStyleOptionSpinBox, QStyleOptionTab, QStyleOptionToolButton, QStyleOptionViewItem,
                               QSlider, QTabBar, QWidget, QLineEdit)

from src.ui.button_weight import ButtonWeight, set_button_weight
from src.ui.ink_style import InkStyle, set_primary_button, set_signal
from src.ui.widget.disabled_banner import DisabledBanner
from src.ui.widget.keycap_badge import KeycapBadge
from src.ui.widget.panel_header import PanelHeader
from src.ui.widget.panel_section import PanelSection
from src.ui.input_fields.geometry_block import GeometryBlock, _GeometryField
from src.ui.input_fields.number_field import NumberField
from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from src.ui.input_fields.slider_field import SliderField

State = QStyle.StateFlag
Control = QStyle.ControlElement
Complex = QStyle.ComplexControl
Primitive = QStyle.PrimitiveElement
SubControl = QStyle.SubControl

CELL_MARGIN = 6

# ---------------------------------------------------------------------------------------------------------------------
# Style gallery
# ---------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class GalleryState:
    """One gallery column: the style state flags and palette group a control is drawn with."""
    name: str
    state: State
    active_sub_controls: SubControl = SubControl.SC_None

    @property
    def enabled(self) -> bool:
        """Whether this state draws the control as enabled."""
        return bool(self.state & State.State_Enabled)


_ENABLED = State.State_Enabled | State.State_Active
# Styles may show a focus ring only when focus last moved by keyboard, so the focus states set that flag too:
_FOCUSED = _ENABLED | State.State_HasFocus | State.State_KeyboardFocusChange
STANDARD_STATES = (
    GalleryState('normal', _ENABLED),
    GalleryState('hover', _ENABLED | State.State_MouseOver),
    GalleryState('pressed', _ENABLED | State.State_Sunken | State.State_MouseOver),
    GalleryState('focus', _FOCUSED),
    GalleryState('disabled', State.State_None),
)
# Complex controls mark the hovered or pressed part with an active sub-control. Each entry is a function of the part:
_PART_STATES: tuple[Callable[[SubControl], GalleryState], ...] = (
    lambda _part: GalleryState('normal', _ENABLED),
    lambda part: GalleryState('hover', _ENABLED | State.State_MouseOver, part),
    lambda part: GalleryState('pressed', _ENABLED | State.State_Sunken | State.State_MouseOver, part),
    lambda _part: GalleryState('focus', _FOCUSED),
    lambda _part: GalleryState('disabled', State.State_None),
)
MENU_STATES = (
    GalleryState('normal', _ENABLED),
    GalleryState('selected', _ENABLED | State.State_Selected),
    GalleryState('disabled', State.State_None),
)


def part_states(part: SubControl) -> tuple[GalleryState, ...]:
    """Returns the standard states for a complex control whose hovered or pressed part is `part`."""
    return tuple(make_state(part) for make_state in _PART_STATES)


@dataclass(frozen=True)
class GalleryControl:
    """One gallery image: a control drawn once per (variant, state) cell.

    `draw` receives the painter, the cell rectangle, the variant name and the state, and draws one cell.
    """
    name: str
    cell_size: QSize
    variants: tuple[str, ...]
    states: tuple[GalleryState, ...]
    draw: Callable[[QPainter, QRect, str, GalleryState], None]


def _init_option(option: QStyleOption, rect: QRect, state: GalleryState) -> None:
    """Sets the fields QStyleOption.initFrom would set from a widget in the given state."""
    palette = QPalette(QApplication.palette())
    palette.setCurrentColorGroup(QPalette.ColorGroup.Active if state.enabled else QPalette.ColorGroup.Disabled)
    option.palette = palette
    option.rect = rect
    option.state = state.state
    option.direction = Qt.LayoutDirection.LeftToRight
    option.fontMetrics = QFontMetrics(QApplication.font())
    if isinstance(option, QStyleOptionComplex):
        option.activeSubControls = state.active_sub_controls


def _style() -> QStyle:
    return QApplication.style()


_widget_cache: dict[str, QWidget] = {}
_style_cache: dict[str, QStyle] = {}


def _primary_button() -> QPushButton:
    """Returns a hidden push button marked primary, for styles that read the mark from the drawn widget."""
    if 'primary' not in _widget_cache:
        button = QPushButton()
        set_primary_button(button)
        _widget_cache['primary'] = button
    widget = _widget_cache['primary']
    assert isinstance(widget, QPushButton)
    return widget


def _signal_widget(widget_type: type[QCheckBox]) -> QWidget:
    """Returns a hidden widget marked with the signal color."""
    key = f'signal_{widget_type.__name__}'
    if key not in _widget_cache:
        widget = widget_type()
        set_signal(widget)
        _widget_cache[key] = widget
    return _widget_cache[key]


def _classic_scroll_bar_style() -> QStyle:
    """Returns the application style with classic scroll bars, if it has an overlay scroll bar option."""
    style = _style()
    if not isinstance(style, InkStyle) or not style.overlay_scroll_bars:
        return style
    if 'classic_style' not in _style_cache:
        _style_cache['classic_style'] = InkStyle(style.baseStyle().name(), style.colors, overlay_scroll_bars=False)
    return _style_cache['classic_style']


def _draw_push_button(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    option = QStyleOptionButton()
    _init_option(option, rect, state)
    widget: Optional[QWidget] = None
    if variant == 'default':
        option.features = QStyleOptionButton.ButtonFeature.DefaultButton
    elif variant == 'flat':
        option.features = QStyleOptionButton.ButtonFeature.Flat
    elif variant == 'checked':
        option.state |= State.State_On
    elif variant == 'primary':
        widget = _primary_button()
    _style().drawControl(Control.CE_PushButton, option, painter, widget)


def _draw_tool_button(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    option = QStyleOptionToolButton()
    _init_option(option, rect, state)
    option.subControls = SubControl.SC_ToolButton
    option.toolButtonStyle = Qt.ToolButtonStyle.ToolButtonIconOnly
    if variant == 'auto_raise':
        option.state |= State.State_AutoRaise
    else:
        option.state |= State.State_Raised
    if variant == 'checked':
        option.state |= State.State_On
    elif variant == 'menu':
        option.subControls |= SubControl.SC_ToolButtonMenu
        option.features = QStyleOptionToolButton.ToolButtonFeature.MenuButtonPopup
    _style().drawComplexControl(Complex.CC_ToolButton, option, painter, None)


def _check_state(variant: str) -> State:
    return {'off': State.State_Off, 'on': State.State_On, 'partial': State.State_NoChange}[variant]


def _draw_check_box(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    option = QStyleOptionButton()
    _init_option(option, rect, state)
    option.state |= _check_state(variant.removeprefix('signal_'))
    widget = _signal_widget(QCheckBox) if variant.startswith('signal_') else None
    _style().drawControl(Control.CE_CheckBox, option, painter, widget)


def _draw_radio_button(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    option = QStyleOptionButton()
    _init_option(option, rect, state)
    option.state |= _check_state(variant)
    _style().drawControl(Control.CE_RadioButton, option, painter, None)


def _slider_option(rect: QRect, state: GalleryState, orientation: Qt.Orientation, position: int) -> QStyleOptionSlider:
    option = QStyleOptionSlider()
    _init_option(option, rect, state)
    option.orientation = orientation
    if orientation == Qt.Orientation.Horizontal:
        option.state |= State.State_Horizontal
    option.minimum = 0
    option.maximum = 100
    option.sliderPosition = position
    option.sliderValue = position
    option.singleStep = 1
    option.pageStep = 10
    option.upsideDown = orientation == Qt.Orientation.Vertical
    return option


def _draw_slider(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    orientation = Qt.Orientation.Vertical if variant == 'vertical' else Qt.Orientation.Horizontal
    option = _slider_option(rect, state, orientation, 30)
    option.subControls = SubControl.SC_SliderGroove | SubControl.SC_SliderHandle
    if variant == 'ticks':
        option.subControls |= SubControl.SC_SliderTickmarks
        option.tickPosition = QSlider.TickPosition.TicksBelow
        option.tickInterval = 10
    _style().drawComplexControl(Complex.CC_Slider, option, painter, None)


def _draw_scroll_bar(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    style = _style()
    if variant.startswith('classic_'):
        style = _classic_scroll_bar_style()
        variant = variant.removeprefix('classic_')
    orientation, position = {'start': (Qt.Orientation.Horizontal, 0), 'middle': (Qt.Orientation.Horizontal, 50),
                             'end': (Qt.Orientation.Horizontal, 100), 'vertical': (Qt.Orientation.Vertical, 30)}[variant]
    option = _slider_option(rect, state, orientation, position)
    option.upsideDown = False
    option.subControls = SubControl.SC_All
    style.drawComplexControl(Complex.CC_ScrollBar, option, painter, None)


def _draw_spin_box(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    option = QStyleOptionSpinBox()
    _init_option(option, rect, state)
    option.subControls = SubControl.SC_SpinBoxFrame | SubControl.SC_SpinBoxUp | SubControl.SC_SpinBoxDown
    option.frame = True
    option.buttonSymbols = QAbstractSpinBox.ButtonSymbols.UpDownArrows
    step = QAbstractSpinBox.StepEnabledFlag
    option.stepEnabled = {'both': step.StepUpEnabled | step.StepDownEnabled, 'at_minimum': step.StepUpEnabled,
                          'at_maximum': step.StepDownEnabled}[variant]
    _style().drawComplexControl(Complex.CC_SpinBox, option, painter, None)


def _draw_combo_box(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    option = QStyleOptionComboBox()
    _init_option(option, rect, state)
    option.subControls = SubControl.SC_All
    option.frame = True
    option.editable = variant == 'editable'
    _style().drawComplexControl(Complex.CC_ComboBox, option, painter, None)


def _draw_line_edit(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    option = QStyleOptionFrame()
    _init_option(option, rect, state)
    option.lineWidth = _style().pixelMetric(QStyle.PixelMetric.PM_DefaultFrameWidth, option, None)
    option.midLineWidth = 0
    option.state |= State.State_Sunken
    if variant == 'read_only':
        option.state |= State.State_ReadOnly
    _style().drawPrimitive(Primitive.PE_PanelLineEdit, option, painter, None)


def _draw_progress_bar(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    option = QStyleOptionProgressBar()
    _init_option(option, rect, state)
    option.state |= State.State_Horizontal
    option.minimum = 0
    option.maximum = 100
    option.progress = int(variant.rstrip('%'))
    option.textVisible = False
    _style().drawControl(Control.CE_ProgressBar, option, painter, None)


def _draw_tab(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    option = QStyleOptionTab()
    _init_option(option, rect, state)
    option.shape = QTabBar.Shape.RoundedNorth
    position = QStyleOptionTab.TabPosition
    option.position = {'beginning': position.Beginning, 'middle': position.Middle, 'end': position.End,
                       'only': position.OnlyOneTab}[variant.removesuffix('_selected')]
    if variant.endswith('_selected'):
        option.state |= State.State_Selected
    _style().drawControl(Control.CE_TabBarTab, option, painter, None)


def _draw_group_box(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    option = QStyleOptionGroupBox()
    _init_option(option, rect, state)
    option.subControls = SubControl.SC_GroupBoxFrame
    option.lineWidth = 1
    if variant == 'flat':
        option.features = QStyleOptionFrame.FrameFeature.Flat
    _style().drawComplexControl(Complex.CC_GroupBox, option, painter, None)


def _draw_frame(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    option = QStyleOptionFrame()
    _init_option(option, rect, state)
    option.lineWidth = 1
    option.midLineWidth = 0
    option.state |= State.State_Sunken if variant == 'sunken' else State.State_Raised
    _style().drawPrimitive(Primitive.PE_Frame, option, painter, None)


def _draw_menu_item(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    menu_option = QStyleOption()
    _init_option(menu_option, rect, GalleryState('menu', _ENABLED))
    _style().drawPrimitive(Primitive.PE_PanelMenu, menu_option, painter, None)
    option = QStyleOptionMenuItem()
    _init_option(option, rect, state)
    option.menuRect = rect
    option.maxIconWidth = 16
    item_type = QStyleOptionMenuItem.MenuItemType
    check_type = QStyleOptionMenuItem.CheckType
    option.menuItemType = {'separator': item_type.Separator, 'submenu': item_type.SubMenu}.get(variant,
                                                                                               item_type.Normal)
    option.checkType = check_type.NonExclusive if variant == 'checked' else check_type.NotCheckable
    option.checked = variant == 'checked'
    _style().drawControl(Control.CE_MenuItem, option, painter, None)


def _draw_menu_bar_item(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    bar_option = QStyleOption()
    _init_option(bar_option, rect, GalleryState('bar', _ENABLED))
    _style().drawControl(Control.CE_MenuBarEmptyArea, bar_option, painter, None)
    option = QStyleOptionMenuItem()
    _init_option(option, rect, state)
    option.menuRect = rect
    option.menuItemType = QStyleOptionMenuItem.MenuItemType.Normal
    if variant == 'open':
        option.state |= State.State_Sunken
    _style().drawControl(Control.CE_MenuBarItem, option, painter, None)


def _draw_item_view_item(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    option = QStyleOptionViewItem()
    _init_option(option, rect, state)
    option.showDecorationSelected = True
    option.viewItemPosition = QStyleOptionViewItem.ViewItemPosition.OnlyOne
    if variant == 'selected':
        option.state |= State.State_Selected
    elif variant == 'alternate':
        option.features = QStyleOptionViewItem.ViewItemFeature.Alternate
    _style().drawPrimitive(Primitive.PE_PanelItemViewItem, option, painter, None)


def _draw_splitter(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    option = QStyleOption()
    _init_option(option, rect, state)
    if variant == 'horizontal':
        option.state |= State.State_Horizontal
    _style().drawControl(Control.CE_Splitter, option, painter, None)


def _draw_tooltip(painter: QPainter, rect: QRect, _variant: str, state: GalleryState) -> None:
    option = QStyleOption()
    _init_option(option, rect, state)
    tooltip_palette = QPalette(option.palette)
    tooltip_palette.setBrush(QPalette.ColorRole.Window, option.palette.toolTipBase())
    option.palette = tooltip_palette
    _style().drawPrimitive(Primitive.PE_PanelTipLabel, option, painter, None)


class _TextFreeNumberField(NumberField):
    """A number field that draws no label or value, so its render doesn't depend on the system's text rasterizer."""

    def _paint_text(self, painter: QPainter) -> None:
        pass


class _TextFreeSliderField(SliderField):
    """A slider field that draws no label or value."""

    def _paint_text(self, painter: QPainter) -> None:
        pass


FIELD_STATES = (GalleryState('normal', _ENABLED), GalleryState('hover', _ENABLED | State.State_MouseOver),
                GalleryState('focus', _FOCUSED), GalleryState('editing', _FOCUSED),
                GalleryState('disabled', State.State_None))


def _draw_number_field(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    """Draws a real `NumberField` or `SliderField` in a gallery state. Hover, focus and editing are put on the widget
    with the events Qt would send."""
    field: NumberField
    if variant == 'number':
        field = _TextFreeNumberField('', 25)
    else:
        field = _TextFreeSliderField('', 40, 0, 100)
    if variant in ('slider_pressure_off', 'slider_pressure_on'):
        field.set_pressure_link_available(True)
        field.set_pressure_link_enabled(variant == 'slider_pressure_on')
    field.resize(rect.size())
    field.setEnabled(state.enabled)
    if state.state & State.State_MouseOver:
        QApplication.sendEvent(field, QEvent(QEvent.Type.HoverEnter))
    if state.name == 'focus':
        QApplication.sendEvent(field, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason))
    if state.name == 'editing':
        field.begin_edit()
        editor = field.findChild(QLineEdit)
        if editor is not None:
            editor.setText('')
            editor.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            editor.clearFocus()
    field.render(painter, QPoint())


def _draw_button_weight(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    """Draws a push button of one weight. Text-free, so a danger button is a bar in its text color where its label
    would be."""
    weight = ButtonWeight(variant)
    button = QPushButton()
    set_button_weight(button, weight)
    option = QStyleOptionButton()
    _init_option(option, rect, state)
    if weight == ButtonWeight.FLAT:
        option.features = QStyleOptionButton.ButtonFeature.Flat
    _style().drawControl(Control.CE_PushButton, option, painter, button)
    style = _style()
    if weight == ButtonWeight.DANGER and isinstance(style, InkStyle) and state.enabled:
        painter.fillRect(QRect(rect.center().x() - 14, rect.center().y() - 1, 28, 3),
                         style.signal_text_color(state.state))


class _TextFreeBadge(KeycapBadge):
    """A keycap that draws no key text."""

    def _paint_text(self, painter: QPainter, bounds) -> None:
        pass


class _TextFreeHeader(PanelHeader):
    """A panel header whose keycap draws no text."""

    def _make_key_badge(self) -> KeycapBadge:
        return _TextFreeBadge()


def _draw_widget(painter: QPainter, rect: QRect, widget: QWidget, state: GalleryState) -> None:
    """Renders a real widget in an enabled or disabled state at the cell size."""
    widget.resize(rect.size())
    widget.setEnabled(state.enabled)
    widget.render(painter, QPoint())


def _draw_panel_section(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    """Draws a section header: expanded, collapsed, or collapsed with a header keycap."""
    body = QWidget()
    body.setFixedHeight(10)
    section = PanelSection('', body, expanded=variant == 'expanded')
    section.set_summary('')
    if variant == 'collapsed_keycap':
        section.add_header_widget(_TextFreeBadge('Q'))
    _draw_widget(painter, rect, section, state)


def _draw_panel_header(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    header = _TextFreeHeader('', None, 'Q' if variant == 'with_key' else '')
    header.set_popover_content(QWidget())
    _draw_widget(painter, rect, header, state)


def _draw_disabled_banner(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    banner = DisabledBanner('', '' if variant == 'no_fix' else ' ')
    _draw_widget(painter, rect, banner, state)


SECTION_STATES = (STANDARD_STATES[0], STANDARD_STATES[4])


class _TextFreeSegmentedControl(SegmentedControl):
    """A segmented control that draws no label text."""

    def _paint_text(self, painter: QPainter, text: str, rect: QRect) -> None:
        pass


SEGMENTED_STATES = (GalleryState('normal', _ENABLED), GalleryState('hover', _ENABLED | State.State_MouseOver),
                    GalleryState('focus', _FOCUSED), GalleryState('hint', _ENABLED),
                    GalleryState('disabled', State.State_None))


def _segment_icon() -> QIcon:
    """Returns a plain square icon, so the gallery needs no icon files."""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.fillRect(3, 3, 10, 10, QApplication.palette().color(QPalette.ColorRole.Text))
    painter.end()
    return QIcon(pixmap)


def _draw_segmented_control(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    """Draws a real `SegmentedControl`. Variants are `<segment count>_<display mode>`; the second segment is checked
    and the last is hinted in the hint state."""
    count_text, mode_text = variant.split('_', 1)
    count = int(count_text)
    segments = [Segment(str(i), f'Option {i}', _segment_icon()) for i in range(count)]
    control = _TextFreeSegmentedControl(segments, DisplayMode(mode_text))
    control.set_value('1')
    control.resize(rect.size())
    control.setEnabled(state.enabled)
    if state.state & State.State_MouseOver:
        hover_pos = QPointF(control.segment_rect(0).center())
        QApplication.sendEvent(control, QHoverEvent(QEvent.Type.HoverEnter, hover_pos, hover_pos, hover_pos))
    if state.name == 'focus':
        QApplication.sendEvent(control, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason))
    if state.name == 'hint':
        control.set_hint_value(str(count - 1))
    control.render(painter, QPoint())


class _TextFreeGeometryField(_GeometryField):
    """A geometry field that draws no label or value."""

    def _paint_text(self, painter: QPainter) -> None:
        pass


class _TextFreeGeometryBlock(GeometryBlock):
    """A geometry block whose fields draw no text."""

    def _make_field(self, *args, **kwargs) -> NumberField:
        return _TextFreeGeometryField(*args, **kwargs)


def _draw_geometry_block(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    """Draws a real `GeometryBlock`. Variants: `base`, `locked`, `temporary_lock` and `scale_angle` (stacked, with the
    scale and angle rows and a locked ratio), and `strip_short` (the one-line form). Fields are set to varied
    fractions of their ranges so each fill is visible."""
    full = variant == 'scale_angle'
    block = _TextFreeGeometryBlock(show_scale=full, show_angle=full, integer=True)
    block.set_image_size(QSize(100, 100))
    block.set_values(x=40, y=-30, w=120, h=60)
    if full:
        block.set_values(scale_x=1, scale_y=1, angle=45)
    block.set_horizontal(variant == 'strip_short')
    if variant in ('locked', 'scale_angle'):
        block.set_ratio_locked(True)
    if variant == 'temporary_lock':
        block.set_temporary_lock(True)
    block.resize(rect.size())
    block.setEnabled(state.enabled)
    block.render(painter, QPoint())


GALLERY_CONTROLS: tuple[GalleryControl, ...] = (
    GalleryControl('push_button', QSize(72, 28), ('plain', 'default', 'checked', 'flat', 'primary'), STANDARD_STATES,
                   _draw_push_button),
    GalleryControl('tool_button', QSize(44, 32), ('plain', 'auto_raise', 'checked', 'menu'), STANDARD_STATES,
                   _draw_tool_button),
    GalleryControl('check_box', QSize(24, 24), ('off', 'on', 'partial', 'signal_on'), STANDARD_STATES, _draw_check_box),
    GalleryControl('radio_button', QSize(24, 24), ('off', 'on'), STANDARD_STATES, _draw_radio_button),
    GalleryControl('slider', QSize(120, 32), ('plain', 'ticks'), part_states(SubControl.SC_SliderHandle),
                   _draw_slider),
    GalleryControl('slider_vertical', QSize(32, 120), ('vertical',), part_states(SubControl.SC_SliderHandle),
                   _draw_slider),
    GalleryControl('scroll_bar', QSize(140, 16), ('start', 'middle', 'end'), part_states(SubControl.SC_ScrollBarSlider),
                   _draw_scroll_bar),
    GalleryControl('scroll_bar_vertical', QSize(16, 140), ('vertical',), part_states(SubControl.SC_ScrollBarSlider),
                   _draw_scroll_bar),
    GalleryControl('scroll_bar_classic', QSize(140, 16), ('classic_start', 'classic_middle', 'classic_end'),
                   part_states(SubControl.SC_ScrollBarSlider), _draw_scroll_bar),
    GalleryControl('spin_box', QSize(80, 26), ('both', 'at_minimum', 'at_maximum'), part_states(SubControl.SC_SpinBoxUp),
                   _draw_spin_box),
    GalleryControl('combo_box', QSize(100, 26), ('plain', 'editable'), part_states(SubControl.SC_ComboBoxArrow),
                   _draw_combo_box),
    GalleryControl('line_edit', QSize(100, 26), ('plain', 'read_only'), STANDARD_STATES, _draw_line_edit),
    GalleryControl('progress_bar', QSize(120, 20), ('0%', '40%', '100%'), STANDARD_STATES, _draw_progress_bar),
    GalleryControl('tab', QSize(64, 28), ('beginning', 'middle', 'end', 'only', 'middle_selected'), STANDARD_STATES,
                   _draw_tab),
    GalleryControl('group_box', QSize(100, 60), ('plain', 'flat'), STANDARD_STATES, _draw_group_box),
    GalleryControl('frame', QSize(80, 40), ('sunken', 'raised'), STANDARD_STATES, _draw_frame),
    GalleryControl('menu_item', QSize(140, 24), ('plain', 'checked', 'submenu', 'separator'), MENU_STATES,
                   _draw_menu_item),
    GalleryControl('menu_bar_item', QSize(60, 24), ('plain', 'open'), MENU_STATES, _draw_menu_bar_item),
    GalleryControl('item_view_item', QSize(120, 24), ('plain', 'selected', 'alternate'), STANDARD_STATES,
                   _draw_item_view_item),
    GalleryControl('splitter', QSize(40, 40), ('horizontal', 'vertical'), STANDARD_STATES, _draw_splitter),
    GalleryControl('tooltip', QSize(100, 30), ('plain',), (STANDARD_STATES[0],), _draw_tooltip),
    GalleryControl('number_field', QSize(150, 24), ('slider', 'slider_pressure_off', 'slider_pressure_on', 'number'),
                   FIELD_STATES, _draw_number_field),
    GalleryControl('button_weight', QSize(72, 28), tuple(weight.value for weight in ButtonWeight), STANDARD_STATES,
                   _draw_button_weight),
    GalleryControl('panel_section', QSize(200, 40), ('expanded', 'collapsed', 'collapsed_keycap'), SECTION_STATES,
                   _draw_panel_section),
    GalleryControl('panel_header', QSize(200, 28), ('with_key', 'without_key'), SECTION_STATES, _draw_panel_header),
    GalleryControl('disabled_banner', QSize(200, 36), ('with_fix', 'no_fix'), SECTION_STATES,
                   _draw_disabled_banner),

    GalleryControl('segmented_control', QSize(200, 24),
                   tuple(f'{count}_{mode.value}' for count in (2, 3, 4)
                         for mode in (DisplayMode.ICON_AND_LABEL, DisplayMode.LABEL, DisplayMode.ICON)),
                   SEGMENTED_STATES, _draw_segmented_control),
    GalleryControl('geometry_block', QSize(280, 130), ('base', 'locked', 'temporary_lock', 'scale_angle'),
                   SECTION_STATES, _draw_geometry_block),
    GalleryControl('geometry_block_strip_short', QSize(560, 24), ('strip_short',), SECTION_STATES,
                   _draw_geometry_block),
)


def gallery_cell_rect(control: GalleryControl, row: int, column: int) -> QRect:
    """Returns the rectangle of one cell in a gallery image."""
    step = control.cell_size + QSize(CELL_MARGIN, CELL_MARGIN)
    return QRect(QPoint(CELL_MARGIN + column * step.width(), CELL_MARGIN + row * step.height()), control.cell_size)


def render_gallery_control(control: GalleryControl) -> QImage:
    """Draws a control in every variant and state, one row per variant and one column per state, on the window color.

    The image has no text, and its size depends only on the control's cell size and its variant and state counts.
    """
    step = control.cell_size + QSize(CELL_MARGIN, CELL_MARGIN)
    size = QSize(CELL_MARGIN + step.width() * len(control.states), CELL_MARGIN + step.height() * len(control.variants))
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QApplication.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.Window))
    painter = QPainter(image)
    try:
        for row, variant in enumerate(control.variants):
            for column, state in enumerate(control.states):
                painter.save()
                # Styles place a complex control's parts relative to (0, 0), so each cell draws in local coordinates:
                painter.translate(gallery_cell_rect(control, row, column).topLeft())
                control.draw(painter, QRect(QPoint(), control.cell_size), variant, state)
                painter.restore()
    finally:
        painter.end()
    return image
