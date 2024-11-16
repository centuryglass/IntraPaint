"""Control panel widget for GLID-3-XL inpainting."""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QPushButton, QLabel, QGridLayout, QSizePolicy, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.ui.panel.generators.generator_panel import GeneratorPanel
from src.ui.widget.rotating_toolbar_button import RotatingToolbarButton
from src.util.application_state import APP_STATE_EDITING, AppStateTracker
from src.util.layout import clear_layout
from src.util.shared_constants import BUTTON_TEXT_GENERATE, BUTTON_TOOLTIP_GENERATE

INPAINT_BUTTON_TEXT = 'Start inpainting'


class GlidPanel(GeneratorPanel):
    """Control panel widget for GLID-3-XL inpainting."""

    generate_signal = Signal()

    def __init__(self):
        super().__init__()
        cache = Cache()
        config = AppConfig()
        self._orientation = Qt.Orientation.Horizontal
        self._layout = QGridLayout(self)
        self._layout.setSpacing(3)
        self._layout.setContentsMargins(3, 10, 3, 10)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        AppStateTracker.set_enabled_states(self, [APP_STATE_EDITING])

        self._text_prompt_label = QLabel(cache.get_label(Cache.PROMPT), self)
        self._text_prompt_textbox = cache.get_control_widget(Cache.PROMPT, multi_line=False)
        self._negative_prompt_label = QLabel(cache.get_label(Cache.NEGATIVE_PROMPT), self)
        self._negative_prompt_textbox = cache.get_control_widget(Cache.NEGATIVE_PROMPT, multi_line=False)
        # Font size will be used to limit the height of the prompt boxes:
        line_height = self.font().pixelSize()
        if line_height < 0:  # font uses pt, not px
            line_height = round(self.font().pointSize() * 1.5)
        textbox_height = line_height * 4
        for textbox in (self._text_prompt_textbox, self._negative_prompt_textbox):
            textbox.setMaximumHeight(textbox_height)

        self._batch_size_spinbox = cache.get_control_widget(Cache.BATCH_SIZE)
        self._batch_size_spinbox.setText(cache.get_label(Cache.BATCH_SIZE))
        self._batch_count_spinbox = cache.get_control_widget(Cache.BATCH_COUNT)
        self._batch_count_spinbox.setText(cache.get_label(Cache.BATCH_COUNT))
        self._guidance_scale_spinbox = cache.get_control_widget(Cache.GUIDANCE_SCALE)
        self._guidance_scale_spinbox.setText(cache.get_label(Cache.GUIDANCE_SCALE))
        self._skip_steps_spinbox = cache.get_control_widget(Cache.SKIP_STEPS)
        self._skip_steps_spinbox.setText(cache.get_label(Cache.SKIP_STEPS))
        self._cutn_spinbox = cache.get_control_widget(Cache.CUTN)
        self._cutn_spinbox.setText(cache.get_label(Cache.CUTN))

        self._enable_scale_checkbox = cache.get_control_widget(Cache.INPAINT_FULL_RES)
        self._enable_scale_checkbox.setText(cache.get_label(Cache.INPAINT_FULL_RES))
        self._upscale_mode_label = QLabel(config.get_label(AppConfig.PIL_UPSCALE_MODE), self)
        self._upscale_mode_list = config.get_control_widget(AppConfig.PIL_UPSCALE_MODE)
        self._downscale_mode_label = QLabel(config.get_label(AppConfig.PIL_DOWNSCALE_MODE), self)
        self._downscale_mode_list = config.get_control_widget(AppConfig.PIL_DOWNSCALE_MODE)

        self._inpaint_button = QPushButton()
        self._inpaint_button.setText(INPAINT_BUTTON_TEXT)
        self._inpaint_button.clicked.connect(self.generate_signal)

        self._toolbar_generate_button = RotatingToolbarButton(BUTTON_TEXT_GENERATE)
        self._toolbar_generate_button.setToolTip(BUTTON_TOOLTIP_GENERATE)
        self._toolbar_generate_button.clicked.connect(self.generate_signal)
        self._toolbar_generate_button.hide()
        self._build_layout()

    def _build_layout(self) -> None:
        layout = self._layout
        for column in range(layout.columnCount()):
            layout.setColumnStretch(column, 0)
        for row in range(layout.rowCount()):
            layout.setRowStretch(row, 0)
        clear_layout(layout)
        if self._orientation == Qt.Orientation.Horizontal:
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self._text_prompt_label, 1, 0, 1, 1)
            layout.addWidget(self._text_prompt_textbox, 1, 1, 2, 1)
            layout.addWidget(self._negative_prompt_label, 3, 0, 1, 1)
            layout.addWidget(self._negative_prompt_textbox, 3, 1, 2, 1)
            layout.addWidget(self._guidance_scale_spinbox, 5, 0, 1, 2)
            layout.addWidget(self._skip_steps_spinbox, 6, 0, 1, 2)
            layout.addWidget(self._cutn_spinbox, 7, 0, 1, 2)

            layout.addWidget(self._batch_size_spinbox, 1, 2, 1, 2)
            layout.addWidget(self._batch_count_spinbox, 2, 2, 1, 2)
            layout.addWidget(self._enable_scale_checkbox, 3, 2, 1, 2)
            layout.addWidget(self._upscale_mode_label, 4, 2)
            layout.addWidget(self._upscale_mode_list, 4, 3)
            layout.addWidget(self._downscale_mode_label, 6, 2)
            layout.addWidget(self._downscale_mode_list, 6, 3)
            layout.addWidget(self._inpaint_button, 7, 2, 1, 2)
        else:  # Vertical
            layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(self._text_prompt_label, 1, 0)
            layout.addWidget(self._text_prompt_textbox, 2, 0, 2, 2)
            # layout.setRowStretch(2, 50)
            layout.addWidget(self._negative_prompt_label, 4, 0)
            layout.addWidget(self._negative_prompt_textbox, 5, 0, 2, 2)
            # layout.setRowStretch(5, 50)
            layout.addWidget(self._guidance_scale_spinbox, 7, 0, 1, 2)
            layout.addWidget(self._skip_steps_spinbox, 8, 0, 1, 2)
            layout.addWidget(self._cutn_spinbox, 9, 0, 1, 2)

            # layout.setRowStretch(10, 80)
            layout.addWidget(self._enable_scale_checkbox, 11, 0, 1, 2)
            layout.addWidget(self._upscale_mode_label, 12, 0)
            layout.addWidget(self._upscale_mode_list, 12, 1)
            layout.addWidget(self._downscale_mode_label, 13, 0)
            layout.addWidget(self._downscale_mode_list, 13, 1)
            # layout.setRowStretch(14, 20)
            layout.addWidget(self._batch_size_spinbox, 15, 0, 1, 2)
            layout.addWidget(self._batch_count_spinbox, 16, 0, 1, 2)
            layout.addWidget(self._inpaint_button, 17, 0, 3, 2)

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

    def get_tab_bar_widgets(self) -> list[QWidget]:
        """Returns the toolbar generate button as the only toolbar widget."""
        return [self._toolbar_generate_button]
