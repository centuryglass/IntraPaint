"""The Stable Diffusion generation panel, for the WebUI and ComfyUI backends.

It is a `DockPanel` that places controls by how often they're used. The action block holds the ones used after every
generation: denoising strength, CFG scale, steps, batch size, context and Generate, with Generate last. It is a side
panel's footer (`DockPanel.set_footer`) and a strip's trailing column (`DockPanel.trailing_layout`), so Generate stays
at the bottom and never scrolls. Generate is capped at the fields' width, so in a wide side panel it ends where they
do. The sections run Prompt, Mask, Sampling, Size and batch, then Advanced. A strip pins Prompt in a column at the left
(`DockPanel.pinned_layout`) and packs the rest into columns between the two (`DockPanel.set_column_packing`).

- Every control is bound to its config value and has one owner here. Backend-specific controls arrive as constructor
  arguments (`webui`) and `set_advanced_content`.
- The edit mode decides which controls show, and the panel plans again when it changes. The Mask section and context
  show in Inpaint only, and denoising strength in Inpaint and Image to image. Outside Inpaint, the header's edit mode
  selector takes the caution color and a note above Generate names the mode.
- The edit mode selector sits in the header. A strip puts the header at the top of the prompt column, so the columns
  beside it get the strip's full height. The prompt column scrolls on its own, so the header never collapses.
- The header's More menu holds Describe and the commands that open other windows. The panel emits signals for them
  and the generator acts on them.
- The panel stays unaware of the backend connection. The generator shows `DisabledBanner` through
  `set_disconnected`.
"""
from functools import partial
from typing import Callable, Optional, Sequence

