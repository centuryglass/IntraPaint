"""The ControlNet panel, for the Stable Diffusion WebUI and ComfyUI ControlNet units.

It is a `DockPanel` with one set of controls that edits the unit chosen in its tab bar. Each unit is saved to its own
`Cache` key as a `SavedControlNetUnit`, and the request adapters read it from there, so the panel only shapes how the
saved values are edited.

- Choosing a tab saves any pending edit, then loads that unit into the controls. The control type and the preview image
  are kept per unit for the session, and aren't saved.
- Each tab shows the unit's number, its control type and a dot that fills while the unit is on. A strip has no room
  for a row of tabs, so it shows the same titles in a vertical unit list (`UnitList`) instead.
- A unit that is off and has settings other than the defaults shows a summary of them in place of its sections.
  "Edit settings" opens the sections with live controls, and editing them doesn't turn the unit on.
- The control image is the generation area or an image file. The two map to `CONTROLNET_REUSE_IMAGE_CODE` and the
  file's path in `SavedControlNetUnit.image_string`.
- The sections run Control image, Preprocessor, then Strength. A strip pins the header, unit list and Enabled in a
  column at the left.
- The preprocessor preview sits under the preprocessor's type, preprocessor and model in a side panel. A strip moves it
  into a section of its own after Preprocessor, so it gets a column beside the preprocessor controls.
"""
# pylint: disable=too-many-lines
# One panel class: every control edits the selected unit through its load, save and summary methods.
import logging
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Optional

from PySide6.QtCore import QEvent, QFileInfo, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout, QLineEdit, QPushButton, QSizePolicy,
                               QTabBar, QVBoxLayout, QWidget)

from sd_backend_client import CONTROLNET_MODEL_NONE, PREPROCESSOR_NONE, PREPROCESSOR_RES_PARAM_KEY, ControlNetModel, \
    ControlNetPreprocessor, ControlNetUnit, ControlTypeDef, ParameterDef, PreprocessorParams

from src.config.cache import Cache
from src.controller.image_generation.sd_adapters.controlnet_adapter import CONTROLNET_REUSE_IMAGE_CODE, \
    SavedControlNetUnit, select_preprocessor
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.number_field import NumberField
from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from src.ui.input_fields.slider_field import SliderField
from src.ui.layout.dock_panel import QWIDGETSIZE_MAX, DockPanel, PanelLayout
from src.ui.layout.panel_fit import FIELD_MAX_WIDTH, REQUIRED, STRIP_SECTION_MIN_WIDTH, FitItem, Orientation
from src.ui.modal.modal_utils import open_image_file
from src.ui.panel.controlnet_widgets import DOT_SIZE, PREVIEW_IMAGE_SIZE, PreviewImage, UnitList
from src.ui.panel.generators.stable_diffusion_panel import FieldPair, LabeledRows
from src.ui.widget.elided_label import ElidedLabel
from src.ui.widget.parameter_def_widget import create_parameter_field, create_parameter_widget, \
    is_numeric_field_parameter
from src.util.parameter_def_labels import parameter_label, parameter_tooltip
from src.util.signals_blocked import signals_blocked

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.controlnet_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


PANEL_TITLE = _tr('ControlNet')
BACKEND_DESCRIPTION_WEBUI = _tr('WebUI')
BACKEND_DESCRIPTION_COMFYUI = _tr('ComfyUI')
TOOLTIP_RESET_UNIT = _tr('Reset this unit to its default settings')

TAB_TITLE = _tr('{unit_number} {control_type}', 'ControlNet unit tab title')
TAB_TOOLTIP_ON = _tr('Unit {unit_number}: on')
TAB_TOOLTIP_OFF = _tr('Unit {unit_number}: off')
ENABLED_CHECKBOX_LABEL = _tr('Enabled')
ENABLED_CHECKBOX_TOOLTIP = _tr('Apply this ControlNet unit when generating images')
BUTTON_TEXT_EDIT_SETTINGS = _tr('Edit settings')
BUTTON_TEXT_HIDE_SETTINGS = _tr('Hide settings')
BUTTON_TOOLTIP_EDIT_SETTINGS = _tr('Change the unit\'s settings without turning it on')

SECTION_TITLE_UNIT = _tr('Unit')
SECTION_TITLE_CONTROL_IMAGE = _tr('Control image')
SECTION_TITLE_PREPROCESSOR = _tr('Preprocessor')
SECTION_TITLE_STRENGTH = _tr('Strength')
SECTION_TITLE_PREVIEW = _tr('Preview', 'Preprocessor preview section title')

SOURCE_GENERATION_AREA = _tr('Generation area')
SOURCE_IMAGE_FILE = _tr('Image file')
SOURCE_GENERATION_AREA_TOOLTIP = _tr('Use the generation area\'s content as the control image')
SOURCE_IMAGE_FILE_TOOLTIP = _tr('Use an image file as the control image')
IMAGE_PATH_PLACEHOLDER = _tr('Image file path')
BUTTON_TEXT_BROWSE = _tr('...', 'Button that opens a file picker')
BUTTON_TOOLTIP_BROWSE = _tr('Choose a control image file')

LABEL_CONTROL_TYPE = _tr('Type')
LABEL_PREPROCESSOR = _tr('Preprocessor')
LABEL_MODEL = _tr('Model')
BUTTON_TEXT_PREVIEW = _tr('Preview')
BUTTON_TOOLTIP_PREVIEW = _tr('Show what the preprocessor makes of the control image')
LOW_VRAM_LABEL = _tr('Low VRAM')
PX_PERFECT_CHECKBOX_LABEL = _tr('Pixel perfect')
LABEL_WEIGHT = _tr('Weight')
LABEL_START = _tr('Start')
LABEL_END = _tr('End')

SUMMARY_GENERATION_AREA = _tr('generation area', 'Control image section summary')
SUMMARY_NO_IMAGE = _tr('no image', 'Control image section summary')
SUMMARY_PREPROCESSOR = _tr('{preprocessor}, {model}', 'Preprocessor section summary')
SUMMARY_STRENGTH = _tr('weight {weight}, steps {start}-{end}', 'Strength section summary')
SUMMARY_OFF_TYPE = _tr('{control_type} · {preprocessor}', 'First line of a disabled unit\'s summary')
SUMMARY_OFF_STRENGTH = _tr('Weight {weight}, steps {start}-{end}', 'A disabled unit\'s summary')
SUMMARY_OFF_IMAGE_FILE = _tr('Image file: {file_name}', 'A disabled unit\'s summary')
SUMMARY_OFF_GENERATION_AREA = _tr('Control image: generation area', 'A disabled unit\'s summary')

