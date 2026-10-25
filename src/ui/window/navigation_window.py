"""Shows the edited image in a small viewer, with controls for moving the main image view and the generation area.

The same panel fills the Navigation dock and the floating navigation window. It plans its own layout from its size:

- The viewer sits above the controls (`Orientation.SIDE`) or left of them (`Orientation.STRIP`), whichever leaves the
  viewer larger. The viewer is sized to the image's aspect ratio, so it shows no empty bands, and the panel's spare
  space goes after the controls.
- The controls are items for `src.ui.layout.panel_fit.plan_fit`: the mode toggle and Reset view are required, the hint
  and the zoom percentage are optional and hide where they don't fit. The hint is decorative, since the viewer's
  tooltip carries the same text.
- The panel's minimum size is the smaller of the two orientations' minimums with only required controls, so it doesn't
  depend on what the panel showed before.
"""
from functools import partial
from typing import Callable, Optional

from PySide6.QtCore import QEvent, QPoint, QSize, SignalInstance
from PySide6.QtGui import QIcon, Qt, QCursor, QMouseEvent, QPalette, QResizeEvent
from PySide6.QtWidgets import QWidget, QApplication, QBoxLayout, QGridLayout, QLabel, QPushButton, QSizePolicy

from src.config.cache import Cache
from src.controller.tool_controller import ToolController
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.tools.context_pin_dragger import ContextPinDragger
from src.tools.generation_area_tool import GenerationAreaTool, GEN_AREA_CONTROL_HINT
from src.ui.button_weight import ButtonWeight, set_button_weight
from src.ui.graphics_items.click_and_drag_selection import ClickAndDragSelection
from src.ui.image_viewer import ImageViewer
from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from src.ui.layout.dock_panel import QWIDGETSIZE_MAX
from src.ui.layout.panel_fit import (HYSTERESIS, REQUIRED, FitItem, Orientation, Placement, base_placement,
                                     fresh_minimum_size, held_weakly, orientation_for_size, plan_fit)
from src.ui.panel.image_panel import ImagePanel
from src.ui.widget.panel_header import GlyphButton
from src.util.shared_constants import APP_ICON_PATH, PROJECT_DIR

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.window.navigation_window'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


WINDOW_TITLE = _tr('Navigate')
ZOOM_LABEL = _tr('Move view')
ZOOM_TOOLTIP = _tr('Left-click to pan, Shift + left-click to draw viewport, right-click to add, move or remove '
                   'context pins')
IMAGE_GEN_LABEL = _tr('Move gen. area')
ZOOM_LABEL_SHORT = _tr('View')
IMAGE_GEN_LABEL_SHORT = _tr('Gen. area')
BUTTON_TEXT_RESET_VIEW = _tr('Reset view')
ZOOM_PERCENT_TEXT = _tr('Zoom {percent}%')
# Each hint is a list of lines, joined into one line where the panel has the width for it:
VIEW_HINT_LINES = (_tr('Drag: pan'), _tr('Shift+drag: draw new view'))
# Added to the viewer's tooltip in the view mode, which has room the hint line doesn't:
CONTEXT_PIN_HINT = _tr('Right-click: add, move or remove context pins')
GEN_AREA_HINT_LINES = (_tr('Drag: move area'), _tr('Right-drag: resize area'))
HINT_LINE_SEPARATOR = _tr(', ')

ICON_PATH_ZOOM_TOOL = f'{PROJECT_DIR}/resources/icons/tools/zoom_icon.svg'
ICON_PATH_GEN_AREA_TOOL = f'{PROJECT_DIR}/resources/icons/tools/gen_area_icon.svg'
MIN_AREA = 4

# Planner items, in `NavigationWindow._items` order:
TOGGLE_ITEM = 0
RESET_ITEM = 1
HINT_ITEM = 2
ZOOM_ITEM = 3
# Toggle forms, largest first:
TOGGLE_FULL_LABELS = 0
TOGGLE_SHORT_LABELS = 1
TOGGLE_ICONS = 2
# Reset view forms:
RESET_TEXT = 0
RESET_GLYPH = 1
# Hint forms. A strip tries the stacked lines first, since they leave the viewer more width. A side layout shows both
# forms as one line, since stacking lines there would only take height from the viewer:
HINT_STACKED = 0
HINT_ONE_LINE = 1


