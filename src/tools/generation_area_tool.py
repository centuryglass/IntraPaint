"""An image editing tool that moves the selected editing region."""

from typing import Optional, cast, List

from PySide6.QtCore import Qt, QRect, QPoint, QSize
from PySide6.QtGui import QMouseEvent, QKeyEvent, QCursor, QIcon, QKeySequence
from PySide6.QtWidgets import QWidget, QApplication, QPushButton, QGridLayout, QHBoxLayout, QLabel, QSlider, QSpinBox

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.image.layers.transform_layer import TransformLayer
from src.tools.base_tool import BaseTool
from src.ui.image_viewer import ImageViewer
from src.ui.layout.divider import Divider
from src.util.shared_constants import PROJECT_DIR


# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.generation_area_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


RESOURCES_GENERATION_AREA_ICON = f'{PROJECT_DIR}/resources/icons/tools/gen_area_icon.svg'
GENERATION_AREA_LABEL = _tr('Set Image Generation Area')
GENERATION_AREA_TOOLTIP = _tr('Select an image region for AI image generation')
SELECT_LAYER_BUTTON_TEXT = _tr('Full image as generation area')
SELECT_LAYER_BUTTON_TOOLTIP = _tr('Send the entire image during image generation.')
GEN_AREA_CONTROL_HINT = _tr('LMB:move area - RMB:resize area - ')

GENERATION_AREA_X_LABEL = _tr('X:')
GENERATION_AREA_Y_LABEL = _tr('Y:')
GENERATION_AREA_WIDTH_LABEL = _tr('W:')
GENERATION_AREA_HEIGHT_LABEL = _tr('H:')
GENERATION_AREA_X_TOOLTIP = _tr('Set the left edge position of the image generation area.')
GENERATION_AREA_Y_TOOLTIP = _tr('Set the top edge position of the image generation area.')
GENERATION_AREA_WIDTH_TOOLTIP = _tr('Set the width of the image generation area.')
GENERATION_AREA_HEIGHT_TOOLTIP = _tr('Set the top edge position of the image generation area.')


