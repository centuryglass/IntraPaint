"""Popup modal window used for scaling the edited image."""
from typing import Optional
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout, QPushButton
from PyQt5.QtCore import QSize

from src.config.cache import Cache
from src.ui.config_control_setup import connected_combobox, connected_checkbox, connected_spinbox
from src.ui.widget.labeled_spinbox import LabeledSpinbox
from src.config.application_config import AppConfig


WIDTH_PX_BOX_LABEL = 'Width:'
WIDTH_PX_BOX_TOOLTIP = 'New image width in pixels'
HEIGHT_PX_BOX_LABEL = 'Height:'
HEIGHT_PX_BOX_TOOLTIP = 'New image height in pixels'
WIDTH_MULT_BOX_LABEL = 'Width scale:'
WIDTH_MULT_BOX_TOOLTIP = 'New image width (as multiplier)'
HEIGHT_MULT_BOX_LABEL = 'Height scale:'
HEIGHT_MULT_BOX_TOOLTIP = 'New image height (as multiplier)'
UPSCALE_METHOD_LABEL = 'Upscale Method:'
CONTROLNET_TILE_LABEL = 'Use ControlNet Tiles'
SCALE_BUTTON_LABEL = 'Scale image'
CANCEL_BUTTON_LABEL = 'Cancel'

MIN_PX_VALUE = 8
MAX_PX_VALUE = 20000


class ImageScaleModal(QDialog):
    """Popup modal window used for scaling the edited image."""

    def __init__(self, default_width: int, default_height: int):
        super().__init__()
        config = AppConfig.instance()
        self._should_scale = False
        self.setModal(True)
        self._layout = QVBoxLayout()

        self._title = QLabel(self)
        self._title.setText('Scale image')
        self._layout.addWidget(self._title)

        min_val = MIN_PX_VALUE
        max_val = MAX_PX_VALUE
        self._width_box = LabeledSpinbox(self, WIDTH_PX_BOX_LABEL, WIDTH_PX_BOX_TOOLTIP, min_val,
                                         default_width, max_val)
        self._layout.addWidget(self._width_box)
        self._height_box = LabeledSpinbox(self, HEIGHT_PX_BOX_LABEL, HEIGHT_PX_BOX_TOOLTIP, min_val,
                                          default_height, max_val)
        self._layout.addWidget(self._height_box)
        self._x_mult_box = LabeledSpinbox(self, WIDTH_MULT_BOX_LABEL, WIDTH_MULT_BOX_TOOLTIP, 0.0, 1.0,
                                          999.0)
        self._layout.addWidget(self._x_mult_box)
        self._y_mult_box = LabeledSpinbox(self, HEIGHT_MULT_BOX_LABEL, HEIGHT_MULT_BOX_TOOLTIP, 0.0, 1.0,
                                          999.0)
        self._layout.addWidget(self._y_mult_box)
        self._upscale_method_box, self._upscale_layout = connected_combobox(self, AppConfig.UPSCALE_METHOD,
                                                                            text=UPSCALE_METHOD_LABEL)
        self._layout.addLayout(self._upscale_layout)

        def set_scale_on_px_change(pixel_size: int, base_value: int, scale_box: LabeledSpinbox):
            """Apply scale box changes to pixel size boxes."""
            current_scale = scale_box.spinbox.value()
            new_scale = round(int(pixel_size) / base_value, 2)
            # Ignore rounding errors:
            if int(base_value * float(current_scale)) != pixel_size:
                scale_box.spinbox.setValue(new_scale)

        def set_px_on_scale_change(scale: float, base_value: float, px_box: LabeledSpinbox):
            """Apply pixel size changes to scale size boxes."""
            current_pixel_size = px_box.spinbox.value()
            new_pixel_size = int(base_value * float(scale))
            # Ignore rounding errors:
            if round(int(current_pixel_size) / base_value, 2) != scale:
                px_box.spinbox.setValue(new_pixel_size)

        self._width_box.spinbox.valueChanged.connect(
            lambda px: set_scale_on_px_change(px, default_width, self._x_mult_box))
        self._x_mult_box.spinbox.valueChanged.connect(
            lambda px: set_px_on_scale_change(px, default_width, self._width_box))
        self._height_box.spinbox.valueChanged.connect(
            lambda px: set_scale_on_px_change(px, default_height, self._y_mult_box))
        self._y_mult_box.spinbox.valueChanged.connect(
            lambda px: set_px_on_scale_change(px, default_height, self._height_box))

        # Add controlnet upscale option:
        if Cache.instance().get(Cache.CONTROLNET_VERSION) > 0:
            self._controlnet_checkbox = connected_checkbox(self, AppConfig.CONTROLNET_UPSCALING,
                                                           text=CONTROLNET_TILE_LABEL)
            self._controlnet_rate_box = connected_spinbox(self, AppConfig.CONTROLNET_DOWNSAMPLE_RATE)
            self._controlnet_rate_box.setEnabled(config.get(AppConfig.CONTROLNET_UPSCALING))
            self._controlnet_checkbox.stateChanged.connect(self._controlnet_rate_box.setEnabled)
            self._layout.addWidget(self._controlnet_checkbox)
            self._layout.addWidget(self._controlnet_rate_box)

        def on_finish(should_scale: bool) -> None:
            """Cleanup, set choice, and close on 'scale image'/'cancel'."""
            config.disconnect(self._upscale_method_box, AppConfig.UPSCALE_METHOD)
            self._should_scale = should_scale
            self.hide()

        self._create_button = QPushButton(self)
        self._create_button.setText(SCALE_BUTTON_LABEL)
        self._create_button.clicked.connect(lambda: on_finish(True))
        self._layout.addWidget(self._create_button)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setText(CANCEL_BUTTON_LABEL)

        self._cancel_button.clicked.connect(lambda: on_finish(False))
        self._layout.addWidget(self._cancel_button)

        self.setLayout(self._layout)

    def show_image_modal(self) -> Optional[QSize]:
        """Show the modal, returning the selected size when the modal closes."""
        self.exec_()
        if self._should_scale:
            return QSize(self._width_box.spinbox.value(), self._height_box.spinbox.value())
        return None
