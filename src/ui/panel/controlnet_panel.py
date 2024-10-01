"""
Panel providing controls for the stable-diffusion ControlNet extension. Only supported by stable_diffusion_controller.
"""
import logging
from typing import Optional, List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QPushButton, QLineEdit, QComboBox, QApplication, QTabWidget, QGridLayout, \
    QLabel, QWidget

from src.config.cache import Cache
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox, FloatSliderSpinbox
from src.ui.layout.bordered_widget import BorderedWidget
from src.ui.layout.divider import Divider
from src.ui.modal.modal_utils import open_image_file
from src.util.layout import clear_layout
from src.util.parameter import Parameter, TYPE_FLOAT, TYPE_INT
from src.util.shared_constants import CONTROLNET_REUSE_IMAGE_CODE
from src.util.signals_blocked import signals_blocked

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.controlnet_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


# UI/Label text:
CONTROLNET_TITLE = _tr('ControlNet')
CONTROLNET_UNIT_TITLE = _tr('ControlNet Unit {unit_number}')
ENABLE_CONTROLNET_CHECKBOX_LABEL = _tr('Enable ControlNet Unit')
LOW_VRAM_LABEL = _tr('Low VRAM')
PX_PERFECT_CHECKBOX_LABEL = _tr('Pixel Perfect')
CONTROL_IMAGE_LABEL = _tr('Control Image:')
CONTROL_IMAGE_BUTTON_LABEL = _tr('Set Control Image')
GENERATION_AREA_AS_CONTROL = _tr('Generation Area as Control')
CONTROL_TYPE_BOX_TITLE = _tr('Control Type')
MODULE_BOX_TITLE = _tr('Control Module')
MODEL_BOX_TITLE = _tr('Control Model')
CONTROL_WEIGHT_TITLE = _tr('Control Weight')
CONTROL_START_STEP_TITLE = _tr('Starting Control Step')
CONTROL_END_STEP_TITLE = _tr('Ending Control Step')

# Config/request body keys:
CONTROL_CONFIG_LOW_VRAM_KEY = 'low_vram'
CONTROL_CONFIG_PX_PERFECT_KEY = 'pixel_perfect'
CONTROL_CONFIG_IMAGE_KEY = 'image'

# API response body keys:
MODULE_LIST_KEY = 'module_list'
MODULE_DETAIL_KEY = 'module_detail'
CONTROL_WEIGHT_KEY = 'weight'
CONTROL_START_STEP_KEY = 'guidance_start'
CONTROL_END_STEP_KEY = 'guidance_end'
CONTROL_SLIDER_DEF_KEY = 'sliders'
SLIDER_NAME_KEY = 'name'
SLIDER_TITLE_KEY = 'display'
SLIDER_VALUE_KEY = 'value'
SLIDER_MIN_KEY = 'min'
SLIDER_MAX_KEY = 'max'
SLIDER_RES_KEY = 'Resolution'
SLIDER_STEP_KEY = 'step'
CONTROL_RESOLUTION_KEY = 'processor_res'
CONTROL_MODULE_PARAM_1_KEY = 'threshold_a'
CONTROL_MODULE_PARAM_2_KEY = 'threshold_b'
DEFAULT_MODEL_KEY = 'default_model'
MODEL_LIST_KEY = 'model_list'
DEFAULT_OPTION_KEY = 'default_option'
CONTROL_MODULE_KEY = 'module'
CONTROL_MODEL_KEY = 'model'
# Default parameters used in ControlNet requests for all modules/models
DEFAULT_PARAMS = ['module', 'model', 'low_vram', 'pixel_perfect', 'image', 'weight', 'guidance_start',
                  'guidance_end']

# Defaults:
DEFAULT_CONTROL_TYPE = 'All'
DEFAULT_MODULE_NAME = 'none'
DEFAULT_MODEL_NAME = 'none'


