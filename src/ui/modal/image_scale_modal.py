"""Popup modal window used for scaling the edited image.

A `SegmentedControl` picks the scaling mode (basic, generator or AI upscaling), listing only the modes the current
backend offers. The size sits in a `GeometryBlock` with an aspect lock and a pixel / percent switch. The AI upscaling
settings sit in their own `PanelSection`, built the first time that mode is picked so that opening the dialog in
another mode leaves the saved ControlNet tile settings alone.
"""
import logging
from typing import Any, Optional, cast

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from sd_backend_client import CONTROL_MODE_PARAM_KEY, CONTROLNET_MODEL_NONE, PREPROCESSOR_RES_PARAM_KEY, \
    RESIZE_MODE_PARAM_KEY, ControlNetModel, ControlNetPreprocessor, ParameterDef

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.sd_adapters.controlnet_adapter import SavedControlNetUnit, select_preprocessor
from src.ui.input_fields import geometry_block
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.field_factory import create_control_widget
from src.ui.input_fields.geometry_block import GeometryBlock
from src.ui.input_fields.number_field import MAX_WIDTH as NUMBER_FIELD_MAX_WIDTH, NumberField
from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from src.ui.input_fields.slider_field import number_field_for_parameter
from src.ui.modal.controls_column import ControlsColumn, MAX_SCREEN_FRACTION
from src.ui.modal.dialog_footer import DialogFooter
from src.ui.panel.controlnet_panel import CONTROL_END_PARAM, CONTROL_END_FIELD, CONTROL_START_FIELD, \
    CONTROL_START_PARAM, CONTROL_STRENGTH_FIELD, CONTROL_WEIGHT_PARAM, CONTROL_WEIGHT_TITLE, CONTROL_START_STEP_TITLE, \
    CONTROL_END_STEP_TITLE, set_unit_value
from src.ui.widget.panel_section import PanelSection
from src.ui.widget.parameter_def_widget import create_parameter_field, create_parameter_widget, \
    is_numeric_field_parameter
from src.util.parameter_def_labels import parameter_label, parameter_tooltip
from src.util.shared_constants import APP_ICON_PATH
from src.util.shared_text import PIL_SCALING_MODES, UPSCALE_OPTION_NONE
from src.util.signals_blocked import signals_blocked

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.image_scale_modal'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


TITLE_TEXT = _tr('Scale image')

SCALING_MODE_BASIC = _tr('Basic')
SCALING_MODE_BASIC_TOOLTIP = _tr('Scale with a basic image scaling algorithm.')
SCALING_MODE_GENERATOR = _tr('Generator')
SCALING_MODE_GENERATOR_TOOLTIP = _tr('Scale with one of the image generator\'s scaling modes.')
SCALING_MODE_AI = _tr('AI upscaling')
SCALING_MODE_AI_TOOLTIP = _tr('Upscale with Stable Diffusion, adding detail while scaling.')

LABEL_TEXT_BASIC_SCALING_DROPDOWN = _tr('Scaling algorithm:')
LABEL_TEXT_UPSCALE_METHOD = _tr('Upscale method:')
LABEL_TEXT_UPSCALE_METHOD_ADVANCED = _tr('Assisting upscale method:')

SIZE_SECTION_TITLE = _tr('Size')
AI_SECTION_TITLE = _tr('AI upscaling settings')
UNIT_PIXELS = _tr('Pixels')
UNIT_PIXELS_TOOLTIP = _tr('Enter the new size in pixels.')
UNIT_PERCENT = _tr('Percent')
UNIT_PERCENT_TOOLTIP = _tr('Enter the new size as a percentage of the current size.')
NEW_SIZE_TEXT = _tr('New size: {width} x {height} px')
SCALE_BUTTON_LABEL = _tr('Scale image')