class GenerationAreaTool(BaseTool):
    """An image editing tool that moves the selected editing region."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__()
        self._image_stack = image_stack
        self._image_viewer = image_viewer
        self._icon = QIcon(RESOURCES_GENERATION_AREA_ICON)
        self._resizing = False
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        self._control_panel: Optional[QWidget] = None
        self._control_layout: Optional[QGridLayout] = None

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.GENERATION_AREA_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return GENERATION_AREA_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return GENERATION_AREA_TOOLTIP

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        return f'{GEN_AREA_CONTROL_HINT}{BaseTool.fixed_aspect_hint()}{super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        if self._control_panel is not None:
            return self._control_panel
        self._control_panel = QWidget()
        self._control_layout = QGridLayout(self._control_panel)
        self._control_layout.setSpacing(20)
        self._control_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        for i, stretch in enumerate((0, 8, 1)):
            self._control_layout.setColumnStretch(i, stretch)
        self._control_layout.addWidget(Divider(Qt.Orientation.Horizontal), 0, 0, 1, 3)
        # self._control_layout.setRowMinimumHeight(0, 100)

        # wire x/y coordinate boxes to set image generation area coordinates:
        coordinate_controls = get_generation_area_control_boxes(self._image_stack, True)
        for control_widget in coordinate_controls:
            row = self._control_layout.rowCount()
            ctrl_label, ctrl_slider, ctrl_box = (cast(QWidget, child) for child in control_widget.children()
                                                 if isinstance(child, QWidget))
            self._control_layout.addWidget(ctrl_label, row, 0)
            self._control_layout.addWidget(ctrl_slider, row, 1)
            self._control_layout.addWidget(ctrl_box, row, 2)
        for row in range(1, self._control_layout.rowCount(), 1):
            self._control_layout.setRowStretch(row, 1)

        def select_full_layer():
            """Expand the image generation area to fit the entire active layer."""
            active_layer = self._image_stack.active_layer
            if isinstance(active_layer, TransformLayer):
                self._image_stack.generation_area = active_layer.transformed_bounds
            else:
                self._image_stack.generation_area = active_layer.bounds

        select_layer_button = QPushButton()
        select_layer_button.setText(SELECT_LAYER_BUTTON_TEXT)
        select_layer_button.setToolTip(SELECT_LAYER_BUTTON_TOOLTIP)
        select_layer_button.clicked.connect(select_full_layer)
        self._control_layout.addWidget(select_layer_button, self._control_layout.rowCount(), 0, 1, 3)

        return self._control_panel

    def _move_generation_area(self, selection_pt: QPoint) -> None:
        """Updates the image generation area's location in the image."""
        self._image_stack.generation_area = QRect(selection_pt, self._image_stack.generation_area.size())

    def _resize_generation_area(self, bottom_right: QPoint) -> None:
        """Updates the image generation area's size in the image."""
        generation_area = self._image_stack.generation_area
        width = min(self._image_stack.width - generation_area.x(), bottom_right.x() - generation_area.x())
        height = min(self._image_stack.height - generation_area.y(), bottom_right.y() - generation_area.y())
        if width > 0 and height > 0:
            if KeyConfig.modifier_held(KeyConfig.FIXED_ASPECT_MODIFIER):
                width = max(width, height)
                height = max(width, height)
            self._image_stack.generation_area = QRect(generation_area.x(), generation_area.y(), width, height)

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Move the image generation area on left-click, start resizing on right-click."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.LeftButton:
            if QApplication.keyboardModifiers() != Qt.KeyboardModifier.NoModifier:
                return False
            self._move_generation_area(image_coordinates)
        elif event.buttons() == Qt.MouseButton.RightButton:
            self._image_viewer.follow_generation_area = False
            self._resizing = True
            self._resize_generation_area(image_coordinates)
        else:
            return False
        return True

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """If resizing, dynamically adjust the image generation area if the new size would be non-empty."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.LeftButton:
            return self.mouse_click(event, image_coordinates)
        if event.buttons() == Qt.MouseButton.RightButton and self._resizing:
            self._resize_generation_area(image_coordinates)
            return True
        return False

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """If resizing, finish on mouse_release."""
        self._resizing = False
        return False

    def key_event(self, event: Optional[QKeyEvent]) -> bool:
        """Move image generation area with arrow keys."""
        assert event is not None
        translation = QPoint(0, 0)
        multiplier = 10 if KeyConfig().modifier_held(KeyConfig.SPEED_MODIFIER) else 1
        match event.key():
            case Qt.Key.Key_Left:
                translation.setX(-1 * multiplier)
            case Qt.Key.Key_Right:
                translation.setX(1 * multiplier)
            case Qt.Key.Key_Up:
                translation.setY(-1 * multiplier)
            case Qt.Key.Key_Down:
                translation.setY(1 * multiplier)
            case _:
                return False
        self._image_stack.generation_area = self._image_stack.generation_area.translated(translation)
        return True


def get_generation_area_control_boxes(image_stack: ImageStack,
                                      include_sliders: bool = False) -> List[QWidget]:
    """
    Creates and returns labeled widgets for controlling the image generation area.
    Parameters
    ----------
        image_stack: ImageStack
            Edited image object responsible for maintaining the selected image generation area
        include_sliders: bool, default=False
            Whether the returned widgets should also contain sliders.
    Returns
    -------
        x_widget: QWidget
            Control for setting the area's x-coordinate.
        y_widget: QWidget
            Control for setting the area's y-coordinate.
        width: QWidget
            Control for setting the area's width.
        width: QWidget
            Control for setting the area's width.
        height: QWidget
            Control for setting the area's height.
    """
    config = AppConfig()
    # Create widgets:
    control_widgets = []
    sliders = []
    spin_boxes = []
    for label_text, tooltip in (
            (GENERATION_AREA_X_LABEL, GENERATION_AREA_X_TOOLTIP),
            (GENERATION_AREA_Y_LABEL, GENERATION_AREA_Y_TOOLTIP),
            (GENERATION_AREA_WIDTH_LABEL, GENERATION_AREA_WIDTH_TOOLTIP),
            (GENERATION_AREA_HEIGHT_LABEL, GENERATION_AREA_HEIGHT_TOOLTIP)):
        widget = QWidget()
        widget.setToolTip(tooltip)
        layout = QHBoxLayout(widget)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(label_text)
        layout.addWidget(label, stretch=1)
        if include_sliders:
            new_slider = QSlider(Qt.Orientation.Horizontal)
            new_slider.setContentsMargins(1, 1, 1, 1)
            sliders.append(new_slider)
            layout.addWidget(new_slider, stretch=2)
        spin_box = QSpinBox()
        spin_boxes.append(spin_box)
        layout.addWidget(spin_box)
        control_widgets.append(widget)

    assert len(spin_boxes) == 4
    x_box, y_box, w_box, h_box = spin_boxes
    x_slider, y_slider, w_slider, h_slider = sliders if include_sliders else (None, None, None, None)

    # Set fixed ranges:
    min_edit_size = config.get(AppConfig.MIN_EDIT_SIZE)
    max_edit_size = config.get(AppConfig.MAX_EDIT_SIZE)
    for box, slider, min_val, max_val in ((w_box, w_slider, min_edit_size.width(), max_edit_size.width()),
                                          (h_box, h_slider, min_edit_size.height(), max_edit_size.height())):
        for control in (box, slider):
            if control is not None:
                control.setRange(min_val, max_val)
                control.setSingleStep(1)
    for coord_widget in x_box, x_slider, y_box, y_slider:
        if coord_widget is not None:
            coord_widget.setMinimum(0)

    # Apply image generation area changes to controls:
    control_sets = [spin_boxes]
    if include_sliders:
        control_sets.append(sliders)

    def set_coordinates(new_area: QRect):
        """Use image generation area bounds and the ImageStack size to set all values and dynamic ranges."""
        for x_widget, y_widget, w_widget, h_widget in control_sets:
            for ctrl, value, maximum in ((x_widget, new_area.x(), image_stack.width - new_area.width()),
                                         (y_widget, new_area.y(), image_stack.height - new_area.height()),
                                         (w_widget, new_area.width(), min(max_edit_size.width(), image_stack.width)),
                                         (h_widget, new_area.height(),
                                          min(max_edit_size.height(), image_stack.height))):
                if value != ctrl.value():
                    ctrl.setValue(value)
                ctrl.setMaximum(maximum)

    set_coordinates(image_stack.generation_area)
    image_stack.generation_area_bounds_changed.connect(set_coordinates)

    def update_size_bounds(size: QSize):
        """Update the control bounds when the image size changes."""
        generation_area = image_stack.generation_area
        for x_widget, y_widget, w_widget, h_widget in control_sets:
            for ctrl, maximum in ((x_widget, size.width() - generation_area.width()),
                                  (y_widget, size.height() - generation_area.height()),
                                  (w_widget, min(max_edit_size.width(), size.width())),
                                  (h_widget, min(max_edit_size.height(), size.height()))):
                ctrl.setMaximum(maximum)

    image_stack.size_changed.connect(update_size_bounds)

    # Apply control changes to image generation area:
    for x_ctrl, y_ctrl, w_ctrl, h_ctrl in control_sets:
        def set_x(value: int):
            """Handle image generation area x-coordinate changes."""
            last_selected = image_stack.generation_area
            if value != last_selected.x():
                last_selected.moveLeft(min(value, image_stack.width - last_selected.width()))
                image_stack.generation_area = last_selected

        x_ctrl.valueChanged.connect(set_x)

        def set_y(value: int):
            """Handle image generation area y-coordinate changes."""
            last_area = image_stack.generation_area
            if value != last_area.y():
                last_area.moveTop(min(value, image_stack.height - last_area.height()))
                image_stack.generation_area = last_area

        y_ctrl.valueChanged.connect(set_y)

        def set_w(value: int):
            """Handle image generation area width changes."""
            generation_area = image_stack.generation_area
            if generation_area.width() != value:
                generation_area.setWidth(value)
                image_stack.generation_area = generation_area

        w_ctrl.valueChanged.connect(set_w)

        def set_h(value: int):
            """Handle image generation area height changes."""
            generation_area = image_stack.generation_area
            if generation_area.height() != value:
                generation_area.setHeight(value)
                image_stack.generation_area = generation_area

        h_ctrl.valueChanged.connect(set_h)
    return control_widgets
