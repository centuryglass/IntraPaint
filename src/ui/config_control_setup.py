"""
Creates UI input components linked to data_model.config values.
- Initial component values are read from config.
- Changes to the component update the corresponding config value.
- Changes to the config value are applied to the input (if necessary).
"""
from typing import Optional, List

from PyQt5.QtCore import Qt, QSize, QRect
from PyQt5.QtWidgets import QDoubleSpinBox, QLineEdit, QCheckBox, QComboBox, QPlainTextEdit, QHBoxLayout, QLabel, \
    QWidget, QSpinBox, QSlider
from PyQt5.QtGui import QFont, QFontMetrics

from src.config.config_entry import RangeKey
from src.image.layer_stack import LayerStack
from src.ui.widget.big_int_spinbox import BigIntSpinbox
from src.config.application_config import AppConfig

SELECTION_X_LABEL = 'X:'
SELECTION_Y_LABEL = 'Y:'
SELECTION_WIDTH_LABEL = 'W:'
SELECTION_HEIGHT_LABEL = 'H:'
SELECTION_X_TOOLTIP = 'Set the left edge position of the image generation area.'
SELECTION_Y_TOOLTIP = 'Set the top edge position of the image generation area.'
SELECTION_WIDTH_TOOLTIP = 'Set the width of the image generation area.'
SELECTION_HEIGHT_TOOLTIP = 'Set the top edge position of the image generation area.'


def connected_spinbox(parent: Optional[QWidget],
                      config: AppConfig,
                      key: str,
                      min_val: Optional[int | float] = None,
                      max_val: Optional[int | float] = None,
                      step_val: Optional[int | float] = None,
                      dict_key: Optional[str] = None) -> QDoubleSpinBox | BigIntSpinbox:
    """Creates a spinbox widget connected to a numeric config property.

    Properties can be either integer or floating point, but the type needs to be consistent with the config value's
    fixed type.

    Parameters
    ----------
    parent : QWidget or None
        Optional parent widget.
    config : AppConfig
        Shared application configuration object.
    key : str
        Numeric config value to connect to the spinbox.
    min_val : int or float or None
        Minimum spinbox value. If not provided and dict_key is None, use the minimum from config.
    max_val : int or float or None
        Maximum spinbox value. If not provided and dict_key is None, use the maximum from config.
    step_val : int or float or None
        Value for a single spinbox step. If not provided and dict_key is None, use the step value from config.
    dict_key : str or None
        If not None, the spinbox will be connected to the inner property of a dict config value.
    """
    initial_value = config.get(key, inner_key=dict_key)
    spinbox = QDoubleSpinBox(parent) if isinstance(initial_value, float) else BigIntSpinbox(parent)
    if initial_value < spinbox.minimum() or initial_value > spinbox.maximum():
        spinbox.setRange(min(spinbox.minimum(), initial_value), max(spinbox.maximum(), initial_value))
    min_width = spinbox.sizeHint().width()
    spinbox.setValue(initial_value)

    if dict_key is None and step_val is None:
        step = config.get(key, inner_key=RangeKey.STEP)
        spinbox.setSingleStep(step)
    elif step_val is not None:
        spinbox.setSingleStep(step_val)

    if dict_key is None and min_val is None:
        min_config_val = config.get(key, inner_key=RangeKey.MIN)
        spinbox.setRange(min_config_val, spinbox.maximum())
    elif min_val is not None:
        spinbox.setRange(min_val, spinbox.maximum())

    if dict_key is None and max_val is None:
        max_config_val = config.get(key, inner_key=RangeKey.MAX)
        spinbox.setRange(spinbox.minimum(), max_config_val)
    elif max_val is not None:
        spinbox.setRange(spinbox.minimum(), max_val)
        spinbox.setRange(min_val, spinbox.maximum())

    def apply_change_to_spinbox(new_value: int) -> None:
        """Update the spinbox when the config value changes."""
        if spinbox.value() != new_value:
            spinbox.setValue(new_value if new_value is not None else 0)

    config.connect(spinbox, key, apply_change_to_spinbox, inner_key=dict_key)

    def apply_change_to_config(new_value: int) -> None:
        """Update the config value when the spinbox changes."""
        num_value = int(new_value) if isinstance(initial_value, int) else float(new_value)
        if config.get(key, inner_key=dict_key) != num_value:
            config.set(key, num_value, inner_key=dict_key)

    spinbox.valueChanged.connect(apply_change_to_config)
    if dict_key is None:
        spinbox.setToolTip(config.get_tooltip(key))

    font = QFont()
    font.setPointSize(config.get(AppConfig.FONT_POINT_SIZE))
    longest_str = str(spinbox.maximum())
    if isinstance(initial_value, float) and '.' not in longest_str:
        longest_str += '.00'
    min_size = QFontMetrics(font).boundingRect(longest_str).size()
    min_size.setWidth(min_size.width() + min_width)
    spinbox.setMinimumSize(min_size)
    return spinbox


