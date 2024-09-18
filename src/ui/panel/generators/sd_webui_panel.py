"""A control panel for the Stable-Diffusion WebUI image generator."""
from typing import Tuple, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSizePolicy, QGridLayout, QLabel, QPushButton, \
    QApplication, QWidget

from src.config.cache import Cache
from src.ui.input_fields.size_field import SizeField
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox
from src.ui.layout.divider import Divider
from src.ui.panel.generators.generator_panel import GeneratorPanel
from src.util.application_state import APP_STATE_EDITING, AppStateTracker
from src.util.parameter import DynamicFieldWidget
from src.util.shared_constants import BUTTON_TEXT_GENERATE, EDIT_MODE_INPAINT, EDIT_MODE_TXT2IMG

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.generators.sd_webui_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


INTERROGATE_BUTTON_TEXT = _tr('Interrogate')
INTERROGATE_BUTTON_TOOLTIP = _tr('Attempt to generate a prompt that describes the current image generation area')


class SDWebUIPanel(GeneratorPanel):
    """A control panel for the Stable-Diffusion WebUI image generator."""

    interrogate_signal = Signal()
    generate_signal = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        cache = Cache()
        AppStateTracker.set_enabled_states(self, [APP_STATE_EDITING])

        self._layout = QGridLayout(self)
        self._orientation = Qt.Orientation.Horizontal

        def _get_control_with_label(config_key: str, **kwargs) -> Tuple[QLabel, DynamicFieldWidget]:
            label = QLabel(cache.get_label(config_key))
            label.setWordWrap(True)
            control = cache.get_control_widget(config_key, **kwargs)
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
        self._full_res_label, self._full_res_checkbox = _get_control_with_label(Cache.INPAINT_FULL_RES)
        self._full_res_checkbox.setText('')
        self._padding_label, self._padding_slider = _get_control_with_label(Cache.INPAINT_FULL_RES_PADDING)
        self._seed_label, self._seed_textbox = _get_control_with_label(Cache.SEED)
        self._last_seed_label = QLabel(Cache().get_label(Cache.LAST_SEED))
        self._last_seed_textbox = Cache().get_control_widget(Cache.LAST_SEED)
        self._last_seed_textbox.setReadOnly(True)

        self._interrogate_button = QPushButton()
        self._interrogate_button.setText(INTERROGATE_BUTTON_TEXT)
        self._interrogate_button.setToolTip(INTERROGATE_BUTTON_TOOLTIP)
        self._interrogate_button.clicked.connect(self.interrogate_signal)
        self._generate_button = QPushButton()
        self._generate_button.setText(BUTTON_TEXT_GENERATE)
        self._generate_button.clicked.connect(self.generate_signal)

        def _edit_mode_control_update(edit_mode: str) -> None:
            self._denoising_strength_label.setEnabled(edit_mode != EDIT_MODE_TXT2IMG)
            self._denoising_strength_slider.setEnabled(edit_mode != EDIT_MODE_TXT2IMG)
            self._full_res_label.setEnabled(edit_mode == EDIT_MODE_INPAINT)
            self._full_res_checkbox.setEnabled(edit_mode == EDIT_MODE_INPAINT)
            self._padding_label.setEnabled(edit_mode == EDIT_MODE_INPAINT)
            self._padding_slider.setEnabled(edit_mode == EDIT_MODE_INPAINT)
        _edit_mode_control_update(cache.get(Cache.EDIT_MODE))
        cache.connect(self, Cache.EDIT_MODE, _edit_mode_control_update)

        def padding_layout_update(inpaint_full_res: bool) -> None:
            """Only show the 'full-res padding' spin box if 'inpaint full-res' is checked."""
            self._padding_label.setVisible(inpaint_full_res)
            self._padding_slider.setVisible(inpaint_full_res)
        cache.connect(self, Cache.INPAINT_FULL_RES, padding_layout_update)
        padding_layout_update(cache.get(Cache.INPAINT_FULL_RES))
        self._build_layout()

    def _build_layout(self) -> None:
        grid = self._layout
        for column in range(grid.columnCount()):
            grid.setColumnStretch(column, 0)
        for row in range(grid.rowCount()):
            grid.setRowStretch(row, 0)
        while grid.count() > 0:
            item = grid.takeAt(0)
            assert item is not None
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        # Horizontal setup:
        if self._orientation == Qt.Orientation.Horizontal:
            grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label_columns = (0, 3, 6)
            for col in label_columns:
                grid.setColumnStretch(col, 1)
            grid.setColumnStretch(1, 10)
            grid.setColumnStretch(4, 2)
            grid.setColumnStretch(7, 2)

            # prompt column:
            grid.setColumnStretch(1, 6)
            prompt_labels = (self._prompt_label, self._negative_label)
            prompt_controls = (self._prompt_textbox, self._negative_textbox)
            for row, label, control in zip(range(len(prompt_labels)), prompt_labels, prompt_controls):
                grid.addWidget(label, row, 0)
                grid.addWidget(control, row, 1, 1, 4)

            # sliders:
            slider_labels = (self._step_count_label, self._guidance_scale_label, self._denoising_strength_label)
            slider_controls = (self._step_count_slider, self._guidance_scale_slider, self._denoising_strength_slider)
            for row, label, control in zip(range(len(slider_labels)), slider_labels, slider_controls):
                grid.addWidget(label, row + len(prompt_controls), 0)
                grid.addWidget(control, row + len(prompt_controls), 1)
                control.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)

            slider_divider = Divider(Qt.Orientation.Vertical)
            grid.addWidget(slider_divider, len(prompt_controls), 2, len(slider_controls), 1)
            grid.setColumnStretch(2, 1)

            # second column:
            assert isinstance(self._gen_size_input, SizeField)
            self._gen_size_input.orientation = Qt.Orientation.Vertical
            second_column_labels = (self._gen_size_label, self._batch_size_label, self._batch_count_label)
            second_column_controls = (self._gen_size_input, self._batch_size_spinbox, self._batch_count_spinbox)
            second_column_heights = (2, 1, 1)
            grid.setColumnStretch(len(prompt_controls), 3)

            second_column_row = len(prompt_controls)
            for height, label, control in zip(second_column_heights, second_column_labels, second_column_controls):
                grid.addWidget(label, second_column_row, 3, height, 1)
                grid.addWidget(control, second_column_row, 4, height, 1)
                second_column_row += height

            second_col_divider = Divider(Qt.Orientation.Vertical)
            grid.addWidget(second_col_divider, 0, 5, 5, 1)

            # third column:
            third_column_labels = (self._edit_mode_label,
                                   self._sampler_label,
                                   self._full_res_label,
                                   self._padding_label,
                                   self._seed_label,
                                   self._last_seed_label)
            third_column_controls = (self._edit_mode_combobox,
                                     self._sampler_combobox,
                                     self._full_res_checkbox,
                                     self._padding_slider,
                                     self._seed_textbox,
                                     self._last_seed_textbox)
            for row, label, control in zip(range(len(third_column_labels)), third_column_labels, third_column_controls):
                grid.addWidget(label, row, 6)
                grid.addWidget(control, row, 7)

            button_divider = Divider(Qt.Orientation.Horizontal)
            grid.setRowStretch(6, 0)
            grid.setRowStretch(7, 1)
            grid.addWidget(button_divider, 6, 1, 1, 7)
            grid.addWidget(self._interrogate_button, 7, 0, 1, 3)
            grid.addWidget(self._generate_button, 7, 3, 1, 5)

        # Vertical setup:
        else:
            grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignVCenter)
            assert isinstance(self._gen_size_input, SizeField)
            self._gen_size_input.orientation = Qt.Orientation.Horizontal
            vertical_labels: List[QWidget | Tuple[QWidget, QWidget]] = [
                self._edit_mode_label,
                self._prompt_label,
                self._negative_label,
                self._gen_size_label,
                (self._batch_size_label, self._batch_count_label),
                self._step_count_label,
                self._guidance_scale_label,
                self._denoising_strength_label,
                (self._full_res_label, self._padding_label),
                self._sampler_label,
                (self._seed_label, self._last_seed_label)
            ]
            vertical_controls: List[QWidget | Tuple[QWidget, QWidget]] = [
                self._edit_mode_combobox,
                self._prompt_textbox,
                self._negative_textbox,
                self._gen_size_input,
                (self._batch_size_spinbox, self._batch_count_spinbox),
                self._step_count_slider,
                self._guidance_scale_slider,
                self._denoising_strength_slider,
                (self._full_res_checkbox, self._padding_slider),
                self._sampler_combobox,
                (self._seed_textbox, self._last_seed_textbox)
            ]
            for i in range(10):
                grid.setColumnStretch(i, 1)
            for row, vertical_label, vertical_control in zip(range(len(vertical_labels)), vertical_labels,
                                                             vertical_controls):
                # grid.setRowStretch(row, 1)
                if isinstance(vertical_label, tuple) and isinstance(vertical_control, tuple):
                    label1, label2 = vertical_label
                    control1, control2 = vertical_control
                    grid.addWidget(label1, row, 0, 1, 2)
                    grid.addWidget(control1, row, 2, 1, 3)
                    grid.addWidget(label2, row, 5, 1, 2)
                    grid.addWidget(control2, row, 7, 1, 3)
                else:
                    assert isinstance(vertical_label, QWidget)
                    assert isinstance(vertical_control, QWidget)
                    grid.addWidget(vertical_label, row, 0, 1, 2)
                    grid.addWidget(vertical_control, row, 2, 1, 8)
            # increase stretch for textbox rows:
            # for i in range(2):
                # grid.setRowStretch(i, 3)
            grid.setRowStretch(len(vertical_labels), 1)
            grid.addWidget(self._interrogate_button, len(vertical_labels), 0, 1, 2)
            grid.addWidget(self._generate_button, len(vertical_labels), 2, 1, 8)

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
