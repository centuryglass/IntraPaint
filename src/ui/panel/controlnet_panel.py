"""
Panel providing controls for the stable-diffusion ControlNet extension. Only supported by stable_diffusion_controller.
"""
import logging
from copy import deepcopy
from json import JSONDecodeError
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QCheckBox, QPushButton, QLineEdit, QComboBox, QApplication, QTabWidget, QGridLayout, \
    QLabel, QWidget

import src.api.webui.controlnet_webui_constants as webui_constants
from src.api.controlnet.controlnet_constants import PREPROCESSOR_NONE, \
    CONTROLNET_REUSE_IMAGE_CODE, CONTROLNET_MODEL_NONE
from src.api.controlnet.controlnet_model import ControlNetModel
from src.api.controlnet.controlnet_preprocessor import ControlNetPreprocessor
from src.api.controlnet.controlnet_unit import ControlNetUnit, KeyType
from src.config.cache import Cache
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox
from src.ui.layout.bordered_widget import BorderedWidget
from src.ui.layout.divider import Divider
from src.ui.modal.modal_utils import open_image_file
from src.ui.widget.image_widget import ImageWidget
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
PREPROCESSOR_PREVIEW_BUTTON_LABEL = _tr('Preview Preprocessor')
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

CACHE_SAVE_TIMER_INTERVAL = 100
PREVIEW_IMAGE_SIZE = 300


