"""Control panel for GLID-3-XL inpainting.

It is a `GenerateFooterPanel` built from the same pieces as the Stable Diffusion panel: Prompt, Sampling and Scaling
sections, slider fields bound to the config values, and a pinned Generate button. GLID-3-XL is legacy, so this file
only arranges its controls.
"""
from functools import partial
from typing import Optional

from PySide6.QtWidgets import QApplication, QPlainTextEdit, QSizePolicy

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.ui.layout.dock_panel import PanelLayout
from src.ui.layout.label_column_layout import normalize_row_label
from src.ui.layout.panel_fit import REQUIRED
from src.ui.panel.generators.generator_panel import GenerateFooterPanel
from src.ui.panel.generators.stable_diffusion_panel import LabeledRows, config_slider_field, option_combo_box
from src.ui.widget.panel_section import PanelSection
from src.util.application_state import APP_STATE_EDITING, AppStateTracker
from src.ui.input_fields.field_factory import create_control_widget

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.generators.glid_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


PANEL_TITLE = _tr('Image generation')
BACKEND_DESCRIPTION = _tr('GLID-3-XL')

SECTION_TITLE_PROMPT = _tr('Prompt')
SECTION_TITLE_SAMPLING = _tr('Sampling')
SECTION_TITLE_SCALING = _tr('Scaling')
LABEL_NEGATIVE_PROMPT = _tr('Negative prompt')

# Planning collapses Sampling, then Scaling, to their summaries when the panel is short:
SAMPLING_PRIORITY = 1
SCALING_PRIORITY = 2

# Prompt boxes are this many text lines tall:
PROMPT_LINES = 4
PROMPT_BOX_PADDING = 12


# `build` runs in the `DockPanel` constructor, so the controls it creates are attributes defined outside `__init__`:
# pylint: disable=attribute-defined-outside-init
class GlidPanel(GenerateFooterPanel):
    """Control panel widget for GLID-3-XL inpainting."""

    def __init__(self) -> None:
        super().__init__(PANEL_TITLE)
        AppStateTracker.set_enabled_states(self, [APP_STATE_EDITING])
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.header.set_description(BACKEND_DESCRIPTION)
        self.header.reset_button.hide()

    def build(self, ui: PanelLayout) -> None:
        """Declares the sections."""
        self._build_prompt_section(ui)
        self._build_sampling_section(ui)
        self._build_scaling_section(ui)

    def _prompt_box_height(self) -> int:
        return self.fontMetrics().lineSpacing() * PROMPT_LINES + PROMPT_BOX_PADDING

    def _prompt_box(self, key: str) -> QPlainTextEdit:
        box = create_control_widget(Cache(), key, multi_line=True)
        assert isinstance(box, QPlainTextEdit)
        box.setMaximumHeight(self._prompt_box_height())
        box.setMinimumHeight(self._prompt_box_height())
        return box

    def _build_prompt_section(self, ui: PanelLayout) -> None:
        cache = Cache()
        section = ui.section(SECTION_TITLE_PROMPT)
        self._prompt_textbox = self._prompt_box(Cache.PROMPT)
        section.add(self._prompt_textbox, REQUIRED)
        self._negative_textbox = self._prompt_box(Cache.NEGATIVE_PROMPT)
        # The negative prompt folds to one line that shows its text:
        self._negative_fold = PanelSection(LABEL_NEGATIVE_PROMPT, self._negative_textbox, expanded=False)
        self._negative_fold.setToolTip(cache.get_tooltip(Cache.NEGATIVE_PROMPT))
        self._negative_fold.bind_summary(partial(self._negative_summary, self._negative_textbox),
                                         self._negative_textbox.textChanged)
        self._negative_fold.expanded_changed.connect(lambda _expanded: self.refit())
        section.add(self._negative_fold, REQUIRED)

    @staticmethod
    def _negative_summary(textbox: QPlainTextEdit) -> str:
        return ' '.join(textbox.toPlainText().split())

    def _build_sampling_section(self, ui: PanelLayout) -> None:
        cache = Cache()
        section = ui.section(SECTION_TITLE_SAMPLING, collapsible=True, priority=SAMPLING_PRIORITY)
        self._guidance_scale_field = config_slider_field(cache, Cache.GUIDANCE_SCALE)
        self._skip_steps_field = config_slider_field(cache, Cache.SKIP_STEPS)
        self._cutn_field = config_slider_field(cache, Cache.CUTN)
        self._batch_size_field = config_slider_field(cache, Cache.BATCH_SIZE)
        self._batch_count_field = config_slider_field(cache, Cache.BATCH_COUNT)
        for field in (self._guidance_scale_field, self._skip_steps_field, self._cutn_field, self._batch_size_field,
                      self._batch_count_field):
            section.add(field, REQUIRED)
        self._full_res_checkbox = create_control_widget(cache, Cache.INPAINT_FULL_RES)
        self._full_res_checkbox.setText(normalize_row_label(cache.get_label(Cache.INPAINT_FULL_RES)))
        section.add(self._full_res_checkbox, REQUIRED)
        section.widget.bind_summary(
            lambda: f'{cache.get(Cache.GUIDANCE_SCALE):g}, {cache.get(Cache.BATCH_SIZE)} x '
                    f'{cache.get(Cache.BATCH_COUNT)}',
            self._guidance_scale_field.valueChanged, self._batch_size_field.valueChanged,
            self._batch_count_field.valueChanged)

    def _build_scaling_section(self, ui: PanelLayout) -> None:
        config = AppConfig()
        section = ui.section(SECTION_TITLE_SCALING, collapsible=True, priority=SCALING_PRIORITY)
        self._upscale_mode_list = option_combo_box(config, AppConfig.PIL_UPSCALE_MODE)
        self._downscale_mode_list = option_combo_box(config, AppConfig.PIL_DOWNSCALE_MODE)
        section.add(LabeledRows([
            (normalize_row_label(config.get_label(AppConfig.PIL_UPSCALE_MODE)), self._upscale_mode_list),
            (normalize_row_label(config.get_label(AppConfig.PIL_DOWNSCALE_MODE)), self._downscale_mode_list)]),
            REQUIRED)
        section.widget.bind_summary(
            lambda: f'{config.get(AppConfig.PIL_UPSCALE_MODE)}, {config.get(AppConfig.PIL_DOWNSCALE_MODE)}',
            self._upscale_mode_list.valueChanged, self._downscale_mode_list.valueChanged)
        section.widget.set_expanded(False)
