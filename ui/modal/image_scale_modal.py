"""
Popup modal window used for scaling the edited image.
"""
from PyQt5.QtWidgets import QWidget, QDialog, QSpinBox, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtCore import QSize
from ui.config_control_setup import connected_combobox, connected_checkbox, connected_spinbox
from ui.widget.labeled_spinbox import LabeledSpinbox


class ImageScaleModal(QDialog):
    def __init__(heightbox, default_width, default_height, config):
        super().__init__()

        heightbox._create = False
        heightbox.setModal(True)
        heightbox._layout = QVBoxLayout()

        heightbox._title = QLabel(heightbox)
        heightbox._title.setText("Scale image")
        heightbox._layout.addWidget(heightbox._title)

        min_val = 8
        max_val = 20000
        heightbox._widthbox = LabeledSpinbox(heightbox, "Width:", "New image width in pixels", min_val, default_width, max_val)
        heightbox._layout.addWidget(heightbox._widthbox)
        heightbox._heightBox = LabeledSpinbox(heightbox, "Height:", "New image height in pixels", min_val, default_height, max_val)
        heightbox._layout.addWidget(heightbox._heightBox)
        heightbox._xMultBox = LabeledSpinbox(heightbox, "Width scale:", "New image width (as multiplier)", 0.0, 1.0, 999.0)
        heightbox._layout.addWidget(heightbox._xMultBox)
        heightbox._yMultBox = LabeledSpinbox(heightbox, "Height scale:", "New image height (as multiplier)", 0.0, 1.0, 999.0)
        heightbox._layout.addWidget(heightbox._yMultBox)
        heightbox._upscaleMethodBox, heightbox._upscaleLayout = connected_combobox(heightbox, config, 'upscale_method', text='Upscale Method:')
        heightbox._layout.addLayout(heightbox._upscaleLayout)

        # Synchronize scale boxes with pixel size boxes
        def set_scale_on_px_change(pixel_size, base_value, scale_box):
            current_scale = scale_box.spinbox.value()
            new_scale = round(int(pixel_size) / base_value, 2)
            if int(base_value * float(current_scale)) != pixel_size:
                scale_box.spinbox.setValue(new_scale)
            elif current_scale != new_scale:
                print(f"ignoring rounding error, {current_scale} vs {new_scale}")

        def set_px_on_scale_change(scale, base_value, pxbox):
            current_pixel_size = pxbox.spinbox.value()
            new_pixel_size = int(base_value * float(scale))
            if round(int(current_pixel_size) / base_value, 2) != scale:
                pxbox.spinbox.setValue(new_pixel_size)
            elif current_pixel_size != new_pixel_size:
                print(f"ignoring rounding error, {current_pixel_size} vs {new_pixel_size}")

        heightbox._widthbox.spinbox.valueChanged.connect(lambda px: set_scale_on_px_change(px, default_width, heightbox._xMultBox))
        heightbox._xMultBox.spinbox.valueChanged.connect(lambda px: set_px_on_scale_change(px, default_width, heightbox._widthbox))
        heightbox._heightBox.spinbox.valueChanged.connect(lambda px: set_scale_on_px_change(px, default_height, heightbox._yMultBox))
        heightbox._yMultBox.spinbox.valueChanged.connect(lambda px: set_px_on_scale_change(px, default_height, heightbox._heightBox))

        # Add controlnet upscale option:
        if config.get('controlnet_version') > 0:
            heightbox._controlnet_checkbox = connected_checkbox(heightbox, config, 'controlnet_upscaling', text='Use ControlNet Tiles')
            heightbox._controlnet_ratebox = connected_spinbox(
                    heightbox,
                    config,
                    'controlnet_downsample_rate')
            heightbox._controlnet_ratebox.setEnabled(config.get('controlnet_upscaling'))
            heightbox._controlnet_checkbox.stateChanged.connect(lambda enabled: heightbox._controlnet_ratebox.setEnabled(enabled))
            heightbox._layout.addWidget(heightbox._controlnet_checkbox)
            heightbox._layout.addWidget(heightbox._controlnet_ratebox)

        heightbox._create_button = QPushButton(heightbox)
        heightbox._create_button.setText("Scale image")
        heightbox._layout.addWidget(heightbox._create_button)
        def on_create():
            config.disconnect(heightbox._upscaleMethodBox, 'upscale_method')
            heightbox._create = True
            heightbox.hide()
        heightbox._create_button.clicked.connect(on_create)

        heightbox._cancel_button = QPushButton(heightbox)
        heightbox._cancel_button.setText("Cancel")
        def on_cancel():
            config.disconnect(heightbox._upscaleMethodBox, 'upscale_method')
            heightbox._create = False
            heightbox.hide()
        heightbox._cancel_button.clicked.connect(on_cancel)
        heightbox._layout.addWidget(heightbox._cancel_button)
        
        heightbox.setLayout(heightbox._layout)

    def show_image_modal(self):
        self.exec_()
        if self._create:
            return QSize(self._widthbox.spinbox.value(), self._heightBox.spinbox.value())