class TabbedControlnetPanel(QTabWidget):
    """Tabbed ControlNet panel with three ControlNet units."""

    def __init__(self,
                 control_types: Optional[dict],
                 module_detail: dict,
                 model_list: dict):
        """Initializes the panel based on data from the stable-diffusion-webui.

        Parameters
        ----------
        control_types : dict or None
            API data defining available control types. If none, only the module and model dropdowns are used.
        module_detail : dict
            API data defining available ControlNet modules.
        model_list : dict
            API data defining available ControlNet models.
        """
        super().__init__()
        self._panel1 = ControlnetPanel(Cache.CONTROLNET_ARGS_0, control_types, module_detail, model_list)
        self._panel2 = ControlnetPanel(Cache.CONTROLNET_ARGS_1, control_types, module_detail, model_list)
        self._panel3 = ControlnetPanel(Cache.CONTROLNET_ARGS_2, control_types, module_detail, model_list)
        self.addTab(self._panel1, CONTROLNET_UNIT_TITLE.format(unit_number='1'))
        self.addTab(self._panel2, CONTROLNET_UNIT_TITLE.format(unit_number='2'))
        self.addTab(self._panel3, CONTROLNET_UNIT_TITLE.format(unit_number='3'))

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Sets the active panel orientation"""
        self._panel1.set_orientation(orientation)
        self._panel2.set_orientation(orientation)
        self._panel3.set_orientation(orientation)


class ControlnetPanel(BorderedWidget):
    """ControlnetPanel provides controls for the stable-diffusion ControlNet extension."""

    def __init__(self,
                 cache_key: str,
                 control_types: Optional[dict],
                 module_detail: dict,
                 model_list: dict):
        """Initializes the panel based on data from the stable-diffusion-webui.

        Parameters
        ----------
        cache_key : str, default = Cache.CONTROLNET_ARGS_0
            Cache key where ControlNet settings will be saved.
        control_types : dict or None
            API data defining available control types. If none, only the module and model dropdowns are used.
        module_detail : dict
            API data defining available ControlNet modules.
        model_list : dict
            API data defining available ControlNet models.
        """
        super().__init__()
        if isinstance(control_types, dict) and len(control_types) == 0:
            control_types = None
        assert isinstance(model_list, dict)
        if MODEL_LIST_KEY not in model_list:
            raise KeyError(f'Controlnet model list had unexpected structure: {model_list}')
        cache = Cache()
        initial_control_state = cache.get(cache_key)
        self._saved_state = initial_control_state
        self._cache_key = cache_key
        self._control_types = control_types
        self._module_detail = module_detail
        self._model_list = model_list
        self._orientation = Qt.Orientation.Horizontal
        self._layout = QGridLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._dynamic_sliders: List[FloatSliderSpinbox | IntSliderSpinbox] = []
        self._dynamic_slider_labels: List[QLabel] = []

        # Labels:
        self._control_image_label = QLabel(CONTROL_IMAGE_LABEL)
        self._module_label = QLabel(MODULE_BOX_TITLE)
        self._model_label = QLabel(MODEL_BOX_TITLE)
        if control_types is not None:
            self._control_type_label: Optional[QLabel] = QLabel(CONTROL_TYPE_BOX_TITLE)
        else:
            self._control_type_label = None

        # Main checkboxes:
        self._enabled_checkbox = CheckBox()
        self._enabled_checkbox.setText(ENABLE_CONTROLNET_CHECKBOX_LABEL)
        self._vram_checkbox = _ControlnetCheckbox(cache_key, CONTROL_CONFIG_LOW_VRAM_KEY, LOW_VRAM_LABEL)
        self._px_perfect_checkbox = _ControlnetCheckbox(cache_key, CONTROL_CONFIG_PX_PERFECT_KEY,
                                                        PX_PERFECT_CHECKBOX_LABEL)

        # Control image inputs:
        use_generation_area = bool(CONTROL_CONFIG_IMAGE_KEY not in initial_control_state
                                   or initial_control_state[CONTROL_CONFIG_IMAGE_KEY] == CONTROLNET_REUSE_IMAGE_CODE)

        self._load_image_button = QPushButton()
        self._load_image_button.setText(CONTROL_IMAGE_BUTTON_LABEL)
        self._image_path_edit = QLineEdit('' if use_generation_area or CONTROL_CONFIG_IMAGE_KEY
                                          not in initial_control_state
                                          else initial_control_state[CONTROL_CONFIG_IMAGE_KEY])
        self._image_path_edit.setEnabled(not use_generation_area)
        self._reuse_image_checkbox = QCheckBox()
        self._reuse_image_checkbox.setText(GENERATION_AREA_AS_CONTROL)
        self._reuse_image_checkbox.setChecked(use_generation_area)

        def open_control_image_file() -> None:
            """Select an image to use as the control image."""
            if self._reuse_image_checkbox.isChecked():
                with signals_blocked(self._reuse_image_checkbox):
                    self._reuse_image_checkbox.setChecked(False)
            image_path = open_image_file(self)
            if image_path is not None:
                if isinstance(image_path, list):
                    image_path = image_path[0]
                if isinstance(image_path, str):
                    self._image_path_edit.setText(image_path)
                self._image_path_edit.setEnabled(True)
                self._control_image_label.setEnabled(True)
        self._load_image_button.clicked.connect(open_control_image_file)

        def reuse_image_update(checked: bool):
            """Update config, disable/enable appropriate components if the 'reuse image as control' box changes."""
            value = CONTROLNET_REUSE_IMAGE_CODE if checked else self._image_path_edit.text()
            for control_img_widget in (self._control_image_label, self._image_path_edit):
                control_img_widget.setEnabled(not checked)
            if checked:
                self._image_path_edit.setText('')
            cache.set(cache_key, value, inner_key=CONTROL_CONFIG_IMAGE_KEY)

        self._reuse_image_checkbox.stateChanged.connect(reuse_image_update)

        def image_path_update(text: str):
            """Update config when the selected control image changes."""
            if self._reuse_image_checkbox.isChecked():
                return
            cache.set(cache_key, text, inner_key=CONTROL_CONFIG_IMAGE_KEY)

        self._image_path_edit.textChanged.connect(image_path_update)

        # Mode-selection inputs:
        self._control_type_combobox: Optional[QComboBox] = None
        if control_types is not None:
            self._control_type_combobox = QComboBox(self)
            for control in control_types:
                self._control_type_combobox.addItem(control)
            self._control_type_combobox.setCurrentIndex(self._control_type_combobox.findText(DEFAULT_CONTROL_TYPE))
            self._control_type_combobox.currentTextChanged.connect(self._load_control_type)

        self._module_combobox = QComboBox(self)
        self._model_combobox = QComboBox(self)
        self._module_combobox.currentTextChanged.connect(self._handle_module_change)
        self._model_combobox.currentTextChanged.connect(self._handle_model_change)

        self._load_control_type(DEFAULT_CONTROL_TYPE)
        # Restore previous state on start:
        if CONTROL_MODULE_KEY in initial_control_state:
            module = self._module_combobox.findText(initial_control_state[CONTROL_MODULE_KEY])
            if module is not None:
                self._module_combobox.setCurrentIndex(module)
        if CONTROL_MODEL_KEY in initial_control_state:
            model = self._model_combobox.findText(initial_control_state[CONTROL_MODEL_KEY])
            if model is not None:
                self._model_combobox.setCurrentIndex(model)

        def set_enabled(checked: bool):
            """Update config and active widgets when controlnet is enabled or disabled."""
            if self._enabled_checkbox.isChecked() != checked:
                self._enabled_checkbox.setChecked(checked)
            main_control_widgets = [
                self._module_label,
                self._model_label,
                self._control_type_label,
                self._vram_checkbox,
                self._px_perfect_checkbox,
                self._reuse_image_checkbox,
                self._control_type_combobox,
                self._module_combobox,
                self._model_combobox
            ] + self._dynamic_slider_labels + self._dynamic_sliders
            control_image_widgets = [
                self._control_image_label,
                self._image_path_edit
            ]
            for widget in main_control_widgets:
                if widget is not None:
                    widget.setEnabled(checked)
            for widget in control_image_widgets:
                widget.setEnabled(checked and not self._reuse_image_checkbox.isChecked())
            if checked:
                cache.set(cache_key, self._saved_state)
            else:
                self._saved_state = cache.get(cache_key)
                cache.set(cache_key, {})

        set_enabled(CONTROL_MODEL_KEY in initial_control_state)
        self._enabled_checkbox.stateChanged.connect(set_enabled)
        self._build_layout()

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Sets the active panel orientation"""
        if self._orientation != orientation:
            self._orientation = orientation
            self._build_layout()

    def _build_layout(self) -> None:
        """Builds the panel layout, or updates it when orientation changes."""
        clear_layout(self._layout)

        for row in range(self._layout.rowCount()):
            self._layout.setRowStretch(row, 0)
        for column in range(self._layout.columnCount()):
            self._layout.setColumnStretch(column, 0)

        # Build horizontal layout:
        if self._orientation == Qt.Orientation.Horizontal:
            for column in (0, 2):
                self._layout.setColumnStretch(column, 1)
            for column in (1, 3):
                self._layout.setColumnStretch(column, 3)
            layout_items: List[Tuple[Optional[QWidget], int, int, int, int]] = [
                (self._enabled_checkbox, 0, 0, 1, 1),
                (self._vram_checkbox, 0, 1, 1, 1),
                (self._px_perfect_checkbox, 1, 0, 1, 1),
                (self._reuse_image_checkbox, 1, 1, 1, 1),
                (self._control_image_label, 2, 0, 1, 1),
                (self._image_path_edit, 2, 1, 1, 3),
                (self._load_image_button, 3, 1, 1, 1),
                (Divider(Qt.Orientation.Horizontal), 4, 0, 1, 4)
            ]

            if self._control_type_combobox is not None:
                layout_items += [
                    (self._control_type_label, 5, 0, 1, 1),
                    (self._control_type_combobox, 5, 1, 1, 1)
                ]
            layout_items += [
                (self._module_label, 6, 0, 1, 1),
                (self._module_combobox, 6, 1, 1, 1),
                (self._model_label, 6, 2, 1, 1),
                (self._model_combobox, 6, 3, 1, 1),
                (Divider(Qt.Orientation.Horizontal), 7, 0, 1, 4)
            ]
            row = 8
            col = 0
            for label, slider in zip(self._dynamic_slider_labels, self._dynamic_sliders):
                layout_items.append((label, row, col, 1, 1))
                layout_items.append((slider, row, col + 1, 1, 1))
                if col > 0:
                    row += 1
                    col = 0
                else:
                    col = 2
        # Build vertical layout:
        else:
            layout_items = [
                (self._enabled_checkbox, 0, 0, 1, 1),
                (self._vram_checkbox, 0, 1, 1, 1),
                (self._px_perfect_checkbox, 1, 0, 1, 1),
                (self._reuse_image_checkbox, 2, 0, 1, 1),
                (self._load_image_button, 2, 1, 1, 1),
                (self._control_image_label, 3, 0, 1, 1),
                (self._image_path_edit, 3, 1, 1, 1)
            ]
            if self._control_type_combobox is not None:
                layout_items += [
                    (self._control_type_label, 4, 0, 1, 1),
                    (self._control_type_combobox, 4, 1, 1, 1)
                ]
            layout_items += [
                (self._module_label, 5, 0, 1, 1),
                (self._module_combobox, 5, 1, 1, 1),
                (self._model_label, 6, 0, 1, 1),
                (self._model_combobox, 6, 1, 1, 1)
            ]
            row = 7
            for label, slider in zip(self._dynamic_slider_labels, self._dynamic_sliders):
                layout_items.append((label, row, 0, 1, 1))
                layout_items.append((slider, row, 1, 1, 1))
                row += 1
        for widget, row, column, row_span, column_span in layout_items:
            self._layout.addWidget(widget, row, column, row_span, column_span)

    def _load_control_type(self, control_type: str) -> None:
        """Update module/model options for the selected control type."""
        self._model_combobox.currentTextChanged.disconnect(self._handle_model_change)
        while self._model_combobox.count() > 0:
            self._model_combobox.removeItem(0)
        default_model = DEFAULT_MODEL_NAME
        if self._control_types is not None:
            for control_model in self._control_types[control_type][MODEL_LIST_KEY]:
                self._model_combobox.addItem(control_model)
            default_model = self._control_types[control_type][DEFAULT_MODEL_KEY]
        else:
            for control_model in self._model_list[MODEL_LIST_KEY]:
                self._model_combobox.addItem(control_model)
        self._model_combobox.currentTextChanged.connect(self._handle_model_change)
        if default_model != DEFAULT_MODEL_NAME:
            self._model_combobox.setCurrentIndex(self._model_combobox.findText(default_model))
        else:
            self._model_combobox.setCurrentIndex(0)

        self._module_combobox.currentTextChanged.disconnect(self._handle_module_change)
        default_module = DEFAULT_MODULE_NAME
        while self._module_combobox.count() > 0:
            self._module_combobox.removeItem(0)
        if self._control_types is not None:
            for control_module in self._control_types[control_type][MODULE_LIST_KEY]:
                self._module_combobox.addItem(control_module)
            default_module = self._control_types[control_type][DEFAULT_OPTION_KEY]
        else:
            for control_module in self._module_detail[MODULE_LIST_KEY]:
                self._module_combobox.addItem(control_module)
        self._module_combobox.currentTextChanged.connect(self._handle_module_change)
        if default_module != DEFAULT_MODULE_NAME:
            self._module_combobox.setCurrentIndex(self._module_combobox.findText(default_module))
        else:
            self._module_combobox.setCurrentIndex(0)

    def _handle_module_change(self, selected_module: str) -> None:
        """When the selected module changes, update config and module option controls."""
        cache = Cache()
        details = {}
        cache.set(self._cache_key, selected_module, inner_key=CONTROL_MODULE_KEY)
        for label, slider in zip(self._dynamic_slider_labels, self._dynamic_sliders):
            self._layout.removeWidget(label)
            self._layout.removeWidget(slider)
            cache.disconnect(slider, self._cache_key)
            label.setParent(None)
            slider.setParent(None)
        self._dynamic_slider_labels = []
        self._dynamic_sliders = []
        if MODULE_DETAIL_KEY in self._module_detail:
            if selected_module not in self._module_detail[MODULE_DETAIL_KEY]:
                for option in self._module_detail[MODULE_LIST_KEY]:
                    if selected_module.startswith(option):
                        selected_module = option
                        break
            if selected_module not in self._module_detail[MODULE_DETAIL_KEY]:
                logger.warning(f'Warning: chosen module {selected_module} not found')
            else:
                details = self._module_detail[MODULE_DETAIL_KEY][selected_module]
        current_keys = list(cache.get(self._cache_key).keys())
        for param in current_keys:
            if param not in DEFAULT_PARAMS:
                cache.set(self._cache_key, None, inner_key=param)
        if selected_module != DEFAULT_MODULE_NAME:
            sliders = [
                {
                    SLIDER_TITLE_KEY: CONTROL_WEIGHT_TITLE,
                    SLIDER_NAME_KEY: CONTROL_WEIGHT_KEY,
                    SLIDER_VALUE_KEY: 1.0,
                    SLIDER_MIN_KEY: 0.0,
                    SLIDER_MAX_KEY: 2.0,
                    SLIDER_STEP_KEY: 0.1
                },
                {
                    SLIDER_TITLE_KEY: CONTROL_START_STEP_TITLE,
                    SLIDER_NAME_KEY: CONTROL_START_STEP_KEY,
                    SLIDER_VALUE_KEY: 0.0,
                    SLIDER_MIN_KEY: 0.0,
                    SLIDER_MAX_KEY: 1.0,
                    SLIDER_STEP_KEY: 0.1
                },
                {
                    SLIDER_TITLE_KEY: CONTROL_END_STEP_TITLE,
                    SLIDER_NAME_KEY: CONTROL_END_STEP_KEY,
                    SLIDER_VALUE_KEY: 1.0,
                    SLIDER_MIN_KEY: 0.0,
                    SLIDER_MAX_KEY: 1.0,
                    SLIDER_STEP_KEY: 0.1
                },
            ]
            if CONTROL_SLIDER_DEF_KEY in details:
                for slider_params in details[CONTROL_SLIDER_DEF_KEY]:
                    if slider_params is None:
                        continue
                    sliders.append(slider_params)
            for slider_params in sliders:
                if slider_params is None:
                    continue
                key = slider_params[SLIDER_NAME_KEY]
                slider_title = slider_params[SLIDER_TITLE_KEY] if SLIDER_TITLE_KEY in slider_params else key
                value = slider_params[SLIDER_VALUE_KEY]
                min_val = slider_params[SLIDER_MIN_KEY]
                max_val = slider_params[SLIDER_MAX_KEY]
                if key == slider_title:
                    if SLIDER_RES_KEY in key:
                        key = CONTROL_RESOLUTION_KEY
                    elif CONTROL_MODULE_PARAM_1_KEY not in cache.get(self._cache_key):
                        key = CONTROL_MODULE_PARAM_1_KEY
                    elif CONTROL_MODULE_PARAM_2_KEY not in cache.get(self._cache_key):
                        key = CONTROL_MODULE_PARAM_2_KEY
                step = 1 if SLIDER_STEP_KEY not in slider_params else slider_params[SLIDER_STEP_KEY]
                float_mode = any(x != int(x) for x in [value, min_val, max_val, step])
                if float_mode:
                    value = float(value)
                    min_val = float(min_val)
                    max_val = float(max_val)
                    step = float(step)
                else:
                    value = int(value)
                    min_val = int(min_val)
                    max_val = int(max_val)
                    step = int(step)
                cache.set(self._cache_key, value, inner_key=key)
                control_param = Parameter(slider_title,
                                          TYPE_FLOAT if float_mode else TYPE_INT,
                                          value,
                                          minimum=min_val,
                                          maximum=max_val,
                                          single_step=step)
                slider = control_param.get_input_widget()
                assert isinstance(slider, (IntSliderSpinbox, FloatSliderSpinbox))
                label = QLabel(slider_title)

                def _update_value(new_value, inner_key=key):
                    cache.set(self._cache_key, new_value, inner_key=inner_key)

                slider.valueChanged.connect(_update_value)
                self._dynamic_sliders.append(slider)
                self._dynamic_slider_labels.append(label)
        self._build_layout()

    def _handle_model_change(self, selected_model: str) -> None:
        """Update config when the selected model changes."""
        Cache().set(self._cache_key, selected_model, inner_key=CONTROL_MODEL_KEY)


class _ControlnetCheckbox(CheckBox):
    """Connects to a boolean parameter in a controlnet JSON body."""

    def __init__(self, cache_key: str, inner_key: str, label_text: Optional[str] = None) -> None:
        super().__init__(None)
        self._key = cache_key
        self._inner_key = inner_key
        cache = Cache()
        value = cache.get(cache_key, inner_key=inner_key)
        self.setValue(bool(value))
        self.valueChanged.connect(self._update_config)
        if label_text is not None:
            self.setText(label_text)
        cache.connect(self, cache_key, self.setValue, inner_key=inner_key)

    def _update_config(self, new_value: bool) -> None:
        Cache().set(self._key, new_value, inner_key=self._inner_key)
