"""Popup modal window used for scaling the edited image."""
import logging
from typing import Any, Optional, cast, TypeAlias

from PySide6.QtCore import QSize, QTimer, SignalInstance
from PySide6.QtGui import QIcon, Qt
from PySide6.QtWidgets import QDialog, QFormLayout, QPushButton, QComboBox, QSpinBox, QHBoxLayout, QDoubleSpinBox, \
    QWidget, QApplication, QVBoxLayout, QLabel

from sd_backend_client import CONTROL_MODE_PARAM_KEY, CONTROLNET_MODEL_NONE, PREPROCESSOR_RES_PARAM_KEY, \
    RESIZE_MODE_PARAM_KEY, ControlNetModel, ControlNetPreprocessor, ParameterDef

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.sd_adapters.controlnet_adapter import SavedControlNetUnit, select_preprocessor
from src.ui.layout.divider import Divider
from src.ui.panel.controlnet_panel import CONTROL_END_PARAM, CONTROL_END_FIELD, CONTROL_START_FIELD, \
    CONTROL_START_PARAM, CONTROL_STRENGTH_FIELD, CONTROL_WEIGHT_PARAM, CONTROL_WEIGHT_TITLE, CONTROL_START_STEP_TITLE, \
    CONTROL_END_STEP_TITLE, set_unit_value
from src.ui.widget.parameter_def_widget import create_parameter_widget
from src.util.parameter_def_labels import parameter_label, parameter_tooltip
from src.util.parameter import DynamicFieldWidget
from src.util.shared_constants import APP_ICON_PATH, PIL_SCALING_MODES, UPSCALE_OPTION_NONE
from src.util.signals_blocked import signals_blocked

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.image_scale_modal'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


TITLE_TEXT = _tr('Scale image')

LABEL_TEXT_SCALING_MODE = _tr('Image scaling mode:')
SCALING_MODE_OPTION_BASIC = _tr('Basic image scaling')
SCALING_MODE_OPTION_GENERATOR = _tr('Image generator scaling modes')
SCALING_MODE_OPTION_ADVANCED = _tr('Advanced AI upscaling')

LABEL_TEXT_BASIC_SCALING_DROPDOWN = _tr('Scaling algorithm:')
LABEL_TEXT_UPSCALE_METHOD = _tr('Upscale method:')
LABEL_TEXT_UPSCALE_METHOD_ADVANCED = _tr('Assisting upscale method:')

WIDTH_PX_BOX_LABEL = _tr('Width:')
WIDTH_PX_BOX_TOOLTIP = _tr('New image width in pixels')
HEIGHT_PX_BOX_LABEL = _tr('Height:')
HEIGHT_PX_BOX_TOOLTIP = _tr('New image height in pixels')
WIDTH_MULT_BOX_LABEL = _tr('Width scale:')
WIDTH_MULT_BOX_TOOLTIP = _tr('New image width (as multiplier)')
HEIGHT_MULT_BOX_LABEL = _tr('Height scale:')
HEIGHT_MULT_BOX_TOOLTIP = _tr('New image height (as multiplier)')
SCALE_BUTTON_LABEL = _tr('Scale image')
CANCEL_BUTTON_LABEL = _tr('Cancel')

CONTROLNET_TILE_MODEL_LABEL = _tr('Tile ControlNet model:')
CONTROLNET_TILE_MODEL_TOOLTIP = _tr('An optional ControlNet Tile model for stabilizing Stable Diffusion upscaling.')
CONTROLNET_TILE_PREPROCESSOR_LABEL = _tr('Tile ControlNet Preprocessor:')

MIN_PX_VALUE = 8
CONTROLNET_CACHE_TIMER_MS = 100

logger = logging.getLogger(__name__)
Spinbox: TypeAlias = QSpinBox | QDoubleSpinBox
EXCLUDED_PREPROCESSOR_PARAM_KEYS = (RESIZE_MODE_PARAM_KEY, CONTROL_MODE_PARAM_KEY, PREPROCESSOR_RES_PARAM_KEY)


