"""
A MainWindow implementation providing controls specific to stable-diffusion inpainting.
"""
from typing import Optional

from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QGridLayout, QPushButton, QSizePolicy, QSpinBox, QWidget

from src.config.application_config import AppConfig
from src.image.layer_stack import LayerStack
from src.ui.config_control_setup import connected_textedit, connected_spinbox, connected_combobox
from src.ui.panel.controlnet_panel import ControlnetPanel
from src.ui.widget.big_int_spinbox import BigIntSpinbox
from src.ui.widget.bordered_widget import BorderedWidget
from src.ui.widget.collapsible_box import CollapsibleBox
from src.ui.widget.param_slider import ParamSlider
from src.ui.window.main_window import MainWindow

HEIGHT_BOX_TOOLTIP = 'Resize selection content to this height before inpainting'

WIDTH_BOX_TOOLTIP = 'Resize selection content to this width before inpainting'

EDIT_MODE_INPAINT = 'Inpaint'
CONTROL_BOX_LABEL = 'Image Generation Controls'
INTERROGATE_BUTTON_TEXT = 'Interrogate'
INTERROGATE_BUTTON_TOOLTIP = 'Attempt to generate a prompt that describes the current selection'
GENERATE_BUTTON_TEXT = 'Generate'


class StableDiffusionMainWindow(MainWindow):
    """StableDiffusionMainWindow organizes the main application window for Stable-Diffusion inpainting."""

    OPEN_PANEL_STRETCH = 80

    def __init__(self, layer_stack: LayerStack, controller) -> None:
        """Initializes the window and builds the layout.

        Parameters
        ----------
        layer_stack : LayerStack
            Image layers being edited.
        controller : controller.base_controller.stable_diffusion_controller.StableDiffusionController
            Object managing application behavior.
        """
        super().__init__(layer_stack, controller)
        # Decrease imageLayout stretch to make room for additional controls:
        self.layout().setStretch(0, 180)

    def _build_control_panel(self, controller) -> QWidget:
        """Adds controls for Stable-diffusion inpainting."""
        control_panel = BorderedWidget()
        control_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        control_layout = QVBoxLayout()
        control_panel.setLayout(control_layout)
        config = AppConfig.instance()

        main_control_box = CollapsibleBox(CONTROL_BOX_LABEL, control_panel)
        main_control_box.set_expanded_size_policy(QSizePolicy.Maximum)
        if main_control_box.is_expanded():
            self.layout().setStretch(1, self.layout().stretch(1) + StableDiffusionMainWindow.OPEN_PANEL_STRETCH)

        def on_main_controls_expanded(expanded: bool):
            """When the main controls are showing, adjust the layout and hide redundant sliders."""
            stretch = self.layout().stretch(1) + (StableDiffusionMainWindow.OPEN_PANEL_STRETCH if expanded
                                                  else -StableDiffusionMainWindow.OPEN_PANEL_STRETCH)
            stretch = max(stretch, 10)
            self.layout().setStretch(1, stretch)

        main_control_box.toggled().connect(on_main_controls_expanded)
        main_controls = QHBoxLayout()
        main_control_box.set_content_layout(main_controls)
        control_layout.addWidget(main_control_box, stretch=20)

        # Left side: sliders and other wide inputs:
        wide_options = BorderedWidget()
        main_controls.addWidget(wide_options, stretch=50)
        wide_options_layout = QGridLayout()
        wide_options_layout.setVerticalSpacing(max(2, self.height() // 200))
        wide_options.setLayout(wide_options_layout)
        # Font size will be used to limit the height of the prompt boxes:
        textbox_height = self.font().pixelSize() * 4
        if textbox_height < 0:  # font uses pt, not px
            textbox_height = self.font().pointSize() * 6

        # First line: prompt, batch size, width
        wide_options_layout.setRowStretch(0, 2)
        wide_options_layout.addWidget(QLabel(AppConfig.instance().get_label(AppConfig.PROMPT)), 0, 0)
        prompt_textbox = connected_textedit(control_panel, AppConfig.PROMPT, multi_line=True)
        prompt_textbox.setMaximumHeight(textbox_height)
        wide_options_layout.addWidget(prompt_textbox, 0, 1)
        # batch size:
        wide_options_layout.addWidget(QLabel(AppConfig.instance().get_label(AppConfig.BATCH_SIZE)), 0, 2)
        batch_size_spinbox = connected_spinbox(control_panel, AppConfig.BATCH_SIZE)
        wide_options_layout.addWidget(batch_size_spinbox, 0, 3)
        # width:
        wide_options_layout.addWidget(QLabel('W:'), 0, 4)
        width_spinbox = QSpinBox(self)
        width_spinbox.setRange(1, 4096)
        width_spinbox.setValue(config.get(AppConfig.GENERATION_SIZE).width())
        width_spinbox.setToolTip(WIDTH_BOX_TOOLTIP)

        def set_w(value: int):
            """Adjust edited image generation width when the width box changes."""
            size = config.get(AppConfig.GENERATION_SIZE)
            config.set(AppConfig.GENERATION_SIZE, QSize(value, size.height()))

        width_spinbox.valueChanged.connect(set_w)
        wide_options_layout.addWidget(width_spinbox, 0, 5)

        # Second line: negative prompt, batch count, height:
        wide_options_layout.setRowStretch(1, 2)
        wide_options_layout.addWidget(QLabel(config.get_label(AppConfig.NEGATIVE_PROMPT)), 1, 0)
        negative_prompt_textbox = connected_textedit(control_panel, AppConfig.NEGATIVE_PROMPT, multi_line=True)
        negative_prompt_textbox.setMaximumHeight(textbox_height)
        wide_options_layout.addWidget(negative_prompt_textbox, 1, 1)
        # batch count:
        wide_options_layout.addWidget(QLabel(config.get_label(AppConfig.BATCH_COUNT)), 1, 2)
        batch_count_spinbox = connected_spinbox(control_panel, AppConfig.BATCH_COUNT)
        wide_options_layout.addWidget(batch_count_spinbox, 1, 3)
        # Height:
        wide_options_layout.addWidget(QLabel('H:'), 1, 4)
        height_spinbox = QSpinBox(self)
        height_spinbox.setRange(1, 4096)
        height_spinbox.setValue(config.get(AppConfig.GENERATION_SIZE).height())
        height_spinbox.setToolTip(HEIGHT_BOX_TOOLTIP)

        def set_h(value: int):
            """Adjust edited image generation height when the height box changes."""
            size = config.get(AppConfig.GENERATION_SIZE)
            config.set(AppConfig.GENERATION_SIZE, QSize(size.width(), value))

        height_spinbox.valueChanged.connect(set_h)
        wide_options_layout.addWidget(height_spinbox, 1, 5)

        # Misc. sliders:
        wide_options_layout.setRowStretch(2, 1)
        sample_step_slider = ParamSlider(wide_options, config.get_label(AppConfig.SAMPLING_STEPS),
                                         AppConfig.SAMPLING_STEPS)
        wide_options_layout.addWidget(sample_step_slider, 2, 0, 1, 6)
        wide_options_layout.setRowStretch(3, 1)
        cfg_scale_slider = ParamSlider(wide_options, config.get_label(AppConfig.GUIDANCE_SCALE),
                                       AppConfig.GUIDANCE_SCALE)
        wide_options_layout.addWidget(cfg_scale_slider, 3, 0, 1, 6)
        wide_options_layout.setRowStretch(4, 1)
        denoising_slider = ParamSlider(wide_options, config.get_label(AppConfig.DENOISING_STRENGTH),
                                       AppConfig.DENOISING_STRENGTH)
        wide_options_layout.addWidget(denoising_slider, 4, 0, 1, 6)

        # ControlNet panel, if controlnet is installed:
        if config.get(AppConfig.CONTROLNET_VERSION) > 0:
            controlnet_panel = ControlnetPanel(AppConfig.CONTROLNET_ARGS_0,
                                               config.get(AppConfig.CONTROLNET_CONTROL_TYPES),
                                               config.get(AppConfig.CONTROLNET_MODULES),
                                               config.get(AppConfig.CONTROLNET_MODELS))
            controlnet_panel.set_expanded_size_policy(QSizePolicy.Maximum)
            if controlnet_panel.is_expanded():
                self.layout().setStretch(1, self.layout().stretch(1) + StableDiffusionMainWindow.OPEN_PANEL_STRETCH)

            def on_controlnet_expanded(expanded: bool):
                """Adjust layout stretch values to make room when the ControlNet panel is opened."""
                stretch = self.layout().stretch(1) + (StableDiffusionMainWindow.OPEN_PANEL_STRETCH if expanded
                                                      else -StableDiffusionMainWindow.OPEN_PANEL_STRETCH)
                stretch = max(stretch, 1)
                self.layout().setStretch(1, stretch)

            controlnet_panel.toggled().connect(on_controlnet_expanded)
            control_layout.addWidget(controlnet_panel, stretch=20)

        # Right side: box of dropdown/checkbox options:
        option_list = BorderedWidget()
        main_controls.addWidget(option_list, stretch=10)
        option_list_layout = QVBoxLayout()
        option_list_layout.setSpacing(max(2, self.height() // 200))
        option_list.setLayout(option_list_layout)

        def add_option_line(label_text: str, widget: QWidget, tooltip: Optional[str] = None) -> QHBoxLayout:
            """Handles labels and layout when adding a new line."""
            option_line = QHBoxLayout()
            option_list_layout.addLayout(option_line)
            option_line.addWidget(QLabel(label_text), stretch=1)
            if tooltip is not None:
                widget.setToolTip(tooltip)
            option_line.addWidget(widget, stretch=2)
            return option_line

        def add_combo_box(config_key: str, inpainting_only: bool, tooltip: Optional[str] = None) -> QHBoxLayout:
            """Handles layout, labels, and config connections when adding a new combo box."""
            label_text = config.get_label(config_key)
            combobox = connected_combobox(option_list, config_key)
            if inpainting_only:
                config.connect(combobox, AppConfig.EDIT_MODE,
                               lambda new_mode: combobox.setEnabled(new_mode == 'Inpaint'))
            return add_option_line(label_text, combobox, tooltip)

        add_combo_box(AppConfig.EDIT_MODE, False)
        add_combo_box(AppConfig.MASKED_CONTENT, True)
        add_combo_box(AppConfig.SAMPLING_METHOD, False)
        padding_line_index = len(option_list_layout.children())
        padding_line = QHBoxLayout()
        padding_label = QLabel(config.get_label(AppConfig.INPAINT_FULL_RES_PADDING))
        padding_line.addWidget(padding_label, stretch=1)
        padding_spinbox = connected_spinbox(self, AppConfig.INPAINT_FULL_RES_PADDING)
        padding_spinbox.setMinimum(0)
        padding_line.addWidget(padding_spinbox, stretch=2)
        option_list_layout.insertLayout(padding_line_index, padding_line)

        def padding_layout_update(inpaint_full_res: bool) -> None:
            """Only show the 'full-res padding' spin box if 'inpaint full-res' is checked."""
            padding_label.setVisible(inpaint_full_res)
            padding_spinbox.setVisible(inpaint_full_res)

        padding_layout_update(config.get(AppConfig.INPAINT_FULL_RES))
        config.connect(self, AppConfig.INPAINT_FULL_RES, padding_layout_update)
        config.connect(self, AppConfig.EDIT_MODE, lambda mode: padding_layout_update(mode == EDIT_MODE_INPAINT))

        seed_input = connected_spinbox(option_list, AppConfig.SEED, min_val=-1, max_val=BigIntSpinbox.MAXIMUM,
                                       step_val=1)
        add_option_line(config.get_label(AppConfig.SEED), seed_input, None)

        last_seed_box = connected_textedit(option_list, AppConfig.LAST_SEED)
        last_seed_box.setReadOnly(True)
        add_option_line(config.get_label(AppConfig.LAST_SEED), last_seed_box, None)

        # Put action buttons on the bottom:
        button_bar = BorderedWidget(control_panel)
        button_bar_layout = QHBoxLayout()
        button_bar.setLayout(button_bar_layout)
        button_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        control_layout.addWidget(button_bar, stretch=5)

        # interrogate_button:
        interrogate_button = QPushButton()
        interrogate_button.setText(INTERROGATE_BUTTON_TEXT)
        interrogate_button.setToolTip(INTERROGATE_BUTTON_TOOLTIP)
        interrogate_button.clicked.connect(controller.interrogate)
        button_bar_layout.addWidget(interrogate_button, stretch=1)
        interrogate_button.resize(interrogate_button.width(), interrogate_button.height() * 2)
        # Start generation button:
        start_button = QPushButton()
        start_button.setText(GENERATE_BUTTON_TEXT)
        start_button.clicked.connect(controller.start_and_manage_inpainting)
        button_bar_layout.addWidget(start_button, stretch=2)
        start_button.resize(start_button.width(), start_button.height() * 2)
        return control_panel