def connected_textedit(parent: Optional[QWidget],
                       config: AppConfig,
                       key: str,
                       multi_line: bool = False,
                       inner_key: Optional[str] = None) -> QLineEdit | QPlainTextEdit:
    """Creates a textedit widget connected to a string config property.

    Parameters
    ----------
    parent : QWidget or None
        Optional parent widget.
    config : data_model.config.Config
        Shared application configuration object.
    key : str
        String config value to connect to the textedit.
    multi_line : bool
        Whether the textedit should be multi-line.
    inner_key : str or none
        If not None, the textedit will be connected to the inner property of a dict config value.
    """
    textedit = QLineEdit(config.get(key), parent) if not multi_line else QPlainTextEdit(config.get(key), parent)
    if multi_line:
        textedit.textChanged.connect(lambda: config.set(key, textedit.toPlainText(), inner_key=inner_key))

        def set_text(new_text):
            """Copy config value changes to the text box."""
            if new_text != textedit.toPlainText():
                textedit.setPlainText(new_text if new_text is not None else '')

        config.connect(textedit, key, set_text, inner_key=inner_key)
    else:
        textedit.textChanged.connect(lambda new_content: config.set(key, new_content, inner_key=inner_key))

        def set_text(new_text):
            """Copy config value changes to the text box."""
            if new_text != textedit.text():
                textedit.setText(new_text if new_text is not None else '')

        config.connect(textedit, key, set_text, inner_key=inner_key)
    if inner_key is None:
        textedit.setToolTip(config.get_tooltip(key))
    return textedit


def connected_checkbox(parent: Optional[QWidget],
                       config: AppConfig,
                       key: str,
                       text: Optional[str] = None,
                       inner_key: Optional[str] = None) -> QCheckBox:
    """Creates a checkbox widget connected to a boolean config property.

    Parameters
    ----------
    parent : QWidget or None
        Optional parent widget.
    config : AppConfig
        Shared application configuration object.
    key : str
        Boolean config value to connect to the checkbox.
    text : str or None
        Optional label text
    inner_key : str or none
        If not None, the checkbox will be connected to the inner property of a dict config value.
    """
    checkbox = QCheckBox(parent)
    checkbox.setChecked(bool(config.get(key, inner_key)))
    checkbox.stateChanged.connect(lambda is_checked: config.set(key, bool(is_checked), inner_key=inner_key))
    config.connect(checkbox, key, lambda is_checked: checkbox.setChecked(bool(is_checked)), inner_key=inner_key)
    if text is not None:
        checkbox.setText(text)
    if inner_key is None:
        checkbox.setToolTip(config.get_tooltip(key))
    return checkbox


def connected_combobox(parent: Optional[QWidget],
                       config: AppConfig,
                       key: str,
                       text: Optional[str] = None) -> QComboBox | tuple[QComboBox, QHBoxLayout]:
    """Creates a combobox widget connected to a config property with a pre-defined  option list.

    Parameters
    ----------
    parent : QWidget or None
        Optional parent widget.
    config : AppConfig
        Shared application configuration object.
    key : str
        Config value to connect to the combobox.
    text : str or None
        Optional label text
    """
    combobox = QComboBox(parent)
    options = config.get_options(key)
    for option in options:
        combobox.addItem(option)
    default_value = config.get(key)
    combobox.setCurrentIndex(options.index(default_value))

    def apply_change_to_config(index):
        """Copy combo box changes to config."""
        value = combobox.itemText(index)
        config.set(key, value)

    combobox.currentIndexChanged.connect(apply_change_to_config)
    config.connect(combobox, key, lambda new_value: combobox.setCurrentIndex(options.index(new_value)))
    combobox.setToolTip(config.get_tooltip(key))
    if text is not None:
        label = QLabel(text)
        layout = QHBoxLayout()
        layout.addWidget(label)
        layout.addWidget(combobox)
        return combobox, layout
    return combobox


