"""Popup modal window used for scaling the edited image."""
from typing import Optional, cast, TypeAlias

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QFormLayout, QPushButton, QComboBox, QSpinBox, QHBoxLayout, QDoubleSpinBox, \
    QWidget, QApplication

from src.config.cache import Cache
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.slider_spinbox import FloatSliderSpinbox
from src.util.shared_constants import APP_ICON_PATH, PIL_SCALING_MODES

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.image_scale_modal'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


TITLE_TEXT = _tr('Scale image')
WIDTH_PX_BOX_LABEL = _tr('Width:')
WIDTH_PX_BOX_TOOLTIP = _tr('New image width in pixels')
HEIGHT_PX_BOX_LABEL = _tr('Height:')
HEIGHT_PX_BOX_TOOLTIP = _tr('New image height in pixels')
WIDTH_MULT_BOX_LABEL = _tr('Width scale:')
WIDTH_MULT_BOX_TOOLTIP = _tr('New image width (as multiplier)')
HEIGHT_MULT_BOX_LABEL = _tr('Height scale:')
HEIGHT_MULT_BOX_TOOLTIP = _tr('New image height (as multiplier)')
UPSCALE_METHOD_LABEL = _tr('Upscale Method:')
SCALE_BUTTON_LABEL = _tr('Scale image')
CANCEL_BUTTON_LABEL = _tr('Cancel')

MIN_PX_VALUE = 8
MAX_PX_VALUE = 20000

Spinbox: TypeAlias = QSpinBox | QDoubleSpinBox


class ImageScaleModal(QDialog):
    """Popup modal window used for scaling the edited image."""

    def __init__(self, default_width: int, default_height: int, multi_layer: bool = False):
        super().__init__()
        cache = Cache()
        self._should_scale = False
        self.setModal(True)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle(TITLE_TEXT)
        self._layout = QFormLayout(self)

        if len(cache.get_options(Cache.UPSCALE_METHOD)) == 0:
            upscale_modes = list(PIL_SCALING_MODES.keys())
            cache.update_options(Cache.UPSCALE_METHOD, upscale_modes)

        self._upscale_method_box: QComboBox = cast(QComboBox, cache.get_control_widget(Cache.UPSCALE_METHOD))
        self._layout.addRow(UPSCALE_METHOD_LABEL, self._upscale_method_box)

        if multi_layer:
            self._layer_handling_box: QComboBox = cast(QComboBox,
                                                       cache.get_control_widget(Cache.IMAGE_LAYER_SCALING_BEHAVIOR))
            self._layout.addRow(cache.get_label(Cache.IMAGE_LAYER_SCALING_BEHAVIOR), self._layer_handling_box)
        else:
            self._layer_handling_box = None

        def _add_input(default_value, min_val, max_val, title, tooltip) -> Spinbox:
            box = QSpinBox() if isinstance(default_value, int) else QDoubleSpinBox()
            box.setRange(min_val, max_val)
            box.setValue(default_value)
            box.setToolTip(tooltip)
            self._layout.addRow(title, box)
            return box

        self._width_box = _add_input(default_width, MIN_PX_VALUE, MAX_PX_VALUE, WIDTH_PX_BOX_LABEL,
                                     WIDTH_PX_BOX_TOOLTIP)
        self._height_box = _add_input(default_height, MIN_PX_VALUE, MAX_PX_VALUE, HEIGHT_PX_BOX_LABEL,
                                      HEIGHT_PX_BOX_TOOLTIP)
        self._x_mult_box = _add_input(1.0, 0.0, 999.0, WIDTH_MULT_BOX_LABEL,
                                      WIDTH_MULT_BOX_TOOLTIP)
        self._y_mult_box = _add_input(1.0, 0.0, 999.0, HEIGHT_MULT_BOX_LABEL,
                                      HEIGHT_MULT_BOX_TOOLTIP)

        def set_scale_on_px_change(pixel_size: int, base_value: int, scale_box: QDoubleSpinBox):
            """Apply scale box changes to pixel size boxes."""
            current_scale = scale_box.value()
            new_scale = round(int(pixel_size) / base_value, 2)
            # Ignore rounding errors:
            if int(base_value * float(current_scale)) != pixel_size:
                scale_box.setValue(new_scale)

        def set_px_on_scale_change(scale: float, base_value: float, px_box: QSpinBox):
            """Apply pixel size changes to scale size boxes."""
            current_pixel_size = px_box.value()
            new_pixel_size = int(base_value * float(scale))
            # Ignore rounding errors:
            if round(int(current_pixel_size) / base_value, 2) != scale:
                px_box.setValue(new_pixel_size)

        self._width_box.valueChanged.connect(
            lambda px: set_scale_on_px_change(px, default_width, self._x_mult_box))
        self._x_mult_box.valueChanged.connect(
            lambda px: set_px_on_scale_change(px, default_width, self._width_box))
        self._height_box.valueChanged.connect(
            lambda px: set_scale_on_px_change(px, default_height, self._y_mult_box))
        self._y_mult_box.valueChanged.connect(
            lambda px: set_px_on_scale_change(px, default_height, self._height_box))

        # Add controlnet upscale option:
        if Cache().get(Cache.CONTROLNET_VERSION) > 0:
            self._controlnet_checkbox = cache.get_control_widget(Cache.CONTROLNET_UPSCALING)
            assert isinstance(self._controlnet_checkbox, CheckBox)
            self._controlnet_checkbox.setText('')
            self._controlnet_rate_box = cache.get_control_widget(Cache.CONTROLNET_DOWNSAMPLE_RATE)
            assert isinstance(self._controlnet_rate_box, FloatSliderSpinbox)
            self._controlnet_rate_box.set_slider_included(False)
            self._controlnet_rate_box.setEnabled(cache.get(Cache.CONTROLNET_UPSCALING))
            self._controlnet_checkbox.stateChanged.connect(self._controlnet_rate_box.setEnabled)
            self._layout.addRow(cache.get_label(Cache.CONTROLNET_UPSCALING), self._controlnet_checkbox)
            self._layout.addRow(cache.get_label(Cache.CONTROLNET_DOWNSAMPLE_RATE), self._controlnet_rate_box)

        def on_finish(should_scale: bool) -> None:
            """Cleanup, set choice, and close on 'scale image'/'cancel'."""
            cache.disconnect(self._upscale_method_box, Cache.UPSCALE_METHOD)
            if self._layer_handling_box is not None:
                cache.disconnect(self._layer_handling_box, Cache.IMAGE_LAYER_SCALING_BEHAVIOR)
            self._should_scale = should_scale
            self.hide()

        button_row = QWidget(self)
        self._layout.addRow(button_row)
        button_layout = QHBoxLayout(button_row)

        self._create_button = QPushButton(self)
        self._create_button.setText(SCALE_BUTTON_LABEL)
        self._create_button.clicked.connect(lambda: on_finish(True))
        button_layout.addWidget(self._create_button)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setText(CANCEL_BUTTON_LABEL)
        self._cancel_button.clicked.connect(lambda: on_finish(False))
        button_layout.addWidget(self._cancel_button)

    def show_image_modal(self) -> Optional[QSize]:
        """Show the modal, returning the selected size when the modal closes."""
        self.exec()
        if self._should_scale:
            return QSize(int(self._width_box.value()), int(self._height_box.value()))
        return None
