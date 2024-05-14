"""
A MainWindow implementation providing controls specific to stable-diffusion inpainting.
"""
from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QGridLayout, QPushButton, QSizePolicy
from PyQt5.QtCore import Qt, QSize
import sys

from ui.config_control_setup import *
from ui.widget.bordered_widget import BorderedWidget
from ui.widget.big_int_spinbox import BigIntSpinbox
from ui.widget.collapsible_box import CollapsibleBox
from ui.widget.param_slider import ParamSlider
from ui.window.main_window import MainWindow
from ui.panel.controlnet_panel import ControlnetPanel

OPEN_PANEL_STRETCH = 80

class StableDiffusionMainWindow(MainWindow):
    def __init__(self, config, editedImage, mask, sketch, controller):
        super().__init__(config, editedImage, mask, sketch, controller)
        # Decrease imageLayout stretch to make room for additional controls:
        self.layout().setStretch(0, 180)

    def _build_control_layout(self, controller):
        control_panel = BorderedWidget(self)
        control_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        control_layout = QVBoxLayout()
        control_panel.setLayout(control_layout)
        self.layout().addWidget(control_panel, stretch=10)

        main_control_box = CollapsibleBox(
                "Controls",
                control_panel,
                start_closed=self.should_use_wide_layout())
        main_control_box.set_expanded_size_policy(QSizePolicy.Maximum)
        if main_control_box.is_expanded():
            self.layout().setStretch(1, self.layout().stretch(1) + OPEN_PANEL_STRETCH)
        def on_main_controls_expanded(isExpanded):
            self.set_image_sliders_enabled(not isExpanded)
            stretch = self.layout().stretch(1) + (OPEN_PANEL_STRETCH if isExpanded else -OPEN_PANEL_STRETCH)
            stretch = max(stretch, 10)
            self.layout().setStretch(1, stretch)
        main_control_box.toggled().connect(on_main_controls_expanded)
        main_controls = QHBoxLayout();
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
        if textbox_height < 0: #font uses pt, not px
            textbox_height = self.font().pointSize() * 6

        # First line: prompt, batch size, width
        wide_options_layout.setRowStretch(0, 2)
        wide_options_layout.addWidget(QLabel("Prompt:"), 0, 0)
        prompt_textbox = connected_textedit(control_panel, self._config, 'prompt', multi_line=True)
        prompt_textbox.setMaximumHeight(textbox_height)
        wide_options_layout.addWidget(prompt_textbox, 0, 1)
        # batch size:
        wide_options_layout.addWidget(QLabel("Batch size:"), 0, 2)
        batch_size_spinbox = connected_spinbox(control_panel, self._config, 'batch_size')
        wide_options_layout.addWidget(batch_size_spinbox, 0, 3)
        # width: 
        wide_options_layout.addWidget(QLabel("W:"), 0, 4)
        width_spinbox = QSpinBox(self)
        width_spinbox.setRange(1, 4096)
        width_spinbox.setValue(self._config.get('edit_size').width())
        width_spinbox.setToolTip('Resize selection content to this width before inpainting')
        config = self._config
        def set_w(value):
            size = config.get('edit_size')
            config.set('edit_size', QSize(value, size.height()))
        width_spinbox.valueChanged.connect(set_w)
        wide_options_layout.addWidget(width_spinbox, 0, 5)


        # Second line: negative prompt, batch count, height:
        wide_options_layout.setRowStretch(1, 2)
        wide_options_layout.addWidget(QLabel('Negative:'), 1, 0)
        negative_prompt_textbox = connected_textedit(control_panel, self._config, 'negative_prompt', multi_line=True)
        negative_prompt_textbox.setMaximumHeight(textbox_height)
        wide_options_layout.addWidget(negative_prompt_textbox, 1, 1)
        # batch count:
        wide_options_layout.addWidget(QLabel('Batch count:'), 1, 2)
        batch_count_spinbox = connected_spinbox(control_panel, self._config, 'batch_count')
        wide_options_layout.addWidget(batch_count_spinbox, 1, 3)
        # Height: 
        wide_options_layout.addWidget(QLabel("H:"), 1, 4)
        height_spinbox = QSpinBox(self)
        height_spinbox.setRange(1, 4096)
        height_spinbox.setValue(self._config.get('edit_size').height())
        height_spinbox.setToolTip('Resize selection content to this height before inpainting')
        config = self._config
        def set_h(value):
            size = config.get('edit_size')
            config.set('edit_size', QSize(size.width(), value))
        height_spinbox.valueChanged.connect(set_h)
        wide_options_layout.addWidget(height_spinbox, 1, 5)

        # Misc. sliders:
        wide_options_layout.setRowStretch(2, 1)
        sample_step_slider = ParamSlider(wide_options, 'Sampling steps:', self._config, 'sampling_steps')
        wide_options_layout.addWidget(sample_step_slider, 2, 0, 1, 6)
        wide_options_layout.setRowStretch(3, 1)
        cfg_scale_slider = ParamSlider(wide_options, 'CFG scale:', self._config, 'guidance_scale')
        wide_options_layout.addWidget(cfg_scale_slider, 3, 0, 1, 6)
        wide_options_layout.setRowStretch(4, 1)
        denoising_slider = ParamSlider(wide_options, 'Denoising strength:', self._config, 'denoising_strength')
        wide_options_layout.addWidget(denoising_slider, 4, 0, 1, 6)

        # ControlNet panel, if controlnet is installed:
        if self._config.get('controlnet_version') > 0:
            control_types = None
            try:
                control_types = controller._webservice.get_controlnet_control_types(),
            except RuntimeError:
                pass # API doesn't support control type selection, make do without it.
            controlnet_panel = ControlnetPanel(self._config,
                    control_types,
                    controller._webservice.get_controlnet_modules(),
                    controller._webservice.get_controlnet_models())
            controlnet_panel.set_expanded_size_policy(QSizePolicy.Maximum)
            if controlnet_panel.is_expanded():
                self.layout().setStretch(1, self.layout().stretch(1) + OPEN_PANEL_STRETCH)
            def on_controlnet_expanded(expanded):
                stretch = self.layout().stretch(1) + (OPEN_PANEL_STRETCH if expanded else -OPEN_PANEL_STRETCH)
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
        def add_option_line(label_text, widget, tooltip=None):
            option_line = QHBoxLayout()
            option_list_layout.addLayout(option_line)
            option_line.addWidget(QLabel(label_text), stretch=1)
            if tooltip is not None:
                widget.setToolTip(tooltip)
            option_line.addWidget(widget, stretch=2)
            return option_line

        def add_combo_box(label_text, config_key, inpainting_only, tooltip=None):
            combobox = connected_combobox(option_list, self._config, config_key)
            if inpainting_only:
                self._config.connect(combobox, 'edit_mode', lambda newMode: combobox.setEnabled(newMode == 'Inpaint'))
            return add_option_line(label_text, combobox, tooltip)

        add_combo_box('Editing mode:', 'edit_mode', False)
        add_combo_box('Masked content:', 'masked_content', True)
        add_combo_box('Sampling method:', 'sampling_method', False)
        padding_line_index = len(option_list_layout.children())
        padding_line = QHBoxLayout()
        padding_label = QLabel('Inpaint padding:')
        padding_line.addWidget(padding_label, stretch = 1)
        padding_spinbox = connected_spinbox(self, self._config, 'inpaint_full_res_padding')
        padding_spinbox.setMinimum(0)
        padding_line.addWidget(padding_spinbox, stretch = 2)
        option_list_layout.insertLayout(padding_line_index, padding_line)
        def padding_layout_update(inpaintFullRes):
            padding_label.setVisible(inpaintFullRes)
            padding_spinbox.setVisible(inpaintFullRes)
        padding_layout_update(self._config.get('inpaint_full_res'))
        self._config.connect(self, 'inpaint_full_res', lambda isSet: padding_layout_update(isSet))
        self._config.connect(self, 'edit_mode', lambda mode: padding_layout_update(mode == 'Inpaint'))


        checkbox_line = QHBoxLayout()
        option_list_layout.addLayout(checkbox_line)
        checkbox_line.addWidget(QLabel('Restore faces:'), stretch=4)
        face_checkbox = connected_checkbox(option_list, self._config, 'restore_faces')
        checkbox_line.addWidget(face_checkbox, stretch=1)
        checkbox_line.addWidget(QLabel('Tiling:'), stretch=4)
        tiling_checkbox = connected_checkbox(option_list, self._config, 'tiling')
        checkbox_line.addWidget(tiling_checkbox, stretch=1)

        inpaint_line = QHBoxLayout()
        option_list_layout.addLayout(inpaint_line)
        inpaint_line.addWidget(QLabel('Inpaint Masked Only:'), stretch = 4)
        inpaint_checkbox = connected_checkbox(option_list, self._config, 'inpaint_full_res')
        inpaint_line.addWidget(inpaint_checkbox, stretch = 1)

        seed_input = connected_spinbox(option_list, self._config, 'seed', min_val=-1, max_val=BigIntSpinbox.MAXIMUM,
                step_val=1)
        add_option_line("Seed:", seed_input, None)

        last_seed_box = connected_textedit(option_list, self._config, 'last_seed');
        last_seed_box.setReadOnly(True)
        add_option_line("Last Seed", last_seed_box, None)

        
        # Put action buttons on the bottom:
        button_bar = BorderedWidget(control_panel)
        button_bar_layout = QHBoxLayout()
        button_bar.setLayout(button_bar_layout)
        button_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        control_layout.addWidget(button_bar, stretch=5)

        # interrogate_button:
        interrogate_button = QPushButton();
        interrogate_button.setText("Interrogate")
        interrogate_button.setToolTip("Attempt to generate a prompt that describes the current selection")
        interrogate_button.clicked.connect(lambda: controller.interrogate())
        button_bar_layout.addWidget(interrogate_button, stretch=1)
        interrogate_button.resize(interrogate_button.width(), interrogate_button.height() * 2)
        # Start generation button:
        start_button = QPushButton();
        start_button.setText("Generate")
        start_button.clicked.connect(lambda: controller.start_and_manage_inpainting())
        button_bar_layout.addWidget(start_button, stretch=2)
        start_button.resize(start_button.width(), start_button.height() * 2)

        # Add image panel sliders:
        self._step_slider = ParamSlider(self,
                'Sampling steps:',
                self._config,
                'sampling_steps',
                orientation=Qt.Orientation.Vertical,
                vertical_text_pt=int(self._config.get("font_point_size") * 1.3))
        self._cfg_slider = ParamSlider(
                self,
                "CFG scale:",
                config,
                'guidance_scale',
                orientation=Qt.Orientation.Vertical,
                vertical_text_pt=int(self._config.get("font_point_size") * 1.3))
        self._denoise_slider = ParamSlider(self,
                'Denoising strength:',
                self._config,
                'denoising_strength',
                orientation=Qt.Orientation.Vertical,
                vertical_text_pt=int(self._config.get("font_point_size") * 1.3))
        self._image_panel.add_slider(self._step_slider)
        self._image_panel.add_slider(self._cfg_slider)
        self._image_panel.add_slider(self._denoise_slider)