class ImageScaleModal(QDialog):
    """Popup modal window used for scaling the edited image."""

    def __init__(self, default_width: int, default_height: int, multi_layer: bool = False):
        super().__init__()
        cache = Cache()
        self._base_width = default_width
        self._base_height = default_height
        self._should_scale = False
        self.setModal(True)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle(TITLE_TEXT)
        self._controlnet_cache_timer = QTimer()
        self._controlnet_cache_timer.timeout.connect(self._save_controlnet_to_cache)
        self._controlnet_cache_timer.setInterval(CONTROLNET_CACHE_TIMER_MS)
        self._controlnet_cache_timer.setSingleShot(True)
        self._layout = QVBoxLayout(self)
        self._form_layout = QFormLayout()
        self._layout.addLayout(self._form_layout)
        self._layout.addStretch(10)

        self._basic_scaling_modes = list(PIL_SCALING_MODES.keys())
        self._generator_scaling_modes = cast(list[str], cache.get(Cache.GENERATOR_SCALING_MODES))

        initial_mode = SCALING_MODE_OPTION_BASIC
        self._scaling_mode_categories = [SCALING_MODE_OPTION_BASIC]
        if len(self._generator_scaling_modes) > 0:
            self._scaling_mode_categories.append(SCALING_MODE_OPTION_GENERATOR)
        if cache.get(Cache.SD_UPSCALING_AVAILABLE):
            self._scaling_mode_categories.append(SCALING_MODE_OPTION_ADVANCED)
        self._scaling_mode_dropdown: Optional[QComboBox] = None
        if len(self._scaling_mode_categories) > 1:
            self._scaling_mode_dropdown = QComboBox()
            self._scaling_mode_dropdown.addItems(self._scaling_mode_categories)
            if (cache.get(Cache.USE_STABLE_DIFFUSION_UPSCALING)
                    and SCALING_MODE_OPTION_ADVANCED in self._scaling_mode_categories):
                initial_mode = SCALING_MODE_OPTION_ADVANCED
            elif cache.get(Cache.SCALING_MODE) in self._generator_scaling_modes:
                initial_mode = SCALING_MODE_OPTION_GENERATOR
            self._scaling_mode_dropdown.setCurrentText(initial_mode)
            assert isinstance(self._scaling_mode_dropdown.currentTextChanged, SignalInstance)
            self._scaling_mode_dropdown.currentTextChanged.connect(self._change_scaling_mode_category)
            self._form_layout.addRow(LABEL_TEXT_SCALING_MODE, self._scaling_mode_dropdown)

        self._upscale_method_dropdown = QComboBox()
        self._upscale_method_dropdown.currentTextChanged.connect(lambda upscale_method: cache.set(Cache.SCALING_MODE,
                                                                                                  upscale_method))
        self._form_layout.addRow(LABEL_TEXT_BASIC_SCALING_DROPDOWN, self._upscale_method_dropdown)
        self._form_layout.addRow(Divider(Qt.Orientation.Horizontal))

        def _add_input(default_value, min_val, max_val, title, tooltip) -> Spinbox:
            box = QSpinBox() if isinstance(default_value, int) else QDoubleSpinBox()
            box.setRange(min_val, max_val)
            box.setValue(default_value)
            box.setToolTip(tooltip)
            self._form_layout.addRow(title, box)
            return box

        max_size = cast(QSize, AppConfig().get(AppConfig.MAX_IMAGE_SIZE))
        self._width_box = _add_input(default_width, MIN_PX_VALUE, max_size.width(), WIDTH_PX_BOX_LABEL,
                                     WIDTH_PX_BOX_TOOLTIP)
        self._height_box = _add_input(default_height, MIN_PX_VALUE, max_size.height(), HEIGHT_PX_BOX_LABEL,
                                      HEIGHT_PX_BOX_TOOLTIP)
        self._x_mult_box = _add_input(1.0, 0.0, 999.0, WIDTH_MULT_BOX_LABEL,
                                      WIDTH_MULT_BOX_TOOLTIP)
        self._y_mult_box = _add_input(1.0, 0.0, 999.0, HEIGHT_MULT_BOX_LABEL,
                                      HEIGHT_MULT_BOX_TOOLTIP)

        def set_scale_on_px_change(pixel_size: int, base_value: int, scale_box: QDoubleSpinBox):
            """Apply scale box changes to pixel size boxes."""
            current_scale = scale_box.value()
            new_scale = round(int(pixel_size) / base_value, 2)
            # Ignore rounding errors:
            if int(base_value * float(current_scale)) != pixel_size:
                scale_box.setValue(new_scale)

        def set_px_on_scale_change(scale: float, base_value: float, px_box: QSpinBox):
            """Apply pixel size changes to scale size boxes."""
            current_pixel_size = px_box.value()
            new_pixel_size = int(base_value * float(scale))
            # Ignore rounding errors:
            if round(int(current_pixel_size) / base_value, 2) != scale:
                px_box.setValue(new_pixel_size)
        assert isinstance(self._width_box.valueChanged, SignalInstance)
        assert isinstance(self._x_mult_box.valueChanged, SignalInstance)
        assert isinstance(self._height_box.valueChanged, SignalInstance)
        assert isinstance(self._y_mult_box.valueChanged, SignalInstance)
        self._width_box.valueChanged.connect(
            lambda px: set_scale_on_px_change(px, default_width, self._x_mult_box))
        self._x_mult_box.valueChanged.connect(
            lambda px: set_px_on_scale_change(px, default_width, self._width_box))
        self._height_box.valueChanged.connect(
            lambda px: set_scale_on_px_change(px, default_height, self._y_mult_box))
        self._y_mult_box.valueChanged.connect(
            lambda px: set_px_on_scale_change(px, default_height, self._height_box))

        self._layer_handling_box: Optional[QComboBox] = None
        if multi_layer:
            self._layer_handling_box = cast(QComboBox, cache.get_control_widget(Cache.IMAGE_LAYER_SCALING_BEHAVIOR))
            self._form_layout.addRow(cache.get_label(Cache.IMAGE_LAYER_SCALING_BEHAVIOR), self._layer_handling_box)

        # Declare Stable Diffusion upscale controls, load options:
        self._ult_upscale_checkbox: Optional[DynamicFieldWidget] = None
        self._sd_upscale_denoising_slider: Optional[DynamicFieldWidget] = None
        self._sd_upscale_step_slider: Optional[DynamicFieldWidget] = None
        self._tile_model_dropdown: Optional[QComboBox] = None
        self._tile_preprocessor_dropdown: Optional[QComboBox] = None
        self._tile_unit_param_controls: dict[str, DynamicFieldWidget] = {}
        self._tile_preprocessor_param_controls: list[DynamicFieldWidget] = []

        self._tile_model_options = cache.get(Cache.SD_UPSCALING_CONTROLNET_TILE_MODELS)
        if len(self._tile_model_options) > 0:
            assert CONTROLNET_MODEL_NONE in self._tile_model_options
        tile_preprocessor_text = cast(list[str], cache.get(Cache.SD_UPSCALING_CONTROLNET_TILE_PREPROCESSORS))
        try:
            self._tile_preprocessors = [ControlNetPreprocessor.model_validate_json(processor_str)
                                        for processor_str in tile_preprocessor_text]
        except ValueError as err:
            logger.error(f'Error decoding tile preprocessors: {err}')
            self._tile_preprocessors = []

        self._tile_saved: Optional[SavedControlNetUnit] = None
        try:
            self._tile_saved = SavedControlNetUnit.from_json(cache.get(Cache.SD_UPSCALING_CONTROLNET_TILE_SETTINGS))
        except ValueError:
            self._tile_saved = None

        self._form_layout.addRow(Divider(Qt.Orientation.Horizontal))
        self._first_sd_upscale_row = self._form_layout.rowCount()

        def on_finish(should_scale: bool) -> None:
            """Cleanup, set choice, and close on 'scale image'/'cancel'."""
            if self._controlnet_cache_timer.isActive():
                self._save_controlnet_to_cache()
            if self._layer_handling_box is not None:
                self._remove_widget(self._layer_handling_box)
            self._remove_sd_upscale_controls()
            self._should_scale = should_scale
            self.hide()

        button_row = QWidget(self)
        self._layout.addWidget(button_row)
        button_layout = QHBoxLayout(button_row)

        self._create_button = QPushButton(self)
        self._create_button.setText(SCALE_BUTTON_LABEL)
        self._create_button.clicked.connect(lambda: on_finish(True))
        button_layout.addWidget(self._create_button)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setText(CANCEL_BUTTON_LABEL)
        self._cancel_button.clicked.connect(lambda: on_finish(False))
        button_layout.addWidget(self._cancel_button)
        self._change_scaling_mode_category(initial_mode)

    def _remove_widget(self, widget: QWidget) -> None:
        Cache().disconnect_all(widget)
        widget.setHidden(True)
        self._form_layout.removeRow(widget)

    def _change_scaling_mode_category(self, scaling_mode_category: str) -> None:
        cache = Cache()
        last_scaling_mode = cache.get(Cache.SCALING_MODE)
        mode_dropdown_label = self._form_layout.labelForField(self._upscale_method_dropdown)
        assert isinstance(mode_dropdown_label, QLabel)
        with signals_blocked(self._upscale_method_dropdown):
            while self._upscale_method_dropdown.count() > 0:
                self._upscale_method_dropdown.removeItem(0)
            if scaling_mode_category == SCALING_MODE_OPTION_BASIC:
                scaling_modes = [*self._basic_scaling_modes]
                mode_dropdown_label.setText(LABEL_TEXT_BASIC_SCALING_DROPDOWN)
            else:
                scaling_modes = [*self._generator_scaling_modes]
                mode_dropdown_label.setText(LABEL_TEXT_UPSCALE_METHOD
                                            if scaling_mode_category == SCALING_MODE_OPTION_GENERATOR
                                            else LABEL_TEXT_UPSCALE_METHOD_ADVANCED)
            if scaling_mode_category != SCALING_MODE_OPTION_GENERATOR and UPSCALE_OPTION_NONE not in scaling_modes:
                scaling_modes.append(UPSCALE_OPTION_NONE)
            self._upscale_method_dropdown.addItems(scaling_modes)
            if last_scaling_mode in scaling_modes:
                self._upscale_method_dropdown.setCurrentText(last_scaling_mode)
            else:
                upscale_mode = scaling_modes[0]
                if scaling_mode_category == SCALING_MODE_OPTION_BASIC:
                    pil_upscale_mode = AppConfig().get(AppConfig.PIL_UPSCALE_MODE)
                    if pil_upscale_mode in scaling_modes:
                        upscale_mode = pil_upscale_mode
                else:
                    cached_webui_mode = cache.get(Cache.WEBUI_CACHED_SCALING_MODE)
                    if cached_webui_mode in scaling_modes:
                        upscale_mode = cached_webui_mode
                    else:
                        cached_comfyui_mode = cache.get(Cache.COMFYUI_CACHED_SCALING_MODE)
                        if cached_comfyui_mode in scaling_modes:
                            upscale_mode = cached_comfyui_mode
                self._upscale_method_dropdown.setCurrentText(upscale_mode)
                cache.set(Cache.SCALING_MODE, upscale_mode)
        if scaling_mode_category == SCALING_MODE_OPTION_ADVANCED:
            cache.set(Cache.USE_STABLE_DIFFUSION_UPSCALING, True)
            self._create_sd_upscale_controls()
        else:
            cache.set(Cache.USE_STABLE_DIFFUSION_UPSCALING, False)
            self._remove_sd_upscale_controls()

    def _save_controlnet_to_cache(self) -> None:
        if self._controlnet_cache_timer.isActive():
            self._controlnet_cache_timer.stop()
        if self._tile_saved is None:
            logger.warning('No ControlNet tile scaling unit to save.')
            return
        Cache().set(Cache.SD_UPSCALING_CONTROLNET_TILE_SETTINGS, self._tile_saved.to_json())

    def _schedule_controlnet_cache_save(self, _=None) -> None:
        if not self._controlnet_cache_timer.isActive():
            self._controlnet_cache_timer.start()

    def _toggle_4x_scaling_limit(self, use_limit: bool) -> None:
        if use_limit:
            self._width_box.setMaximum(self._base_width * 4)
            self._height_box.setMaximum(self._base_height * 4)
            self._x_mult_box.setMaximum(4.0)
            self._y_mult_box.setMaximum(4.0)
        else:
            max_size = cast(QSize, AppConfig().get(AppConfig.MAX_IMAGE_SIZE))
            self._width_box.setMaximum(max_size.width())
            self._height_box.setMaximum(max_size.height())
            self._x_mult_box.setMaximum(max_size.width() / self._base_width)
            self._y_mult_box.setMaximum(max_size.height() / self._base_height)

    def _tile_model_update(self, model_name: str) -> None:
        assert self._tile_model_dropdown is not None and self._tile_model_dropdown.currentText() == model_name
        assert self._tile_saved is not None
        self._tile_saved.enabled = model_name != CONTROLNET_MODEL_NONE
        self._tile_saved.unit.model = None if model_name == CONTROLNET_MODEL_NONE else ControlNetModel(model_name)
        self._schedule_controlnet_cache_save()
        if model_name == CONTROLNET_MODEL_NONE:
            self._remove_controlnet_tile_inputs()
        else:
            if len(self._tile_unit_param_controls) == 0:
                unit = self._tile_saved.unit
                for field, param, label in self._tile_unit_params():
                    control_widget = create_parameter_widget(
                        param, getattr(unit, field), lambda value, name=field: self._tile_unit_update(name, value))
                    self._form_layout.insertRow(self._form_layout.rowCount(), label, control_widget)
                    self._tile_unit_param_controls[field] = control_widget
            new_preprocessor_name: Optional[str] = None
            if self._tile_preprocessor_dropdown is None:
                self._tile_preprocessor_dropdown = QComboBox()
                preprocessor_names = [preprocessor.name for preprocessor in self._tile_preprocessors]
                self._tile_preprocessor_dropdown.addItems(preprocessor_names)
                preprocessor = self._tile_saved.unit.preprocessor
                selected_name = None if preprocessor is None else preprocessor.typedef.name
                if selected_name not in preprocessor_names:
                    selected_name = preprocessor_names[0]
                self._tile_preprocessor_dropdown.setCurrentText(selected_name)
                self._form_layout.insertRow(self._form_layout.rowCount(), CONTROLNET_TILE_PREPROCESSOR_LABEL,
                                            self._tile_preprocessor_dropdown)
                self._tile_preprocessor_dropdown.currentTextChanged.connect(self._tile_preprocessor_update)
                new_preprocessor_name = selected_name
            if new_preprocessor_name is not None:
                self._tile_preprocessor_update(new_preprocessor_name)

    def _tile_unit_update(self, field: str, value: float) -> None:
        """Sets a tile unit value, updating the other step input if it moved."""
        assert self._tile_saved is not None
        moved_field = set_unit_value(self._tile_saved.unit, field, value)
        if moved_field is not None and moved_field in self._tile_unit_param_controls:
            with signals_blocked(self._tile_unit_param_controls[moved_field]):
                self._tile_unit_param_controls[moved_field].setValue(value)  # type: ignore[arg-type]
        self._schedule_controlnet_cache_save()

    def _tile_preprocessor_update(self, preprocessor_name: str) -> None:
        assert self._tile_saved is not None
        self._tile_saved.enabled = True
        self._remove_controlnet_tile_preprocessor_inputs()
        typedef = next(preprocessor for preprocessor in self._tile_preprocessors
                       if preprocessor.name == preprocessor_name)
        preprocessor = select_preprocessor(typedef, self._tile_saved.unit.preprocessor)
        self._tile_saved.unit.preprocessor = preprocessor

        for preprocessor_param in typedef.parameters:
            if preprocessor_param.key in EXCLUDED_PREPROCESSOR_PARAM_KEYS:
                continue
            control_widget = create_parameter_widget(
                preprocessor_param, preprocessor.parameter_values[preprocessor_param.key],
                lambda value, key=preprocessor_param.key: self._tile_preprocessor_value_update(key, value))
            control_widget.setToolTip(parameter_tooltip(preprocessor_param))
            self._form_layout.insertRow(self._form_layout.rowCount(), parameter_label(preprocessor_param),
                                        control_widget)
            self._tile_preprocessor_param_controls.append(control_widget)
        self._schedule_controlnet_cache_save()

    def _tile_preprocessor_value_update(self, key: str, value: Any) -> None:
        assert self._tile_saved is not None
        if self._tile_saved.unit.preprocessor is not None:
            self._tile_saved.unit.preprocessor.parameter_values[key] = value
        self._schedule_controlnet_cache_save()

    def _remove_controlnet_tile_preprocessor_inputs(self) -> None:
        for preprocessor_widget in self._tile_preprocessor_param_controls:
            preprocessor_widget.setHidden(True)
            self._form_layout.removeRow(preprocessor_widget)
        self._tile_preprocessor_param_controls.clear()

    @staticmethod
    def _tile_unit_params() -> list[tuple[str, ParameterDef, str]]:
        """Returns the tile unit's strength, start and end fields, definitions and labels, in input order."""
        return [(CONTROL_STRENGTH_FIELD, CONTROL_WEIGHT_PARAM, CONTROL_WEIGHT_TITLE),
                (CONTROL_START_FIELD, CONTROL_START_PARAM, CONTROL_START_STEP_TITLE),
                (CONTROL_END_FIELD, CONTROL_END_PARAM, CONTROL_END_STEP_TITLE)]

    def _remove_controlnet_tile_inputs(self) -> None:
        self._remove_controlnet_tile_preprocessor_inputs()
        for unit_widget in self._tile_unit_param_controls.values():
            unit_widget.setHidden(True)
            self._form_layout.removeRow(unit_widget)
        self._tile_unit_param_controls.clear()
        if self._tile_preprocessor_dropdown is not None:
            self._tile_preprocessor_dropdown.currentTextChanged.disconnect(self._tile_preprocessor_update)
            self._tile_preprocessor_dropdown.setHidden(True)
            self._form_layout.removeRow(self._tile_preprocessor_dropdown)
            self._tile_preprocessor_dropdown = None

    def _create_sd_upscale_controls(self) -> None:
        cache = Cache()
        if not cache.get(Cache.SD_UPSCALING_AVAILABLE):
            raise RuntimeError('Tried to add SD Upscaling controls when SD Upscaling is not available.')
        if not cache.get(Cache.USE_STABLE_DIFFUSION_UPSCALING):
            raise RuntimeError('Tried to add SD Upscaling controls when SD Upscaling is not enabled.')
        row_insert_idx = self._first_sd_upscale_row + 1

        assert self._ult_upscale_checkbox is None
        if cache.get(Cache.ULTIMATE_UPSCALE_SCRIPT_AVAILABLE):
            self._ult_upscale_checkbox = cache.get_control_widget(Cache.USE_ULTIMATE_UPSCALE_SCRIPT)
            self._ult_upscale_checkbox.setText('')
            self._form_layout.insertRow(row_insert_idx, cache.get_label(Cache.USE_ULTIMATE_UPSCALE_SCRIPT),
                                        self._ult_upscale_checkbox)
            self._ult_upscale_checkbox.valueChanged.connect(self._toggle_4x_scaling_limit)
            if cache.get(Cache.USE_ULTIMATE_UPSCALE_SCRIPT):
                self._toggle_4x_scaling_limit(True)
            row_insert_idx += 1

        assert self._sd_upscale_denoising_slider is None
        self._sd_upscale_denoising_slider = cache.get_control_widget(Cache.SD_UPSCALING_DENOISING_STRENGTH)
        self._form_layout.insertRow(row_insert_idx, cache.get_label(Cache.SD_UPSCALING_DENOISING_STRENGTH),
                                    self._sd_upscale_denoising_slider)
        row_insert_idx += 1

        assert self._sd_upscale_step_slider is None
        self._sd_upscale_step_slider = cache.get_control_widget(Cache.SD_UPSCALING_STEP_COUNT)
        self._form_layout.insertRow(row_insert_idx, cache.get_label(Cache.SD_UPSCALING_STEP_COUNT),
                                    self._sd_upscale_step_slider)
        row_insert_idx += 1

        assert self._tile_model_dropdown is None
        if len(self._tile_model_options) > 0 and len(self._tile_preprocessors) > 0 \
                and self._tile_saved is not None:
            self._tile_model_dropdown = QComboBox()
            self._tile_model_dropdown.setToolTip(CONTROLNET_TILE_MODEL_TOOLTIP)
            self._tile_model_dropdown.addItems(self._tile_model_options)
            tile_model = self._tile_saved.unit.model
            tile_model_name = CONTROLNET_MODEL_NONE if tile_model is None else tile_model.full_model_name
            if tile_model_name in self._tile_model_options:
                self._tile_model_dropdown.setCurrentText(tile_model_name)
            else:
                self._tile_model_dropdown.setCurrentIndex(0)
                self._tile_saved.unit.model = ControlNetModel(self._tile_model_options[0])
                self._schedule_controlnet_cache_save()
            self._tile_model_dropdown.currentTextChanged.connect(self._tile_model_update)
            self._form_layout.insertRow(row_insert_idx, CONTROLNET_TILE_MODEL_LABEL,
                                        self._tile_model_dropdown)
            self._tile_model_update(self._tile_model_dropdown.currentText())

    def _remove_sd_upscale_controls(self) -> None:
        if self._ult_upscale_checkbox is not None:
            self._toggle_4x_scaling_limit(False)
            self._ult_upscale_checkbox.valueChanged.disconnect(self._toggle_4x_scaling_limit)
            self._remove_widget(self._ult_upscale_checkbox)
            self._ult_upscale_checkbox = None
        if self._sd_upscale_denoising_slider is not None:
            self._remove_widget(self._sd_upscale_denoising_slider)
            self._sd_upscale_denoising_slider = None
        if self._sd_upscale_step_slider is not None:
            self._remove_widget(self._sd_upscale_step_slider)
            self._sd_upscale_step_slider = None
        if self._tile_model_dropdown is not None:
            self._tile_model_dropdown.currentTextChanged.disconnect(self._tile_model_update)
            self._remove_widget(self._tile_model_dropdown)
            self._tile_model_dropdown = None
        self._remove_controlnet_tile_inputs()

    def show_image_modal(self) -> Optional[QSize]:
        """Show the modal, returning the selected size when the modal closes."""
        self.exec()
        if self._should_scale:
            return QSize(int(self._width_box.value()), int(self._height_box.value()))
        return None