class TabbedControlNetPanel(QTabWidget):
    """Tabbed ControlNet panel with three ControlNet units."""

    request_preview = Signal(ControlNetPreprocessor, str)

    def __init__(self,
                 preprocessors: list[ControlNetPreprocessor],
                 model_list: list[str],
                 control_types: dict[str, webui_constants.ControlTypeDef],
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
            panel.request_preview.connect(self.request_preview)

    def set_preview(self, preview_image: QImage) -> None:
        """Shows a preprocessor preview image in the active tab."""
        active_panel = self._panels[self.currentIndex()]
        active_panel.set_preprocessor_preview(preview_image)

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Sets the active panel orientation"""
        for panel in self._panels:
            panel.set_orientation(orientation)


class ControlNetPanel(BorderedWidget):
    """ControlnetPanel provides controls for the stable-diffusion ControlNet extension."""

    request_preview = Signal(ControlNetPreprocessor, str)

    def __init__(self,
                 cache_key: str,
                 preprocessors: list[ControlNetPreprocessor],
                 model_list: list[str],
                 control_types: dict[str, webui_constants.ControlTypeDef],
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
        try:
            self._control_unit = ControlNetUnit.deserialize(Cache().get(cache_key))
        except (TypeError, KeyError, JSONDecodeError):
            self._control_unit = ControlNetUnit(KeyType.WEBUI if show_webui_options else KeyType.COMFYUI)
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

        # Save timer:
        self._cache_timer = QTimer()
        self._cache_timer.setSingleShot(True)
        self._cache_timer.setInterval(CACHE_SAVE_TIMER_INTERVAL)
        self._cache_timer.timeout.connect(self._save_data_to_cache)

        # Labels:
        self._control_image_label = QLabel(CONTROL_IMAGE_LABEL)
        self._module_label = QLabel(MODULE_BOX_TITLE)
        self._model_label = QLabel(MODEL_BOX_TITLE)
        self._control_type_label = QLabel(CONTROL_TYPE_BOX_TITLE)

        # Main checkboxes:
        self._enabled_checkbox = CheckBox()
        self._enabled_checkbox.setText(ENABLE_CONTROLNET_CHECKBOX_LABEL)
        self._vram_checkbox: Optional[CheckBox] = None
        self._px_perfect_checkbox: Optional[CheckBox] = None
        self._resolution_label: Optional[QLabel] = None
        self._resolution_slider: Optional[IntSliderSpinbox] = None
        if show_webui_options:
            self._vram_checkbox = CheckBox()
            self._vram_checkbox.setText(LOW_VRAM_LABEL)
            self._vram_checkbox.setChecked(self._control_unit.low_vram)

            def _update_low_vram(checked: bool) -> None:
                self._control_unit.low_vram = checked
                self._schedule_cache_update()
            self._vram_checkbox.valueChanged.connect(_update_low_vram)

            self._px_perfect_checkbox = CheckBox()
            self._px_perfect_checkbox.setText(PX_PERFECT_CHECKBOX_LABEL)
            self._px_perfect_checkbox.setChecked(self._control_unit.pixel_perfect)

            def _update_px_perfect(checked: bool) -> None:
                self._control_unit.pixel_perfect = checked
                if self._resolution_label is not None:
                    self._resolution_label.setHidden(checked)
                if self._resolution_slider is not None:
                    self._resolution_slider.setHidden(checked)
                self._schedule_cache_update()
            self._px_perfect_checkbox.valueChanged.connect(_update_px_perfect)

        # Control image inputs:
        use_generation_area = self._control_unit.image_string == CONTROLNET_REUSE_IMAGE_CODE

        self._load_image_button = QPushButton()
        self._load_image_button.setText(CONTROL_IMAGE_BUTTON_LABEL)
        self._image_path_edit = QLineEdit('' if use_generation_area else self._control_unit.image_string)
        self._image_path_edit.setEnabled(not use_generation_area)
        self._reuse_image_checkbox = QCheckBox()
        self._reuse_image_checkbox.setText(GENERATION_AREA_AS_CONTROL)
        self._reuse_image_checkbox.setChecked(use_generation_area)

        # Preprocessor preview_button:
        self._preview_button = QPushButton()
        self._preview_button.setText(PREPROCESSOR_PREVIEW_BUTTON_LABEL)
        self._preview_image_widget = ImageWidget(QImage())
        self._preview_image_widget.setMaximumSize(QSize(PREVIEW_IMAGE_SIZE, PREVIEW_IMAGE_SIZE))

        def _request_preview() -> None:
            self.request_preview.emit(self._control_unit.preprocessor, self._control_unit.image_string)
        self._preview_button.clicked.connect(_request_preview)
        self._preview_button.setEnabled(self._control_unit.preprocessor.name != PREPROCESSOR_NONE)

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
                    self._control_unit.image_string = image_path
                self._image_path_edit.setEnabled(True)
                self._control_image_label.setEnabled(True)
                self._schedule_cache_update()

        self._load_image_button.clicked.connect(open_control_image_file)

        def reuse_image_update(checked: bool):
            """Update config, disable/enable appropriate components if the 'reuse image as control' box changes."""
            value = CONTROLNET_REUSE_IMAGE_CODE if checked else self._image_path_edit.text()
            for control_img_widget in (self._control_image_label, self._image_path_edit):
                control_img_widget.setEnabled(not checked)
            if checked:
                self._image_path_edit.setText('')
            self._control_unit.image_string = value
            self._schedule_cache_update()

        self._reuse_image_checkbox.stateChanged.connect(reuse_image_update)

        def image_path_update(text: str):
            """Update config when the selected control image changes."""
            if self._reuse_image_checkbox.isChecked():
                return

            self._control_unit.image_string = text
            self._schedule_cache_update()

        self._image_path_edit.textChanged.connect(image_path_update)

        # Mode-selection inputs:
        self._control_type_combobox: Optional[QComboBox] = None
        self._control_type_combobox = QComboBox(self)
        for control in control_types:
            self._control_type_combobox.addItem(control)
        self._control_type_combobox.setCurrentIndex(self._control_type_combobox.findText(DEFAULT_CONTROL_TYPE))
        self._control_type_combobox.currentTextChanged.connect(self._load_control_type)

        self._preprocessor_combobox = QComboBox(self)
        self._model_combobox = QComboBox(self)
        self._preprocessor_combobox.currentTextChanged.connect(self._handle_preprocessor_change)
        self._model_combobox.currentIndexChanged.connect(self._handle_model_change)

        # Avoid letting excessively long type/preprocessor/model names distort the UI layout:
        for large_combobox in (self._model_combobox, self._preprocessor_combobox, self._control_type_combobox):
            assert isinstance(large_combobox, QComboBox)
            large_combobox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)

        self._load_control_type(DEFAULT_CONTROL_TYPE)
        # Restore previous state on start:
        module_idx = self._preprocessor_combobox.findText(self._control_unit.preprocessor.name)
        if module_idx >= 0:
            self._preprocessor_combobox.setCurrentIndex(module_idx)
        model_idx = self._model_combobox.findText(self._control_unit.model.display_name)
        if model_idx >= 0:
            self._model_combobox.setCurrentIndex(model_idx)

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
                                       self._preprocessor_combobox,
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
            self._control_unit.enabled = checked
            self._schedule_cache_update()

        set_enabled(self._control_unit.enabled)
        self._enabled_checkbox.valueChanged.connect(set_enabled)
        self._build_layout()

    def set_preprocessor_preview(self, preview_image: Optional[QImage], skip_layout_update=False) -> None:
        """Shows the preprocessor preview image, or hides it if preview_image is None."""
        if preview_image is None:
            preview_image = QImage()
        if self._preview_image_widget.image == preview_image:
            return
        self._preview_image_widget.image = preview_image
        if not skip_layout_update:
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
                (self._reuse_image_checkbox, 0, 1, 1, 1),
                (self._px_perfect_checkbox, 0, 2, 1, 1),
                (self._vram_checkbox, 0, 3, 1, 1),
                (self._control_image_label, 1, 0, 1, 1),
                (self._image_path_edit, 1, 1, 1, 3),
                (self._load_image_button, 2, 1, 1, 1),
                (self._preview_button, 2, 2, 1, 1),
                (Divider(Qt.Orientation.Horizontal), 3, 0, 1, 4)
            ]

            if self._control_type_combobox is not None:
                layout_items += [
                    (self._control_type_label, 4, 0, 1, 1),
                    (self._control_type_combobox, 4, 1, 1, 1)
                ]
            layout_items += [
                (self._module_label, 5, 0, 1, 1),
                (self._preprocessor_combobox, 5, 1, 1, 1),
                (self._model_label, 5, 2, 1, 1),
                (self._model_combobox, 5, 3, 1, 1),
                (Divider(Qt.Orientation.Horizontal), 6, 0, 1, 4)
            ]
            row = 7
            col = 0
            for label, slider in zip(self._dynamic_control_labels, self._dynamic_controls):
                layout_items.append((label, row, col, 1, 1))
                layout_items.append((slider, row, col + 1, 1, 1))
                if col > 0:
                    row += 1
                    col = 0
                else:
                    col = 2
            if self._preview_image_widget.image is not None and not self._preview_image_widget.image.isNull():
                layout_items.append((Divider(Qt.Orientation.Vertical), 0, 4, row + 1, 1))
                layout_items.append((self._preview_image_widget, 0, 5, row + 1, 2))

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
                (self._preprocessor_combobox, 5, 1, 1, 1),
                (self._model_label, 6, 0, 1, 1),
                (self._model_combobox, 6, 1, 1, 1),
                (self._preview_button, 7, 1, 1, 1)
            ]
            row = 8
            for label, slider in zip(self._dynamic_control_labels, self._dynamic_controls):
                layout_items.append((label, row, 0, 1, 1))
                layout_items.append((slider, row, 1, 1, 1))
                row += 1
            if self._preview_image_widget.image is not None and not self._preview_image_widget.image.isNull():
                layout_items.append((Divider(Qt.Orientation.Horizontal), row, 0, 2, 1))
                layout_items.append((self._preview_image_widget, row + 2, 0, 4, 4))
        for widget, row, column, row_span, column_span in layout_items:
            if widget is not None:
                self._layout.addWidget(widget, row, column, row_span, column_span)

        self._preview_image_widget.setHidden(self._preview_image_widget.image is None
                                             or self._preview_image_widget.image.isNull())

    def _schedule_cache_update(self) -> None:
        if not self._cache_timer.isActive():
            self._cache_timer.start()

    def _save_data_to_cache(self) -> None:
        if self._cache_timer.isActive():
            self._cache_timer.stop()
        Cache().set(self._cache_key, self._control_unit.serialize())

    def _load_control_type(self, control_type_name: str) -> None:
        """Update preprocessor/model options for the selected control type."""
        assert control_type_name in self._control_types
        control_type = self._control_types[control_type_name]
        with signals_blocked(self._model_combobox):
            while self._model_combobox.count() > 0:
                self._model_combobox.removeItem(0)
            models = [ControlNetModel(model_name) for model_name in control_type['model_list']]
            # Sort alphabetically, except that "None" option should be last:
            models.sort(key=lambda model: model.display_name.lower() if model.display_name != CONTROLNET_MODEL_NONE
                        else '~')
            for control_model in models:
                self._model_combobox.addItem(control_model.display_name, userData=control_model.full_model_name)
            selected_model = self._control_unit.model
            if selected_model not in models or selected_model.full_model_name == CONTROLNET_MODEL_NONE:
                selected_model = ControlNetModel(control_type['default_model'])
                if selected_model not in control_type['model_list']:
                    selected_model = ControlNetModel(CONTROLNET_MODEL_NONE)
            model_index = self._model_combobox.findData(selected_model.full_model_name)
            if model_index < 0:
                raise RuntimeError(f'Failed to find model "{selected_model}" in control type'
                                   f' {control_type_name}, options={[self._model_combobox.itemText(i) for 
                                                                     i in range(len(models))]}')
            self._model_combobox.setCurrentIndex(model_index)
            if selected_model != self._control_unit.model:
                self._handle_model_change(model_index)

        with signals_blocked(self._preprocessor_combobox):
            while self._preprocessor_combobox.count() > 0:
                self._preprocessor_combobox.removeItem(0)
            preprocessors = [*control_type['module_list']]
            # Sort alphabetically, except that "None" preprocessor should be last:
            preprocessors.sort(key=lambda module: module.lower() if module != PREPROCESSOR_NONE else '~')
            for preprocessor in preprocessors:
                self._preprocessor_combobox.addItem(preprocessor)
            selected_preprocessor = self._control_unit.preprocessor.name
            if selected_preprocessor not in preprocessors or selected_preprocessor.lower() == PREPROCESSOR_NONE.lower():
                selected_preprocessor = control_type['default_option']
                if selected_preprocessor not in preprocessors:
                    selected_preprocessor = PREPROCESSOR_NONE
            preprocessor_index = self._preprocessor_combobox.findText(selected_preprocessor)
            if preprocessor_index < 0:
                raise RuntimeError(f'Failed to find preprocessor "{selected_preprocessor}" in control type'
                                   f' {control_type_name}, options={[self._preprocessor_combobox.itemText(i) for
                                                                     i in range(len(preprocessors))]}')

            self._preprocessor_combobox.setCurrentIndex(preprocessor_index)
            if selected_preprocessor != self._control_unit.preprocessor.name:
                self._handle_preprocessor_change(selected_preprocessor)

    def _handle_preprocessor_change(self, selected_preprocessor: str) -> None:
        """When the selected preprocessor module changes, update config and module option controls."""
        self._resolution_label = None
        self._resolution_slider = None
        self.set_preprocessor_preview(None)
        for label, parameter_widget in zip(self._dynamic_control_labels, self._dynamic_controls):
            self._layout.removeWidget(label)
            self._layout.removeWidget(parameter_widget)
            label.setParent(None)
            parameter_widget.setParent(None)
        self._dynamic_control_labels = []
        self._dynamic_controls = []
        preprocessor: Optional[ControlNetPreprocessor] = None
        if selected_preprocessor.lower() == PREPROCESSOR_NONE.lower():
            preprocessor = ControlNetPreprocessor(PREPROCESSOR_NONE, PREPROCESSOR_NONE, [])
        else:
            for saved_preprocessor in self._preprocessors:
                if saved_preprocessor.name == selected_preprocessor:
                    preprocessor = saved_preprocessor
            if preprocessor is None:
                raise ValueError(f'Could not find "{selected_preprocessor}" preprocessor. This indicates a bug in either'
                                 ' control type option setup or preprocessor parameterization.')
        self._control_unit.preprocessor = preprocessor
        self._schedule_cache_update()
        if selected_preprocessor.lower() != PREPROCESSOR_NONE.lower():
            for parameter in preprocessor.parameters:
                parameter_widget, label = parameter.get_input_widget(True)
                parameter_widget.valueChanged.connect(lambda _: self._schedule_cache_update())
                if self._px_perfect_checkbox is not None \
                        and parameter.key == webui_constants.PREPROCESSOR_RES_PARAM_KEY:
                    assert isinstance(parameter_widget, IntSliderSpinbox)
                    self._resolution_label = label
                    self._resolution_slider = parameter_widget
                    label.setHidden(self._control_unit.pixel_perfect)
                    parameter_widget.setHidden(self._control_unit.pixel_perfect)
                else:
                    self._dynamic_controls.append(parameter_widget)
                    self._dynamic_control_labels.append(label)
            # Resolution slider goes last so that the UI doesn't have any weird gaps if the "pixel perfect" checkbox
            # is hiding it:
            if self._resolution_slider is not None and self._resolution_label is not None:
                self._dynamic_controls.append(self._resolution_slider)
                self._dynamic_control_labels.append(self._resolution_label)
        self._preview_button.setEnabled(self._control_unit.preprocessor.name != PREPROCESSOR_NONE)
        self._build_layout()

    def _handle_model_change(self, model_idx: int) -> None:
        """Update config when the selected model changes."""
        selected_model = self._model_combobox.itemData(model_idx)
        assert isinstance(selected_model, str), (f'Expected full_name at {model_idx}/{self._model_combobox.count()},'
                                                 f' got {selected_model}({type(selected_model)},'
                                                 f' text = {self._model_combobox.itemText(model_idx)})')
        self._control_unit.model = ControlNetModel(selected_model)
        self._schedule_cache_update()

