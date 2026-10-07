"""Renders the Qt style's controls in every state, and IntraPaint's panels at extreme sizes, for tests and screenshots.

`style_gallery_test.py` and `panel_layout_test.py` compare these renders with committed goldens and snapshots, and
`scripts/capture_ui.py` saves them as images for review. Both go through the same functions, so a screenshot shows
what a test checked.

- Style gallery images draw each control through `QStyle` with hand-built options, one cell per state. They contain no
  text: Qt rasterizes glyphs with the system's FreeType and fontconfig, so text pixels differ between machines.
- Panel captures resize each panel inside a plain host widget, which lets them go below the panel's minimum size the
  way a squeezed dock or divider can. `find_layout_problems` lists overlapping, clipped and squeezed child widgets.
  Its results depend on font metrics, which the bundled theme font fixes.
"""
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import Callable, Optional, TYPE_CHECKING
from unittest.mock import patch

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6 import QtGui
from PySide6.QtGui import QFontMetrics, QImage, QPainter, QPalette, QTextDocumentFragment
from PySide6.QtWidgets import (QAbstractButton, QAbstractScrollArea, QAbstractSpinBox, QApplication, QGroupBox, QLabel, QLayout,
                               QSizePolicy, QStyle, QStyleOption, QStyleOptionButton, QStyleOptionComboBox,
                               QStyleOptionComplex, QStyleOptionFrame, QStyleOptionGroupBox, QStyleOptionMenuItem,
                               QStyleOptionProgressBar, QStyleOptionSlider, QStyleOptionSpinBox, QStyleOptionTab,
                               QStyleOptionToolButton, QStyleOptionViewItem, QSlider, QTabBar, QWidget)