# The image upscaling window builds its tile ControlNet unit inputs from these:
CONTROL_WEIGHT_TITLE = _tr('Control weight:')
CONTROL_START_STEP_TITLE = _tr('Starting control step:')
CONTROL_END_STEP_TITLE = _tr('Ending control step:')
CONTROL_WEIGHT_TOOLTIP = _tr('A multiplier that controls how strongly the ControlNet unit will affect image'
                             ' generation.')
CONTROL_START_STEP_TOOLTIP = _tr('The step in the image generation process where the ControlNet unit will be enabled,'
                                 ' as a fraction of the total step count.')
CONTROL_END_STEP_TOOLTIP = _tr('The step in the image generation process where the ControlNet unit will be disabled,'
                               ' as a fraction of the total step count.')

# Definitions for the inputs that set the unit's strength and step range:
CONTROL_WEIGHT_PARAM = ParameterDef(key='control_strength', default_value=1.0, description=CONTROL_WEIGHT_TOOLTIP,
                                    min_val=0.0, max_val=2.0, step_val=0.01)
CONTROL_START_PARAM = ParameterDef(key='control_start', default_value=0.0, description=CONTROL_START_STEP_TOOLTIP,
                                   min_val=0.0, max_val=1.0, step_val=0.01)
CONTROL_END_PARAM = ParameterDef(key='control_end', default_value=1.0, description=CONTROL_END_STEP_TOOLTIP,
                                 min_val=0.0, max_val=1.0, step_val=0.01)

# Unit fields set by the inputs above:
CONTROL_STRENGTH_FIELD = 'control_strength'
CONTROL_START_FIELD = 'control_start'
CONTROL_END_FIELD = 'control_end'

DEFAULT_CONTROL_TYPE = 'All'

CACHE_SAVE_TIMER_INTERVAL = 100
STRENGTH_DECIMALS = 2

# If a preprocessor name ends with "Preprocessor", we can just remove that part of the name for conciseness.
PREPROCESSOR_SUFFIX = 'Preprocessor'

# The control image choices, as `SegmentedControl` values:
SOURCE_GENERATION_AREA_VALUE = 'generation_area'
SOURCE_IMAGE_FILE_VALUE = 'image_file'

# Planning collapses sections to their summaries, and hides the preview, from the highest priority number down. The
# preview is a panel fit item (`DockPanel.add_fit_item`), since it moves between sections with the orientation:
STRENGTH_PRIORITY = 1
CONTROL_IMAGE_PRIORITY = 2
PREPROCESSOR_PRIORITY = 3
PREVIEW_PRIORITY = 4

# The widest the pinned unit column of a strip grows:
UNIT_COLUMN_MAX_WIDTH = 240
COMBO_MIN_CHARACTERS = 8


def set_unit_value(unit: ControlNetUnit, field_name: str, value: float) -> Optional[str]:
    """Sets the unit's strength, starting step or ending step.

    The library rejects a starting step above the ending step. When a new value would cause that, this moves the other
    bound to the new value and returns its field name so the caller can update its input. Otherwise it returns None.
    """
    moved_field: Optional[str] = None
    if field_name == CONTROL_START_FIELD and value > unit.control_end:
        unit.control_end = value
        moved_field = CONTROL_END_FIELD
    elif field_name == CONTROL_END_FIELD and value < unit.control_start:
        unit.control_start = value
        moved_field = CONTROL_START_FIELD
    setattr(unit, field_name, value)
    return moved_field


def default_saved_unit() -> SavedControlNetUnit:
    """Returns the settings of a unit that was never saved: off, using the generation area, with library defaults."""
    return SavedControlNetUnit(False, CONTROLNET_REUSE_IMAGE_CODE, ControlNetUnit())


def preprocessor_display_name(full_name: str) -> str:
    """Remove any unnecessary 'Preprocessor' or '_preprocessor' suffix."""
    if not full_name.lower().endswith(PREPROCESSOR_SUFFIX.lower()):
        return full_name
    display_name = full_name[:-len(PREPROCESSOR_SUFFIX)]
    while display_name.endswith('-') or display_name.endswith('_'):
        display_name = display_name[:-1]
    return display_name


def unit_control_type(unit: ControlNetUnit, control_types: dict[str, ControlTypeDef]) -> str:
    """Returns a short name for what a unit controls: the first control type other than "All" that lists its
    preprocessor, or else its model, or else the preprocessor's display name. A unit with neither returns ''."""
    preprocessor = unit.preprocessor.typedef.name if unit.preprocessor is not None else None
    model = unit.model.full_model_name if unit.model is not None else None
    for listed_key, listed in (('module_list', preprocessor), ('model_list', model)):
        if listed is None:
            continue
        for type_name, control_type in control_types.items():
            listed_names = control_type[listed_key]  # type: ignore[literal-required]
            if type_name != DEFAULT_CONTROL_TYPE and listed in listed_names:
                return type_name
    return preprocessor_display_name(preprocessor) if preprocessor is not None else ''


def _load_saved_unit(cache_key: str) -> SavedControlNetUnit:
    try:
        return SavedControlNetUnit.from_json(Cache().get(cache_key))
    except ValueError:
        return default_saved_unit()


@dataclass
class _UnitState:
    """One unit's saved settings and its session-only state."""
    cache_key: str
    saved: SavedControlNetUnit
    control_type: str = DEFAULT_CONTROL_TYPE
    preview: QImage = field(default_factory=QImage)


def _shrinking_combo_box() -> QComboBox:
    """Returns a combo box that can shrink below its longest option, so a long model or preprocessor name can't widen
    the panel."""
    combo_box = QComboBox()
    combo_box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo_box.setMinimumContentsLength(COMBO_MIN_CHARACTERS)
    combo_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    combo_box.setMaximumWidth(FIELD_MAX_WIDTH)
    return combo_box


