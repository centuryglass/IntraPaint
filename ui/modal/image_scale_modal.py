"""Popup modal window used for scaling the edited image."""
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout, QPushButton
from PyQt5.QtCore import QSize
from ui.config_control_setup import connected_combobox, connected_checkbox, connected_spinbox
from ui.widget.labeled_spinbox import LabeledSpinbox
from data_model.config import Config


class ImageScaleModal(QDialog):
    """Popup modal window used for scaling the edited image."""

    def __init__(self, default_width: int, default_height: int, config: Config):
        super().__init__()

        self._create = False
        self.setModal(True)
        self._layout = QVBoxLayout()

        self._title = QLabel(self)
        self._title.setText('Scale image')
        self._layout.addWidget(self._title)

        min_val = 8
        max_val = 20000
        self._widthbox = LabeledSpinbox(self, 'Width:', 'New image width in pixels', min_val, default_width,
                max_val)
        self._layout.addWidget(self._widthbox)
        self._heightbox = LabeledSpinbox(self, 'Height:', 'New image height in pixels', min_val,
                default_height, max_val)
        self._layout.addWidget(self._heightbox)
        self._x_mult_box = LabeledSpinbox(self, 'Width scale:', 'New image width (as multiplier)', 0.0, 1.0,
                999.0)
        self._layout.addWidget(self._x_mult_box)
        self._y_mult_box = LabeledSpinbox(self, 'Height scale:', 'New image height (as multiplier)', 0.0, 1.0,
                999.0)
        self._layout.addWidget(self._y_mult_box)
        self._upscale_method_box, self._upscale_layout = connected_combobox(self, config,
                Config.UPSCALE_METHOD, text='Upscale Method:')
        self._layout.addLayout(self._upscale_layout)

        # Synchronize scale boxes with pixel size boxes
        def set_scale_on_px_change(pixel_size: int, base_value: int, scale_box: LabeledSpinbox):
            current_scale = scale_box.spinbox.value()
            new_scale = round(int(pixel_size) / base_value, 2)
            # Ignore rounding errors:
            if int(base_value * float(current_scale)) != pixel_size:
                scale_box.spinbox.setValue(new_scale)

        def set_px_on_scale_change(scale: float, base_value: float, pxbox: LabeledSpinbox):
            current_pixel_size = pxbox.spinbox.value()
            new_pixel_size = int(base_value * float(scale))
            # Ignore rounding errors:
            if round(int(current_pixel_size) / base_value, 2) != scale:
                pxbox.spinbox.setValue(new_pixel_size)


        self._widthbox.spinbox.valueChanged.connect(
                lambda px: set_scale_on_px_change(px, default_width, self._x_mult_box))
        self._x_mult_box.spinbox.valueChanged.connect(
                lambda px: set_px_on_scale_change(px, default_width, self._widthbox))
        self._heightbox.spinbox.valueChanged.connect(
                lambda px: set_scale_on_px_change(px, default_height, self._y_mult_box))
        self._y_mult_box.spinbox.valueChanged.connect(
                lambda px: set_px_on_scale_change(px, default_height, self._heightbox))

        # Add controlnet upscale option:
        if config.get(Config.CONTROLNET_VERSION) > 0:
            self._controlnet_checkbox = connected_checkbox(self, config, Config.CONTROLNET_UPSCALING,
                    text='Use ControlNet Tiles')
            self._controlnet_ratebox = connected_spinbox(
                    self,
                    config,
                    Config.CONTROLNET_DOWNSAMPLE_RATE)
            self._controlnet_ratebox.setEnabled(config.get(Config.CONTROLNET_UPSCALING))
            self._controlnet_checkbox.stateChanged.connect(self._controlnet_ratebox.setEnabled)
            self._layout.addWidget(self._controlnet_checkbox)
            self._layout.addWidget(self._controlnet_ratebox)

        self._create_button = QPushButton(self)
        self._create_button.setText('Scale image')
        self._layout.addWidget(self._create_button)
        def on_create() -> None:
            config.disconnect(self._upscale_method_box, Config.UPSCALE_METHOD)
            self._create = True
            self.hide()
        self._create_button.clicked.connect(on_create)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setText('Cancel')
        def on_cancel() -> None:
            config.disconnect(self._upscale_method_box, Config.UPSCALE_METHOD)
            self._create = False
            self.hide()
        self._cancel_button.clicked.connect(on_cancel)
        self._layout.addWidget(self._cancel_button)

        self.setLayout(self._layout)

    def show_image_modal(self) -> None:
        """Show the modal, returning the selected size when the modal closes."""
        self.exec_()
        if self._create:
            return QSize(self._widthbox.spinbox.value(), self._heightbox.spinbox.value())
        return None