if TYPE_CHECKING:
    from src.controller.app_controller import AppController

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
STANDARD_STATES = (
    GalleryState('normal', _ENABLED),
    GalleryState('hover', _ENABLED | State.State_MouseOver),
    GalleryState('pressed', _ENABLED | State.State_Sunken | State.State_MouseOver),
    GalleryState('focus', _ENABLED | State.State_HasFocus),
    GalleryState('disabled', State.State_None),
)
# Complex controls mark the hovered or pressed part with an active sub-control. Each entry is a function of the part:
_PART_STATES: tuple[Callable[[SubControl], GalleryState], ...] = (
    lambda _part: GalleryState('normal', _ENABLED),
    lambda part: GalleryState('hover', _ENABLED | State.State_MouseOver, part),
    lambda part: GalleryState('pressed', _ENABLED | State.State_Sunken | State.State_MouseOver, part),
    lambda _part: GalleryState('focus', _ENABLED | State.State_HasFocus),
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


def _draw_push_button(painter: QPainter, rect: QRect, variant: str, state: GalleryState) -> None:
    option = QStyleOptionButton()
    _init_option(option, rect, state)
    if variant == 'default':
        option.features = QStyleOptionButton.ButtonFeature.DefaultButton
    elif variant == 'flat':
        option.features = QStyleOptionButton.ButtonFeature.Flat
    elif variant == 'checked':
        option.state |= State.State_On
    _style().drawControl(Control.CE_PushButton, option, painter, None)


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
    option.state |= _check_state(variant)
    _style().drawControl(Control.CE_CheckBox, option, painter, None)


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
    orientation, position = {'start': (Qt.Orientation.Horizontal, 0), 'middle': (Qt.Orientation.Horizontal, 50),
                             'end': (Qt.Orientation.Horizontal, 100), 'vertical': (Qt.Orientation.Vertical, 30)}[variant]
    option = _slider_option(rect, state, orientation, position)
    option.upsideDown = False
    option.subControls = SubControl.SC_All
    _style().drawComplexControl(Complex.CC_ScrollBar, option, painter, None)


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


GALLERY_CONTROLS: tuple[GalleryControl, ...] = (
    GalleryControl('push_button', QSize(72, 28), ('plain', 'default', 'checked', 'flat'), STANDARD_STATES,
                   _draw_push_button),
    GalleryControl('tool_button', QSize(44, 32), ('plain', 'auto_raise', 'checked', 'menu'), STANDARD_STATES,
                   _draw_tool_button),
    GalleryControl('check_box', QSize(24, 24), ('off', 'on', 'partial'), STANDARD_STATES, _draw_check_box),
    GalleryControl('radio_button', QSize(24, 24), ('off', 'on'), STANDARD_STATES, _draw_radio_button),
    GalleryControl('slider', QSize(120, 32), ('plain', 'ticks'), part_states(SubControl.SC_SliderHandle),
                   _draw_slider),
    GalleryControl('slider_vertical', QSize(32, 120), ('vertical',), part_states(SubControl.SC_SliderHandle),
                   _draw_slider),
    GalleryControl('scroll_bar', QSize(140, 16), ('start', 'middle', 'end'), part_states(SubControl.SC_ScrollBarSlider),
                   _draw_scroll_bar),
    GalleryControl('scroll_bar_vertical', QSize(16, 140), ('vertical',), part_states(SubControl.SC_ScrollBarSlider),
                   _draw_scroll_bar),
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


# ---------------------------------------------------------------------------------------------------------------------
# Panel layouts
# ---------------------------------------------------------------------------------------------------------------------

SIZE_CASES = ('preferred', 'minimum', 'wide', 'tall', 'narrow', 'short')
FALLBACK_SIZE = QSize(400, 300)
WIDE_MIN_WIDTH = 1600
TALL_MIN_HEIGHT = 1200


def panel_size(case: str, widget: QWidget) -> QSize:
    """Returns the size a panel is captured at for one of SIZE_CASES.

    - preferred, minimum: the panel's size hint and minimum size hint.
    - wide, tall: the preferred size stretched to at least WIDE_MIN_WIDTH wide or TALL_MIN_HEIGHT tall.
    - narrow, short: the preferred size with its width or height cut to half the minimum, below what the panel asks
      for.
    """
    preferred = widget.sizeHint()
    if not preferred.isValid() or preferred.isEmpty():
        preferred = FALLBACK_SIZE
    minimum = widget.minimumSizeHint().expandedTo(QSize(1, 1))
    if case == 'preferred':
        return preferred
    if case == 'minimum':
        return minimum.expandedTo(QSize(1, 1))
    if case == 'wide':
        return QSize(max(preferred.width() * 3, WIDE_MIN_WIDTH), preferred.height())
    if case == 'tall':
        return QSize(preferred.width(), max(preferred.height() * 3, TALL_MIN_HEIGHT))
    if case == 'narrow':
        return QSize(max(minimum.width() // 2, 1), preferred.height())
    if case == 'short':
        return QSize(preferred.width(), max(minimum.height() // 2, 1))
    raise ValueError(f'Unknown size case {case}, expected one of {SIZE_CASES}')


def _settle_layouts(root: QWidget) -> None:
    """Activates every layout under root, parents first, so geometry is final without running the event loop."""
    for widget in [root, *root.findChildren(QWidget)]:
        layout = widget.layout()
        if layout is not None and widget.isVisibleTo(root):
            layout.activate()


class PanelHost(QWidget):
    """A plain parent that sets a panel's geometry directly, so the panel can be sized below its minimum."""

    def __init__(self, panel: QWidget) -> None:
        super().__init__()
        self.panel = panel
        self._old_parent = panel.parentWidget()
        self._panel_was_visible = panel.isVisible()
        panel.setParent(self)
        panel.show()

    def capture(self, size: QSize) -> QImage:
        """Resizes the panel, settles its layouts and returns a render of it."""
        self.resize(size)
        self.panel.setGeometry(QRect(QPoint(), size))
        self.show()
        _settle_layouts(self.panel)
        return self.panel.grab().toImage()

    def release(self) -> None:
        """Hides the host and returns the panel to its original parent, or makes it a hidden window if it had none."""
        self.hide()
        self.panel.setParent(self._old_parent)
        self.panel.setVisible(self._panel_was_visible and self._old_parent is not None)


def _widget_label(widget: QWidget) -> str:
    """Returns a short identifier for a widget: its object name, or its class name and any short text it shows."""
    if widget.objectName() != '' and not widget.objectName().startswith('qt_'):
        return widget.objectName()
    label = type(widget).__name__
    text = ''
    if isinstance(widget, (QLabel, QAbstractButton)):
        text = widget.text()
    elif isinstance(widget, QGroupBox):
        text = widget.title()
    if QtGui.Qt.mightBeRichText(text):
        text = QTextDocumentFragment.fromHtml(text).toPlainText()
    text = text.replace('&', '').replace('\n', ' ').strip()
    if text != '':
        label += f" '{text[:24]}'"
    return label


def widget_path(widget: QWidget, root: QWidget) -> str:
    """Returns a widget's path from root, naming each step with _widget_label and a sibling index where labels repeat."""
    steps = []
    while widget is not root and widget is not None:
        parent = widget.parentWidget()
        label = _widget_label(widget)
        if parent is not None:
            same_label = [child for child in parent.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)
                          if _widget_label(child) == label]
            if len(same_label) > 1:
                label += f'[{same_label.index(widget)}]'
        steps.append(label)
        widget = parent
    return '/'.join(reversed(steps))


def _is_scroll_viewport(widget: QWidget) -> bool:
    parent = widget.parentWidget()
    return isinstance(parent, QAbstractScrollArea) and parent.viewport() is widget


def _is_qt_internal(widget: QWidget, root: QWidget) -> bool:
    """Returns whether a widget is, or is inside, a part Qt builds into a composite widget, like a spin box's line edit.

    A scroll area's viewport is the exception: it holds IntraPaint's own content.
    """
    while widget is not None and widget is not root:
        if widget.objectName().startswith('qt_') and not _is_scroll_viewport(widget):
            return True
        widget = widget.parentWidget()
    return False


def _rect_in(widget: QWidget, root: QWidget) -> QRect:
    return QRect(widget.mapTo(root, QPoint()), widget.size())


def _visible_rect(widget: QWidget, root: QWidget) -> QRect:
    """Returns the part of a widget its ancestors up to root don't clip, or up to a scroll area viewport if nearer.

    Content under a scroll area viewport is meant to extend past it, so clipping is only measured below the viewport.
    """
    visible = _rect_in(widget, root)
    ancestor = widget.parentWidget()
    while ancestor is not None and not _is_scroll_viewport(ancestor):
        visible = visible.intersected(_rect_in(ancestor, root))
        if ancestor is root:
            break
        ancestor = ancestor.parentWidget()
    return visible


def _layout_widgets(layout: QLayout) -> list[QWidget]:
    """Returns the widgets a layout and its nested layouts manage."""
    widgets = []
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is not None:
            widgets.append(item.widget())
        elif item.layout() is not None:
            widgets.extend(_layout_widgets(item.layout()))
    return widgets


def _ignores_size(widget: QWidget, orientation: Qt.Orientation) -> bool:
    policy = widget.sizePolicy()
    value = policy.horizontalPolicy() if orientation == Qt.Orientation.Horizontal else policy.verticalPolicy()
    return value == QSizePolicy.Policy.Ignored


def find_layout_problems(root: QWidget) -> list[str]:
    """Lists visible widgets under root that overlap, are clipped, or are smaller than their minimum size hint.

    - overlap: two widgets in the same layout whose rectangles intersect.
    - clipped: a widget partly cut off by an ancestor, measured as described in _visible_rect.
    - squeezed: a widget narrower or shorter than its minimum size hint, unless its size policy ignores hints in that
      direction.

    Parts Qt builds into composite widgets are left out, as _is_qt_internal describes.
    """
    problems = []
    widgets = [widget for widget in root.findChildren(QWidget)
               if widget.isVisibleTo(root) and not widget.isWindow() and not _is_qt_internal(widget, root)]
    for widget in [root, *widgets]:
        layout = widget.layout()
        if layout is None:
            continue
        managed = [child for child in _layout_widgets(layout)
                   if child.isVisibleTo(root) and not _is_qt_internal(child, root)]
        for i, first in enumerate(managed):
            for second in managed[i + 1:]:
                overlap = first.geometry().intersected(second.geometry())
                if not overlap.isEmpty():
                    problems.append(f'overlap: {widget_path(first, root)} and {widget_path(second, root)} '
                                    f'share {overlap.width()}x{overlap.height()}')
    for widget in widgets:
        path = widget_path(widget, root)
        full = _rect_in(widget, root)
        visible = _visible_rect(widget, root)
        if visible != full and not full.isEmpty():
            problems.append(f'clipped: {path} shows {visible.width()}x{visible.height()} of '
                            f'{full.width()}x{full.height()}')
        minimum = widget.minimumSizeHint()
        if not minimum.isValid():
            continue
        too_narrow = widget.width() < minimum.width() and not _ignores_size(widget, Qt.Orientation.Horizontal)
        too_short = widget.height() < minimum.height() and not _ignores_size(widget, Qt.Orientation.Vertical)
        if too_narrow or too_short:
            problems.append(f'squeezed: {path} is {widget.width()}x{widget.height()}, minimum '
                            f'{minimum.width()}x{minimum.height()}')
    return problems


def layout_report(size: QSize, problems: list[str]) -> dict:
    """Returns the JSON-compatible record of one panel capture."""
    return {'size': [size.width(), size.height()], 'problems': problems}


# Common screen sizes the main window is captured at, along with its minimum size:
WINDOW_SIZES = {'small': QSize(800, 600), 'hd': QSize(1280, 720), 'full_hd': QSize(1920, 1080),
                'ultrawide': QSize(3440, 1440), 'portrait': QSize(1080, 1920)}
# MainWindow shrinks itself to the screen, and the offscreen platform's screen is smaller than most of WINDOW_SIZES:
_LARGE_SCREEN = QSize(8192, 8192)


def _large_screen() -> AbstractContextManager:
    return patch('src.ui.window.main_window.get_screen_size', return_value=_LARGE_SCREEN)


@dataclass(frozen=True)
class PanelScene:
    """A panel to capture: its snapshot name, and a function that returns the panel from a mock-mode AppController.

    A scene with `fixed_sizes` is captured at its minimum size and those sizes, and other scenes at SIZE_CASES. Captures
    run inside the context manager `context` returns.
    """
    name: str
    build: Callable[['AppController'], Optional[QWidget]]
    fixed_sizes: Optional[dict[str, QSize]] = None
    context: Callable[[], AbstractContextManager] = nullcontext

    def sizes(self, panel: QWidget) -> dict[str, QSize]:
        """Returns the sizes to capture the panel at, by size case name."""
        if self.fixed_sizes is not None:
            return {'minimum': panel_size('minimum', panel), **self.fixed_sizes}
        return {case: panel_size(case, panel) for case in SIZE_CASES}


def _snake_case(name: str) -> str:
    return ''.join(f'_{char.lower()}' if char.isupper() and i > 0 else char.lower() for i, char in enumerate(name))


def _tool_control_scenes(controller: 'AppController') -> list[PanelScene]:
    # pylint: disable=protected-access
    scenes = []
    for tool in controller._tool_controller.tools:
        if tool.get_control_panel() is not None:
            scenes.append(PanelScene(_snake_case(type(tool).__name__) + '_controls',
                                     lambda _controller, panel_tool=tool: panel_tool.get_control_panel()))
    return scenes


def panel_scenes(controller: 'AppController') -> list[PanelScene]:
    """Returns every panel scene for a mock-mode AppController, in capture order.

    Later scenes take their panels out of the main window while they're captured, so the main window comes first.
    """
    # pylint: disable=import-outside-toplevel,protected-access
    from src.ui.panel.generators.stable_diffusion_panel import StableDiffusionPanel
    from src.ui.panel.layer_ui.layer_panel import LayerPanel
    # Panels that show the controller's ImageStack are the controller's own: a discarded copy would leave the stack
    # connected to deleted graphics items.
    return [
        PanelScene('main_window', lambda c: c._window, WINDOW_SIZES, _large_screen),
        PanelScene('tool_panel', lambda c: c._tool_panel),
        PanelScene('layer_panel', lambda c: c._tool_panel.findChild(LayerPanel)),
        PanelScene('color_panel', lambda c: c._tool_panel_color_picker),
        PanelScene('navigation_panel', lambda c: c._tool_panel_navigation_panel),
        PanelScene('sd_webui_panel', lambda _c: StableDiffusionPanel(True, True)),
        PanelScene('sd_comfyui_panel', lambda _c: StableDiffusionPanel(False, False)),
        *_tool_control_scenes(controller),
    ]


def mock_app_controller() -> 'AppController':
    """Restores config option lists with restore_option_lists, then returns a new AppController in mock mode."""
    # pylint: disable=import-outside-toplevel
    from src.controller.app_controller import AppController
    from src.util.arg_parser import build_arg_parser
    restore_option_lists()
    args = build_arg_parser(include_edit_params=False).parse_args([])
    args.mode = 'mock'
    args.server_url = ''
    args.fast_ngrok_connection = False
    return AppController(args)


def restore_option_lists() -> None:
    """Restores every AppConfig and Cache option list to its definition, so combo boxes hold all their options.

    IntraPaintTestCase's config reset trims option lists to the default value alone.
    """
    # pylint: disable=import-outside-toplevel
    from src.config.application_config import AppConfig
    from src.config.cache import Cache
    for config in (AppConfig(), Cache()):
        for key in config.get_keys():
            config.restore_default_options(key)

