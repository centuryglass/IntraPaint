"""
Panel providing controls for the stable-diffusion ControlNet extension. Only supported by stable_diffusion_controller.
"""
import logging
from typing import Optional

from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QLineEdit, QComboBox, QApplication, \
    QTabWidget

from src.config.application_config import AppConfig
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox, FloatSliderSpinbox
from src.ui.modal.modal_utils import open_image_file
from src.ui.widget.bordered_widget import BorderedWidget
from src.ui.widget.label_wrapper import LabelWrapper
from src.util.parameter import Parameter, TYPE_FLOAT, TYPE_INT
from src.util.shared_constants import CONTROLNET_REUSE_IMAGE_CODE
from src.util.validation import assert_type

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.controlnet_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


# UI/Label text:
CONTROLNET_TITLE = _tr('ControlNet')
CONTROLNET_UNIT_TITLE = _tr('ControlNet Unit {unit_number}')
ENABLE_CONTROLNET_CHECKBOX_LABEL = _tr('Enable ControlNet')
LOW_VRAM_LABEL = _tr('Low VRAM')
PX_PERFECT_CHECKBOX_LABEL = _tr('Pixel Perfect')
CONTROL_IMAGE_LABEL = _tr('Set Control Image')
GENERATION_AREA_AS_CONTROL = _tr('Generation Area as Control')
CONTROL_TYPE_BOX_TITLE = _tr('Control Type')
MODULE_BOX_TITLE = _tr('Control Module')
MODEL_BOX_TITLE = _tr('Control Model')
OPTION_BOX_TITLE = _tr('Options')
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
        self._panel1 = ControlnetPanel(AppConfig.CONTROLNET_ARGS_0, control_types, module_detail, model_list)
        self._panel2 = ControlnetPanel(AppConfig.CONTROLNET_ARGS_1, control_types, module_detail, model_list)
        self._panel3 = ControlnetPanel(AppConfig.CONTROLNET_ARGS_2, control_types, module_detail, model_list)
        self.addTab(self._panel1, CONTROLNET_UNIT_TITLE.format(unit_number='1'))
        self.addTab(self._panel2, CONTROLNET_UNIT_TITLE.format(unit_number='2'))
        self.addTab(self._panel3, CONTROLNET_UNIT_TITLE.format(unit_number='3'))