CONTROLNET_TILE_MODEL_LABEL = _tr('Tile ControlNet model:')
CONTROLNET_TILE_MODEL_TOOLTIP = _tr('An optional ControlNet Tile model for stabilizing Stable Diffusion upscaling.')
CONTROLNET_TILE_PREPROCESSOR_LABEL = _tr('Tile ControlNet preprocessor:')

MIN_PX_VALUE = 8
# One percent, the percent switch's step:
MIN_PERCENT_SCALE = 0.01
CONTROLNET_CACHE_TIMER_MS = 100
CONTROLS_COLUMN_WIDTH = 380
MIN_WINDOW_HEIGHT = 200
# The Ultimate SD Upscale script limits the scale factor:
ULTIMATE_UPSCALE_MAX_FACTOR = 4

# Mode and unit values, which are never translated:
MODE_BASIC = 'basic'
MODE_GENERATOR = 'generator'
MODE_AI = 'ai'
UNIT_PX = 'px'
UNIT_PCT = 'percent'

logger = logging.getLogger(__name__)
EXCLUDED_PREPROCESSOR_PARAM_KEYS = (RESIZE_MODE_PARAM_KEY, CONTROL_MODE_PARAM_KEY, PREPROCESSOR_RES_PARAM_KEY)


def _plain_label(label: str) -> str:
    """Returns a form-style label ("Steps:") without its colon, for a field that draws its own label."""
    return label.rstrip(': ')


def _labeled_row(label: str, widget: QWidget, parent: QWidget, match_fields: bool = False) -> QWidget:
    """Returns a label and a widget in a row, the widget filling the rest of it.

    With `match_fields`, the row is no wider than a `NumberField`, so the widget's right edge lines up with the number
    fields stacked above and below it.
    """
    row = QWidget(parent)
    if match_fields:
        row.setMaximumWidth(NUMBER_FIELD_MAX_WIDTH)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(QLabel(label, row))
    layout.addWidget(widget, stretch=1)
    return row


def _clamp_combo_boxes(parent: QWidget) -> None:
    """Keeps every dropdown under `parent` from widening the dialog to fit its longest option.

    Backend-supplied option names (upscale methods, ControlNet models) can be arbitrarily long. A dropdown with an
    ignored horizontal size policy fills whatever width its row gets and contributes none of its own, so its right edge
    follows the row's whatever the font or option text. This is the policy `controlnet_panel._shrinking_combo_box`
    uses. Each option also gets a tooltip with its full name; the popup list is not limited to the dropdown's width.
    """
    for combo in parent.findChildren(QComboBox):
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        for index in range(combo.count()):
            combo.setItemData(index, combo.itemText(index), Qt.ItemDataRole.ToolTipRole)


def _clear_layout(layout: QVBoxLayout) -> None:
    """Deletes every widget in a layout."""
    while layout.count() > 0:
        item = layout.takeAt(0)
        widget = item.widget() if item is not None else None
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def _cache_field(key: str) -> NumberField:
    """Returns a field bound to a `Cache` number, labeled and limited by its definition."""
    entry = Cache().get_entry(key)
    field = number_field_for_parameter(entry, Cache().get(key))
    field.set_label(_plain_label(entry.name))
    field.valueChanged.connect(lambda value, cache_key=key: Cache().set(cache_key, value))
    return field


