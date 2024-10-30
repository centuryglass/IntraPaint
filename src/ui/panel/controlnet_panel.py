"""
Panel providing controls for the stable-diffusion ControlNet extension. Only supported by stable_diffusion_controller.
"""
import logging
from copy import deepcopy
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QPushButton, QLineEdit, QComboBox, QApplication, QTabWidget, QGridLayout, \
    QLabel, QWidget

from src.api.controlnet_constants import PREPROCESSOR_NONE, \
    CONTROLNET_REUSE_IMAGE_CODE
from src.api.webui.controlnet_webui import get_common_controlnet_unit_parameters, PREPROCESSOR_PRESET_LABELS, \
    init_controlnet_unit, ControlTypeDef
from src.api.controlnet_preprocessor import ControlNetPreprocessor
from src.config.cache import Cache
from src.ui.input_fields.check_box import CheckBox
from src.ui.layout.bordered_widget import BorderedWidget
from src.ui.layout.divider import Divider
from src.ui.modal.modal_utils import open_image_file
from src.util.layout import clear_layout
from src.util.parameter import DynamicFieldWidget
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
CONTROL_TYPE_BOX_TITLE = _tr('Control Type:')
MODULE_BOX_TITLE = _tr('Preprocessor:')
MODEL_BOX_TITLE = _tr('Control Model:')
CONTROL_WEIGHT_TITLE = _tr('Control Weight:')
CONTROL_START_STEP_TITLE = _tr('Starting Control Step:')
CONTROL_END_STEP_TITLE = _tr('Ending Control Step:')

# Config/request body keys:
CONTROL_CONFIG_LOW_VRAM_KEY = 'low_vram'
CONTROL_CONFIG_PX_PERFECT_KEY = 'pixel_perfect'
CONTROL_CONFIG_IMAGE_KEY = 'image'

CONTROL_MODULE_KEY = 'module'
CONTROL_MODEL_KEY = 'model'
DEFAULT_CONTROL_TYPE = 'All'


