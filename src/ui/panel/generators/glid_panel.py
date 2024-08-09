"""Control panel widget for GLID-3-XL inpainting."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QHBoxLayout, QLabel, QGridLayout

from src.config.application_config import AppConfig
from src.ui.layout.bordered_widget import BorderedWidget

INPAINT_BUTTON_TEXT = 'Start inpainting'


class GlidPanel(BorderedWidget):
    """Control panel widget for GLID-3-XL inpainting."""

    generate_signal = Signal()

    def __init__(self):
        super().__init__()
        config = AppConfig()
        text_prompt_textbox = config.get_control_widget(AppConfig.PROMPT, multi_line=False)
        negative_prompt_textbox = config.get_control_widget(AppConfig.NEGATIVE_PROMPT, multi_line=False)

        batch_size_spinbox = config.get_control_widget(AppConfig.BATCH_SIZE)

        batch_count_spinbox = config.get_control_widget(AppConfig.BATCH_COUNT)

        inpaint_button = QPushButton()
        inpaint_button.setText(INPAINT_BUTTON_TEXT)
        inpaint_button.clicked.connect(self.generate_signal)

        more_options_bar = QHBoxLayout()
        guidance_scale_spinbox = config.get_control_widget(AppConfig.GUIDANCE_SCALE)

        skip_steps_spinbox = config.get_control_widget(AppConfig.SKIP_STEPS)

        enable_scale_checkbox = config.get_control_widget(AppConfig.INPAINT_FULL_RES)
        enable_scale_checkbox.setText(config.get_label(AppConfig.INPAINT_FULL_RES))

        upscale_mode_label = QLabel(config.get_label(AppConfig.UPSCALE_MODE), self)
        upscale_mode_list = config.get_control_widget(AppConfig.UPSCALE_MODE)
        downscale_mode_label = QLabel(config.get_label(AppConfig.DOWNSCALE_MODE), self)
        downscale_mode_list = config.get_control_widget(AppConfig.DOWNSCALE_MODE)

        more_options_bar.addWidget(QLabel(config.get_label(AppConfig.GUIDANCE_SCALE), self), stretch=0)
        more_options_bar.addWidget(guidance_scale_spinbox, stretch=20)
        more_options_bar.addWidget(QLabel(config.get_label(AppConfig.SKIP_STEPS), self), stretch=0)
        more_options_bar.addWidget(skip_steps_spinbox, stretch=20)
        more_options_bar.addWidget(enable_scale_checkbox, stretch=10)
        more_options_bar.addWidget(upscale_mode_label, stretch=0)
        more_options_bar.addWidget(upscale_mode_list, stretch=10)
        more_options_bar.addWidget(downscale_mode_label, stretch=0)
        more_options_bar.addWidget(downscale_mode_list, stretch=10)

        # Build layout with labels:
        layout = QGridLayout()
        layout.addWidget(QLabel(config.get_label(AppConfig.PROMPT), self), 1, 1, 1, 1)
        layout.addWidget(text_prompt_textbox, 1, 2, 1, 1)
        layout.addWidget(QLabel(config.get_label(AppConfig.NEGATIVE_PROMPT), self), 2, 1, 1, 1)
        layout.addWidget(negative_prompt_textbox, 2, 2, 1, 1)
        layout.addWidget(QLabel(config.get_label(AppConfig.BATCH_SIZE), self), 1, 3, 1, 1)
        layout.addWidget(batch_size_spinbox, 1, 4, 1, 1)
        layout.addWidget(QLabel(config.get_label(AppConfig.BATCH_COUNT), self), 2, 3, 1, 1)
        layout.addWidget(batch_count_spinbox, 2, 4, 1, 1)
        layout.addWidget(inpaint_button, 2, 5, 1, 1)
        layout.setColumnStretch(2, 255)  # Maximize prompt input

        layout.addLayout(more_options_bar, 3, 1, 1, 4)
        self.setLayout(layout)
