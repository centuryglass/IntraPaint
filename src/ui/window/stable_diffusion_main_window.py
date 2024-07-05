"""
A MainWindow implementation providing controls specific to stable-diffusion inpainting.
"""
from typing import Optional, cast

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QGridLayout, QPushButton, QSizePolicy, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.image.layers.image_stack import ImageStack
from src.ui.panel.controlnet_panel import ControlnetPanel
from src.ui.widget.bordered_widget import BorderedWidget
from src.ui.widget.collapsible_box import CollapsibleBox
from src.ui.window.main_window import MainWindow
from src.util.shared_constants import GENERATE_BUTTON_TEXT, EDIT_MODE_INPAINT

CONTROL_BOX_LABEL = 'Image Generation Controls'
INTERROGATE_BUTTON_TEXT = 'Interrogate'
INTERROGATE_BUTTON_TOOLTIP = 'Attempt to generate a prompt that describes the current image generation area'
WIDTH_BOX_TOOLTIP = 'Resize image generation area content to this width before inpainting'
HEIGHT_BOX_TOOLTIP = 'Resize image generation area content to this height before inpainting'


class StableDiffusionMainWindow(MainWindow):
    """StableDiffusionMainWindow organizes the main application window for Stable-Diffusion inpainting."""

    OPEN_PANEL_STRETCH = 80

    def __init__(self, image_stack: ImageStack, controller) -> None:
        """Initializes the window and builds the layout.

        Parameters
        ----------
        image_stack : ImageStack
            Image layers being edited.
        controller : controller.base_controller.stable_diffusion_controller.StableDiffusionController
            Object managing application behavior.
        """
        super().__init__(image_stack, controller)
        # Decrease imageLayout stretch to make room for additional controls:
        self.layout().setStretch(0, 180)

    def _build_control_panel(self, controller) -> QWidget:
        """Adds controls for Stable-diffusion inpainting."""
        control_panel = BorderedWidget()
        control_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        control_layout = QVBoxLayout()
        control_panel.setLayout(control_layout)
        config = AppConfig()

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

        # First column: prompt,negative:
        wide_options_layout.setRowStretch(0, 2)
        wide_options_layout.addWidget(QLabel(config.get_label(AppConfig.PROMPT)), 0, 0)
        prompt_textbox = config.get_control_widget(AppConfig.PROMPT, multi_line=True)
        prompt_textbox.setMaximumHeight(textbox_height)
        wide_options_layout.addWidget(prompt_textbox, 0, 1)

        wide_options_layout.setRowStretch(1, 2)
        wide_options_layout.addWidget(QLabel(config.get_label(AppConfig.NEGATIVE_PROMPT)), 1, 0)
        negative_prompt_textbox = config.get_control_widget(AppConfig.NEGATIVE_PROMPT, multi_line=True)
        negative_prompt_textbox.setMaximumHeight(textbox_height)
        wide_options_layout.addWidget(negative_prompt_textbox, 1, 1)

        # width and height:
        gen_size_input = config.get_control_widget(AppConfig.GENERATION_SIZE)
        gen_size_input.orientation = Qt.Orientation.Vertical
        wide_options_layout.addWidget(gen_size_input, 0, 2, 2, 4)

        # batch size, count:
        # NOTE: I'm sneaking these in to the gen_size layout to make sure the alignment is correct.
        #       This is obviously not ideal, but is safe enough as long as the size field orientation
        #       doesn't need to change.
        spinbox_grid_layout = cast(QGridLayout, gen_size_input.layout())
        spinbox_grid_layout.setColumnStretch(3, 1)
        spinbox_grid_layout.setColumnStretch(4, 1)
        spinbox_grid_layout.addWidget(QLabel(config.get_label(AppConfig.BATCH_SIZE)), 0, 3)
        batch_size_spinbox = config.get_control_widget(AppConfig.BATCH_SIZE)
        batch_size_spinbox.set_slider_included(False)
        spinbox_grid_layout.addWidget(batch_size_spinbox, 0, 4)

        # batch count:
        spinbox_grid_layout.addWidget(QLabel(config.get_label(AppConfig.BATCH_COUNT)), 1, 3)
        batch_count_spinbox = config.get_control_widget(AppConfig.BATCH_COUNT)
        batch_count_spinbox.set_slider_included(False)
        spinbox_grid_layout.addWidget(batch_count_spinbox, 1, 4)

        # Misc. sliders:
        for i, slider_key in enumerate((AppConfig.SAMPLING_STEPS, AppConfig.GUIDANCE_SCALE,
                                        AppConfig.DENOISING_STRENGTH)):
            row_num = i + 2
            wide_options_layout.setRowStretch(row_num, 1)
            slider = config.get_control_widget(slider_key)
            assert hasattr(slider, 'setText')
            slider.setText(config.get_label(slider_key))
            wide_options_layout.addWidget(slider, row_num, 0, 1, 6)

        # ControlNet panel, if controlnet is installed:
        cache = Cache()
        if cache.get(cache.CONTROLNET_VERSION) > 0:
            controlnet_panel = ControlnetPanel(AppConfig.CONTROLNET_ARGS_0,
                                               cache.get(Cache.CONTROLNET_CONTROL_TYPES),
                                               cache.get(Cache.CONTROLNET_MODULES),
                                               cache.get(Cache.CONTROLNET_MODELS))
            controlnet_panel.set_expanded_size_policy(QSizePolicy.Maximum)
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
            combobox = config.get_control_widget(config_key)
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
        padding_spinbox = config.get_control_widget(AppConfig.INPAINT_FULL_RES_PADDING)
        padding_line.addWidget(padding_spinbox, stretch=2)
        option_list_layout.insertLayout(padding_line_index, padding_line)

        def padding_layout_update(inpaint_full_res: bool) -> None:
            """Only show the 'full-res padding' spin box if 'inpaint full-res' is checked."""
            padding_label.setVisible(inpaint_full_res)
            padding_spinbox.setVisible(inpaint_full_res)

        padding_layout_update(config.get(AppConfig.INPAINT_FULL_RES))
        config.connect(self, AppConfig.INPAINT_FULL_RES, padding_layout_update)
        config.connect(self, AppConfig.EDIT_MODE, lambda mode: padding_layout_update(mode == EDIT_MODE_INPAINT))

        seed_input = config.get_control_widget(AppConfig.SEED)
        add_option_line(config.get_label(AppConfig.SEED), seed_input, None)

        last_seed_box = cache.get_control_widget(cache.LAST_SEED)
        last_seed_box.setReadOnly(True)
        add_option_line(Cache().get_label(cache.LAST_SEED), last_seed_box, None)

        control_layout.addStretch(255)

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