class ControlnetPanel(BorderedWidget):
    """ControlnetPanel provides controls for the stable-diffusion ControlNet extension."""

    def __init__(self,
                 config_key: str,
                 control_types: Optional[dict],
                 module_detail: dict,
                 model_list: dict):
        """Initializes the panel based on data from the stable-diffusion-webui.

        Parameters
        ----------
        config_key : str, default = Config.CONTROLNET_ARGS_0
            Config key where ControlNet settings will be saved.
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
        assert_type(model_list, dict)
        if MODEL_LIST_KEY not in model_list:
            raise KeyError(f'Controlnet model list had unexpected structure: {model_list}')
        config = AppConfig()
        initial_control_state = config.get(config_key)
        self._saved_state = initial_control_state

        # Build layout:
        layout = QVBoxLayout(self)

        # Basic checkboxes:
        checkbox_row = QHBoxLayout()
        layout.addLayout(checkbox_row)
        enabled_checkbox = CheckBox()
        enabled_checkbox.setText(ENABLE_CONTROLNET_CHECKBOX_LABEL)
        checkbox_row.addWidget(enabled_checkbox)

        vram_checkbox = _ControlnetCheckbox(config_key, CONTROL_CONFIG_LOW_VRAM_KEY, LOW_VRAM_LABEL)
        checkbox_row.addWidget(vram_checkbox)

        px_perfect_checkbox = _ControlnetCheckbox(config_key, CONTROL_CONFIG_PX_PERFECT_KEY, PX_PERFECT_CHECKBOX_LABEL)
        checkbox_row.addWidget(px_perfect_checkbox)

        # Control image row:
        use_generation_area = bool(CONTROL_CONFIG_IMAGE_KEY not in initial_control_state
                                   or initial_control_state[CONTROL_CONFIG_IMAGE_KEY] == CONTROLNET_REUSE_IMAGE_CODE)
        image_row = QHBoxLayout()
        layout.addLayout(image_row)

        load_image_button = QPushButton()
        load_image_button.setText(CONTROL_IMAGE_LABEL)
        load_image_button.setEnabled(not use_generation_area)
        image_row.addWidget(load_image_button, stretch=10)

        image_path_edit = QLineEdit('' if use_generation_area or CONTROL_CONFIG_IMAGE_KEY not in initial_control_state
                                    else initial_control_state[CONTROL_CONFIG_IMAGE_KEY])
        image_path_edit.setEnabled(not use_generation_area)
        image_row.addWidget(image_path_edit, stretch=80)

        reuse_image_checkbox = QCheckBox()
        reuse_image_checkbox.setText(GENERATION_AREA_AS_CONTROL)
        image_row.addWidget(reuse_image_checkbox, stretch=10)
        reuse_image_checkbox.setChecked(use_generation_area)

        def open_control_image_file() -> None:
            """Select an image to use as the control image."""
            image_path, _ = open_image_file(self)
            if image_path is not None:
                if isinstance(image_path, list):
                    image_path = image_path[0]
                if isinstance(image_path, str):
                    image_path_edit.setText(image_path)
        load_image_button.clicked.connect(open_control_image_file)

        def reuse_image_update(checked: bool):
            """Update config, disable/enable appropriate components if the 'reuse image as control' box changes."""
            value = CONTROLNET_REUSE_IMAGE_CODE if checked else image_path_edit.text()
            load_image_button.setEnabled(not checked)
            image_path_edit.setEnabled(not checked)
            if checked:
                image_path_edit.setText('')
            config.set(config_key, value, inner_key=CONTROL_CONFIG_IMAGE_KEY)

        reuse_image_checkbox.stateChanged.connect(reuse_image_update)

        def image_path_update(text: str):
            """Update config when the selected control image changes."""
            if reuse_image_checkbox.isChecked():
                return
            config.set(config_key, text, inner_key=CONTROL_CONFIG_IMAGE_KEY)

        image_path_edit.textChanged.connect(image_path_update)

        # Mode-selection row:
        selection_row = QHBoxLayout()
        layout.addLayout(selection_row)
        control_type_combobox = None
        if control_types is not None:
            control_type_combobox = QComboBox(self)
            for control in control_types:
                control_type_combobox.addItem(control)
            control_type_combobox.setCurrentIndex(control_type_combobox.findText(DEFAULT_CONTROL_TYPE))
            selection_row.addWidget(LabelWrapper(control_type_combobox, CONTROL_TYPE_BOX_TITLE))

        module_combobox = QComboBox(self)
        selection_row.addWidget(LabelWrapper(module_combobox, MODULE_BOX_TITLE))

        model_combobox = QComboBox(self)
        selection_row.addWidget(LabelWrapper(model_combobox, MODEL_BOX_TITLE))
        self._fixed_layout_item_count = layout.count()

        # on model change, update config:
        def handle_model_change():
            """Update config when the selected model changes."""
            config.set(config_key, model_combobox.currentText(), inner_key=CONTROL_MODEL_KEY)

        model_combobox.currentIndexChanged.connect(handle_model_change)

        def handle_module_change(selected_module: str):
            """When the selected module changes, update config and module option controls."""
            details = {}
            if MODULE_DETAIL_KEY in module_detail:
                if selected_module not in module_detail[MODULE_DETAIL_KEY]:
                    for option in module_detail[MODULE_LIST_KEY]:
                        if selected_module.startswith(option):
                            selected_module = option
                            break
                if selected_module not in module_detail[MODULE_DETAIL_KEY]:
                    logger.warning(f'Warning: chosen module {selected_module} not found')
                    return
                details = module_detail[MODULE_DETAIL_KEY][selected_module]
            config.set(config_key, selected_module, inner_key=CONTROL_MODULE_KEY)
            while layout.count() > self._fixed_layout_item_count:
                row = layout.takeAt(layout.count() - 1)
                assert row is not None
                row_layout = row.layout()
                assert row_layout is not None
                while row_layout.count() > 0:
                    item = row_layout.takeAt(0)
                    assert item is not None
                    widget = item.widget()
                    if widget is not None:
                        config.disconnect(widget, config_key)
                        if hasattr(widget, 'disconnect_config'):
                            widget.disconnect_config()
                        else:
                            config.disconnect(widget, config_key)
                        widget.deleteLater()
                row_layout.deleteLater()
            current_keys = list(config.get(config_key).keys())
            for param in current_keys:
                if param not in DEFAULT_PARAMS:
                    config.set(config_key, None, inner_key=param)
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
                slider_row = QHBoxLayout()
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
                        elif CONTROL_MODULE_PARAM_1_KEY not in config.get(config_key):
                            key = CONTROL_MODULE_PARAM_1_KEY
                        elif CONTROL_MODULE_PARAM_2_KEY not in config.get(config_key):
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
                    config.set(config_key, value, inner_key=key)
                    control_param = Parameter(slider_title,
                                              TYPE_FLOAT if float_mode else TYPE_INT,
                                              value,
                                              minimum=min_val,
                                              maximum=max_val,
                                              single_step=step)
                    slider = control_param.get_input_widget()
                    assert isinstance(slider, (IntSliderSpinbox, FloatSliderSpinbox))
                    slider.setText(slider_title)

                    def _update_value(new_value, inner_key=key):
                        config.set(config_key, new_value, inner_key=inner_key)
                    slider.valueChanged.connect(_update_value)
                    if slider_row.count() > 1:
                        layout.addLayout(slider_row)
                        slider_row = QHBoxLayout()
                    slider_row.addWidget(slider)
                if slider_row.count() > 0:
                    layout.addLayout(slider_row)

        def module_change_handler():
            """On module change, apply the new selected module."""
            handle_module_change(module_combobox.currentText())

        module_combobox.currentIndexChanged.connect(module_change_handler)

        def load_control_type(typename: str):
            """Update module/model options when control type changes."""
            model_combobox.currentIndexChanged.disconnect(handle_model_change)
            while model_combobox.count() > 0:
                model_combobox.removeItem(0)
            default_model = DEFAULT_MODEL_NAME
            if control_types is not None:
                for control_model in control_types[typename][MODEL_LIST_KEY]:
                    model_combobox.addItem(control_model)
                default_model = control_types[typename][DEFAULT_MODEL_KEY]
            else:
                for control_model in model_list[MODEL_LIST_KEY]:
                    model_combobox.addItem(control_model)
            model_combobox.currentIndexChanged.connect(handle_model_change)
            if default_model != DEFAULT_MODEL_NAME:
                model_combobox.setCurrentIndex(model_combobox.findText(default_model))
            else:
                model_combobox.setCurrentIndex(0)

            module_combobox.currentIndexChanged.disconnect(module_change_handler)
            default_module = DEFAULT_MODULE_NAME
            while module_combobox.count() > 0:
                module_combobox.removeItem(0)
            if control_types is not None:
                for control_module in control_types[typename][MODULE_LIST_KEY]:
                    module_combobox.addItem(control_module)
                default_module = control_types[typename][DEFAULT_OPTION_KEY]
            else:
                for control_module in module_detail[MODULE_LIST_KEY]:
                    module_combobox.addItem(control_module)
            module_combobox.currentIndexChanged.connect(module_change_handler)
            if default_module != DEFAULT_MODULE_NAME:
                module_combobox.setCurrentIndex(module_combobox.findText(default_module))
            else:
                module_combobox.setCurrentIndex(0)

        load_control_type(DEFAULT_CONTROL_TYPE)
        if control_type_combobox is not None:
            control_type_combobox.currentIndexChanged.connect(
                lambda: load_control_type(control_type_combobox.currentText()))

        # Restore previous state on start:
        if CONTROL_MODULE_KEY in initial_control_state:
            module = module_combobox.findText(initial_control_state[CONTROL_MODULE_KEY])
            if module is not None:
                module_combobox.setCurrentIndex(module)
        if CONTROL_MODEL_KEY in initial_control_state:
            model = model_combobox.findText(initial_control_state[CONTROL_MODEL_KEY])
            if model is not None:
                model_combobox.setCurrentIndex(model)

        def set_enabled(checked: bool):
            """Update config and active widgets when controlnet is enabled or disabled."""
            if enabled_checkbox.isChecked() != checked:
                enabled_checkbox.setChecked(checked)
            for widget in [control_type_combobox, module_combobox, model_combobox]:
                if widget is not None:
                    widget.setEnabled(checked)
            if checked:
                config.set(config_key, self._saved_state)
            else:
                self._saved_state = config.get(config_key)
                config.set(config_key, {})

        set_enabled(CONTROL_MODEL_KEY in initial_control_state)
        enabled_checkbox.stateChanged.connect(set_enabled)


class _ControlnetCheckbox(CheckBox):
    """Connects to a boolean parameter in a controlnet JSON body."""

    def __init__(self, config_key: str, inner_key: str, label_text: Optional[str] = None) -> None:
        super().__init__(None)
        self._key = config_key
        self._inner_key = inner_key
        config = AppConfig()
        value = config.get(config_key, inner_key=inner_key)
        self.setValue(bool(value))
        self.valueChanged.connect(self._update_config)
        if label_text is not None:
            self.setText(label_text)
        config.connect(self, config_key, self.setValue, inner_key=inner_key)

    def _update_config(self, new_value: bool) -> None:
        AppConfig().set(self._key, new_value, inner_key=self._inner_key)
