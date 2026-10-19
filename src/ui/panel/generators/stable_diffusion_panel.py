"""The Stable Diffusion generation panel, for the WebUI and ComfyUI backends.

It is a `DockPanel` with one column of sections in loop order: Edit mode, Prompt, Inpaint, Output, Sampling, Advanced and
a ControlNet summary, with Generate pinned below them (`DockPanel.set_footer`). Strip docks lay the same sections out as
columns.

- Every control is bound to its config value and has one owner here. Backend-specific controls arrive as constructor
  arguments (`webui`) and `set_advanced_content`.
- The Inpaint section keeps its place in every edit mode: Inpaint shows all its controls, Image to image only denoising
  strength, and Text to image a one-line note. Widgets inside the section show and hide, so the planner's placement of
  the section itself never changes.
- The header's More menu holds the commands that open other windows. The panel emits signals for them and the generator
  opens the window.
- The panel stays unaware of the backend connection. The generator shows `DisabledBanner` through
  `set_disconnected`.
"""
from typing import Callable, Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (QApplication, QBoxLayout, QCheckBox, QComboBox, QLabel, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.config import Config
from src.controller.image_generation.sd_adapters.controlnet_adapter import SavedControlNetUnit
from src.ui.ink_style import set_primary_button
from src.ui.input_fields.number_field import NumberField
from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from src.ui.input_fields.seed_value_spinbox import SeedValueSpinbox
from src.ui.input_fields.slider_field import SliderField
from src.ui.layout.dock_panel import DockPanel, PanelLayout
from src.ui.layout.label_column_layout import LabelColumnLayout, normalize_row_label
from src.ui.layout.panel_fit import REQUIRED
from src.ui.widget.disabled_banner import DisabledBanner
from src.util.application_state import APP_STATE_EDITING, AppStateTracker
from src.util.shared_constants import (BUTTON_TEXT_GENERATE, BUTTON_TOOLTIP_GENERATE, EDIT_MODE_IMG2IMG,
                                       EDIT_MODE_INPAINT, EDIT_MODE_TXT2IMG)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.generators.sd_webui_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


PANEL_TITLE = _tr('Image generation')
BACKEND_DESCRIPTION_WEBUI = _tr('WebUI')
BACKEND_DESCRIPTION_COMFYUI = _tr('ComfyUI')

SECTION_TITLE_MODE = _tr('Edit mode')
SECTION_TITLE_PROMPT = _tr('Prompt')
SECTION_TITLE_INPAINT = _tr('Inpaint')
SECTION_TITLE_OUTPUT = _tr('Output')
SECTION_TITLE_SAMPLING = _tr('Sampling')
SECTION_TITLE_ADVANCED = _tr('Advanced')
SECTION_TITLE_CONTROLNET = _tr('ControlNet')

LABEL_NEGATIVE_PROMPT = _tr('Negative prompt')
LABEL_LAST_SEED = _tr('Last seed')
LABEL_FULL_RESOLUTION = _tr('Full resolution')

BUTTON_TEXT_LORA = _tr('LoRA')
BUTTON_TOOLTIP_LORA = _tr('Choose LoRA models to add to the prompt')
BUTTON_TEXT_STYLES = _tr('Styles')
BUTTON_TOOLTIP_STYLES = _tr('Add saved prompt styles to the prompt')
BUTTON_TEXT_INTERROGATE = _tr('Interrogate')
BUTTON_TOOLTIP_INTERROGATE = _tr('Attempt to generate a prompt that describes the current image generation area')

MENU_TEXT_SETUP = _tr('Select image generator...')
MENU_TEXT_SETTINGS = _tr('Stable Diffusion settings...')
MENU_TEXT_LCM_MODE = _tr('LCM mode')
MENU_TEXT_CLEAR_MEMORY = _tr('Clear GPU memory')
TOOLTIP_CLEAR_MEMORY = _tr('Remove cached models from GPU memory in ComfyUI.')

INPAINT_NOTE_TXT2IMG = _tr('Text to image ignores the canvas, so denoising, masked content and padding do not apply.')
BANNER_FIX_TEXT = _tr('Setup...')
CONTROLNET_BUTTON_TOOLTIP = _tr('Open the ControlNet panel')
CONTROLNET_ALL_OFF = _tr('all units off')
CONTROLNET_UNIT_ON = _tr('unit {number} on: {preprocessor}', 'ControlNet summary of an enabled unit')
CONTROLNET_UNITS_ON = _tr('{count} units on', 'ControlNet summary when several units are enabled')
CONTROLNET_NO_PREPROCESSOR = _tr('no preprocessor')

SUMMARY_SAMPLING = _tr('{sampler}, {steps} steps, CFG {guidance}', 'Sampling section summary')
SUMMARY_ADVANCED_DEFAULT = _tr('defaults')

# A pair of fields is stacked in this form:
PAIR_FORM_SIDE_BY_SIDE = 0
PAIR_FORM_STACKED = 1


def config_slider_field(config: Config, key: str, parent: Optional[QWidget] = None, label: Optional[str] = None,
                        **field_options) -> SliderField:
    """Returns a `SliderField` bound to a numeric config value with a finite range. Edits write the config, and config
    changes update the field. `field_options` are passed on to the field, such as `zero_text`.

    Raises
    ------
    ValueError
        If the config value has no finite range.
    """
    minimum, maximum, step = config.get_range(key)
    if minimum is None or maximum is None or step is None:
        raise ValueError(f'Config key {key} needs a numeric range')
    field = SliderField(label if label is not None else normalize_row_label(config.get_label(key)),
                        config.get(key), minimum, maximum, step=step, parent=parent, **field_options)
    field.setToolTip(config.get_tooltip(key))

    def _field_changed(value: int | float) -> None:
        if config.get(key) != value:
            config.set(key, value)

    field.valueChanged.connect(_field_changed)
    config.connect(field, key, lambda value, *_: field.set_value(value))
    return field


def option_combo_box(config: Config, key: str, parent: Optional[QWidget] = None) -> QWidget:
    """Returns the config value's control widget. A combo box is set to shrink below its longest option, so a long
    model or sampler name can't widen the panel."""
    control = config.get_control_widget(key)
    control.setParent(parent)
    if isinstance(control, QComboBox):
        control.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        control.setMinimumContentsLength(8)
        control.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    return control


def controlnet_summary(saved_units: Sequence[str]) -> str:
    """Returns a one-line description of which saved ControlNet units will apply to the next generation. Units that
    fail to parse count as off."""
    enabled: list[tuple[int, SavedControlNetUnit]] = []
    for index, data in enumerate(saved_units):
        try:
            unit = SavedControlNetUnit.from_json(data)
        except ValueError:
            continue
        if unit.enabled:
            enabled.append((index + 1, unit))
    if len(enabled) == 0:
        return CONTROLNET_ALL_OFF
    if len(enabled) > 1:
        return CONTROLNET_UNITS_ON.format(count=len(enabled))
    number, unit = enabled[0]
    preprocessor = unit.unit.preprocessor
    return CONTROLNET_UNIT_ON.format(number=number, preprocessor=CONTROLNET_NO_PREPROCESSOR if preprocessor is None
                                     else preprocessor.typedef.name)


class FieldPair(QWidget):
    """Two fields side by side, or stacked when they don't fit that way. Used as a control with two forms."""

    def __init__(self, first: QWidget, second: QWidget, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(first)
        self._layout.addWidget(second)

    def set_stacked(self, stacked: bool) -> None:
        """Stacks the fields, or puts them side by side."""
        self._layout.setDirection(QBoxLayout.Direction.TopToBottom if stacked else QBoxLayout.Direction.LeftToRight)

    @property
    def forms(self) -> tuple[Callable[[], None], Callable[[], None]]:
        """The callbacks that put the pair in each of its forms, largest first, for `DockSection.add`."""
        return lambda: self.set_stacked(False), lambda: self.set_stacked(True)


class LabeledRows(QWidget):
    """Rows of a label and a field that share one label column."""

    def __init__(self, rows: Sequence[tuple[str, QWidget]], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = LabelColumnLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.labels: list[QLabel] = []
        for text, field in rows:
            label = layout.add_row(text, field)
            label.setToolTip(field.toolTip())
            self.labels.append(label)


class AdvancedControls(QWidget):
    """Backend-specific settings shown in the Advanced section. Subclasses fill it in."""

    def summary(self) -> str:
        """Returns a one-line description of the settings that differ from the usual ones."""
        raise NotImplementedError()

    def change_signals(self) -> list:
        """Returns the signals that mean `summary` may have changed."""
        raise NotImplementedError()


class StableDiffusionPanel(DockPanel):
    """A control panel for the Stable Diffusion WebUI and ComfyUI image generators."""

    generate_signal = Signal()
    interrogate_signal = Signal()
    lora_requested = Signal()
    styles_requested = Signal()
    lcm_mode_requested = Signal()
    clear_memory_requested = Signal()
    setup_requested = Signal()
    settings_requested = Signal()
    controlnet_requested = Signal()

    def __init__(self, webui: bool) -> None:
        # `build` runs in the superclass constructor and needs this:
        self._webui = webui
        super().__init__(PANEL_TITLE)
        AppStateTracker.set_enabled_states(self, [APP_STATE_EDITING])
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.header.set_description(BACKEND_DESCRIPTION_WEBUI if webui else BACKEND_DESCRIPTION_COMFYUI)
        self.header.reset_button.hide()
        self._advanced_controls: Optional[AdvancedControls] = None
        self._controlnet_keys: list[str] = []
        self.lcm_available_check: Optional[Callable[[], bool]] = None

        self._banner = DisabledBanner('', BANNER_FIX_TEXT)
        self._banner.fix_requested.connect(self.setup_requested)
        self._banner.hide()
        outer = self.layout()
        assert isinstance(outer, QVBoxLayout)
        outer.insertWidget(1, self._banner)

        self._generate_button = QPushButton(BUTTON_TEXT_GENERATE)
        self._generate_button.setToolTip(BUTTON_TOOLTIP_GENERATE)
        set_primary_button(self._generate_button)
        self._generate_button.clicked.connect(self.generate_signal)
        self.set_footer(self._generate_button)

        self._build_more_menu()
        self._connect_edit_mode()

    # ---------------------------------------------------------------------------------------------------------------
    # Content
    # ---------------------------------------------------------------------------------------------------------------

    def build(self, ui: PanelLayout) -> None:
        """Declares the sections."""
        cache = Cache()
        self._build_mode_section(ui)
        self._build_prompt_section(ui, cache)
        self._build_inpaint_section(ui, cache)
        self._build_output_section(ui, cache)
        self._build_sampling_section(ui, cache)
        self._build_advanced_section(ui)
        self._build_controlnet_section(ui)

    def _build_mode_section(self, ui: PanelLayout) -> None:
        cache = Cache()
        self._mode_section = ui.section(SECTION_TITLE_MODE)
        self._mode_section.widget.set_header_visible(False)
        self._edit_mode_control = SegmentedControl(
            [Segment(mode, cache.get_option_display(mode))
             for mode in (EDIT_MODE_INPAINT, EDIT_MODE_IMG2IMG, EDIT_MODE_TXT2IMG)],
            display_mode=DisplayMode.LABEL, combo_fallback=True)
        self._edit_mode_control.setToolTip(cache.get_tooltip(Cache.EDIT_MODE))
        self._edit_mode_control.set_value(cache.get(Cache.EDIT_MODE))
        self._mode_section.add(self._edit_mode_control, REQUIRED)

    def _build_prompt_section(self, ui: PanelLayout, cache: Cache) -> None:
        section = ui.section(SECTION_TITLE_PROMPT)
        self._prompt_section = section
        self._prompt_textbox = cache.get_control_widget(Cache.PROMPT, multi_line=True)
        self._negative_textbox = cache.get_control_widget(Cache.NEGATIVE_PROMPT, multi_line=True)
        for textbox in (self._prompt_textbox, self._negative_textbox):
            textbox.setMaximumHeight(textbox.fontMetrics().lineSpacing() * 5 + 12)
        self._negative_label = QLabel(LABEL_NEGATIVE_PROMPT)
        self._negative_label.setBuddy(self._negative_textbox)
        self._negative_label.setToolTip(self._negative_textbox.toolTip())
        section.add(self._prompt_textbox, REQUIRED)
        section.add(self._negative_label, REQUIRED)
        section.add(self._negative_textbox, REQUIRED)

        # Prompt tools open existing windows. Each hides when it has nothing to show:
        self._lora_button = self._header_tool_button(BUTTON_TEXT_LORA, BUTTON_TOOLTIP_LORA, self.lora_requested)
        self._styles_button: Optional[QPushButton] = None
        self._interrogate_button: Optional[QPushButton] = None
        section.widget.add_header_widget(self._lora_button)
        if self._webui:
            self._styles_button = self._header_tool_button(BUTTON_TEXT_STYLES, BUTTON_TOOLTIP_STYLES,
                                                           self.styles_requested)
            section.widget.add_header_widget(self._styles_button)
            self._interrogate_button = self._header_tool_button(BUTTON_TEXT_INTERROGATE, BUTTON_TOOLTIP_INTERROGATE,
                                                                self.interrogate_signal)
            section.widget.add_header_widget(self._interrogate_button)

        def _lora_update(models: list) -> None:
            self._lora_button.setVisible(len(models) > 0)

        cache.connect(self._lora_button, Cache.LORA_MODELS, _lora_update)
        _lora_update(cache.get(Cache.LORA_MODELS))
        if self._styles_button is not None:
            styles_button = self._styles_button

            def _styles_update(styles: list) -> None:
                styles_button.setVisible(len(styles) > 0)

            cache.connect(styles_button, Cache.STYLES, _styles_update)
            _styles_update(cache.get(Cache.STYLES))

    @staticmethod
    def _header_tool_button(text: str, tooltip: str, signal) -> QPushButton:
        button = QPushButton(text)
        button.setFlat(True)
        button.setToolTip(tooltip)
        button.clicked.connect(signal)
        return button

    def _build_inpaint_section(self, ui: PanelLayout, cache: Cache) -> None:
        section = ui.section(SECTION_TITLE_INPAINT)
        self._inpaint_section = section
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)

        self._inpaint_note = QLabel(INPAINT_NOTE_TXT2IMG)
        self._inpaint_note.setWordWrap(True)
        self._inpaint_note.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._denoising_field = config_slider_field(cache, Cache.DENOISING_STRENGTH, body)
        self._masked_content_rows: Optional[LabeledRows] = None
        if self._webui:
            self._masked_content_combobox = option_combo_box(cache, Cache.MASKED_CONTENT, body)
            self._masked_content_rows = LabeledRows([(normalize_row_label(cache.get_label(Cache.MASKED_CONTENT)),
                                                      self._masked_content_combobox)], body)
        self._full_res_checkbox = QCheckBox(LABEL_FULL_RESOLUTION)
        self._full_res_checkbox.setToolTip(cache.get_tooltip(Cache.INPAINT_FULL_RES))
        self._full_res_checkbox.setChecked(bool(cache.get(Cache.INPAINT_FULL_RES)))

        def _full_res_toggled(checked: bool) -> None:
            if cache.get(Cache.INPAINT_FULL_RES) != checked:
                cache.set(Cache.INPAINT_FULL_RES, checked)

        self._full_res_checkbox.toggled.connect(_full_res_toggled)
        self._padding_field = config_slider_field(cache, Cache.INPAINT_FULL_RES_PADDING, body)

        def _full_res_changed(checked: bool) -> None:
            if self._full_res_checkbox.isChecked() != checked:
                self._full_res_checkbox.setChecked(checked)
            self._padding_field.setEnabled(checked)

        cache.connect(self._full_res_checkbox, Cache.INPAINT_FULL_RES, _full_res_changed)
        _full_res_changed(bool(cache.get(Cache.INPAINT_FULL_RES)))
        self._full_res_pair = FieldPair(self._full_res_checkbox, self._padding_field, body)
        self._mask_blur_field = config_slider_field(AppConfig(), AppConfig.MASK_BLUR, body)

        for widget in (self._inpaint_note, self._denoising_field, self._masked_content_rows, self._full_res_pair,
                       self._mask_blur_field):
            if widget is not None:
                body_layout.addWidget(widget)
        section.add(body, REQUIRED)

    def _build_output_section(self, ui: PanelLayout, cache: Cache) -> None:
        section = ui.section(SECTION_TITLE_OUTPUT)
        self._output_section = section
        self._gen_size_input = cache.get_control_widget(Cache.GENERATION_SIZE)
        self._resolution_rule_combobox = option_combo_box(cache, Cache.GENERATION_RESOLUTION_RULE)
        section.add(LabeledRows([(normalize_row_label(cache.get_label(Cache.GENERATION_SIZE)), self._gen_size_input),
                                 (normalize_row_label(cache.get_label(Cache.GENERATION_RESOLUTION_RULE)),
                                  self._resolution_rule_combobox)]), REQUIRED)
        self._batch_size_field = config_slider_field(cache, Cache.BATCH_SIZE)
        self._batch_count_field = config_slider_field(cache, Cache.BATCH_COUNT)
        batch_pair = FieldPair(self._batch_size_field, self._batch_count_field)
        section.add(batch_pair, REQUIRED, batch_pair.forms)

        self._seed_input = SeedValueSpinbox(Cache.SEED, Cache.LAST_SEED)
        section.add(LabeledRows([(normalize_row_label(cache.get_label(Cache.SEED)), self._seed_input)]), REQUIRED)
        self._last_seed_label = QLabel()
        self._last_seed_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._last_seed_label.setToolTip(cache.get_tooltip(Cache.LAST_SEED))

        def _last_seed_update(last_seed: str) -> None:
            self._last_seed_label.setText(f'{LABEL_LAST_SEED} {last_seed}')

        cache.connect(self._last_seed_label, Cache.LAST_SEED, _last_seed_update)
        _last_seed_update(cache.get(Cache.LAST_SEED))
        section.add(self._last_seed_label, REQUIRED)

    def _build_sampling_section(self, ui: PanelLayout, cache: Cache) -> None:
        section = ui.section(SECTION_TITLE_SAMPLING)
        self._sampling_section = section
        self._model_combobox = option_combo_box(cache, Cache.SD_MODEL)
        self._sampler_combobox = option_combo_box(cache, Cache.SAMPLING_METHOD)
        section.add(LabeledRows([(normalize_row_label(cache.get_label(Cache.SD_MODEL)), self._model_combobox),
                                 (normalize_row_label(cache.get_label(Cache.SAMPLING_METHOD)),
                                  self._sampler_combobox)]), REQUIRED)
        self._steps_field = config_slider_field(cache, Cache.SAMPLING_STEPS)
        self._guidance_field = config_slider_field(cache, Cache.GUIDANCE_SCALE)
        sampling_pair = FieldPair(self._steps_field, self._guidance_field)
        section.add(sampling_pair, REQUIRED, sampling_pair.forms)
        self._clip_skip_field = config_slider_field(cache, Cache.CLIP_SKIP)
        section.add(self._clip_skip_field, REQUIRED)

        def _sampling_summary() -> str:
            return SUMMARY_SAMPLING.format(sampler=cache.get(Cache.SAMPLING_METHOD),
                                           steps=cache.get(Cache.SAMPLING_STEPS),
                                           guidance=cache.get(Cache.GUIDANCE_SCALE))

        section.widget.bind_summary(_sampling_summary, self._steps_field.valueChanged,
                                    self._guidance_field.valueChanged, self._sampler_combobox.valueChanged)

    def _build_advanced_section(self, ui: PanelLayout) -> None:
        section = ui.section(SECTION_TITLE_ADVANCED)
        self._advanced_section = section
        self._advanced_body = QWidget()
        self._advanced_layout = QVBoxLayout(self._advanced_body)
        self._advanced_layout.setContentsMargins(0, 0, 0, 0)
        section.add(self._advanced_body, REQUIRED)
        section.widget.set_expanded(False)

    def _build_controlnet_section(self, ui: PanelLayout) -> None:
        section = ui.section(SECTION_TITLE_CONTROLNET)
        self._controlnet_section = section
        self._controlnet_button = QPushButton()
        self._controlnet_button.setFlat(True)
        self._controlnet_button.setToolTip(CONTROLNET_BUTTON_TOOLTIP)
        self._controlnet_button.setStyleSheet('text-align: left;')
        self._controlnet_button.clicked.connect(self.controlnet_requested)
        section.add(self._controlnet_button, REQUIRED)

    # ---------------------------------------------------------------------------------------------------------------
    # Backend-specific content
    # ---------------------------------------------------------------------------------------------------------------

    def set_advanced_content(self, controls: AdvancedControls) -> None:
        """Fills the Advanced section with a backend's extra settings, and summarizes them when it is collapsed.

        Raises
        ------
        RuntimeError
            If the section was already filled.
        """
        if self._advanced_controls is not None:
            raise RuntimeError('Tried to set the advanced content twice')
        self._advanced_controls = controls
        self._advanced_layout.addWidget(controls)
        self._advanced_section.widget.bind_summary(controls.summary, *controls.change_signals())
        self.refit()

    @property
    def advanced_controls(self) -> Optional[AdvancedControls]:
        """The backend-specific content of the Advanced section, once set."""
        return self._advanced_controls

    def set_controlnet_cache_keys(self, keys: list[str]) -> None:
        """Shows the ControlNet summary for the units saved under these Cache keys, or hides it for an empty list."""
        cache = Cache()
        self._controlnet_keys = list(keys)
        for key in keys:
            cache.connect(self._controlnet_button, key, lambda *_: self.refresh_controlnet_summary())
        self.refresh_controlnet_summary()
        self.refit()

    def refresh_controlnet_summary(self) -> None:
        """Updates the ControlNet summary from the saved units."""
        cache = Cache()
        self._controlnet_button.setText(controlnet_summary([cache.get(key) for key in self._controlnet_keys]))

    # ---------------------------------------------------------------------------------------------------------------
    # More menu, banner and edit mode
    # ---------------------------------------------------------------------------------------------------------------

    def _build_more_menu(self) -> None:
        self._more_content = QWidget()
        more_layout = QVBoxLayout(self._more_content)
        more_layout.setContentsMargins(0, 0, 0, 0)
        self._setup_menu_button = self._add_more_button(MENU_TEXT_SETUP, more_layout, self.setup_requested)
        self._settings_menu_button = self._add_more_button(MENU_TEXT_SETTINGS, more_layout, self.settings_requested)
        self._lcm_menu_button = self._add_more_button(MENU_TEXT_LCM_MODE, more_layout, self.lcm_mode_requested)
        self._clear_memory_menu_button = self._add_more_button(MENU_TEXT_CLEAR_MEMORY, more_layout,
                                                               self.clear_memory_requested)
        self._clear_memory_menu_button.setToolTip(TOOLTIP_CLEAR_MEMORY)
        self._clear_memory_menu_button.setVisible(not self._webui)
        self.header.more_requested.connect(self._refresh_more_menu)

    def _add_more_button(self, text: str, layout: QVBoxLayout, signal) -> QPushButton:
        button = QPushButton(text)
        button.setFlat(True)
        button.clicked.connect(lambda: self.header.popover.hide())
        button.clicked.connect(signal)
        layout.addWidget(button)
        return button

    def _refresh_more_menu(self) -> None:
        self._lcm_menu_button.setVisible(self.lcm_available_check is not None and self.lcm_available_check())

    def more_content(self) -> Optional[QWidget]:
        """Returns the More menu, which the panel always has."""
        return self._more_content

    def set_disconnected(self, message: Optional[str]) -> None:
        """Shows the not-connected banner with this message, or hides it for None."""
        if message is not None:
            self._banner.set_message(message)
        self._banner.setVisible(message is not None)
        self.refit()

    def _connect_edit_mode(self) -> None:
        cache = Cache()

        def _control_changed(mode: str) -> None:
            if cache.get(Cache.EDIT_MODE) != mode:
                cache.set(Cache.EDIT_MODE, mode)

        self._edit_mode_control.valueChanged.connect(_control_changed)

        def _edit_mode_changed(edit_mode: str) -> None:
            self._edit_mode_control.set_value(edit_mode)
            self._update_inpaint_section(edit_mode)

        cache.connect(self._edit_mode_control, Cache.EDIT_MODE, _edit_mode_changed)
        self._update_inpaint_section(cache.get(Cache.EDIT_MODE))

    def _update_inpaint_section(self, edit_mode: str) -> None:
        """Shows the Inpaint section's controls for the mode. The section itself always shows."""
        inpaint = edit_mode == EDIT_MODE_INPAINT
        self._inpaint_note.setVisible(edit_mode == EDIT_MODE_TXT2IMG)
        self._denoising_field.setVisible(edit_mode in (EDIT_MODE_INPAINT, EDIT_MODE_IMG2IMG))
        if self._masked_content_rows is not None:
            self._masked_content_rows.setVisible(inpaint)
        self._full_res_pair.setVisible(inpaint)
        self._mask_blur_field.setVisible(inpaint)
        self.refit()

    # ---------------------------------------------------------------------------------------------------------------
    # Layout
    # ---------------------------------------------------------------------------------------------------------------

    def finish_placement(self) -> None:
        """Hides the ControlNet section while the backend has no ControlNet units."""
        super().finish_placement()
        self._controlnet_section.widget.setVisible(len(self._controlnet_keys) > 0)

    # ---------------------------------------------------------------------------------------------------------------
    # Accessors for tests and the generators
    # ---------------------------------------------------------------------------------------------------------------

    @property
    def edit_mode_control(self) -> SegmentedControl:
        """The edit mode selector."""
        return self._edit_mode_control

    @property
    def generate_button(self) -> QPushButton:
        """The Generate button."""
        return self._generate_button

    @property
    def inpaint_fields(self) -> list[NumberField]:
        """The Inpaint section's number fields."""
        return [self._denoising_field, self._padding_field, self._mask_blur_field]

    @property
    def banner(self) -> DisabledBanner:
        """The not-connected banner."""
        return self._banner

    @property
    def prompt_tool_buttons(self) -> list[QPushButton]:
        """The Prompt header's buttons, in display order."""
        return [button for button in (self._lora_button, self._styles_button, self._interrogate_button)
                if button is not None]

    @property
    def more_menu_buttons(self) -> list[QPushButton]:
        """The More menu's buttons, in display order."""
        return [self._setup_menu_button, self._settings_menu_button, self._lcm_menu_button,
                self._clear_memory_menu_button]

