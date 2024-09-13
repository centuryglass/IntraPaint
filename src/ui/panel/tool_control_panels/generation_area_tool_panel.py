"""Control panel for the GenerationAreaTool."""
from typing import List, cast, Tuple

from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtWidgets import QApplication, QWidget, QGridLayout, QPushButton, QHBoxLayout, QLabel, QSlider, QSpinBox, \
    QSizePolicy

from src.config.application_config import AppConfig
from src.image.layers.image_stack import ImageStack
from src.image.layers.transform_layer import TransformLayer
from src.ui.input_fields.size_field import SizeField
from src.ui.layout.divider import Divider

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panel.generation_area_tool_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


GENERATION_AREA_LABEL = _tr('Image generation area:')
GENERATION_AREA_X_LABEL = _tr('X:')
GENERATION_AREA_Y_LABEL = _tr('Y:')
GENERATION_AREA_WIDTH_LABEL = _tr('W:')
GENERATION_AREA_HEIGHT_LABEL = _tr('H:')
GENERATION_AREA_X_TOOLTIP = _tr('Set the left edge position of the image generation area.')
GENERATION_AREA_Y_TOOLTIP = _tr('Set the top edge position of the image generation area.')
GENERATION_AREA_WIDTH_TOOLTIP = _tr('Set the width of the image generation area.')
GENERATION_AREA_HEIGHT_TOOLTIP = _tr('Set the top edge position of the image generation area.')
GEN_RESOLUTION_LABEL = _tr('Image generation resolution:')

BUTTON_LABEL_FILL_IMAGE = _tr('Select full image')
BUTTON_LABEL_AREA_TO_RES = _tr('Gen. area size to resolution')
BUTTON_LABEL_RES_TO_AREA = _tr('Resolution to gen. area size')

BUTTON_TOOLTIP_FILL_IMAGE = _tr('Send the entire image during image generation.')
BUTTON_TOOLTIP_AREA_TO_RES = _tr('Set the generation area size to the image generation resolution')
BUTTON_TOOLTIP_RES_TO_AREA = _tr('Set the image generation resolution to the current generation area size.')


