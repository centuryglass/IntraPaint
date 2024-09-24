"""A control panel for the Stable-Diffusion WebUI image generator."""
from typing import Tuple, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSizePolicy, QLabel, QPushButton, \
    QApplication, QWidget, QVBoxLayout, QHBoxLayout

from src.config.cache import Cache
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox
from src.ui.layout.divider import Divider
from src.ui.panel.generators.generator_panel import GeneratorPanel
from src.ui.widget.rotating_toolbar_button import RotatingToolbarButton
from src.util.application_state import APP_STATE_EDITING, AppStateTracker
from src.util.layout import clear_layout, synchronize_widths
from src.util.parameter import DynamicFieldWidget
from src.util.shared_constants import BUTTON_TEXT_GENERATE, EDIT_MODE_INPAINT, EDIT_MODE_TXT2IMG, \
    BUTTON_TOOLTIP_GENERATE

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.generators.sd_webui_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


BUTTON_TEXT_INTERROGATE = _tr('Interrogate')
BUTTON_TOOLTIP_INTERROGATE = _tr('Attempt to generate a prompt that describes the current image generation area')


class SDWebUIPanel(GeneratorPanel):
    """A control panel for the Stable-Diffusion WebUI image generator."""

    interrogate_signal = Signal()
    generate_signal = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        cache = Cache()
        AppStateTracker.set_enabled_states(self, [APP_STATE_EDITING])

        self._layout: QVBoxLayout = QVBoxLayout(self)
        self._layout.setSpacing(2)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._orientation = Qt.Orientation.Horizontal

        def _get_control_with_label(config_key: str, **kwargs) -> Tuple[QLabel, DynamicFieldWidget]:
            label = QLabel(cache.get_label(config_key), parent=self)
            label.setWordWrap(True)
            control = cache.get_control_widget(config_key, **kwargs)
            control.setParent(self)
            label.setBuddy(control)
            return label, control

        self._prompt_label, self._prompt_textbox = _get_control_with_label(Cache.PROMPT, multi_line=True)
        self._negative_label, self._negative_textbox = _get_control_with_label(Cache.NEGATIVE_PROMPT,
                                                                               multi_line=True)
        # Font size will be used to limit the height of the prompt boxes:
        line_height = self.font().pixelSize()
        if line_height < 0:  # font uses pt, not px
            line_height = round(self.font().pointSize() * 1.5)
        textbox_height = line_height * 5
        for textbox in (self._prompt_textbox, self._negative_textbox):
            textbox.setMaximumHeight(textbox_height)

        self._gen_size_label, self._gen_size_input = _get_control_with_label(Cache.GENERATION_SIZE)
        self._batch_size_label, self._batch_size_spinbox = _get_control_with_label(Cache.BATCH_SIZE)
        self._batch_count_label, self._batch_count_spinbox = _get_control_with_label(Cache.BATCH_COUNT)
        self._step_count_label, self._step_count_slider = _get_control_with_label(Cache.SAMPLING_STEPS)
        self._guidance_scale_label, self._guidance_scale_slider = _get_control_with_label(Cache.GUIDANCE_SCALE)
        self._denoising_strength_label, self._denoising_strength_slider = _get_control_with_label(
            Cache.DENOISING_STRENGTH)
        IntSliderSpinbox.align_slider_spinboxes([self._step_count_slider, self._guidance_scale_slider,
                                                 self._denoising_strength_slider])
        self._edit_mode_label, self._edit_mode_combobox = _get_control_with_label(Cache.EDIT_MODE)
        self._sampler_label, self._sampler_combobox = _get_control_with_label(Cache.SAMPLING_METHOD)
        self._masked_content_label, self._masked_content_combobox = _get_control_with_label(Cache.MASKED_CONTENT)
        self._full_res_label, self._full_res_checkbox = _get_control_with_label(Cache.INPAINT_FULL_RES)
        self._full_res_checkbox.setText('')
        self._padding_label, self._padding_slider = _get_control_with_label(Cache.INPAINT_FULL_RES_PADDING)
        self._seed_label, self._seed_textbox = _get_control_with_label(Cache.SEED)
        self._last_seed_label = QLabel(Cache().get_label(Cache.LAST_SEED))
        self._last_seed_textbox = Cache().get_control_widget(Cache.LAST_SEED)
        self._last_seed_textbox.setReadOnly(True)

        self._interrogate_button = QPushButton()
        self._interrogate_button.setText(BUTTON_TEXT_INTERROGATE)
        self._interrogate_button.setToolTip(BUTTON_TOOLTIP_INTERROGATE)
        self._interrogate_button.clicked.connect(self.interrogate_signal)
        self._generate_button = QPushButton()
        self._generate_button.setText(BUTTON_TEXT_GENERATE)
        self._generate_button.setToolTip(BUTTON_TOOLTIP_GENERATE)
        self._generate_button.clicked.connect(self.generate_signal)

        self._toolbar_generate_button = RotatingToolbarButton(BUTTON_TEXT_GENERATE)
        self._toolbar_generate_button.setToolTip(BUTTON_TOOLTIP_GENERATE)
        self._toolbar_generate_button.clicked.connect(self.generate_signal)
        self._toolbar_generate_button.hide()

        def _edit_mode_control_update(edit_mode: str) -> None:
            self._denoising_strength_label.setVisible(edit_mode != EDIT_MODE_TXT2IMG)
            self._denoising_strength_slider.setVisible(edit_mode != EDIT_MODE_TXT2IMG)
            self._full_res_label.setVisible(edit_mode == EDIT_MODE_INPAINT)
            self._full_res_checkbox.setVisible(edit_mode == EDIT_MODE_INPAINT)
            self._padding_label.setVisible(edit_mode == EDIT_MODE_INPAINT)
            self._padding_slider.setVisible(edit_mode == EDIT_MODE_INPAINT)
            self._masked_content_label.setVisible(edit_mode == EDIT_MODE_INPAINT)
            self._masked_content_combobox.setVisible(edit_mode == EDIT_MODE_INPAINT)

        _edit_mode_control_update(cache.get(Cache.EDIT_MODE))
        cache.connect(self, Cache.EDIT_MODE, _edit_mode_control_update)

        def padding_layout_update(inpaint_full_res: bool) -> None:
            """Only show the 'full-res padding' spin box if 'inpaint full-res' is checked."""
            self._padding_label.setVisible(inpaint_full_res)
            self._padding_slider.setVisible(inpaint_full_res)

        cache.connect(self, Cache.INPAINT_FULL_RES, padding_layout_update)
        padding_layout_update(cache.get(Cache.INPAINT_FULL_RES))
        self._build_layout()

    def get_tab_bar_widgets(self) -> List[QWidget]:
        """Returns the toolbar generate button as the only toolbar widget."""
        return [self._toolbar_generate_button]

    def _build_layout(self) -> None:
        clear_layout(self._layout)

        all_inner_layouts = []
        aligned_sliders = [self._step_count_slider, self._guidance_scale_slider, self._denoising_strength_slider]

        if self._orientation == Qt.Orientation.Horizontal:
            primary_layout = QHBoxLayout()
            button_layout = QHBoxLayout()
            self._layout.addLayout(primary_layout)
            self._layout.addWidget(Divider(Qt.Orientation.Horizontal))
            self._layout.addLayout(button_layout)
            left_panel_layout = QVBoxLayout()
            right_panel_layout = QVBoxLayout()
            primary_layout.addLayout(left_panel_layout, stretch=30)
            primary_layout.addWidget(Divider(Qt.Orientation.Vertical))
            primary_layout.addLayout(right_panel_layout, stretch=10)
            right_panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self._gen_size_input.orientation = Qt.Orientation.Horizontal

            # Alignment lists:
            left_labels: List[QWidget] = []
            center_labels: List[QWidget] = []
            right_labels: List[QWidget] = []
            right_inputs: List[QWidget] = []
            all_inner_layouts += [primary_layout, button_layout, left_panel_layout, right_panel_layout]

            for label, textbox in ((self._prompt_label, self._prompt_textbox),
                                   (self._negative_label, self._negative_textbox)):
                text_row = QHBoxLayout()
                text_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
                text_row.addWidget(label)
                text_row.addWidget(textbox)
                left_panel_layout.addLayout(text_row)
                left_labels.append(label)
                all_inner_layouts.append(text_row)

            lower_left_panel = QHBoxLayout()
            slider_layout = QVBoxLayout()
            size_count_layout = QVBoxLayout()
            left_panel_layout.addLayout(lower_left_panel)
            lower_left_panel.addLayout(slider_layout, stretch=30)
            lower_left_panel.addWidget(Divider(Qt.Orientation.Vertical))
            lower_left_panel.addLayout(size_count_layout, stretch=10)
            all_inner_layouts += [lower_left_panel, slider_layout, size_count_layout]

            for label, slider in ((self._step_count_label, self._step_count_slider),
                                  (self._guidance_scale_label, self._guidance_scale_slider),
                                  (self._denoising_strength_label, self._denoising_strength_slider)):
                slider_row = QHBoxLayout()
                slider_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
                slider_row.addWidget(label)
                slider_row.addWidget(slider)
                slider_layout.addLayout(slider_row)
                all_inner_layouts.append(slider_row)
                left_labels.append(label)

            for label, input_widget in ((self._gen_size_label, self._gen_size_input),
                                        (self._batch_size_label, self._batch_size_spinbox),
                                        (self._batch_count_label, self._batch_count_spinbox)):
                input_row = QHBoxLayout()
                input_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
                input_row.addWidget(label)
                input_row.addWidget(input_widget)
                size_count_layout.addLayout(input_row)
                all_inner_layouts.append(input_row)
                center_labels.append(label)

            for label, input_widget in ((self._edit_mode_label, self._edit_mode_combobox),
                                        (self._sampler_label, self._sampler_combobox),
                                        (self._masked_content_label, self._masked_content_combobox),
                                        (self._full_res_label, self._full_res_checkbox),
                                        (self._padding_label, self._padding_slider),
                                        (self._seed_label, self._seed_textbox),
                                        (self._last_seed_label, self._last_seed_textbox)):
                input_row = QHBoxLayout()
                input_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
                input_row.addWidget(label, stretch=1)
                input_row.addWidget(input_widget, stretch=2)
                right_panel_layout.addLayout(input_row)
                all_inner_layouts.append(input_row)
                if label == self._full_res_label:
                    input_row.setStretch(1, 0)
                else:
                    right_labels.append(label)
                    right_inputs.append(input_widget)

            for i in (0, 1, 4, 5):
                right_panel_layout.setStretch(i, 1)
            right_panel_layout.insertSpacing(right_panel_layout.count() - 4, 20)
            right_panel_layout.insertSpacing(right_panel_layout.count() - 2, 20)

            button_layout.addWidget(self._interrogate_button)
            button_layout.addWidget(self._generate_button)

            for alignment_group in (left_labels, center_labels, right_labels, right_inputs):
                synchronize_widths(alignment_group)
            self._batch_size_spinbox.align_slider_spinboxes([self._batch_size_spinbox, self._batch_count_spinbox])
        else:
            assert self._orientation == Qt.Orientation.Vertical
            self._gen_size_input.orientation = Qt.Orientation.Vertical

            # Alignment groups:
            labels = []
            inputs = []
            for label, input_widget in ((self._edit_mode_label, self._edit_mode_combobox),
                                        (self._sampler_label, self._sampler_combobox),
                                        (self._masked_content_label, self._masked_content_combobox),
                                        (self._prompt_label, self._prompt_textbox),
                                        (self._negative_label, self._negative_textbox),
                                        (self._gen_size_label, self._gen_size_input),
                                        (self._batch_size_label, self._batch_size_spinbox),
                                        (self._batch_count_label, self._batch_count_spinbox),
                                        (self._step_count_label, self._step_count_slider),
                                        (self._guidance_scale_label, self._guidance_scale_slider),
                                        (self._denoising_strength_label, self._denoising_strength_slider),
                                        (self._full_res_label, self._full_res_checkbox),
                                        (self._padding_label, self._padding_slider),
                                        (self._seed_label, self._seed_textbox),
                                        (self._last_seed_label, self._last_seed_textbox),
                                        (self._interrogate_button, self._generate_button)):
                row_layout = QHBoxLayout()
                row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                row_layout.addWidget(label, stretch=1)
                row_layout.addWidget(input_widget, stretch=5)
                labels.append(label)
                inputs.append(input_widget)
                all_inner_layouts.append(row_layout)
                self._layout.addLayout(row_layout, stretch=1)
            aligned_sliders += [self._batch_size_spinbox, self._batch_count_spinbox]
            self._layout.insertStretch(self._layout.count() - 3, 3)
            self._layout.insertWidget(self._layout.count() - 1, Divider(Qt.Orientation.Horizontal))
            synchronize_widths(labels)
            synchronize_widths(inputs)
        for layout in all_inner_layouts:
            layout.setSpacing(2)
            layout.setContentsMargins(1, 1, 1, 1)
        self._step_count_slider.align_slider_spinboxes(aligned_sliders)

    def set_orientation(self, new_orientation: Qt.Orientation) -> None:
        """Sets panel orientation."""
        if new_orientation == self._orientation:
            return
        self._orientation = new_orientation
        self._build_layout()

    @property
    def orientation(self) -> Qt.Orientation:
        """Access panel orientation."""
        return self._orientation

    @orientation.setter
    def orientation(self, new_orientation: Qt.Orientation) -> None:
        self.set_orientation(new_orientation)