class ZoomTool(BaseTool):
    """Tool used to control the zoom level of the primary image view from within the navigation window."""

    def __init__(self, image_stack: ImageStack, main_view: ImageViewer, controller_view: ImageViewer) -> None:
        super().__init__('', ZOOM_LABEL, ZOOM_TOOLTIP, QIcon(ICON_PATH_ZOOM_TOOL))
        self._main_view = main_view
        self._control_view = controller_view
        scene = controller_view.scene()
        self._selection_handler = ClickAndDragSelection(scene)
        self._dragging = False
        self._pin_dragger = ContextPinDragger(image_stack, controller_view)
        self.cursor = QCursor(Qt.CursorShape.OpenHandCursor)

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        return f'{GEN_AREA_CONTROL_HINT}{BaseTool.fixed_aspect_hint()}{super().get_input_hint()}'

    def _move_view(self, image_coordinates: QPoint) -> None:
        initial_scene_pos = self._main_view.mapToScene(QPoint())
        offset_change = image_coordinates - initial_scene_pos.toPoint()
        initial_offset = self._main_view.offset
        final_offset = initial_offset + offset_change
        self._main_view.offset = final_offset

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Move the view on left-click, start resizing the view on Shift + left-click, and edit context pins on
           right-click."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.RightButton:
            return self._pin_dragger.press(event, image_coordinates)
        if event.buttons() == Qt.MouseButton.LeftButton:
            if not QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._move_view(image_coordinates)
                return True
            if self._selection_handler.selecting:
                self._selection_handler.end_selection(image_coordinates)
            aspect_ratio = self._main_view.width() / self._main_view.height()
            self._selection_handler.set_aspect_ratio(aspect_ratio)
            self._selection_handler.start_selection(image_coordinates)
            self._dragging = True
            return True
        return False

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Continue moving or resizing the view or dragging a context pin if mouse buttons are down."""
        assert event is not None
        if self._pin_dragger.move(event, image_coordinates):
            return True
        if event.buttons() == Qt.MouseButton.LeftButton:
            if self._dragging:
                self._selection_handler.drag_to(image_coordinates)
            else:
                self._move_view(image_coordinates)
            return True
        return False

    def mouse_release(self, _event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """If resizing, finish on mouse_release."""
        if self._pin_dragger.release(image_coordinates):
            return True
        if not self._dragging:
            return False
        self._dragging = False
        final_bounds = self._selection_handler.end_selection(image_coordinates).boundingRect().toAlignedRect()
        if MIN_AREA <= final_bounds.width() * final_bounds.height():
            self._main_view.zoom_to_bounds(final_bounds)
        return True

    def _on_deactivate(self) -> None:
        self._pin_dragger.finish()
        super()._on_deactivate()


class _NavigationBody(QWidget):
    """Holds the viewer and the controls, reports the sizes the panel planned, and asks it to plan again when
    resized."""

    def __init__(self, on_resize: Callable[[], None], parent: QWidget) -> None:
        super().__init__(parent)
        self._on_resize = held_weakly(on_resize)
        self.base_size = QSize()
        self.preferred_size = QSize()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the planned preferred size, or the layout's before the first plan."""
        return QSize(self.preferred_size) if self.preferred_size.isValid() else super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the planned minimum size, or the layout's before the first plan."""
        return QSize(self.base_size) if self.base_size.isValid() else super().minimumSizeHint()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Plans for the new size."""
        super().resizeEvent(event)
        self._on_resize()


class NavigationWindow(ImagePanel):
    """Shows the edited image in a small viewer, with controls for moving the main image view and the generation
    area."""

    def __init__(self, image_stack: ImageStack, main_image_view: ImageViewer, include_zoom_controls=True,
                 use_keybindings=False) -> None:
        super().__init__(image_stack, include_zoom_controls=include_zoom_controls, use_keybindings=use_keybindings)
        self._main_image_viewer = main_image_view
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle(WINDOW_TITLE)
        self._image_stack = image_stack
        self._tool_controller = ToolController(image_stack, self.image_viewer, False, False)
        self._tool_controller.active_tool_changed.connect(self._update_tool_slot)
        self._generation_area_tool = GenerationAreaTool(image_stack, self.image_viewer, show_handles=False)
        self._zoom_tool = ZoomTool(image_stack, main_image_view, self.image_viewer)
        self._tool_controller.active_tool = self._generation_area_tool
        self._tool_controller.active_tool = self._zoom_tool
        self.image_viewer.set_viewport_highlight(main_image_view.visible_scene_bounds)

        # Planning state:
        self._ready = False
        self._planning = False
        self._planned_size: Optional[QSize] = None
        self._orientation: Optional[Orientation] = None
        self._placement: Optional[Placement] = None
        self._items = (FitItem(REQUIRED, 3), FitItem(REQUIRED, 2), FitItem(1, 2), FitItem(2, 1))
        self._toggle_shown = True
        self._hint_lines: tuple[str, ...] = VIEW_HINT_LINES

        self._body = _NavigationBody(self._refit_for_size, self)
        self._body_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self.vertical_layout.removeWidget(self.image_viewer)
        self._body_layout.addWidget(self.image_viewer)
        self.vertical_layout.insertWidget(0, self._body, stretch=255)

        self._controls = QWidget(self._body)
        self._controls_layout = QGridLayout(self._controls)
        self._controls_layout.setContentsMargins(0, 0, 0, 0)

        # The stored values are the full labels, which `Cache.LAST_NAV_PANEL_TOOL` has always held:
        self._tool_toggle = SegmentedControl([Segment(ZOOM_LABEL, ZOOM_LABEL, ICON_PATH_ZOOM_TOOL,
                                                      f'{ZOOM_LABEL}\n{ZOOM_TOOLTIP}'),
                                              Segment(IMAGE_GEN_LABEL, IMAGE_GEN_LABEL, ICON_PATH_GEN_AREA_TOOL,
                                                      IMAGE_GEN_LABEL)], parent=self._controls)
        self._tool_toggle.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        initial_tool = Cache().get(Cache.LAST_NAV_PANEL_TOOL)
        if initial_tool == IMAGE_GEN_LABEL:
            self._tool_toggle.set_value(initial_tool)
            self._set_active_tool(initial_tool)
        self._tool_toggle.valueChanged.connect(self._set_active_tool)

        self._hint_label = QLabel(self._controls)
        self._hint_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)

        self._zoom_label: Optional[QLabel] = None
        self._reset_button: Optional[QPushButton] = None
        self._reset_glyph: Optional[GlyphButton] = None
        if not include_zoom_controls:
            self._zoom_label = QLabel(self._controls)
            self._zoom_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
            self._reset_button = QPushButton(BUTTON_TEXT_RESET_VIEW, self._controls)
            set_button_weight(self._reset_button, ButtonWeight.FLAT)
            self._reset_glyph = GlyphButton(GlyphButton.RESET, BUTTON_TEXT_RESET_VIEW)
            self._reset_glyph.setParent(self._controls)
            for button in (self._reset_button, self._reset_glyph):
                assert isinstance(button.clicked, SignalInstance)
                button.clicked.connect(self.image_viewer.reset_scale)
        self._body_layout.addWidget(self._controls)
        self._body_layout.addStretch(1)

        self.image_viewer.offset_changed.connect(self._local_offset_change_slot)
        self.image_viewer.scale_changed.connect(self._local_scale_change_slot)
        main_image_view.view_changed.connect(self._main_view_change_slot)
        main_image_view.scale_changed.connect(self._main_scale_change_slot)
        image_stack.size_changed.connect(self._image_size_change_slot)
        self._ready = True
        self._update_zoom_text()
        self._update_hint(self._tool_controller.active_tool)

    @property
    def mouse_navigation_enabled(self) -> bool:
        """Returns whether mouse events should be allowed to pan and zoom within the scene."""
        return self.image_viewer.mouse_navigation_enabled

    @mouse_navigation_enabled.setter
    def mouse_navigation_enabled(self, enabled: bool) -> None:
        self.image_viewer.mouse_navigation_enabled = enabled

    @property
    def tool_toggle(self) -> SegmentedControl:
        """Returns the control that switches between moving the view and moving the generation area."""
        return self._tool_toggle

    @property
    def orientation(self) -> Optional[Orientation]:
        """Returns whether the viewer is above the controls or left of them, or None before the first plan."""
        return self._orientation

    def set_image_generation_controls_visible(self, visible: bool) -> None:
        """Only show the tool toggle if generation area controls are visible."""
        if not visible and self._tool_controller.active_tool == self._generation_area_tool:
            self._tool_toggle.set_value(ZOOM_LABEL)
        self._toggle_shown = visible
        self._tool_toggle.setVisible(visible)
        super().set_image_generation_controls_visible(visible)
        self._refit()

    def _set_active_tool(self, tool_name: str) -> None:
        if tool_name == IMAGE_GEN_LABEL:
            self._tool_controller.active_tool = self._generation_area_tool
        elif tool_name == ZOOM_LABEL:
            self._tool_controller.active_tool = self._zoom_tool
        Cache().set(Cache.LAST_NAV_PANEL_TOOL, tool_name)

    def _update_tool_slot(self, active_tool: Optional[BaseTool]) -> None:
        if active_tool is None:
            return
        self.image_viewer.set_cursor(active_tool.cursor)
        self._update_hint(active_tool)

    def _update_hint(self, active_tool: Optional[BaseTool]) -> None:
        """Shows the hint for the active tool's controls, and copies it to the viewer's tooltip."""
        if not getattr(self, '_ready', False):
            return  # The tool controller activates its first tool before the controls exist.
        moving_area = active_tool == self._generation_area_tool
        self._hint_lines = GEN_AREA_HINT_LINES if moving_area else VIEW_HINT_LINES
        tooltip_lines = self._hint_lines if moving_area else (*self._hint_lines, CONTEXT_PIN_HINT)
        self.image_viewer.setToolTip('\n'.join(tooltip_lines))
        self._refit()

    def _reset_shown(self) -> bool:
        return self._reset_button is not None and not self.image_viewer.is_at_default_view

    def _local_offset_change_slot(self, _offset: QPoint) -> None:
        self._refit()

    def _local_scale_change_slot(self, _scale: float) -> None:
        self._refit()

    def _main_view_change_slot(self) -> None:
        self.image_viewer.set_viewport_highlight(self._main_image_viewer.visible_scene_bounds)

    def _main_scale_change_slot(self, _scale: float) -> None:
        self._update_zoom_text()

    def _image_size_change_slot(self, _size: QSize) -> None:
        self._refit()

    def _update_zoom_text(self) -> None:
        if self._zoom_label is not None:
            self._zoom_label.setText(ZOOM_PERCENT_TEXT.format(percent=round(self._main_image_viewer.scene_scale
                                                                            * 100)))
            self._refit()

    # -----------------------------------------------------------------------------------------------------------------
    # Layout planning
    # -----------------------------------------------------------------------------------------------------------------

    def changeEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """Plans again when the font or style changes the controls' sizes."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._refit()

    def _refit(self) -> None:
        """Plans again for the current size, after a change to the controls' content."""
        if self._planned_size is not None:
            self._plan(force=True)

    def _refit_for_size(self) -> None:
        self._plan()

    def _plan(self, force: bool = False) -> None:
        """Picks the orientation and the controls' forms for the body's size, and sizes the viewer.

        Each orientation gets its own `plan_fit` placement. One whose minimum size fits beats one that doesn't. Between
        two that fit, the one with the larger viewer wins, and the current orientation holds until the other's viewer
        is wider by more than `HYSTERESIS`. Trial placements resize nothing, so they don't start another plan.
        """
        if not self._ready:
            return
        available = self._body.size()
        if self._planning or (not force and available == self._planned_size):
            return
        self._planning = True
        try:
            self._planned_size = QSize(available)
            plans: dict[Orientation, tuple[bool, QSize, Placement]] = {}
            base_sizes: list[QSize] = []
            for orientation in (Orientation.SIDE, Orientation.STRIP):
                base_sizes.append(self._measure(orientation, base_placement(self._items)))
                current = self._placement if orientation == self._orientation else None
                placement = plan_fit(self._items, available, orientation, partial(self._measure, orientation),
                                     current)
                need = self._measure(orientation, placement)
                fits = need.width() <= available.width() and need.height() <= available.height()
                viewer = self._viewer_size(orientation, available, fresh_minimum_size(self._controls))
                plans[orientation] = (fits, viewer, placement)
            self._body.base_size = min(base_sizes, key=lambda size: (size.width() * size.height(), size.height()))
            self._body.preferred_size = self._preferred_size()
            orientation = self._choose_orientation(plans, available)
            placement = plans[orientation][2]
            self._apply(orientation, placement)
            self._orientation = orientation
            self._placement = placement
            viewer_size = self._viewer_size(orientation, available, fresh_minimum_size(self._controls))
            self.image_viewer.setFixedSize(viewer_size.expandedTo(self.image_viewer.minimumSizeHint()))
            # Applies the new arrangement now, so the controls' geometry doesn't wait on a posted layout request:
            self._controls_layout.activate()
            self._body_layout.activate()
            self._body.updateGeometry()
        finally:
            self._planning = False

    def _preferred_size(self) -> QSize:
        """Returns the size of a side layout with every control but the decorative hint in its largest form, and a
        viewer as wide as the controls and no taller than wide."""
        largest = tuple(None if index == HINT_ITEM else 0 for index in range(len(self._items)))
        controls_need = self._measure(Orientation.SIDE, largest)
        controls = fresh_minimum_size(self._controls)
        width = controls_need.width()
        image_size = self._image_stack.size
        viewer = QSize(width, width) if image_size.isEmpty() \
            else image_size.scaled(QSize(width, width), Qt.AspectRatioMode.KeepAspectRatio)
        return QSize(width, viewer.height() + self._body_layout.spacing() + controls.height())

    def _choose_orientation(self, plans: dict[Orientation, tuple[bool, QSize, Placement]],
                            available: QSize) -> Orientation:
        side_fits, side_viewer, _ = plans[Orientation.SIDE]
        strip_fits, strip_viewer, _ = plans[Orientation.STRIP]
        if side_fits != strip_fits:
            return Orientation.SIDE if side_fits else Orientation.STRIP
        if self._orientation is not None:
            other = Orientation.STRIP if self._orientation == Orientation.SIDE else Orientation.SIDE
            if plans[other][1].width() > plans[self._orientation][1].width() + HYSTERESIS:
                return other
            return self._orientation
        if side_viewer.width() != strip_viewer.width():
            return Orientation.SIDE if side_viewer.width() > strip_viewer.width() else Orientation.STRIP
        return orientation_for_size(available)

    def _viewer_size(self, orientation: Orientation, available: QSize, controls: QSize) -> QSize:
        """Returns the largest size with the image's aspect ratio that fits beside or above the controls."""
        spacing = self._body_layout.spacing()
        if orientation == Orientation.SIDE:
            space = QSize(available.width(), available.height() - controls.height() - spacing)
        else:
            space = QSize(available.width() - controls.width() - spacing, available.height())
        space = space.expandedTo(QSize(0, 0))
        image_size = self._image_stack.size
        if image_size.isEmpty():
            return space
        return image_size.scaled(space, Qt.AspectRatioMode.KeepAspectRatio)

    def _measure(self, orientation: Orientation, placement: Placement) -> QSize:
        """Arranges the controls for a placement, and returns the body's minimum size with the viewer at its
        minimum."""
        self._apply(orientation, placement)
        controls = fresh_minimum_size(self._controls)
        viewer = self.image_viewer.minimumSizeHint()
        spacing = self._body_layout.spacing()
        if orientation == Orientation.SIDE:
            return QSize(max(viewer.width(), controls.width()), viewer.height() + spacing + controls.height())
        return QSize(viewer.width() + spacing + controls.width(), max(viewer.height(), controls.height()))

    def _apply(self, orientation: Orientation, placement: Placement) -> None:
        """Arranges the viewer and the controls for an orientation and placement, leaving no trace of earlier ones."""
        side = orientation == Orientation.SIDE
        self._body_layout.setDirection(QBoxLayout.Direction.TopToBottom if side else QBoxLayout.Direction.LeftToRight)
        self.image_viewer.setMinimumSize(0, 0)
        self.image_viewer.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
        self._body_layout.setStretchFactor(self.image_viewer, 1)
        self._body_layout.setAlignment(self.image_viewer, Qt.AlignmentFlag.AlignHCenter if side
                                       else Qt.AlignmentFlag.AlignTop)
        # Spare space goes below the controls in a side layout, and to the controls column in a strip:
        self._body_layout.setStretchFactor(self._controls, 0 if side else 1)
        self._body_layout.setStretch(self._body_layout.count() - 1, 1 if side else 0)

        grid = self._controls_layout
        widgets = [widget for widget in (self._tool_toggle, self._hint_label, self._zoom_label, self._reset_button,
                                         self._reset_glyph) if widget is not None]
        for widget in widgets:
            grid.removeWidget(widget)
        for index in range(max(grid.rowCount(), grid.columnCount())):
            grid.setRowStretch(index, 0)
            grid.setColumnStretch(index, 0)

        toggle_form = placement[TOGGLE_ITEM]
        assert toggle_form is not None
        self._tool_toggle.set_display_mode(DisplayMode.ICON if toggle_form == TOGGLE_ICONS
                                           else DisplayMode.ICON_AND_LABEL)
        short = toggle_form == TOGGLE_SHORT_LABELS
        self._tool_toggle.set_segment_label(ZOOM_LABEL, ZOOM_LABEL_SHORT if short else ZOOM_LABEL)
        self._tool_toggle.set_segment_label(IMAGE_GEN_LABEL, IMAGE_GEN_LABEL_SHORT if short else IMAGE_GEN_LABEL)

        hint_form = placement[HINT_ITEM]
        stacked = hint_form == HINT_STACKED and not side
        self._hint_label.setText('\n'.join(self._hint_lines) if stacked
                                 else HINT_LINE_SEPARATOR.join(self._hint_lines))
        self._hint_label.setVisible(hint_form is not None)
        if self._zoom_label is not None:
            self._zoom_label.setVisible(placement[ZOOM_ITEM] is not None)
        reset: Optional[QWidget] = None
        if self._reset_button is not None and self._reset_glyph is not None:
            reset = self._reset_button if placement[RESET_ITEM] == RESET_TEXT else self._reset_glyph
            unused = self._reset_glyph if reset is self._reset_button else self._reset_button
            unused.setVisible(False)
            reset.setVisible(self._reset_shown())

        if side:
            # Mode toggle, spare space, zoom and Reset view on one row, and the hint below. Without the toggle, the
            # hint takes its place:
            hint_row = 1 if self._toggle_shown else 0
            grid.addWidget(self._tool_toggle, 0, 0)
            grid.addWidget(self._hint_label, hint_row, 0, 1, 1 if hint_row == 0 else 4)
            grid.setColumnStretch(1, 1)
            if self._zoom_label is not None:
                grid.addWidget(self._zoom_label, 0, 2)
            if reset is not None:
                grid.addWidget(reset, 0, 3)
        else:
            # One column: mode toggle, hint and zoom at the top, Reset view at the bottom:
            grid.addWidget(self._tool_toggle, 0, 0, Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(self._hint_label, 1, 0)
            if self._zoom_label is not None:
                grid.addWidget(self._zoom_label, 2, 0)
            grid.setRowStretch(3, 1)
            if reset is not None:
                grid.addWidget(reset, 4, 0, Qt.AlignmentFlag.AlignLeft)

    def resizeEvent(self, _event: Optional[QResizeEvent]) -> None:
        """Save navigation window bounds changes when visible."""
        if self.isVisible():
            Cache().save_bounds(Cache.SAVED_NAVIGATION_WINDOW_POS, self)