from PySide6.QtCore import QEvent, QPointF, QSize, Qt, Signal
from PySide6.QtGui import QFont, QPainter, QPainterPath, QPalette, QResizeEvent
from PySide6.QtWidgets import (QApplication, QBoxLayout, QComboBox, QFormLayout, QLabel, QPlainTextEdit, QPushButton,
                               QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.config import Config
from src.ui.ink_style import caution_color, set_primary_button
from src.ui.input_fields.number_field import NumberField
from src.ui.input_fields.seed_value_spinbox import SeedValueSpinbox
from src.ui.input_fields.size_field import SizeField
from src.ui.input_fields.slider_field import SliderField
from src.ui.layout.dock_panel import QWIDGETSIZE_MAX, DockPanel, PanelDivider, PanelLayout
from src.ui.layout.label_column_layout import LabelColumnLayout, normalize_row_label
from src.ui.layout.panel_fit import (FIELD_MAX_WIDTH, REQUIRED, FitItem, Orientation, fresh_minimum_size,
                                     held_weakly)
from src.ui.panel.generators.prompt_boxes import PromptBoxes
from src.ui.panel.generators.soft_inpainting_controls import SoftInpaintingControls
from src.ui.widget.disabled_banner import DisabledBanner
from src.ui.widget.panel_section import PanelSection
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

SECTION_TITLE_PROMPT = _tr('Prompt')
SECTION_TITLE_MASK = _tr('Mask')
SECTION_TITLE_SAMPLING = _tr('Sampling')
SECTION_TITLE_SIZE = _tr('Size and batch')
SECTION_TITLE_ADVANCED = _tr('Advanced')

GROUP_TITLE_INPAINT_AND_SIZE = _tr('Inpainting and size')
GROUP_TITLE_MODEL = _tr('Model')

LABEL_MODEL = _tr('Model')
LABEL_CFG_SCALE = _tr('CFG scale')
LABEL_STEPS = _tr('Steps')
LABEL_NEGATIVE_PROMPT = _tr('Negative prompt')
LABEL_LAST_SEED = _tr('Last seed')
CONTEXT_OFF = _tr('whole area', 'Inpaint context while it covers the whole generation area')
TOOLTIP_LIMIT_CONTEXT_TILING = _tr('Inpainting ignores the context limit while tiling is on.')
BUTTON_TEXT_TILING_ON = _tr('Tiling on')
BUTTON_TOOLTIP_TILING_ON = _tr('Generated images tile, and inpainting ignores the context limit. Click to turn tiling '
                               'off.')

BUTTON_TEXT_LORA = _tr('LoRA')
BUTTON_TOOLTIP_LORA = _tr('Choose LoRA models to add to the prompt')
BUTTON_TEXT_STYLES = _tr('Styles')
BUTTON_TOOLTIP_STYLES = _tr('Add saved prompt styles to the prompt')

MENU_TEXT_DESCRIBE = _tr('Describe')
TOOLTIP_DESCRIBE = _tr('Replace the prompt with a description of the generation area')
MENU_TEXT_SETUP = _tr('Select image generator...')
MENU_TEXT_SETTINGS = _tr('Stable Diffusion settings...')
MENU_TEXT_LCM_MODE = _tr('LCM mode')
MENU_TEXT_CLEAR_MEMORY = _tr('Clear GPU memory')
TOOLTIP_CLEAR_MEMORY = _tr('Remove cached models from GPU memory in ComfyUI.')

NOTE_IMG2IMG = _tr('Image to image: ignores the mask')
NOTE_TXT2IMG = _tr('Text to image: ignores the canvas')
BANNER_FIX_TEXT = _tr('Setup...')

SUMMARY_MASK = _tr('blur {blur}', 'Mask section summary')
SUMMARY_MASK_SOFT = _tr('blur {blur}, soft inpainting', 'Mask section summary')
SUMMARY_SAMPLING_FIXED_SEED = _tr('seed {seed}, {sampler}', 'Sampling section summary while the seed is fixed')
SUMMARY_SIZE = _tr('{width} x {height}, count {count}', 'Size and batch section summary')
SUMMARY_ADVANCED_DEFAULT = _tr('defaults')

# The widest the pinned prompt column of a strip grows:
PROMPT_COLUMN_MAX_WIDTH = 300
# The widest the action block grows as a strip's trailing column:
ACTION_COLUMN_MAX_WIDTH = 240

# The prompt box is never narrower than this many average characters. A strip with no room for that beside the other
# columns plans as a side panel:
PROMPT_MIN_CHARACTERS = 24

# Denoising strength is the most used value, so its field is taller than the others:
DENOISING_FIELD_HEIGHT = 30

# Planning collapses sections to their summaries, and hides the edit mode note, from the highest priority number down:
NOTE_PRIORITY = 1
MASK_PRIORITY = 1
SAMPLING_PRIORITY = 2
SIZE_PRIORITY = 3
ADVANCED_PRIORITY = 4

# The action block's field pairs, in their two forms:
PAIR_FORM_SIDE_BY_SIDE = 0
PAIR_FORM_STACKED = 1

# The seed value that means a random seed:
RANDOM_SEED = -1


def config_slider_field(config: Config, key: str, parent: Optional[QWidget] = None, label: Optional[str] = None,
                        field_class: type[SliderField] = SliderField, **field_options) -> SliderField:
    """Returns a `field_class` field bound to a numeric config value with a finite range. Edits write the config, and
    config changes update the field. `field_options` are passed on to the field, such as `zero_text`.

    Raises
    ------
    ValueError
        If the config value has no finite range.
    """
    minimum, maximum, step = config.get_range(key)
    if minimum is None or maximum is None or step is None:
        raise ValueError(f'Config key {key} needs a numeric range')
    field = field_class(label if label is not None else normalize_row_label(config.get_label(key)),
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
    control.setMaximumWidth(FIELD_MAX_WIDTH)
    return control


def group_label(text: str) -> QLabel:
    """Returns a dim heading for a group of controls inside a section."""
    label = QLabel(text)
    label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
    font = QFont(label.font())
    font.setWeight(QFont.Weight.DemiBold)
    label.setFont(font)
    return label


class ToggledSliderField(SliderField):
    """A `SliderField` whose link toggles the setting its value belongs to, such as context that is limited only
    while the toggle is on.

    The toggle is the field's pen pressure link (`set_pressure_link_enabled`, `pressureLinkToggled`), drawn with a
    full-frame glyph. While it is off, the field reads `off_text` in dim text with no fill, and ignores dragging, typing
    and stepping. It passes wheel events on, so the wheel scrolls the panel. While locked (`set_toggle_locked`),
    clicks and Space leave the toggle as it is.
    """

    def __init__(self, label: str, value: int | float, minimum: int | float, maximum: int | float,
                 parent: Optional[QWidget] = None, off_text: str = '', **kwargs) -> None:
        # The superclass constructor reads `value_text`:
        self._off_text = off_text
        self._toggle_locked = False
        super().__init__(label, value, minimum, maximum, parent=parent, **kwargs)
        self.set_pressure_link_available(True)
        self.pressureLinkToggled.connect(self._toggled)

    def is_off(self) -> bool:
        """Returns whether the toggle is off, so the value doesn't apply."""
        return not self.pressure_link_enabled()

    def set_toggle_locked(self, locked: bool) -> None:
        """Locks or unlocks the toggle against clicks and Space. `set_pressure_link_enabled` still changes it."""
        self._toggle_locked = locked

    def toggle_locked(self) -> bool:
        """Returns whether clicks and Space leave the toggle as it is."""
        return self._toggle_locked

    def _toggled(self, _enabled: bool) -> None:
        self._update_accessible_description()
        self.update()

    def value_text(self, value: Optional[int | float] = None) -> str:
        """Returns `off_text` for the current value while the toggle is off, and the value's text otherwise."""
        if value is None and self.is_off():
            return self._off_text
        return super().value_text(value)

    def _fill_fraction(self) -> Optional[float]:
        return None if self.is_off() else super()._fill_fraction()

    def _paint_text(self, painter: QPainter) -> None:
        if not self.is_off():
            super()._paint_text(painter)
            return
        text = self._colors.text
        self._colors.text = self._colors.label
        super()._paint_text(painter)
        self._colors.text = text

    def _link_glyph(self, origin: QPointF) -> QPainterPath:
        """Returns four corner brackets, the full-frame glyph."""
        glyph = QPainterPath()
        for corner in ((1.0, 4.5, 1.0, 1.0, 4.5, 1.0), (7.5, 1.0, 11.0, 1.0, 11.0, 4.5),
                       (11.0, 7.5, 11.0, 11.0, 7.5, 11.0), (4.5, 11.0, 1.0, 11.0, 1.0, 7.5)):
            glyph.moveTo(origin + QPointF(corner[0], corner[1]))
            glyph.lineTo(origin + QPointF(corner[2], corner[3]))
            glyph.lineTo(origin + QPointF(corner[4], corner[5]))
        return glyph

    def mousePressEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Toggles on a press on the link, unless locked. While off, ignores other presses."""
        if self._toggle_locked and self._pressure_link_rect().contains(event.position().toPoint()):
            event.accept()
            return
        if self.is_off() and not self._pressure_link_rect().contains(event.position().toPoint()):
            event.ignore()
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Steps the value, or passes the event on while off."""
        if self.is_off():
            event.ignore()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Handles keys as `NumberField` does, except that while off only Space, which toggles, does anything. While
        locked, Space does nothing."""
        if self._toggle_locked and event.key() == Qt.Key.Key_Space:
            event.accept()
            return
        if self.is_off() and event.key() != Qt.Key.Key_Space:
            QWidget.keyPressEvent(self, event)
            return
        super().keyPressEvent(event)

    def begin_edit(self) -> None:
        """Opens the text entry, except while off."""
        if not self.is_off():
            super().begin_edit()


class FieldPair(QWidget):
    """Two fields side by side, or stacked when they don't fit that way. Used as a control with two forms. The pair is
    capped at `FIELD_MAX_WIDTH`, so its right edge lines up with the other fields' in a wide side panel."""

    def __init__(self, first: QWidget, second: QWidget, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMaximumWidth(FIELD_MAX_WIDTH)
        self._layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(first)
        self._layout.addWidget(second)
        self._fields = (first, second)

    def set_stacked(self, stacked: bool) -> None:
        """Stacks the fields, or puts them side by side."""
        self._layout.setDirection(QBoxLayout.Direction.TopToBottom if stacked else QBoxLayout.Direction.LeftToRight)

    def is_stacked(self) -> bool:
        """Returns whether the fields are stacked."""
        return self._layout.direction() == QBoxLayout.Direction.TopToBottom

    def fits_side_by_side(self, width: int) -> bool:
        """Returns whether both fields fit side by side in `width` without eliding their labels or values."""
        widths = [field.unelided_width() if isinstance(field, NumberField) else field.sizeHint().width()
                  for field in self._fields]
        return sum(widths) + max(self._layout.spacing(), 0) <= width

    def forms(self, column_width: Callable[[], Optional[int]]) -> tuple[Callable[[], None], Callable[[], None]]:
        """Returns the callbacks that put the pair side by side and stacked, for `DockSection.add`.

        `column_width` returns the width of the strip column the pair sits in, or None in a side panel. A side panel
        stacks the fields when the panel is too narrow for them side by side. A strip has a fixed column width, so it
        stacks them in both forms when the column is too narrow for both fields' text side by side. A bound method
        `column_width` is held weakly.
        """
        column_width = held_weakly(column_width)

        def _side_by_side() -> None:
            width = column_width()
            self.set_stacked(width is not None and not self.fits_side_by_side(width))

        def _stacked() -> None:
            self.set_stacked(True)

        return _side_by_side, _stacked


class HonestSizeHints(QWidget):
    """Holds a widget whose own size hints understate what its layout needs, such as `SizeField`, and reports its
    layout's size hints instead."""

    def __init__(self, content: QWidget, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._content = content
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(content)
        self.setToolTip(content.toolTip())

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the content layout's minimum size."""
        layout = self._content.layout()
        return layout.minimumSize() if layout is not None else super().minimumSizeHint()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the content layout's preferred size."""
        layout = self._content.layout()
        return layout.sizeHint() if layout is not None else super().sizeHint()


class LabeledRows(QWidget):
    """Rows of a label and a field that share one label column. The rows are capped at `FIELD_MAX_WIDTH`, label
    included, so every row's right edge lines up with the other fields' in a wide side panel."""

    def __init__(self, rows: Sequence[tuple[str, QWidget]], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMaximumWidth(FIELD_MAX_WIDTH)
        layout = LabelColumnLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._form = layout
        self._fields = [field for _, field in rows]
        self.labels: list[QLabel] = []
        for text, field in rows:
            label = layout.add_row(text, field)
            label.setWordWrap(True)
            label.setToolTip(field.toolTip())
            self.labels.append(label)

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Moves every label above its field when the width can't hold the widest label and the widest field's
        minimum width side by side."""
        super().resizeEvent(event)
        needed = (max(label.sizeHint().width() for label in self.labels) + self._form.horizontalSpacing()
                  + max(field.minimumSizeHint().width() for field in self._fields))
        policy = QFormLayout.RowWrapPolicy.WrapAllRows if self.width() < needed \
            else QFormLayout.RowWrapPolicy.DontWrapRows
        if policy != self._form.rowWrapPolicy():
            self._form.setRowWrapPolicy(policy)


class AdvancedControls(QWidget):
    """Backend-specific settings shown in the Advanced section. Subclasses fill it in."""

    def summary(self) -> str:
        """Returns a one-line description of the settings that differ from the usual ones."""
        raise NotImplementedError()

    def change_signals(self) -> list:
        """Returns the signals that mean `summary` may have changed."""
        raise NotImplementedError()


# `build` runs in the `DockPanel` constructor, so the controls it creates are attributes defined outside `__init__`:
# pylint: disable=attribute-defined-outside-init
class StableDiffusionPanel(DockPanel):
    """A control panel for the Stable Diffusion WebUI and ComfyUI image generators."""

    generate_signal = Signal()
    describe_signal = Signal()
    lora_requested = Signal()
    styles_requested = Signal()
    lcm_mode_requested = Signal()
    clear_memory_requested = Signal()
    setup_requested = Signal()
    settings_requested = Signal()

    def __init__(self, webui: bool) -> None:
        # `build` runs in the superclass constructor and needs this:
        self._webui = webui
        super().__init__(PANEL_TITLE)
        AppStateTracker.set_enabled_states(self, [APP_STATE_EDITING])
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.header.set_description(BACKEND_DESCRIPTION_WEBUI if webui else BACKEND_DESCRIPTION_COMFYUI)
        self.header.reset_button.hide()
        self._advanced_controls: Optional[AdvancedControls] = None
        self.lcm_available_check: Optional[Callable[[], bool]] = None

        self._banner = DisabledBanner('', BANNER_FIX_TEXT)
        self._banner.fix_requested.connect(self.setup_requested)
        self._banner.hide()
        outer = self.layout()
        assert isinstance(outer, QVBoxLayout)
        outer.insertWidget(1, self._banner)

        self._build_edit_mode_control()
        self._build_action_block()
        self._build_more_menu()
        self._connect_edit_mode()
        # Takes a strip's spare column height past the Prompt section's cap. `arrange` puts the header and section
        # above it:
        self._prompt_column_spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.pinned_layout.addItem(self._prompt_column_spacer)

    # ---------------------------------------------------------------------------------------------------------------
    # Content
    # ---------------------------------------------------------------------------------------------------------------

    def build(self, ui: PanelLayout) -> None:
        """Declares the sections."""
        self.set_column_packing(True)
        cache = Cache()
        self._build_prompt_section(ui, cache)
        self._build_mask_section(ui)
        self._build_sampling_section(ui, cache)
        self._build_size_section(ui, cache)
        self._build_advanced_section(ui, cache)

    def _build_edit_mode_control(self) -> None:
        cache = Cache()
        combobox = cache.get_control_widget(Cache.EDIT_MODE)
        assert isinstance(combobox, QComboBox)
        self._edit_mode_combobox = combobox
        # It prefers the width of its longest mode, and shrinks to a few characters in a narrow header:
        combobox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combobox.setMinimumContentsLength(3)
        minimum_width = combobox.minimumSizeHint().width()
        combobox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        combobox.setMinimumWidth(minimum_width)
        combobox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        combobox.setToolTip(cache.get_tooltip(Cache.EDIT_MODE))
        self.header.add_widget(combobox)

    def _build_prompt_section(self, ui: PanelLayout, cache: Cache) -> None:
        section = ui.section(SECTION_TITLE_PROMPT)
        self._prompt_section = section
        # Replaces the pinned column's divider in a side panel, where Prompt sits at the top of the scrolled sections:
        self._prompt_divider = PanelDivider(Qt.Orientation.Horizontal)
        self._prompt_divider.hide()
        # Model sits here and not in the action block, so a wheel turned over denoising strength can't change it by a
        # near miss:
        self._model_combobox = option_combo_box(cache, Cache.SD_MODEL)
        section.add(LabeledRows([(LABEL_MODEL, self._model_combobox)]), REQUIRED)
        self._prompt_textbox = cache.get_control_widget(Cache.PROMPT, multi_line=True)
        self._prompt_textbox.setMinimumWidth(self._prompt_textbox.fontMetrics().averageCharWidth()
                                             * PROMPT_MIN_CHARACTERS)
        self._negative_textbox = cache.get_control_widget(Cache.NEGATIVE_PROMPT, multi_line=True)
        # The negative prompt folds to one line that shows its text:
        self._negative_fold = PanelSection(LABEL_NEGATIVE_PROMPT, self._negative_textbox, expanded=False)
        self._negative_fold.setToolTip(self._negative_textbox.toolTip())
        self._negative_fold.bind_summary(partial(self._negative_summary, self._negative_textbox),
                                         self._negative_textbox.textChanged)
        self._prompt_boxes = PromptBoxes(self._prompt_textbox, self._negative_textbox, self._negative_fold)
        # Connected after the boxes' own connection, so planning sees the fold's new cap:
        self._negative_fold.expanded_changed.connect(lambda _expanded: self.refit())
        self._prompt_boxes.limits_changed.connect(self._cap_prompt_section)
        section.add(self._prompt_boxes, REQUIRED)

        # Prompt tools open existing windows. Each hides when it has nothing to show:
        self._lora_button = self._header_tool_button(BUTTON_TEXT_LORA, BUTTON_TOOLTIP_LORA, self.lora_requested)
        self._styles_button: Optional[QPushButton] = None
        section.widget.add_header_widget(self._lora_button)
        if self._webui:
            self._styles_button = self._header_tool_button(BUTTON_TEXT_STYLES, BUTTON_TOOLTIP_STYLES,
                                                           self.styles_requested)
            section.widget.add_header_widget(self._styles_button)

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
    def _negative_summary(textbox: QPlainTextEdit) -> str:
        return ' '.join(textbox.toPlainText().split())

    def _cap_prompt_section(self) -> None:
        """Caps the Prompt section at its minimum height plus the prompt boxes' spare height, so spare height past the
        boxes' caps goes below the section. A side panel's sections take that much spare height before the space
        below them does."""
        section = self._prompt_section.widget
        spare = 0 if section.is_collapsed() else self._prompt_boxes.spare_height()
        section.setMaximumHeight(fresh_minimum_size(section).height() + spare)
        self.set_section_growth(spare if self.orientation == Orientation.SIDE else 0)

    @staticmethod
    def _header_tool_button(text: str, tooltip: str, signal) -> QPushButton:
        button = QPushButton(text)
        button.setFlat(True)
        button.setToolTip(tooltip)
        button.clicked.connect(signal)
        return button

    def _build_mask_section(self, ui: PanelLayout) -> None:
        section = ui.section(SECTION_TITLE_MASK, collapsible=True, priority=MASK_PRIORITY)
        self._mask_section = section
        self._mask_blur_field = config_slider_field(AppConfig(), AppConfig.MASK_BLUR)
        section.add(self._mask_blur_field, REQUIRED)
        self._soft_inpainting_controls = SoftInpaintingControls()
        self._soft_inpainting_controls.layout_changed.connect(self.refit)
        section.add(self._soft_inpainting_controls, REQUIRED)
        section.widget.bind_summary(self._mask_summary, self._mask_blur_field.valueChanged,
                                    self._soft_inpainting_controls.checkbox.toggled)

    def _mask_summary(self) -> str:
        cache = Cache()
        summary = SUMMARY_MASK_SOFT if cache.get(Cache.SOFT_INPAINTING_AVAILABLE) \
            and cache.get(Cache.SOFT_INPAINTING) else SUMMARY_MASK
        return summary.format(blur=self._mask_blur_field.value_text())

    def _build_sampling_section(self, ui: PanelLayout, cache: Cache) -> None:
        section = ui.section(SECTION_TITLE_SAMPLING, collapsible=True, priority=SAMPLING_PRIORITY)
        self._sampling_section = section
        self._seed_input = SeedValueSpinbox(Cache.SEED, Cache.LAST_SEED)
        self._seed_input.setMaximumWidth(FIELD_MAX_WIDTH)
        section.add(LabeledRows([(normalize_row_label(cache.get_label(Cache.SEED)), self._seed_input)]), REQUIRED)
        self._last_seed_label = QLabel()
        self._last_seed_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._last_seed_label.setToolTip(cache.get_tooltip(Cache.LAST_SEED))

        def _last_seed_update(last_seed: str) -> None:
            self._last_seed_label.setText(f'{LABEL_LAST_SEED} {last_seed}')

        cache.connect(self._last_seed_label, Cache.LAST_SEED, _last_seed_update)
        _last_seed_update(cache.get(Cache.LAST_SEED))
        section.add(self._last_seed_label, REQUIRED)
        self._sampler_combobox = option_combo_box(cache, Cache.SAMPLING_METHOD)
        section.add(LabeledRows([(normalize_row_label(cache.get_label(Cache.SAMPLING_METHOD)),
                                  self._sampler_combobox)]), REQUIRED)

        section.widget.bind_summary(self._sampling_summary, self._sampler_combobox.valueChanged,
                                    self._seed_input.valueChanged)

    @staticmethod
    def _sampling_summary() -> str:
        cache = Cache()
        seed = int(cache.get(Cache.SEED))
        if seed != RANDOM_SEED:
            return SUMMARY_SAMPLING_FIXED_SEED.format(seed=seed, sampler=cache.get(Cache.SAMPLING_METHOD))
        return cache.get(Cache.SAMPLING_METHOD)

    def _build_size_section(self, ui: PanelLayout, cache: Cache) -> None:
        section = ui.section(SECTION_TITLE_SIZE, collapsible=True, priority=SIZE_PRIORITY)
        self._size_section = section
        self._gen_resolution_input = cache.get_control_widget(Cache.GENERATION_SIZE)
        # The boxes' width follows their maximum, which is unbounded by default. The maximum image size bounds it, and
        # never below the current value, so no saved value is clamped:
        if isinstance(self._gen_resolution_input, SizeField):
            self._gen_resolution_input.maximum = AppConfig().get(AppConfig.MAX_IMAGE_SIZE).expandedTo(
                self._gen_resolution_input.value())
        # The width and height boxes sit side by side, or stacked when the section is too narrow for that:
        self._gen_resolution_holder = HonestSizeHints(self._gen_resolution_input)
        # Both boxes together are as wide as one field, with each label beside its box:
        self._gen_resolution_holder.setMaximumWidth(FIELD_MAX_WIDTH)
        size_rows = LabeledRows([(normalize_row_label(cache.get_label(Cache.GENERATION_SIZE)),
                                  self._gen_resolution_holder)])
        section.add(size_rows, REQUIRED, (partial(self._set_size_orientation, Qt.Orientation.Horizontal),
                                          partial(self._set_size_orientation, Qt.Orientation.Vertical)))
        self._batch_count_field = config_slider_field(cache, Cache.BATCH_COUNT)
        section.add(self._batch_count_field, REQUIRED)

        section.widget.bind_summary(self._size_summary, self._gen_resolution_input.valueChanged,
                                    self._batch_count_field.valueChanged)
        section.widget.set_expanded(False)

    @staticmethod
    def _size_summary() -> str:
        cache = Cache()
        size = cache.get(Cache.GENERATION_SIZE)
        return SUMMARY_SIZE.format(width=size.width(), height=size.height(), count=cache.get(Cache.BATCH_COUNT))

    def _set_size_orientation(self, orientation: Qt.Orientation) -> None:
        # Strip columns are wide enough for the boxes side by side, and stacking them only takes more height there:
        if self.orientation == Orientation.STRIP:
            orientation = Qt.Orientation.Horizontal
        self._gen_resolution_input.orientation = orientation
        self._gen_resolution_holder.updateGeometry()

    def _build_advanced_section(self, ui: PanelLayout, cache: Cache) -> None:
        section = ui.section(SECTION_TITLE_ADVANCED, collapsible=True, priority=ADVANCED_PRIORITY)
        self._advanced_section = section
        self._advanced_body = QWidget()
        self._advanced_layout = QVBoxLayout(self._advanced_body)
        self._advanced_layout.setContentsMargins(0, 0, 0, 0)
        self._advanced_layout.addWidget(group_label(GROUP_TITLE_INPAINT_AND_SIZE))
        self._masked_content_rows: Optional[LabeledRows] = None
        if self._webui:
            self._masked_content_combobox = option_combo_box(cache, Cache.MASKED_CONTENT)
            self._masked_content_rows = LabeledRows([(normalize_row_label(cache.get_label(Cache.MASKED_CONTENT)),
                                                      self._masked_content_combobox)])
            self._advanced_layout.addWidget(self._masked_content_rows)
        self._resolution_rule_combobox = option_combo_box(cache, Cache.GENERATION_RESOLUTION_RULE)
        self._advanced_layout.addWidget(LabeledRows([(normalize_row_label(
            cache.get_label(Cache.GENERATION_RESOLUTION_RULE)), self._resolution_rule_combobox)]))
        self._advanced_layout.addWidget(group_label(GROUP_TITLE_MODEL))
        self._clip_skip_field = config_slider_field(cache, Cache.CLIP_SKIP)
        self._advanced_layout.addWidget(self._clip_skip_field)
        section.add(self._advanced_body, REQUIRED)
        section.widget.set_expanded(False)

    def _build_action_block(self) -> None:
        """Builds the action block, and pins it as the footer."""
        cache = Cache()
        self._denoising_field = config_slider_field(cache, Cache.DENOISING_STRENGTH)
        self._denoising_field.setFixedHeight(DENOISING_FIELD_HEIGHT)
        self._cfg_scale_field = config_slider_field(cache, Cache.GUIDANCE_SCALE, label=LABEL_CFG_SCALE)
        self._steps_field = config_slider_field(cache, Cache.SAMPLING_STEPS, label=LABEL_STEPS)
        self._sampling_pair = FieldPair(self._cfg_scale_field, self._steps_field)
        self._batch_size_field = config_slider_field(cache, Cache.BATCH_SIZE)
        context_field = config_slider_field(cache, Cache.INPAINT_FULL_RES_PADDING, field_class=ToggledSliderField,
                                            off_text=CONTEXT_OFF)
        assert isinstance(context_field, ToggledSliderField)
        self._context_field = context_field

        def _limit_context_toggled(enabled: bool) -> None:
            if not context_field.toggle_locked() and cache.get(Cache.INPAINT_FULL_RES) != enabled:
                cache.set(Cache.INPAINT_FULL_RES, enabled)

        context_field.pressureLinkToggled.connect(_limit_context_toggled)

        # Tiling shows the context limit as off and locks its toggle, leaving the saved value for when tiling ends:
        def _sync_limit_context_toggle(*_) -> None:
            tiling = cache.tiling_in_effect()
            context_field.set_toggle_locked(tiling)
            context_field.set_pressure_link_tooltip(TOOLTIP_LIMIT_CONTEXT_TILING if tiling
                                                    else cache.get_tooltip(Cache.INPAINT_FULL_RES))
            context_field.set_pressure_link_enabled(cache.limited_context_in_effect())

        for limit_context_key in (Cache.INPAINT_FULL_RES, Cache.WEBUI_TILING, Cache.WEBUI_TILING_AVAILABLE):
            cache.connect(context_field, limit_context_key, _sync_limit_context_toggle)
        _sync_limit_context_toggle()
        self._action_pair = FieldPair(self._batch_size_field, context_field)
        # Batch size sits at the left edge, under CFG scale, while context is hidden:
        for field in (self._batch_size_field, context_field):
            self._action_pair.layout().setAlignment(field, Qt.AlignmentFlag.AlignLeft)
        self.add_fit_item(FitItem(REQUIRED, 2), self._apply_pair_form)

        # The note repeats what the edit mode selector shows, so it hides when the action block has no room for it:
        self._mode_note = QLabel()
        self._mode_note.setWordWrap(True)
        self._note_fits = True
        self.add_fit_item(FitItem(NOTE_PRIORITY), self._apply_note_form)
        # Tiling carries over between sessions, so the action block shows it while it is on:
        self._tiling_button = QPushButton(BUTTON_TEXT_TILING_ON)
        self._tiling_button.setToolTip(BUTTON_TOOLTIP_TILING_ON)
        self._tiling_button.setFlat(True)
        self._tiling_button.clicked.connect(lambda: Cache().set(Cache.WEBUI_TILING, False))
        for tiling_key in (Cache.WEBUI_TILING, Cache.WEBUI_TILING_AVAILABLE):
            cache.connect(self._tiling_button, tiling_key, self._update_tiling_button)
        self._tiling_button.setVisible(self._webui and cache.tiling_in_effect())
        self._generate_button = QPushButton(BUTTON_TEXT_GENERATE)
        # Capped like the fields above it, so its right edge lines up with theirs in a wide side panel:
        self._generate_button.setMaximumWidth(FIELD_MAX_WIDTH)
        self._generate_button.setToolTip(BUTTON_TOOLTIP_GENERATE)
        set_primary_button(self._generate_button)
        self._generate_button.clicked.connect(self.generate_signal)

        self._action_block = QWidget()
        block_layout = QVBoxLayout(self._action_block)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.addWidget(self._denoising_field)
        block_layout.addWidget(self._sampling_pair)
        block_layout.addWidget(self._action_pair)
        # Keeps Generate at the bottom of a strip's trailing column. `arrange` closes it in a side panel, where spare
        # height collects above the footer:
        self._action_spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        block_layout.addItem(self._action_spacer)
        block_layout.addWidget(self._tiling_button)
        block_layout.addWidget(self._mode_note)
        block_layout.addWidget(self._generate_button)
        # The footer holds the action block in a side panel, and hides while a strip shows it in the trailing column:
        self._footer_holder = QWidget()
        footer_layout = QVBoxLayout(self._footer_holder)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.addWidget(self._action_block)
        self.set_footer(self._footer_holder)
        self.set_trailing_scrolls(False)

    def _apply_pair_form(self, form: Optional[int]) -> None:
        for pair in (self._sampling_pair, self._action_pair):
            pair.set_stacked(form == PAIR_FORM_STACKED)

    def _update_tiling_button(self, *_) -> None:
        self._tiling_button.setVisible(self._webui and Cache().tiling_in_effect())
        self.refit()

    def _apply_note_form(self, form: Optional[int]) -> None:
        self._note_fits = form is not None
        self._mode_note.setVisible(self._note_fits and self._mode_note.text() != '')

    # ---------------------------------------------------------------------------------------------------------------
    # Backend-specific content
    # ---------------------------------------------------------------------------------------------------------------

    def set_advanced_content(self, controls: AdvancedControls) -> None:
        """Adds a backend's extra settings to the Advanced section, which summarizes them when it is collapsed.

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

    # ---------------------------------------------------------------------------------------------------------------
    # More menu, banner and edit mode
    # ---------------------------------------------------------------------------------------------------------------

    def _build_more_menu(self) -> None:
        self._more_content = QWidget()
        more_layout = QVBoxLayout(self._more_content)
        more_layout.setContentsMargins(0, 0, 0, 0)
        self._describe_menu_button = self._add_more_button(MENU_TEXT_DESCRIBE, more_layout,
                                                              self.describe_signal)
        self._describe_menu_button.setToolTip(TOOLTIP_DESCRIBE)
        self._describe_menu_button.setVisible(self._webui)
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
        button.clicked.connect(self.header.popover.hide)
        button.clicked.connect(signal)
        layout.addWidget(button)
        return button

    def _refresh_more_menu(self) -> None:
        check = self.lcm_available_check
        self._lcm_menu_button.setVisible(check is not None and check())  # pylint: disable=not-callable

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
        cache.connect(self, Cache.EDIT_MODE, lambda edit_mode, *_: self._update_edit_mode(edit_mode))
        self._update_edit_mode(cache.get(Cache.EDIT_MODE))

    def _update_edit_mode(self, edit_mode: str) -> None:
        """Shows the controls the edit mode uses, marks a mode other than Inpaint, and plans again."""
        inpaint = edit_mode == EDIT_MODE_INPAINT
        self._denoising_field.setVisible(edit_mode in (EDIT_MODE_INPAINT, EDIT_MODE_IMG2IMG))
        self._context_field.setVisible(inpaint)
        if self._masked_content_rows is not None:
            self._masked_content_rows.setVisible(inpaint)
        notes = {EDIT_MODE_IMG2IMG: NOTE_IMG2IMG, EDIT_MODE_TXT2IMG: NOTE_TXT2IMG}
        self._mode_note.setText(notes.get(edit_mode, ''))
        self._mode_note.setVisible(self._note_fits and not inpaint)
        self._apply_caution(not inpaint)
        self.refit()

    def _apply_caution(self, caution: bool) -> None:
        """Draws the edit mode selector and the mode note in the caution color, or restores their usual colors. The
        tiling button always takes the caution color."""
        color = caution_color()
        combo_palette = QPalette()
        note_palette = QPalette()
        tiling_palette = QPalette()
        if color is not None:
            for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.Shadow):
                tiling_palette.setColor(QPalette.ColorGroup.Active, role, color)
                tiling_palette.setColor(QPalette.ColorGroup.Inactive, role, color)
                if caution:
                    combo_palette.setColor(QPalette.ColorGroup.Active, role, color)
                    combo_palette.setColor(QPalette.ColorGroup.Inactive, role, color)
            if caution:
                note_palette.setColor(QPalette.ColorRole.WindowText, color)
        self._edit_mode_combobox.setPalette(combo_palette)
        self._mode_note.setPalette(note_palette)
        self._tiling_button.setPalette(tiling_palette)

    def changeEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """Takes the caution color from the new style when the style changes."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.StyleChange:
            self._apply_caution(Cache().get(Cache.EDIT_MODE) != EDIT_MODE_INPAINT)

    # ---------------------------------------------------------------------------------------------------------------
    # Layout
    # ---------------------------------------------------------------------------------------------------------------

    def arrange(self, orientation: Orientation) -> None:
        """Pins the Prompt section in a column at the left of a strip and the action block in a column at the right,
        with the other sections packed into columns between them. Strip sections shrink to their content's minimum
        within their column widths, instead of taking their content's preferred width as a floor."""
        super().arrange(orientation)
        strip = orientation == Orientation.STRIP
        prompt = self._prompt_section.widget
        outer = self.layout()
        assert isinstance(outer, QVBoxLayout)
        if strip:
            self.pinned_layout.insertWidget(0, self.header)
        else:
            outer.insertWidget(0, self.header)
        if strip:
            # The pinned column sets its own width, so the section drops the strip column limits. It goes under the
            # header and above the spacer, and takes spare height before the spacer does:
            self.pinned_layout.insertWidget(1, prompt, stretch=1)
            prompt.setMinimumWidth(0)
            prompt.setMaximumWidth(QWIDGETSIZE_MAX)
            self.pinned_layout.parentWidget().setMaximumWidth(PROMPT_COLUMN_MAX_WIDTH)
        else:
            self.section_layout.insertWidget(0, prompt)
            self.section_layout.insertWidget(1, self._prompt_divider)
        self._prompt_divider.setVisible(not strip)
        self.set_pinned_visible(strip)
        if strip:
            self.trailing_layout.addWidget(self._action_block)
            self.trailing_layout.parentWidget().setMaximumWidth(ACTION_COLUMN_MAX_WIDTH)
        else:
            self._footer_holder.layout().addWidget(self._action_block)
        self._action_spacer.changeSize(0, 0, QSizePolicy.Policy.Minimum,
                                       QSizePolicy.Policy.Expanding if strip else QSizePolicy.Policy.Fixed)
        self._action_block.layout().invalidate()
        # Reparenting hides a widget:
        self._action_block.show()
        self._footer_holder.setVisible(not strip)
        self.set_trailing_visible(strip)
        for section in self.sections:
            if strip:
                section.widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            self.section_layout.setAlignment(section.widget, Qt.AlignmentFlag.AlignTop if strip
                                             else Qt.AlignmentFlag(0))

    def header_width(self, available: QSize) -> int:
        """Returns the prompt column's widest width in a strip, and the available width in a side panel."""
        if self.orientation == Orientation.STRIP:
            return min(available.width(), PROMPT_COLUMN_MAX_WIDTH)
        return available.width()

    def fit_finished(self, orientation: Orientation) -> None:
        """Caps the Prompt section for its planned contents."""
        super().fit_finished(orientation)
        self._cap_prompt_section()

    def finish_placement(self) -> None:
        """Hides the Mask section outside Inpaint mode."""
        super().finish_placement()
        self._mask_section.widget.setVisible(Cache().get(Cache.EDIT_MODE) == EDIT_MODE_INPAINT)

    # ---------------------------------------------------------------------------------------------------------------
    # Accessors for tests and the generators
    # ---------------------------------------------------------------------------------------------------------------

    @property
    def edit_mode_control(self) -> QComboBox:
        """The edit mode selector."""
        return self._edit_mode_combobox

    @property
    def generate_button(self) -> QPushButton:
        """The Generate button."""
        return self._generate_button

    @property
    def action_block(self) -> QWidget:
        """The widget holding denoising strength, batch size, context and Generate."""
        return self._action_block

    @property
    def action_fields(self) -> list[NumberField]:
        """The action block's number fields: denoising strength, CFG scale, steps, batch size and context."""
        return [self._denoising_field, self._cfg_scale_field, self._steps_field, self._batch_size_field,
                self._context_field]

    @property
    def context_field(self) -> ToggledSliderField:
        """The context field, whose toggle limits inpaint context to the selection or lifts the limit."""
        return self._context_field

    @property
    def model_combobox(self) -> QWidget:
        """The Stable Diffusion model selector."""
        return self._model_combobox

    @property
    def prompt_boxes(self) -> PromptBoxes:
        """The prompt box and the negative prompt fold under it."""
        return self._prompt_boxes

    @property
    def prompt_textbox(self) -> QPlainTextEdit:
        """The prompt box."""
        return self._prompt_textbox

    @property
    def negative_prompt_textbox(self) -> QPlainTextEdit:
        """The negative prompt box."""
        return self._negative_textbox

    @property
    def negative_prompt_fold(self) -> PanelSection:
        """The fold that holds the negative prompt box."""
        return self._negative_fold

    @property
    def tiling_button(self) -> QPushButton:
        """The button above Generate that shows while tiling is on, and turns it off."""
        return self._tiling_button

    @property
    def mode_note(self) -> QLabel:
        """The note above Generate that names an edit mode other than Inpaint."""
        return self._mode_note

    @property
    def banner(self) -> DisabledBanner:
        """The not-connected banner."""
        return self._banner

    @property
    def prompt_tool_buttons(self) -> list[QPushButton]:
        """The Prompt header's buttons, in display order."""
        return [button for button in (self._lora_button, self._styles_button) if button is not None]

    @property
    def more_menu_buttons(self) -> list[QPushButton]:
        """The More menu's buttons, in display order: Describe, setup, settings, LCM mode and Clear GPU memory."""
        return [self._describe_menu_button, self._setup_menu_button, self._settings_menu_button,
                self._lcm_menu_button, self._clear_memory_menu_button]