class TabbedControlNetPanel(QTabWidget):
    """Tabbed ControlNet panel with three ControlNet units."""

    def __init__(self,
                 preprocessors: list[ControlNetPreprocessor],
                 model_list: list[str],
                 control_types: dict[str, ControlTypeDef],
                 control_unit_cache_keys: list[str],
                 show_webui_options: bool):
        """Initializes the panel based on data from a stable-diffusio API.

        Parameters
        ----------
        preprocessors: list[ControlNetPreprocessor]
            List of all available ControlNet preprocessor modules, pre-parameterized to enable easy UI setup.
        model_list: list[str]
            List of all available ControlNet models.
        control_types: dict[str, ControlTypeDef]
            Data defining how preprocessors and models can be sorted into categories.
        control_unit_cache_keys: list[str]
            Cache keys for each ControlNet unit that the panel can use.
        show_webui_options: bool
            Whether the "Low VRAM" and "Pixel Perfect" checkboxes (only relevant in the WebUI API) should be shown.
        """
        super().__init__()
        self._panels: list[ControlNetPanel] = []
        for i, key in enumerate(control_unit_cache_keys):
            panel = ControlNetPanel(key, deepcopy(preprocessors), model_list, control_types, show_webui_options)
            self.addTab(panel, CONTROLNET_UNIT_TITLE.format(unit_number=str(i + 1)))
            self._panels.append(panel)

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Sets the active panel orientation"""
        for panel in self._panels:
            panel.set_orientation(orientation)


class ControlNetPanel(BorderedWidget):
    """ControlnetPanel provides controls for the stable-diffusion ControlNet extension."""

    def __init__(self,
                 cache_key: str,
                 preprocessors: list[ControlNetPreprocessor],
                 model_list: list[str],
                 control_types: dict[str, ControlTypeDef],
                 show_webui_options: bool) -> None:
        """Initializes the panel based on data from the stable-diffusion-webui.

        Parameters
        ----------
        preprocessors: list[ControlNetPreprocessor]
            List of all available ControlNet preprocessor modules, pre-parameterized to enable easy UI setup.
        model_list: list[str]
            List of all available ControlNet models.
        control_types: dict[str, ControlTypeDef]
            Data defining how preprocessors and models can be sorted into categories.
        show_webui_options: bool
            Whether the "Low VRAM" and "Pixel Perfect" checkboxes (only relevant in the WebUI API) should be shown.
        """
        super().__init__()
        cache = Cache()
        initial_control_state = init_controlnet_unit(cache.get(cache_key))
        self._saved_state = initial_control_state
        self._cache_key = cache_key
        self._control_types = control_types
        self._preprocessors = preprocessors
        self._model_list = model_list
        self._orientation = Qt.Orientation.Horizontal
        self._layout = QGridLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._dynamic_controls: list[DynamicFieldWidget] = []
        self._dynamic_control_labels: list[QLabel] = []
        self._show_webui_options = show_webui_options

        # Labels:
        self._control_image_label = QLabel(CONTROL_IMAGE_LABEL)
        self._module_label = QLabel(MODULE_BOX_TITLE)
        self._model_label = QLabel(MODEL_BOX_TITLE)
        self._control_type_label = QLabel(CONTROL_TYPE_BOX_TITLE)

        # Main checkboxes:
        self._enabled_checkbox = CheckBox()
        self._enabled_checkbox.setText(ENABLE_CONTROLNET_CHECKBOX_LABEL)
        self._vram_checkbox: Optional[_ControlnetCheckbox] = None
        self._px_perfect_checkbox: Optional[_ControlnetCheckbox] = None
        if show_webui_options:
            self._vram_checkbox = _ControlnetCheckbox(cache_key, CONTROL_CONFIG_LOW_VRAM_KEY, LOW_VRAM_LABEL)

            self._px_perfect_checkbox = _ControlnetCheckbox(cache_key, CONTROL_CONFIG_PX_PERFECT_KEY,
                                                            PX_PERFECT_CHECKBOX_LABEL)

        # Control image inputs:
        use_generation_area = initial_control_state['image'] == CONTROLNET_REUSE_IMAGE_CODE

        self._load_image_button = QPushButton()
        self._load_image_button.setText(CONTROL_IMAGE_BUTTON_LABEL)
        self._image_path_edit = QLineEdit('' if use_generation_area else initial_control_state['image'])
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
                    self._saved_state['image'] = image_path
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
            self._saved_state['image'] = CONTROLNET_REUSE_IMAGE_CODE
            cache.set(cache_key, value, inner_key=CONTROL_CONFIG_IMAGE_KEY)

        self._reuse_image_checkbox.stateChanged.connect(reuse_image_update)

        def image_path_update(text: str):
            """Update config when the selected control image changes."""
            if self._reuse_image_checkbox.isChecked():
                return
            self._saved_state['image'] = text
            cache.set(cache_key, text, inner_key=CONTROL_CONFIG_IMAGE_KEY)

        self._image_path_edit.textChanged.connect(image_path_update)

        # Mode-selection inputs:
        self._control_type_combobox: Optional[QComboBox] = None
        self._control_type_combobox = QComboBox(self)
        for control in control_types:
            self._control_type_combobox.addItem(control)
        self._control_type_combobox.setCurrentIndex(self._control_type_combobox.findText(DEFAULT_CONTROL_TYPE))
        self._control_type_combobox.currentTextChanged.connect(self._load_control_type)

        self._module_combobox = QComboBox(self)
        self._model_combobox = QComboBox(self)
        self._module_combobox.currentTextChanged.connect(self._handle_module_change)
        self._model_combobox.currentTextChanged.connect(self._handle_model_change)

        # Avoid letting excessively long type/preprocessor/model names distort the UI layout:
        for large_combobox in (self._model_combobox, self._module_combobox, self._control_type_combobox):
            assert isinstance(large_combobox, QComboBox)
            large_combobox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)

        self._load_control_type(DEFAULT_CONTROL_TYPE)
        # Restore previous state on start:
        module = self._module_combobox.findText(initial_control_state['module'])
        if module is not None:
            self._module_combobox.setCurrentIndex(module)
        model = self._model_combobox.findText(initial_control_state['model'])
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
                                   ] + self._dynamic_control_labels + self._dynamic_controls
            control_image_widgets = [
                self._control_image_label,
                self._image_path_edit
            ]
            for widget in main_control_widgets:
                if widget is not None:
                    widget.setEnabled(checked)
            for widget in control_image_widgets:
                widget.setEnabled(checked and not self._reuse_image_checkbox.isChecked())
            self._saved_state['enabled'] = checked
            cache.set(cache_key, checked, inner_key='enabled')

        set_enabled(initial_control_state['enabled'])
        self._enabled_checkbox.valueChanged.connect(set_enabled)
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
            layout_items: list[tuple[Optional[QWidget], int, int, int, int]] = [
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
            for label, slider in zip(self._dynamic_control_labels, self._dynamic_controls):
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
            for label, slider in zip(self._dynamic_control_labels, self._dynamic_controls):
                layout_items.append((label, row, 0, 1, 1))
                layout_items.append((slider, row, 1, 1, 1))
                row += 1
        for widget, row, column, row_span, column_span in layout_items:
            if widget is not None:
                self._layout.addWidget(widget, row, column, row_span, column_span)

    def _load_control_type(self, control_type_name: str) -> None:
        """Update module/model options for the selected control type."""
        assert control_type_name in self._control_types
        control_type = self._control_types[control_type_name]
        self._model_combobox.currentTextChanged.disconnect(self._handle_model_change)
        while self._model_combobox.count() > 0:
            self._model_combobox.removeItem(0)
        default_model = control_type['default_model']
        for control_model in control_type['model_list']:
            self._model_combobox.addItem(control_model)
        self._model_combobox.currentTextChanged.connect(self._handle_model_change)
        self._model_combobox.setCurrentIndex(self._model_combobox.findText(default_model))

        self._module_combobox.currentTextChanged.disconnect(self._handle_module_change)
        default_module = control_type['default_option']
        while self._module_combobox.count() > 0:
            self._module_combobox.removeItem(0)
        for preprocessor in control_type['module_list']:
            self._module_combobox.addItem(preprocessor)
        self._module_combobox.currentTextChanged.connect(self._handle_module_change)
        self._module_combobox.setCurrentIndex(self._module_combobox.findText(default_module))

    def _handle_module_change(self, selected_module: str) -> None:
        """When the selected module changes, update config and module option controls."""
        cache = Cache()
        cache.set(self._cache_key, selected_module, inner_key=CONTROL_MODULE_KEY)
        for label, parameter_widget in zip(self._dynamic_control_labels, self._dynamic_controls):
            self._layout.removeWidget(label)
            self._layout.removeWidget(parameter_widget)
            cache.disconnect(parameter_widget, self._cache_key)
            label.setParent(None)
            parameter_widget.setParent(None)
        self._dynamic_control_labels = []
        self._dynamic_controls = []
        preprocessor: Optional[ControlNetPreprocessor] = None
        for saved_preprocessor in self._preprocessors:
            if saved_preprocessor.name == selected_module:
                preprocessor = saved_preprocessor
        if preprocessor is None:
            raise ValueError(f'Could not find "{selected_module}" preprocessor. This indicates a bug in either control'
                             ' type option setup or preprocessor parameterization.')
        saved_control_unit = init_controlnet_unit(cache.get(self._cache_key))
        preprocessor.update_webui_data(saved_control_unit)
        cache.set(self._cache_key, saved_control_unit)
        if selected_module != PREPROCESSOR_NONE:
            parameters = get_common_controlnet_unit_parameters(preprocessor.name, self._show_webui_options)
            for preprocessor_parameter in preprocessor.parameters:
                parameters.append(deepcopy(preprocessor_parameter))
            for parameter in parameters:
                parameter_widget = parameter.get_input_widget()
                label = QLabel(parameter.name if parameter.name not in PREPROCESSOR_PRESET_LABELS
                               else PREPROCESSOR_PRESET_LABELS[parameter.name])

                if parameter.name in PREPROCESSOR_PRESET_LABELS:
                    parameter_key = parameter.name
                else:
                    parameter_key = preprocessor.get_parameter_webui_key(parameter)

                def _update_value(new_value, inner_key=parameter_key):
                    cache.set(self._cache_key, new_value, inner_key=inner_key)

                parameter_widget.valueChanged.connect(_update_value)
                _update_value(parameter_widget.value())
                self._dynamic_controls.append(parameter_widget)
                self._dynamic_control_labels.append(label)
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