class GenerationAreaToolPanel(QWidget):
    """Control panel for the GenerationAreaTool."""
    def __init__(self, image_stack: ImageStack):
        super().__init__()
        self._layout = QGridLayout(self)
        self._orientation = Qt.Orientation.Horizontal

        self._gen_area_label = QLabel(GENERATION_AREA_LABEL)
        self._gen_area_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # wire x/y coordinate boxes to set image generation area coordinates:
        self._coordinate_controls: List[Tuple[QWidget, QWidget, QWidget]] = []
        control_boxes = get_generation_area_control_boxes(image_stack, True)

        def _extract_widgets(idx: int) -> Tuple[QWidget, ...]:
            return tuple(cast(QWidget, child) for child in control_boxes[idx].children() if isinstance(child, QWidget))
        self._x_label, self._x_slider, self._x_spinbox = _extract_widgets(0)
        self._y_label, self._y_slider, self._y_spinbox = _extract_widgets(1)
        self._w_label, self._w_slider, self._w_spinbox = _extract_widgets(2)
        self._h_label, self._h_slider, self._h_spinbox = _extract_widgets(3)

        def select_full_image() -> None:
            """Expand the image generation area to fit the entire image."""
            image_stack.generation_area = image_stack.bounds

        self._select_layer_button = QPushButton()
        self._select_layer_button.setText(BUTTON_LABEL_FILL_IMAGE)
        self._select_layer_button.setToolTip(BUTTON_TOOLTIP_FILL_IMAGE)
        self._select_layer_button.clicked.connect(select_full_image)
        self._select_layer_button.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)

        self._match_resolution_button = QPushButton()
        self._match_resolution_button.setText(BUTTON_LABEL_AREA_TO_RES)
        self._match_resolution_button.setToolTip(BUTTON_TOOLTIP_AREA_TO_RES)
        self._match_resolution_button.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)

        def _area_to_res() -> None:
            gen_area = image_stack.generation_area
            gen_area.setSize(AppConfig().get(AppConfig.GENERATION_SIZE))
            image_stack.generation_area = gen_area
        self._match_resolution_button.clicked.connect(_area_to_res)

        self._gen_size_label = QLabel(GEN_RESOLUTION_LABEL)
        self._gen_size_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._gen_size_control = cast(SizeField, AppConfig().get_control_widget(AppConfig.GENERATION_SIZE))
        self._gen_size_control.layout().setAlignment(Qt.AlignmentFlag.AlignTop)
        self._gen_size_control.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._match_area_button = QPushButton()
        self._match_area_button.setText(BUTTON_LABEL_RES_TO_AREA)
        self._match_area_button.setToolTip(BUTTON_TOOLTIP_RES_TO_AREA)
        self._match_area_button.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)

        def _res_to_area() -> None:
            area_size = image_stack.generation_area.size()
            AppConfig().set(AppConfig.GENERATION_SIZE, area_size)
        self._match_area_button.clicked.connect(_res_to_area)
        self._build_layout()

    def _build_layout(self) -> None:
        while self._layout.count() > 0:
            item = self._layout.itemAt(0)
            assert item is not None
            widget = item.widget()
            assert widget is not None
            if isinstance(widget, Divider):
                widget.hide()
            self._layout.takeAt(0)
        for grid_col in range(self._layout.columnCount()):
            self._layout.setColumnStretch(grid_col, 0)
        for grid_row in range(self._layout.rowCount()):
            self._layout.setRowStretch(grid_row, 0)

        def _add(added_widget: QWidget, row: int, col: int, row_span: int = 1, col_span: int = 1):
            self._layout.addWidget(added_widget, row, col, row_span, col_span)

        if self._orientation == Qt.Orientation.Horizontal:
            self._layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self._layout.setColumnStretch(3, 10)
            self._layout.setColumnStretch(9, 10)
            _add(Divider(Qt.Orientation.Horizontal), 0, 0, 1, 12)
            _add(self._gen_area_label, 1, 0, 1, 12)

            _add(self._x_label, 2, 0)
            _add(self._x_slider, 2, 1, 1, 4)
            _add(self._x_spinbox, 2, 5)
            _add(self._y_label, 3, 0)
            _add(self._y_slider, 3, 1, 1, 4)
            _add(self._y_spinbox, 3, 5)

            _add(self._w_label, 2, 6)
            _add(self._w_slider, 2, 7, 1, 4)
            _add(self._w_spinbox, 2, 11)

            _add(self._h_label, 3, 6)
            _add(self._h_slider, 3, 7, 1, 4)
            _add(self._h_spinbox, 3, 11)
            _add(self._select_layer_button, 4, 0, 1, 12)
            _add(self._match_resolution_button, 5, 0, 1, 12)

            _add(Divider(Qt.Orientation.Horizontal), 6, 0, 1, 12)
            _add(self._gen_size_label, 7, 0, 1, 12)
            self._gen_size_control.orientation = Qt.Orientation.Horizontal
            _add(self._gen_size_control, 8, 0, 1, 12)
            _add(self._match_area_button, 9, 0, 1, 12)
        else:
            self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            _add(Divider(Qt.Orientation.Horizontal), 0, 0, 1, 6)
            _add(self._gen_area_label, 1, 0, 1, 6)

            _add(self._x_label, 2, 0)
            _add(self._x_slider, 2, 1, 1, 4)
            _add(self._x_spinbox, 2, 5)
            _add(self._y_label, 3, 0)
            _add(self._y_slider, 3, 1, 1, 4)
            _add(self._y_spinbox, 3, 5)

            _add(self._w_label, 4, 0)
            _add(self._w_slider, 4, 1, 1, 4)
            _add(self._w_spinbox, 4, 5)
            _add(self._h_label, 5, 0)
            _add(self._h_slider, 5, 2, 1, 4)
            _add(self._h_spinbox, 5, 5)
            _add(self._select_layer_button, 6, 0, 1, 3)
            _add(self._match_resolution_button, 6, 3, 1, 3)
            _add(Divider(Qt.Orientation.Horizontal), 7, 0, 1, 5)
            _add(self._gen_size_label, 8, 0, 1, 6)
            self._gen_size_control.orientation = Qt.Orientation.Horizontal
            _add(self._gen_size_control, 9, 0, 2, 6)
            _add(self._match_area_button, 11, 0, 1, 6)

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Update the panel orientation."""
        if self._orientation != orientation:
            self._orientation = orientation
            self._build_layout()


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