def get_selection_control_boxes(config: AppConfig,
                                layer_stack: LayerStack,
                                include_sliders: bool = False) -> List[QWidget]:
    """
    Creates and returns labeled widgets for controlling the image generation area selection.
    Parameters
    ----------
        config: AppConfig
            Used to load max bounds and synchronize the EDIT_SIZE parameter.
        layer_stack: LayerStack
            Edited image object responsible for maintaining the selected image generation area
        include_sliders: bool, default=False
            Whether the returned widgets should also contain sliders.
    Returns
    -------
        x_widget: QWidget
            Control for setting the selection's x-coordinate.
        y_widget: QWidget
            Control for setting the selection's y-coordinate.
        width: QWidget
            Control for setting the selection's width.
        width: QWidget
            Control for setting the selection's width.
        height: QWidget
            Control for setting the selection's height.
    """
    # Create widgets:
    control_widgets = []
    sliders = []
    spin_boxes = []
    for label_text, tooltip in ((SELECTION_X_LABEL, SELECTION_X_TOOLTIP), (SELECTION_Y_LABEL, SELECTION_Y_TOOLTIP),
                                (SELECTION_WIDTH_LABEL, SELECTION_WIDTH_TOOLTIP),
                                (SELECTION_HEIGHT_LABEL, SELECTION_HEIGHT_TOOLTIP)):
        widget = QWidget()
        widget.setToolTip(tooltip)
        layout = QHBoxLayout(widget)
        layout.setSpacing(0)
        label = QLabel(label_text)
        layout.addWidget(label, stretch=1)
        if include_sliders:
            slider = QSlider(Qt.Orientation.Horizontal)
            sliders.append(slider)
            layout.addWidget(slider, stretch=2)
        spin_box = QSpinBox()
        spin_boxes.append(spin_box)
        layout.addWidget(spin_box)
        control_widgets.append(widget)

    x_box, y_box, w_box, h_box = spin_boxes
    x_slider, y_slider, w_slider, h_slider = sliders if include_sliders else (None, None, None, None)

    # Set fixed ranges:
    min_edit_size = config.get(AppConfig.MIN_EDIT_SIZE)
    max_edit_size = config.get(AppConfig.MAX_EDIT_SIZE)
    for box, slider, min_val, max_val in ((w_box, w_slider, min_edit_size.width(), max_edit_size.width()),
                                          (h_box, h_slider, min_edit_size.height(), max_edit_size.height())):
        for control in filter(lambda ctrl_widget: ctrl_widget is not None, (box, slider)):
            control.setRange(min_val, max_val)
            control.setSingleStep(min_val)
    for coord_widget in x_box, x_slider, y_box, y_slider:
        if coord_widget is not None:
            coord_widget.setMinimum(0)

    # Apply selection changes to controls:
    control_sets = [spin_boxes]
    if include_sliders:
        control_sets.append(sliders)

    def set_coordinates(selection: QRect):
        """Use a selection rectangle and the LayerStack size to set all values and dynamic ranges."""
        for x_widget, y_widget, w_widget, h_widget in control_sets:
            for ctrl, value, maximum in ((x_widget, selection.x(), layer_stack.width - selection.width()),
                                         (y_widget, selection.y(), layer_stack.height - selection.height()),
                                         (w_widget, selection.width(), min(max_edit_size.width(), layer_stack.width)),
                                         (h_widget, selection.height(),
                                          min(max_edit_size.height(), layer_stack.height))):
                if value != ctrl.value():
                    ctrl.setValue(value)
                ctrl.setMaximum(maximum)

    set_coordinates(layer_stack.selection)
    layer_stack.selection_bounds_changed.connect(set_coordinates)

    def update_size_bounds(size: QSize):
        """Update the control bounds when the image size changes."""
        selection = layer_stack.selection
        for x_widget, y_widget, w_widget, h_widget in control_sets:
            for ctrl, maximum in ((x_widget, size.width() - selection.width()),
                                  (y_widget, size.height() - selection.height()),
                                  (w_widget, min(max_edit_size.width(), size.width())),
                                  (h_widget, min(max_edit_size.height(), size.height()))):
                ctrl.setMaximum(maximum)

    layer_stack.size_changed.connect(update_size_bounds)

    # Apply control changes to selection:
    for x_ctrl, y_ctrl, w_ctrl, h_ctrl in control_sets:
        def set_x(value: int):
            """Handle selection x-coordinate changes."""
            last_selected = layer_stack.selection
            if value != last_selected.x():
                last_selected.moveLeft(min(value, layer_stack.width - last_selected.width()))
                layer_stack.selection = last_selected

        x_ctrl.valueChanged.connect(set_x)

        def set_y(value: int):
            """Handle selection y-coordinate changes."""
            last_selected = layer_stack.selection
            if value != last_selected.y():
                last_selected.moveTop(min(value, layer_stack.height - last_selected.height()))
                layer_stack.selection = last_selected

        y_ctrl.valueChanged.connect(set_y)

        def set_w(value: int):
            """Handle selection width changes."""
            selection = layer_stack.selection
            if selection.width() != value:
                selection.setWidth(value)
                layer_stack.selection = selection

        w_ctrl.valueChanged.connect(set_w)

        def set_h(value: int):
            """Handle selection height changes."""
            selection = layer_stack.selection
            if selection.height() != value:
                selection.setHeight(value)
                layer_stack.selection = selection

        h_ctrl.valueChanged.connect(set_h)
    return control_widgets