class ImageScaleModal(QDialog):
    """Popup modal window used for scaling the edited image."""

    def __init__(self, default_width: int, default_height: int, multi_layer: bool = False):
        super().__init__()
        cache = Cache()
        self._base_width = default_width
        self._base_height = default_height
        self._should_scale = False
        self._mode = MODE_BASIC
        self.setModal(True)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle(TITLE_TEXT)
        self._controlnet_cache_timer = QTimer(self)
        self._controlnet_cache_timer.timeout.connect(self._save_controlnet_to_cache)
        self._controlnet_cache_timer.setInterval(CONTROLNET_CACHE_TIMER_MS)
        self._controlnet_cache_timer.setSingleShot(True)

        self._basic_scaling_modes = list(PIL_SCALING_MODES.keys())
        self._generator_scaling_modes = cast(list[str], cache.get(Cache.GENERATOR_SCALING_MODES))

        segments = [Segment(MODE_BASIC, SCALING_MODE_BASIC, tooltip=SCALING_MODE_BASIC_TOOLTIP)]
        if len(self._generator_scaling_modes) > 0:
            segments.append(Segment(MODE_GENERATOR, SCALING_MODE_GENERATOR, tooltip=SCALING_MODE_GENERATOR_TOOLTIP))
        if cache.get(Cache.SD_UPSCALING_AVAILABLE):
            segments.append(Segment(MODE_AI, SCALING_MODE_AI, tooltip=SCALING_MODE_AI_TOOLTIP))
        initial_mode = MODE_BASIC
        self._mode_control: Optional[SegmentedControl] = None
        if len(segments) > 1:
            self._mode_control = SegmentedControl(segments, DisplayMode.LABEL, parent=self)
            available = {segment.value for segment in segments}
            if cache.get(Cache.USE_STABLE_DIFFUSION_UPSCALING) and MODE_AI in available:
                initial_mode = MODE_AI
            elif cache.get(Cache.SCALING_MODE) in self._generator_scaling_modes:
                initial_mode = MODE_GENERATOR
            self._mode_control.set_value(initial_mode)
            self._mode_control.valueChanged.connect(self._change_scaling_mode)

        self._upscale_method_label = QLabel(LABEL_TEXT_BASIC_SCALING_DROPDOWN, self)
        self._upscale_method_dropdown = QComboBox(self)
        self._upscale_method_dropdown.currentTextChanged.connect(
            lambda upscale_method: Cache().set(Cache.SCALING_MODE, upscale_method))
        method_row = QWidget(self)
        method_layout = QHBoxLayout(method_row)
        method_layout.setContentsMargins(0, 0, 0, 0)
        method_layout.addWidget(self._upscale_method_label)
        method_layout.addWidget(self._upscale_method_dropdown, stretch=1)

        # Size section:
        self._geometry = GeometryBlock(show_position=False, unit_switch=True, parent=self)
        self._geometry.set_image_size(QSize(default_width, default_height))
        self._geometry.set_values(w=default_width, h=default_height, scale_x=1.0, scale_y=1.0)
        self._geometry.valueChanged.connect(self._geometry_changed)
        self._unit_control = SegmentedControl(
            [Segment(UNIT_PX, UNIT_PIXELS, tooltip=UNIT_PIXELS_TOOLTIP),
             Segment(UNIT_PCT, UNIT_PERCENT, tooltip=UNIT_PERCENT_TOOLTIP)], DisplayMode.LABEL, parent=self)
        self._unit_control.valueChanged.connect(self._unit_changed)
        self._size_label = QLabel(self)
        size_body = QWidget(self)
        size_layout = QVBoxLayout(size_body)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.addWidget(self._unit_control)
        size_layout.addWidget(self._geometry)
        size_layout.addWidget(self._size_label)
        self._layer_handling_box: Optional[QWidget] = None
        if multi_layer:
            self._layer_handling_box = create_control_widget(cache, Cache.IMAGE_LAYER_SCALING_BEHAVIOR)
            row = _labeled_row(cache.get_label(Cache.IMAGE_LAYER_SCALING_BEHAVIOR), self._layer_handling_box,
                               size_body)
            row.setToolTip(cache.get_tooltip(Cache.IMAGE_LAYER_SCALING_BEHAVIOR))
            size_layout.addWidget(row)

        # AI upscaling section, filled in by `_create_sd_upscale_controls`:
        self._ult_upscale_checkbox: Optional[CheckBox] = None
        self._tile_model_dropdown: Optional[QComboBox] = None
        self._tile_preprocessor_dropdown: Optional[QComboBox] = None
        self._tile_unit_param_controls: dict[str, NumberField] = {}
        self._tile_preprocessor_param_controls: list[QWidget] = []
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
        self._ai_body = QWidget(self)
        self._ai_layout = QVBoxLayout(self._ai_body)
        self._ai_layout.setContentsMargins(0, 0, 0, 0)
        self._tile_layout = QVBoxLayout()
        self._tile_layout.setContentsMargins(0, 0, 0, 0)
        self._ai_section = PanelSection(AI_SECTION_TITLE, self._ai_body)
        self._ai_section.setVisible(False)
        self._ai_controls_created = False

        controls = QWidget(self)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        if self._mode_control is not None:
            controls_layout.addWidget(self._mode_control)
        controls_layout.addWidget(method_row)
        controls_layout.addWidget(PanelSection(SIZE_SECTION_TITLE, size_body))
        controls_layout.addWidget(self._ai_section)
        controls_layout.addStretch(1)
        self._controls = controls
        self._scroll = ControlsColumn(controls, CONTROLS_COLUMN_WIDTH)
        # No preview sits beside the controls, so the column spans the dialog. A fixed column clips the AI upscaling
        # controls, which need more than CONTROLS_COLUMN_WIDTH:
        self._scroll.set_stacked(True)

        self._footer = DialogFooter(SCALE_BUTTON_LABEL, self)
        self._footer.accepted.connect(self._confirm)
        self._footer.rejected.connect(self.reject)
        self._create_button = self._footer.confirm_button
        self._cancel_button = self._footer.cancel_button

        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self._scroll, stretch=1)
        self._layout.addWidget(self._footer)
        self.setMinimumHeight(MIN_WINDOW_HEIGHT)
        self._apply_size_limits()
        self._update_size_label()
        self._change_scaling_mode(initial_mode)

    # -----------------------------------------------------------------------------------------------------------------
    # Size
    # -----------------------------------------------------------------------------------------------------------------

    def _size_limit_factor(self) -> Optional[int]:
        """Returns the largest scale factor the current mode allows, or None for the configured maximum size."""
        if self._mode == MODE_AI and self._ult_upscale_checkbox is not None and self._ult_upscale_checkbox.value():
            return ULTIMATE_UPSCALE_MAX_FACTOR
        return None

    def _apply_size_limits(self) -> None:
        max_size = cast(QSize, AppConfig().get(AppConfig.MAX_IMAGE_SIZE))
        max_width, max_height = max_size.width(), max_size.height()
        factor = self._size_limit_factor()
        if factor is not None:
            max_width = min(max_width, self._base_width * factor)
            max_height = min(max_height, self._base_height * factor)
        self._geometry.set_limits(geometry_block.WIDTH, MIN_PX_VALUE, max_width)
        self._geometry.set_limits(geometry_block.HEIGHT, MIN_PX_VALUE, max_height)
        self._geometry.set_limits(geometry_block.SCALE_X, MIN_PERCENT_SCALE, max_width / self._base_width)
        self._geometry.set_limits(geometry_block.SCALE_Y, MIN_PERCENT_SCALE, max_height / self._base_height)
        self._sync_size_fields(geometry_block.WIDTH)
        self._sync_size_fields(geometry_block.HEIGHT)

    def _sync_size_fields(self, changed: str) -> None:
        """Updates the pixel or scale field that mirrors the one that changed, without touching the lock's ratio."""
        base = {geometry_block.WIDTH: self._base_width, geometry_block.HEIGHT: self._base_height,
                geometry_block.SCALE_X: self._base_width, geometry_block.SCALE_Y: self._base_height}[changed]
        mirror = {geometry_block.WIDTH: geometry_block.SCALE_X, geometry_block.HEIGHT: geometry_block.SCALE_Y,
                  geometry_block.SCALE_X: geometry_block.WIDTH, geometry_block.SCALE_Y: geometry_block.HEIGHT}[changed]
        value = self._geometry.value(changed)
        mirrored_value = value / base if changed in (geometry_block.WIDTH, geometry_block.HEIGHT) \
            else round(value * base)
        field = self._geometry.field(mirror)
        with signals_blocked(field):
            field.set_value(mirrored_value)

    def _geometry_changed(self, name: str, _value: object) -> None:
        self._sync_size_fields(name)
        self._update_size_label()

    def _unit_changed(self, unit: str) -> None:
        self._geometry.set_percent_mode(unit == UNIT_PCT)

    def _new_size(self) -> QSize:
        return QSize(int(self._geometry.value(geometry_block.WIDTH)), int(self._geometry.value(geometry_block.HEIGHT)))

    def _update_size_label(self) -> None:
        new_size = self._new_size()
        self._size_label.setText(NEW_SIZE_TEXT.format(width=new_size.width(), height=new_size.height()))

    # -----------------------------------------------------------------------------------------------------------------
    # Scaling mode
    # -----------------------------------------------------------------------------------------------------------------

    def _change_scaling_mode(self, mode: str) -> None:
        cache = Cache()
        self._mode = mode
        last_scaling_mode = cache.get(Cache.SCALING_MODE)
        with signals_blocked(self._upscale_method_dropdown):
            while self._upscale_method_dropdown.count() > 0:
                self._upscale_method_dropdown.removeItem(0)
            if mode == MODE_BASIC:
                scaling_modes = [*self._basic_scaling_modes]
                self._upscale_method_label.setText(LABEL_TEXT_BASIC_SCALING_DROPDOWN)
            else:
                scaling_modes = [*self._generator_scaling_modes]
                self._upscale_method_label.setText(LABEL_TEXT_UPSCALE_METHOD if mode == MODE_GENERATOR
                                                   else LABEL_TEXT_UPSCALE_METHOD_ADVANCED)
            if mode != MODE_GENERATOR and UPSCALE_OPTION_NONE not in scaling_modes:
                scaling_modes.append(UPSCALE_OPTION_NONE)
            self._upscale_method_dropdown.addItems(scaling_modes)
            if last_scaling_mode in scaling_modes:
                self._upscale_method_dropdown.setCurrentText(last_scaling_mode)
            else:
                upscale_mode = scaling_modes[0]
                if mode == MODE_BASIC:
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
        cache.set(Cache.USE_STABLE_DIFFUSION_UPSCALING, mode == MODE_AI)
        if mode == MODE_AI:
            self._create_sd_upscale_controls()
        self._ai_section.setVisible(mode == MODE_AI)
        self._apply_size_limits()
        self._update_size_label()
        self._fit_height()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the size that shows every visible control, bounded by the screen."""
        margins = self._layout.contentsMargins()
        hint = QSize(max(CONTROLS_COLUMN_WIDTH, self._controls.minimumSizeHint().width() + self._scroll_extent())
                     + margins.left() + margins.right(),
                     self._controls.sizeHint().height() + self._footer.sizeHint().height() + self._layout.spacing()
                     + margins.top() + margins.bottom())
        screen = self.screen()
        if screen is not None:
            hint.setHeight(min(hint.height(), round(screen.availableGeometry().height() * MAX_SCREEN_FRACTION)))
        return hint.expandedTo(self.minimumSizeHint())

    def _scroll_extent(self) -> int:
        """Returns the width the vertical scroll bar takes from the controls column."""
        return self._scroll.verticalScrollBar().sizeHint().width()

    def _fit_height(self) -> None:
        """Resizes an open dialog to the controls' height and at least their width, after a mode change or a change
        to the controls shows or hides some."""
        _clamp_combo_boxes(self._controls)
        margins = self._layout.contentsMargins()
        min_width = self._controls.minimumSizeHint().width() + self._scroll_extent() + margins.left() + margins.right()
        self.setMinimumWidth(min_width)
        if self.isVisible():
            self.resize(max(self.width(), min_width), self.sizeHint().height())

    # -----------------------------------------------------------------------------------------------------------------
    # AI upscaling controls
    # -----------------------------------------------------------------------------------------------------------------

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

    def _create_sd_upscale_controls(self) -> None:
        """Builds the AI upscaling section's controls the first time AI upscaling is picked."""
        if self._ai_controls_created:
            return
        cache = Cache()
        if not cache.get(Cache.SD_UPSCALING_AVAILABLE):
            raise RuntimeError('Tried to add SD Upscaling controls when SD Upscaling is not available.')
        self._ai_controls_created = True
        if cache.get(Cache.ULTIMATE_UPSCALE_SCRIPT_AVAILABLE):
            checkbox = cast(CheckBox, create_control_widget(cache, Cache.USE_ULTIMATE_UPSCALE_SCRIPT))
            checkbox.setText(_plain_label(cache.get_label(Cache.USE_ULTIMATE_UPSCALE_SCRIPT)))
            checkbox.setToolTip(cache.get_tooltip(Cache.USE_ULTIMATE_UPSCALE_SCRIPT))
            checkbox.valueChanged.connect(self._ultimate_upscale_toggled)
            self._ult_upscale_checkbox = checkbox
            self._ai_layout.addWidget(checkbox)
        self._ai_layout.addWidget(_cache_field(Cache.SD_UPSCALING_DENOISING_STRENGTH))
        self._ai_layout.addWidget(_cache_field(Cache.SD_UPSCALING_STEP_COUNT))
        if len(self._tile_model_options) > 0 and len(self._tile_preprocessors) > 0 and self._tile_saved is not None:
            self._tile_model_dropdown = QComboBox(self)
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
            self._ai_layout.addWidget(_labeled_row(CONTROLNET_TILE_MODEL_LABEL, self._tile_model_dropdown,
                                                   self._ai_body, match_fields=True))
            self._ai_layout.addLayout(self._tile_layout)
            self._tile_model_update(self._tile_model_dropdown.currentText())
        self._ult_upscale_limit_changed()

    def _ultimate_upscale_toggled(self, _checked: bool) -> None:
        self._ult_upscale_limit_changed()

    def _ult_upscale_limit_changed(self) -> None:
        self._apply_size_limits()
        self._update_size_label()

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
                    control_field = create_parameter_field(
                        param, getattr(unit, field), lambda value, name=field: self._tile_unit_update(name, value))
                    control_field.set_label(_plain_label(label))
                    self._tile_layout.addWidget(control_field)
                    self._tile_unit_param_controls[field] = control_field
            new_preprocessor_name: Optional[str] = None
            if self._tile_preprocessor_dropdown is None:
                self._tile_preprocessor_dropdown = QComboBox(self)
                preprocessor_names = [preprocessor.name for preprocessor in self._tile_preprocessors]
                self._tile_preprocessor_dropdown.addItems(preprocessor_names)
                preprocessor = self._tile_saved.unit.preprocessor
                selected_name = None if preprocessor is None else preprocessor.typedef.name
                if selected_name not in preprocessor_names:
                    selected_name = preprocessor_names[0]
                self._tile_preprocessor_dropdown.setCurrentText(selected_name)
                self._tile_layout.addWidget(_labeled_row(CONTROLNET_TILE_PREPROCESSOR_LABEL,
                                                         self._tile_preprocessor_dropdown, self._ai_body,
                                                         match_fields=True))
                self._tile_preprocessor_dropdown.currentTextChanged.connect(self._tile_preprocessor_update)
                new_preprocessor_name = selected_name
            if new_preprocessor_name is not None:
                self._tile_preprocessor_update(new_preprocessor_name)
        self._fit_height()

    def _tile_unit_update(self, field: str, value: float) -> None:
        """Sets a tile unit value, updating the other step input if it moved."""
        assert self._tile_saved is not None
        moved_field = set_unit_value(self._tile_saved.unit, field, value)
        if moved_field is not None and moved_field in self._tile_unit_param_controls:
            with signals_blocked(self._tile_unit_param_controls[moved_field]):
                self._tile_unit_param_controls[moved_field].set_value(value)
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

            def _changed(value: Any, key=preprocessor_param.key) -> None:
                self._tile_preprocessor_value_update(key, value)

            current = preprocessor.parameter_values[preprocessor_param.key]
            control: QWidget
            if is_numeric_field_parameter(preprocessor_param):
                control = create_parameter_field(preprocessor_param, current, _changed)
            else:
                control = _labeled_row(parameter_label(preprocessor_param),
                                       create_parameter_widget(preprocessor_param, current, _changed), self._ai_body,
                                       match_fields=True)
            control.setToolTip(parameter_tooltip(preprocessor_param))
            self._tile_layout.addWidget(control)
            self._tile_preprocessor_param_controls.append(control)
        self._schedule_controlnet_cache_save()
        self._fit_height()

    def _tile_preprocessor_value_update(self, key: str, value: Any) -> None:
        assert self._tile_saved is not None
        if self._tile_saved.unit.preprocessor is not None:
            self._tile_saved.unit.preprocessor.parameter_values[key] = value
        self._schedule_controlnet_cache_save()

    def _remove_controlnet_tile_preprocessor_inputs(self) -> None:
        for preprocessor_widget in self._tile_preprocessor_param_controls:
            self._tile_layout.removeWidget(preprocessor_widget)
            preprocessor_widget.setParent(None)
            preprocessor_widget.deleteLater()
        self._tile_preprocessor_param_controls.clear()

    @staticmethod
    def _tile_unit_params() -> list[tuple[str, ParameterDef, str]]:
        """Returns the tile unit's strength, start and end fields, definitions and labels, in input order."""
        return [(CONTROL_STRENGTH_FIELD, CONTROL_WEIGHT_PARAM, CONTROL_WEIGHT_TITLE),
                (CONTROL_START_FIELD, CONTROL_START_PARAM, CONTROL_START_STEP_TITLE),
                (CONTROL_END_FIELD, CONTROL_END_PARAM, CONTROL_END_STEP_TITLE)]

    def _remove_controlnet_tile_inputs(self) -> None:
        self._remove_controlnet_tile_preprocessor_inputs()
        self._tile_unit_param_controls.clear()
        if self._tile_preprocessor_dropdown is not None:
            self._tile_preprocessor_dropdown.currentTextChanged.disconnect(self._tile_preprocessor_update)
            self._tile_preprocessor_dropdown = None
        _clear_layout(self._tile_layout)

    # -----------------------------------------------------------------------------------------------------------------
    # Closing
    # -----------------------------------------------------------------------------------------------------------------

    def _finish(self, should_scale: bool) -> None:
        """Flushes pending ControlNet settings, unbinds config-bound controls, records the choice and hides."""
        if self._controlnet_cache_timer.isActive():
            self._save_controlnet_to_cache()
        for widget in (self._layer_handling_box, self._ult_upscale_checkbox):
            if widget is not None:
                Cache().disconnect_all(widget)
        self._should_scale = should_scale
        self.hide()

    def _confirm(self) -> None:
        self._finish(True)

    def reject(self) -> None:
        """Cancels the scaling, including when the dialog is dismissed with Escape."""
        self._finish(False)

    def closeEvent(self, event: QCloseEvent) -> None:  # pylint: disable=invalid-name
        """Treats closing the window as cancelling."""
        self._finish(False)
        event.accept()

    def show_image_modal(self) -> Optional[QSize]:
        """Show the modal, returning the selected size when the modal closes."""
        self.exec()
        if self._should_scale:
            return self._new_size()
        return None