def _row(*widgets: QWidget, stretch_first: bool = True) -> QWidget:
    """Returns a widget holding `widgets` in a row with no margins, the first one stretching."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    for index, widget in enumerate(widgets):
        layout.addWidget(widget, stretch=1 if index == 0 and stretch_first else 0)
    return row


def _column(*widgets: QWidget) -> tuple[QWidget, QVBoxLayout]:
    """Returns a widget holding `widgets` in a column with no margins, and its layout."""
    column = QWidget()
    layout = QVBoxLayout(column)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget)
    return column, layout


# `build` runs in the `DockPanel` constructor, so the controls it creates are attributes defined outside `__init__`:
# pylint: disable=attribute-defined-outside-init
class ControlNetPanel(DockPanel):
    """Edits the ControlNet units of a Stable Diffusion backend, one at a time."""

    request_preview = Signal(PreprocessorParams, str)

    def __init__(self,
                 preprocessors: list[ControlNetPreprocessor],
                 model_list: list[str],
                 control_types: dict[str, ControlTypeDef],
                 control_unit_cache_keys: list[str],
                 show_webui_options: bool) -> None:
        """Initializes the panel based on data from a Stable Diffusion API.

        Parameters
        ----------
        preprocessors: list[ControlNetPreprocessor]
            List of all available ControlNet preprocessor modules, pre-parameterized to enable easy UI setup.
        model_list: list[str]
            List of all available ControlNet models.
        control_types: dict[str, ControlTypeDef]
            Data defining how preprocessors and models can be sorted into categories.
        control_unit_cache_keys: list[str]
            Cache keys for each ControlNet unit that the panel can use, one tab each.
        show_webui_options: bool
            Whether the "Low VRAM" and "Pixel perfect" checkboxes (only relevant in the WebUI API) should be shown.
        """
        # `build` runs in the superclass constructor and needs these:
        self._preprocessors = preprocessors
        self._model_list = model_list
        self._control_types = control_types
        self._show_webui_options = show_webui_options
        self._units = [_UnitState(key, _load_saved_unit(key)) for key in control_unit_cache_keys]
        self._index = 0
        self._saved = self._units[0].saved
        self._control_unit = self._saved.unit
        # Whether an off unit's sections are open for editing:
        self._editing_off_unit = False
        # Whether planning left room for the preprocessor preview:
        self._preview_placed = True
        self._dynamic_controls: list[QWidget] = []
        self._resolution_field: Optional[QWidget] = None
        super().__init__(PANEL_TITLE)
        self.header.set_description(BACKEND_DESCRIPTION_WEBUI if show_webui_options else BACKEND_DESCRIPTION_COMFYUI)
        self.header.reset_button.setToolTip(TOOLTIP_RESET_UNIT)
        self.header.reset_button.setAccessibleName(TOOLTIP_RESET_UNIT)
        self.header.reset_requested.connect(self.reset_unit)

        self.pinned_layout.addStretch()

        self._cache_timer = QTimer()
        self._cache_timer.setSingleShot(True)
        self._cache_timer.setInterval(CACHE_SAVE_TIMER_INTERVAL)
        self._cache_timer.timeout.connect(self._save_data_to_cache)

        self._connect_controls()
        self._load_unit(0)
        for index in range(len(self._units)):
            self._update_tab(index)

    # ---------------------------------------------------------------------------------------------------------------
    # Content
    # ---------------------------------------------------------------------------------------------------------------

    def build(self, ui: PanelLayout) -> None:
        """Declares the sections."""
        self.set_column_packing(True)
        self._build_unit_section(ui)
        self._build_control_image_section(ui)
        self._build_preprocessor_section(ui)
        self._build_preview_section(ui)
        self._build_strength_section(ui)
        self.add_fit_item(FitItem(PREVIEW_PRIORITY), self._place_preview)

    def _build_unit_section(self, ui: PanelLayout) -> None:
        section = ui.section(SECTION_TITLE_UNIT)
        self._unit_section = section
        section.widget.set_header_visible(False)
        self._tab_bar = QTabBar()
        self._tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        self._tab_bar.setUsesScrollButtons(False)
        self._tab_bar.setExpanding(False)
        self._tab_bar.setDrawBase(False)
        self._tab_bar.setIconSize(QSize(DOT_SIZE, DOT_SIZE))
        for _ in self._units:
            self._tab_bar.addTab('')
        self._unit_list = UnitList(len(self._units))
        self._unit_list.hide()
        self._enabled_checkbox = CheckBox()
        self._enabled_checkbox.setText(ENABLED_CHECKBOX_LABEL)
        self._enabled_checkbox.setToolTip(ENABLED_CHECKBOX_TOOLTIP)

        # An off unit's settings, shown in place of the sections:
        self._off_summary = QFrame()
        self._off_summary.setFrameShape(QFrame.Shape.StyledPanel)
        summary_layout = QVBoxLayout(self._off_summary)
        self._off_summary_lines = [ElidedLabel() for _ in range(4)]
        for index, line in enumerate(self._off_summary_lines):
            if index > 0:
                line.setForegroundRole(QPalette.ColorRole.PlaceholderText)
            summary_layout.addWidget(line)
        self._edit_settings_button = QPushButton(BUTTON_TEXT_EDIT_SETTINGS)
        self._edit_settings_button.setToolTip(BUTTON_TOOLTIP_EDIT_SETTINGS)
        self._edit_settings_row = _row(self._edit_settings_button, stretch_first=False)
        self._edit_settings_row.layout().addStretch()

        self._unit_block, _ = _column(self._tab_bar, self._unit_list, self._enabled_checkbox, self._off_summary,
                                      self._edit_settings_row)
        section.add(self._unit_block, REQUIRED)

    def _build_control_image_section(self, ui: PanelLayout) -> None:
        section = ui.section(SECTION_TITLE_CONTROL_IMAGE, collapsible=True, priority=CONTROL_IMAGE_PRIORITY)
        self._control_image_section = section
        self._image_source = SegmentedControl([
            Segment(SOURCE_GENERATION_AREA_VALUE, SOURCE_GENERATION_AREA, tooltip=SOURCE_GENERATION_AREA_TOOLTIP),
            Segment(SOURCE_IMAGE_FILE_VALUE, SOURCE_IMAGE_FILE, tooltip=SOURCE_IMAGE_FILE_TOOLTIP)
        ], DisplayMode.LABEL, combo_fallback=True)
        self._image_source.setMaximumWidth(FIELD_MAX_WIDTH)
        self._image_path_edit = QLineEdit()
        self._image_path_edit.setPlaceholderText(IMAGE_PATH_PLACEHOLDER)
        self._image_path_edit.setMinimumWidth(self._image_path_edit.fontMetrics().averageCharWidth()
                                              * COMBO_MIN_CHARACTERS)
        self._browse_button = QPushButton(BUTTON_TEXT_BROWSE)
        self._browse_button.setToolTip(BUTTON_TOOLTIP_BROWSE)
        self._browse_button.setAccessibleName(BUTTON_TOOLTIP_BROWSE)
        self._browse_button.setFixedWidth(self._browse_button.minimumSizeHint().height())
        self._image_path_row = _row(self._image_path_edit, self._browse_button)
        self._image_block, _ = _column(self._image_source, self._image_path_row)
        section.add(self._image_block, REQUIRED)
        section.widget.bind_summary(self._control_image_summary, self._image_source.valueChanged,
                                    self._image_path_edit.textChanged)

    def _build_preprocessor_section(self, ui: PanelLayout) -> None:
        section = ui.section(SECTION_TITLE_PREPROCESSOR, collapsible=True, priority=PREPROCESSOR_PRIORITY)
        self._preprocessor_section = section
        self._control_type_combobox = _shrinking_combo_box()
        for control in self._control_types:
            self._control_type_combobox.addItem(control)
        self._preprocessor_combobox = _shrinking_combo_box()
        self._model_combobox = _shrinking_combo_box()
        self._preview_button = QPushButton(BUTTON_TEXT_PREVIEW)
        self._preview_button.setToolTip(BUTTON_TOOLTIP_PREVIEW)
        preprocessor_row = _row(self._preprocessor_combobox, self._preview_button)
        preprocessor_row.setMaximumWidth(FIELD_MAX_WIDTH)
        self._mode_rows = LabeledRows([(LABEL_CONTROL_TYPE, self._control_type_combobox),
                                       (LABEL_PREPROCESSOR, preprocessor_row),
                                       (LABEL_MODEL, self._model_combobox)])
        section.add(self._mode_rows, REQUIRED)

        # `arrange` moves the preview between this slot and the strip's preview section:
        self._preview_image_widget = PreviewImage(QImage())
        self._preview_image_widget.setMaximumSize(QSize(PREVIEW_IMAGE_SIZE, PREVIEW_IMAGE_SIZE))
        self._side_preview_slot, self._side_preview_layout = _column(self._preview_image_widget)
        section.add(self._side_preview_slot, REQUIRED)

        # Rebuilt for each preprocessor, by `_handle_preprocessor_change`:
        self._parameter_block, self._parameter_layout = _column()
        section.add(self._parameter_block, REQUIRED)

        self._vram_checkbox: Optional[CheckBox] = None
        self._px_perfect_checkbox: Optional[CheckBox] = None
        if self._show_webui_options:
            self._px_perfect_checkbox = CheckBox()
            self._px_perfect_checkbox.setText(PX_PERFECT_CHECKBOX_LABEL)
            self._vram_checkbox = CheckBox()
            self._vram_checkbox.setText(LOW_VRAM_LABEL)
            webui_pair = FieldPair(self._px_perfect_checkbox, self._vram_checkbox)
            for checkbox in (self._px_perfect_checkbox, self._vram_checkbox):
                webui_pair.layout().setAlignment(checkbox, Qt.AlignmentFlag.AlignLeft)
            webui_pair.setMaximumWidth(FIELD_MAX_WIDTH)
            section.add(webui_pair, REQUIRED, webui_pair.forms(self._strip_column_width))
        section.widget.bind_summary(self._preprocessor_summary, self._preprocessor_combobox.currentIndexChanged,
                                    self._model_combobox.currentIndexChanged)

    def _build_preview_section(self, ui: PanelLayout) -> None:
        """Declares the strip's preview column. `finish_placement` hides it outside a strip."""
        section = ui.section(SECTION_TITLE_PREVIEW)
        self._preview_section = section
        section.widget.set_header_visible(False)
        self._strip_preview_slot, self._strip_preview_layout = _column()
        section.add(self._strip_preview_slot, REQUIRED)

    def _build_strength_section(self, ui: PanelLayout) -> None:
        section = ui.section(SECTION_TITLE_STRENGTH, collapsible=True, priority=STRENGTH_PRIORITY)
        self._strength_section = section
        self._control_strength_slider = self._strength_field(LABEL_WEIGHT, CONTROL_WEIGHT_PARAM)
        self._control_start_slider = self._strength_field(LABEL_START, CONTROL_START_PARAM)
        self._control_end_slider = self._strength_field(LABEL_END, CONTROL_END_PARAM)
        section.add(self._control_strength_slider, REQUIRED)
        step_pair = FieldPair(self._control_start_slider, self._control_end_slider)
        # The pair lines up with the weight field above it:
        step_pair.setMaximumWidth(FIELD_MAX_WIDTH)
        section.add(step_pair, REQUIRED, step_pair.forms(self._strip_column_width))
        section.widget.bind_summary(self._strength_summary, self._control_strength_slider.valueChanged,
                                    self._control_start_slider.valueChanged, self._control_end_slider.valueChanged)

    @staticmethod
    def _strength_field(label: str, param: ParameterDef) -> SliderField:
        assert isinstance(param.default_value, float) and param.min_val is not None and param.max_val is not None
        slider = SliderField(label, param.default_value, float(param.min_val), float(param.max_val),
                             step=float(param.step_val if param.step_val is not None else 0.01),
                             decimals=STRENGTH_DECIMALS)
        slider.setToolTip(param.description)
        slider.setMaximumWidth(FIELD_MAX_WIDTH)
        return slider

    def _connect_controls(self) -> None:
        self._tab_bar.currentChanged.connect(self._select_unit)
        self._unit_list.currentRowChanged.connect(self._select_unit)
        self._enabled_checkbox.valueChanged.connect(self._set_enabled)
        self._edit_settings_button.clicked.connect(self._toggle_off_unit_editing)
        self._image_source.valueChanged.connect(self._image_source_changed)
        self._image_path_edit.textChanged.connect(self._image_path_changed)
        self._browse_button.clicked.connect(self._open_control_image_file)
        self._preview_button.clicked.connect(self._request_preview)
        self._control_type_combobox.currentTextChanged.connect(self._control_type_changed)
        self._preprocessor_combobox.currentIndexChanged.connect(self._handle_preprocessor_change)
        self._model_combobox.currentIndexChanged.connect(self._handle_model_change)
        for slider, field_name in ((self._control_strength_slider, CONTROL_STRENGTH_FIELD),
                                   (self._control_start_slider, CONTROL_START_FIELD),
                                   (self._control_end_slider, CONTROL_END_FIELD)):
            slider.valueChanged.connect(lambda value, name=field_name: self._update_control_value(name, value))
        if self._vram_checkbox is not None:
            self._vram_checkbox.valueChanged.connect(self._update_low_vram)
        if self._px_perfect_checkbox is not None:
            self._px_perfect_checkbox.valueChanged.connect(self._update_px_perfect)

    # ---------------------------------------------------------------------------------------------------------------
    # Units
    # ---------------------------------------------------------------------------------------------------------------

    @property
    def unit_index(self) -> int:
        """The index of the unit the controls edit."""
        return self._index

    def _select_unit(self, index: int) -> None:
        if index == self._index or not 0 <= index < len(self._units):
            return
        if self._cache_timer.isActive():
            self._save_data_to_cache()
        self._load_unit(index)

    def _load_unit(self, index: int) -> None:
        """Shows a unit's settings in the controls. Settings the current backend doesn't offer, such as a missing
        preprocessor, are replaced as the control type's options require, and the change is saved."""
        self._index = index
        state = self._units[index]
        self._saved = state.saved
        self._control_unit = state.saved.unit
        self._editing_off_unit = False
        preview = state.preview
        with signals_blocked(self._tab_bar):
            self._tab_bar.setCurrentIndex(index)
        with signals_blocked(self._unit_list):
            self._unit_list.setCurrentRow(index)
        with signals_blocked(self._enabled_checkbox):
            self._enabled_checkbox.setChecked(self._saved.enabled)
        if self._vram_checkbox is not None:
            with signals_blocked(self._vram_checkbox):
                self._vram_checkbox.setChecked(self._control_unit.low_vram)
        if self._px_perfect_checkbox is not None:
            with signals_blocked(self._px_perfect_checkbox):
                self._px_perfect_checkbox.setChecked(self._control_unit.pixel_perfect)

        use_generation_area = self._saved.image_string == CONTROLNET_REUSE_IMAGE_CODE
        with signals_blocked(self._image_source), signals_blocked(self._image_path_edit):
            self._image_source.set_value(SOURCE_GENERATION_AREA_VALUE if use_generation_area
                                         else SOURCE_IMAGE_FILE_VALUE)
            self._image_path_edit.setText('' if use_generation_area else self._saved.image_string)
        self._image_path_row.setVisible(not use_generation_area)

        for slider, value in ((self._control_strength_slider, self._control_unit.control_strength),
                              (self._control_start_slider, self._control_unit.control_start),
                              (self._control_end_slider, self._control_unit.control_end)):
            with signals_blocked(slider):
                slider.set_value(value)

        with signals_blocked(self._control_type_combobox):
            self._control_type_combobox.setCurrentIndex(self._control_type_combobox.findText(state.control_type))
        self._load_control_type(state.control_type)
        module_idx = self._preprocessor_combobox.findText(preprocessor_display_name(self._preprocessor_name()))
        if module_idx >= 0:
            with signals_blocked(self._preprocessor_combobox):
                self._preprocessor_combobox.setCurrentIndex(module_idx)
        model_idx = self._model_combobox.findText(self._selected_model().display_name)
        if model_idx >= 0:
            with signals_blocked(self._model_combobox):
                self._model_combobox.setCurrentIndex(model_idx)
        self._handle_preprocessor_change(self._preprocessor_combobox.currentIndex())
        state.preview = preview
        self._preview_image_widget.image = preview
        for section in (self._control_image_section, self._preprocessor_section, self._strength_section):
            section.widget.set_summary(self._section_summary(section))
        self._update_enabled_controls()
        self.refit()

    def _section_summary(self, section) -> str:
        if section is self._control_image_section:
            return self._control_image_summary()
        if section is self._preprocessor_section:
            return self._preprocessor_summary()
        return self._strength_summary()

    def reset_unit(self) -> None:
        """Returns the selected unit to the settings of a unit that was never saved, keeping whether it is on."""
        state = self._units[self._index]
        enabled = state.saved.enabled
        state.saved = default_saved_unit()
        state.saved.enabled = enabled
        state.control_type = DEFAULT_CONTROL_TYPE
        state.preview = QImage()
        self._load_unit(self._index)
        self._schedule_cache_update()

    def _set_enabled(self, checked: bool) -> None:
        self._saved.enabled = checked
        self._editing_off_unit = False
        self._update_enabled_controls()
        self._schedule_cache_update()
        self.refit()

    def _toggle_off_unit_editing(self) -> None:
        self._editing_off_unit = not self._editing_off_unit
        self._update_enabled_controls()
        self.refit()

    def _new_unit(self) -> ControlNetUnit:
        """Returns the settings a unit that was never saved has once loaded: the "All" control type's default
        preprocessor and model, and the library's other defaults."""
        all_types = self._control_types[DEFAULT_CONTROL_TYPE]
        preprocessor_name = all_types['default_option'] if all_types['default_option'] in all_types['module_list'] \
            else PREPROCESSOR_NONE
        typedef = next((preprocessor for preprocessor in self._preprocessors if preprocessor.name == preprocessor_name
                        and preprocessor_name.lower() != PREPROCESSOR_NONE.lower()), None)
        model_name = all_types['default_model'] if all_types['default_model'] in all_types['model_list'] \
            else CONTROLNET_MODEL_NONE
        return ControlNetUnit(preprocessor=None if typedef is None else select_preprocessor(typedef, None),
                              model=None if model_name == CONTROLNET_MODEL_NONE else ControlNetModel(model_name))

    def _is_default(self, state: _UnitState) -> bool:
        """Returns whether a unit still has the settings of one that was never saved, before or after loading."""
        if state.saved.image_string != CONTROLNET_REUSE_IMAGE_CODE:
            return False
        unit_json = state.saved.unit.model_dump_json(exclude={'image'})
        return unit_json in (ControlNetUnit().model_dump_json(exclude={'image'}),
                             self._new_unit().model_dump_json(exclude={'image'}))

    def _shows_sections(self) -> bool:
        """Returns whether the selected unit's sections show, or its summary in their place."""
        return self._saved.enabled or self._editing_off_unit or self._is_default(self._units[self._index])

    def _update_enabled_controls(self) -> None:
        """Shows the selected unit's summary or sections, and updates its tab and the preview button."""
        sections_shown = self._shows_sections()
        self._off_summary.setVisible(not sections_shown)
        self._edit_settings_row.setVisible(not self._saved.enabled and not self._is_default(self._units[self._index]))
        self._edit_settings_button.setText(BUTTON_TEXT_HIDE_SETTINGS if self._editing_off_unit
                                           else BUTTON_TEXT_EDIT_SETTINGS)
        if not sections_shown:
            self._update_off_summary()
        self._preview_button.setEnabled(self._saved.enabled and self._control_unit.preprocessor is not None)
        self._update_tab(self._index)

    def _update_off_summary(self) -> None:
        unit = self._control_unit
        control_type = unit_control_type(unit, self._control_types)
        preprocessor = preprocessor_display_name(self._preprocessor_name())
        first_line = preprocessor if control_type in ('', preprocessor) \
            else SUMMARY_OFF_TYPE.format(control_type=control_type, preprocessor=preprocessor)
        lines = [first_line,
                 self._selected_model().display_name,
                 SUMMARY_OFF_STRENGTH.format(weight=self._number_text(unit.control_strength),
                                             start=self._number_text(unit.control_start),
                                             end=self._number_text(unit.control_end))]
        if self._saved.image_string == CONTROLNET_REUSE_IMAGE_CODE:
            lines.append(SUMMARY_OFF_GENERATION_AREA)
        else:
            lines.append(SUMMARY_OFF_IMAGE_FILE.format(file_name=QFileInfo(self._saved.image_string).fileName()))
        for label, text in zip(self._off_summary_lines, lines):
            label.set_full_text(text)

    def _update_tab(self, index: int) -> None:
        """Sets a unit's title, tooltip and on/off dot, on its tab and its unit list row."""
        state = self._units[index]
        control_type = unit_control_type(state.saved.unit, self._control_types)
        number = str(index + 1)
        named = control_type != '' and (state.saved.enabled or not self._is_default(state))
        title = TAB_TITLE.format(unit_number=number, control_type=control_type) if named else number
        tooltip = (TAB_TOOLTIP_ON if state.saved.enabled else TAB_TOOLTIP_OFF).format(unit_number=number)
        icon = self._dot_icon(state.saved.enabled)
        self._tab_bar.setTabText(index, title)
        self._tab_bar.setTabToolTip(index, tooltip)
        self._tab_bar.setTabIcon(index, icon)
        self._unit_list.set_row(index, title, tooltip, icon)

    def _dot_icon(self, on: bool) -> QIcon:
        """Returns a tab's dot: filled with the highlight color while the unit is on, and an outline while it's off."""
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(round(DOT_SIZE * ratio), round(DOT_SIZE * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        if on:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(palette.color(QPalette.ColorRole.Highlight))
        else:
            outline = QColor(palette.color(QPalette.ColorRole.PlaceholderText))
            painter.setPen(outline)
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(1, 1, DOT_SIZE - 2, DOT_SIZE - 2)
        painter.end()
        return QIcon(pixmap)

    def changeEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """Redraws the tab dots in the new colors when the palette or style changes."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange) and hasattr(self, '_tab_bar'):
            for index in range(len(self._units)):
                self._update_tab(index)

    # ---------------------------------------------------------------------------------------------------------------
    # Previews
    # ---------------------------------------------------------------------------------------------------------------

    def set_preview(self, preview_image: QImage, index: int = -1) -> None:
        """Shows a preprocessor preview image for a unit, by default the selected one."""
        if index < 0:
            index = self._index
        self._units[index].preview = preview_image
        if index == self._index:
            self.set_preprocessor_preview(preview_image)

    def set_preprocessor_preview(self, preview_image: Optional[QImage]) -> None:
        """Shows the selected unit's preprocessor preview image, or hides it if preview_image is None."""
        if preview_image is None:
            preview_image = QImage()
        self._units[self._index].preview = preview_image
        if self._preview_image_widget.image == preview_image:
            return
        self._preview_image_widget.image = preview_image
        self._preview_image_widget.updateGeometry()
        self.refit()

    def _request_preview(self) -> None:
        if self._control_unit.preprocessor is not None:
            self.request_preview.emit(self._control_unit.preprocessor, self._saved.image_string)

    # ---------------------------------------------------------------------------------------------------------------
    # Saving and summaries
    # ---------------------------------------------------------------------------------------------------------------

    def _schedule_cache_update(self) -> None:
        self._update_tab(self._index)
        if not self._cache_timer.isActive():
            self._cache_timer.start()

    def _save_data_to_cache(self) -> None:
        if self._cache_timer.isActive():
            self._cache_timer.stop()
        state = self._units[self._index]
        Cache().set(state.cache_key, state.saved.to_json())

    @staticmethod
    def _number_text(value: float) -> str:
        return f'{value:.{STRENGTH_DECIMALS}f}'

    def _control_image_summary(self) -> str:
        if self._image_source.value() == SOURCE_GENERATION_AREA_VALUE:
            return SUMMARY_GENERATION_AREA
        path = self._image_path_edit.text()
        return QFileInfo(path).fileName() if path != '' else SUMMARY_NO_IMAGE

    def _preprocessor_summary(self) -> str:
        return SUMMARY_PREPROCESSOR.format(preprocessor=preprocessor_display_name(self._preprocessor_name()),
                                           model=self._selected_model().display_name)

    def _strength_summary(self) -> str:
        unit = self._control_unit
        return SUMMARY_STRENGTH.format(weight=self._number_text(unit.control_strength),
                                       start=self._number_text(unit.control_start),
                                       end=self._number_text(unit.control_end))

    # ---------------------------------------------------------------------------------------------------------------
    # Control image
    # ---------------------------------------------------------------------------------------------------------------

    def _image_source_changed(self, value: str) -> None:
        use_generation_area = value == SOURCE_GENERATION_AREA_VALUE
        self._saved.image_string = CONTROLNET_REUSE_IMAGE_CODE if use_generation_area \
            else self._image_path_edit.text()
        self._image_path_row.setVisible(not use_generation_area)
        self._schedule_cache_update()
        self.refit()

    def _image_path_changed(self, text: str) -> None:
        if self._image_source.value() == SOURCE_IMAGE_FILE_VALUE:
            self._saved.image_string = text
            self._schedule_cache_update()

    def _open_control_image_file(self) -> None:
        """Chooses an image file as the control image."""
        image_path = open_image_file(self)
        if isinstance(image_path, list):
            image_path = image_path[0] if len(image_path) > 0 else None
        if isinstance(image_path, str):
            self._image_path_edit.setText(image_path)

    # ---------------------------------------------------------------------------------------------------------------
    # Preprocessor, model and strength
    # ---------------------------------------------------------------------------------------------------------------

    def _preprocessor_name(self) -> str:
        """Returns the selected preprocessor's name, or `PREPROCESSOR_NONE` if there isn't one."""
        preprocessor = self._control_unit.preprocessor
        return PREPROCESSOR_NONE if preprocessor is None else preprocessor.typedef.name

    def _selected_model(self) -> ControlNetModel:
        """Returns the selected model, or the `CONTROLNET_MODEL_NONE` model if there isn't one."""
        model = self._control_unit.model
        return ControlNetModel(CONTROLNET_MODEL_NONE) if model is None else model

    def _update_control_value(self, field_name: str, value: float) -> None:
        """Sets a unit value, updating the other step input if it moved."""
        moved_field = set_unit_value(self._control_unit, field_name, value)
        if moved_field is not None:
            slider = self._control_start_slider if moved_field == CONTROL_START_FIELD else self._control_end_slider
            with signals_blocked(slider):
                slider.set_value(value)
            self._strength_section.widget.set_summary(self._strength_summary())
        self._schedule_cache_update()

    def _update_low_vram(self, checked: bool) -> None:
        self._control_unit.low_vram = checked
        self._schedule_cache_update()

    def _update_px_perfect(self, checked: bool) -> None:
        self._control_unit.pixel_perfect = checked
        if self._resolution_field is not None:
            self._resolution_field.setHidden(checked)
        self._schedule_cache_update()
        self.refit()

    def _set_preprocessor_parameter(self, key: str, value: Any) -> None:
        if self._control_unit.preprocessor is not None:
            self._control_unit.preprocessor.parameter_values[key] = value
            self._schedule_cache_update()

    def _control_type_changed(self, control_type_name: str) -> None:
        self._units[self._index].control_type = control_type_name
        self._load_control_type(control_type_name)

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
            previous_model = self._selected_model()
            selected_model = previous_model
            if selected_model not in models or selected_model.full_model_name == CONTROLNET_MODEL_NONE:
                selected_model = ControlNetModel(control_type['default_model'])
                if selected_model not in models:
                    selected_model = ControlNetModel(CONTROLNET_MODEL_NONE)
            model_index = self._model_combobox.findData(selected_model.full_model_name)
            if model_index < 0:
                raise RuntimeError(f'Failed to find model "{selected_model}" in control type {control_type_name}, '
                                   f'options={[self._model_combobox.itemText(i) for i in range(len(models))]}')
            self._model_combobox.setCurrentIndex(model_index)
            if selected_model != previous_model:
                self._handle_model_change(model_index)

        with signals_blocked(self._preprocessor_combobox):
            while self._preprocessor_combobox.count() > 0:
                self._preprocessor_combobox.removeItem(0)
            category_preprocessor_names = [*control_type['module_list']]
            all_preprocessors: list[ControlNetPreprocessor] = [*self._preprocessors]
            # Sort alphabetically, except that "None" preprocessor should be last:
            all_preprocessors.sort(key=lambda module: module.name.lower() if module.name != PREPROCESSOR_NONE else '~')
            for preprocessor in all_preprocessors:
                if preprocessor.name not in category_preprocessor_names:
                    continue
                display_name = preprocessor_display_name(preprocessor.name)
                self._preprocessor_combobox.addItem(display_name, userData=preprocessor)
            previous_name = self._preprocessor_name()
            selected_preprocessor = previous_name
            if selected_preprocessor not in category_preprocessor_names \
                    or selected_preprocessor.lower() == PREPROCESSOR_NONE.lower():
                selected_preprocessor = control_type['default_option']
                if selected_preprocessor not in category_preprocessor_names:
                    selected_preprocessor = PREPROCESSOR_NONE
            preprocessor_index = self._preprocessor_combobox.findText(
                preprocessor_display_name(selected_preprocessor))
            if preprocessor_index < 0:
                preprocessor_options = [self._preprocessor_combobox.itemData(i).name
                                        for i in range(self._preprocessor_combobox.count())]
                raise RuntimeError(f'Failed to find preprocessor "{selected_preprocessor}" in control type'
                                   f' {control_type_name}, options={preprocessor_options}')

            self._preprocessor_combobox.setCurrentIndex(preprocessor_index)
            if selected_preprocessor != previous_name:
                self._handle_preprocessor_change(preprocessor_index)
        self._preprocessor_section.widget.set_summary(self._preprocessor_summary())

    def _clear_parameter_controls(self) -> None:
        while self._parameter_layout.count() > 0:
            item = self._parameter_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._dynamic_controls = []
        self._resolution_field = None

    def _handle_preprocessor_change(self, preprocessor_index: int) -> None:
        """When the selected preprocessor module changes, update config and module option controls.

        Numeric parameters get a `SliderField`, and the others share one label column. Resolution goes last, so hiding
        it while Pixel perfect is on leaves no gap.
        """
        typedef = self._preprocessor_combobox.itemData(preprocessor_index)
        assert isinstance(typedef, ControlNetPreprocessor)
        self.set_preprocessor_preview(None)
        self._clear_parameter_controls()
        if typedef.name.lower() == PREPROCESSOR_NONE.lower():
            self._control_unit.preprocessor = None
        else:
            preprocessor = select_preprocessor(typedef, self._control_unit.preprocessor)
            self._control_unit.preprocessor = preprocessor
            parameters = [parameter for parameter in typedef.parameters if parameter.key != PREPROCESSOR_RES_PARAM_KEY]
            parameters += [parameter for parameter in typedef.parameters
                           if parameter.key == PREPROCESSOR_RES_PARAM_KEY]
            labeled: list[tuple[str, QWidget]] = []
            for parameter in parameters:
                value = preprocessor.parameter_values[parameter.key]
                on_changed = partial(self._set_preprocessor_parameter, parameter.key)
                parameter_widget: QWidget
                if is_numeric_field_parameter(parameter):
                    if len(labeled) > 0:
                        self._parameter_layout.addWidget(LabeledRows(labeled))
                        labeled = []
                    parameter_widget = create_parameter_field(parameter, value, on_changed)
                    parameter_widget.setMaximumWidth(FIELD_MAX_WIDTH)
                    self._parameter_layout.addWidget(parameter_widget)
                else:
                    parameter_widget = create_parameter_widget(parameter, value, on_changed)
                    parameter_widget.setToolTip(parameter_tooltip(parameter))
                    labeled.append((parameter_label(parameter), parameter_widget))
                self._dynamic_controls.append(parameter_widget)
                if self._px_perfect_checkbox is not None and parameter.key == PREPROCESSOR_RES_PARAM_KEY:
                    self._resolution_field = parameter_widget
                    parameter_widget.setHidden(self._control_unit.pixel_perfect)
            if len(labeled) > 0:
                self._parameter_layout.addWidget(LabeledRows(labeled))
        self._parameter_block.setVisible(len(self._dynamic_controls) > 0)
        self._schedule_cache_update()
        self._preview_button.setEnabled(self._saved.enabled and self._control_unit.preprocessor is not None)
        self._preprocessor_section.widget.set_summary(self._preprocessor_summary())
        self.refit()

    def _handle_model_change(self, model_idx: int) -> None:
        """Update config when the selected model changes."""
        selected_model = self._model_combobox.itemData(model_idx)
        assert isinstance(selected_model, str), (f'Expected full_name at {model_idx}/{self._model_combobox.count()},'
                                                 f' got {selected_model}({type(selected_model)},'
                                                 f' text = {self._model_combobox.itemText(model_idx)})')
        self._control_unit.model = None if selected_model == CONTROLNET_MODEL_NONE else ControlNetModel(selected_model)
        self._schedule_cache_update()

    # ---------------------------------------------------------------------------------------------------------------
    # Layout
    # ---------------------------------------------------------------------------------------------------------------

    def arrange(self, orientation: Orientation) -> None:
        """Pins the header and the unit section in a column at the left of a strip, with the unit list in place of the
        tabs, and moves the preview into its own section."""
        super().arrange(orientation)
        strip = orientation == Orientation.STRIP
        self._tab_bar.setVisible(not strip)
        self._unit_list.setVisible(strip)
        preview_layout = self._strip_preview_layout if strip else self._side_preview_layout
        preview_layout.addWidget(self._preview_image_widget)
        # Reparenting hides a widget. Its slot's visibility decides whether it shows:
        self._preview_image_widget.show()
        unit = self._unit_section.widget
        outer = self.layout()
        assert isinstance(outer, QVBoxLayout)
        if strip:
            # The pinned layout ends with a stretch, added in the constructor, that keeps its content at the top:
            self.pinned_layout.insertWidget(0, self.header)
            self.pinned_layout.insertWidget(1, unit)
            unit.setMinimumWidth(0)
            unit.setMaximumWidth(QWIDGETSIZE_MAX)
            unit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            self.pinned_layout.parentWidget().setMaximumWidth(UNIT_COLUMN_MAX_WIDTH)
        else:
            outer.insertWidget(0, self.header)
            self.section_layout.insertWidget(0, unit)
        self.set_pinned_visible(strip)
        for section in self.sections:
            self.section_layout.setAlignment(section.widget, Qt.AlignmentFlag.AlignTop if strip
                                             else Qt.AlignmentFlag(0))

    def header_width(self, available: QSize) -> int:
        """Returns the unit column's widest width in a strip, and the available width in a side panel."""
        if self.orientation == Orientation.STRIP:
            return min(available.width(), UNIT_COLUMN_MAX_WIDTH)
        return available.width()

    def prepare_fit(self, orientation: Orientation) -> None:
        """Limits a strip's preview to a column's narrowest width and its height, less room for the horizontal scroll
        bar."""
        super().prepare_fit(orientation)
        available = self.available_size
        limit: Optional[QSize] = None
        if orientation == Orientation.STRIP and available is not None:
            margins = self.content_margins()
            limit = QSize(STRIP_SECTION_MIN_WIDTH,
                          available.height() - margins.top() - margins.bottom() - self.scroll_bar_extent())
        self._preview_image_widget.set_size_limit(limit)

    def _strip_column_width(self) -> Optional[int]:
        return STRIP_SECTION_MIN_WIDTH if self.orientation == Orientation.STRIP else None

    def _place_preview(self, form: Optional[int]) -> None:
        self._preview_placed = form is not None

    def finish_placement(self) -> None:
        """Hides the sections while an off unit shows its summary, and the preview while there is none, planning left
        no room for it, or a strip's Preprocessor section is collapsed."""
        super().finish_placement()
        sections_shown = self._shows_sections()
        for section in (self._control_image_section, self._preprocessor_section, self._preview_section,
                        self._strength_section):
            if not sections_shown:
                section.widget.setVisible(False)
        image = self._preview_image_widget.image
        has_image = image is not None and not (isinstance(image, QImage) and image.isNull())
        preview_shown = has_image and self._preview_placed
        strip = self.orientation == Orientation.STRIP
        self._side_preview_slot.setVisible(preview_shown and not strip)
        if not preview_shown or not strip or self._preprocessor_section.widget.is_collapsed():
            self._preview_section.widget.setVisible(False)

    # ---------------------------------------------------------------------------------------------------------------
    # Accessors for tests and the generators
    # ---------------------------------------------------------------------------------------------------------------

    @property
    def tab_bar(self) -> QTabBar:
        """The unit tabs, shown in a side panel."""
        return self._tab_bar

    @property
    def unit_list(self) -> UnitList:
        """The unit list, shown in a strip in place of the tabs."""
        return self._unit_list

    @property
    def preview_image_widget(self) -> PreviewImage:
        """The preprocessor preview."""
        return self._preview_image_widget

    @property
    def strength_fields(self) -> list[NumberField]:
        """The weight, start and end fields, in display order."""
        return [self._control_strength_slider, self._control_start_slider, self._control_end_slider]
