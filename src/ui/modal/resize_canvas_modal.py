"""Popup modal window used for cropping or extending the edited image without scaling its contents."""
from typing import Optional, cast
import math
from PySide6.QtWidgets import QWidget, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QApplication, QLabel
from PySide6.QtCore import QSize, QRect, QPoint
from PySide6.QtGui import QResizeEvent, QIcon

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.image.layers.image_stack import ImageStack
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox
from src.ui.widget.canvas_change_preview_widget import CanvasChangePreviewWidget
from src.util.shared_constants import APP_ICON_PATH

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.resize_canvas_modal'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


WINDOW_TITLE = _tr('Resize image canvas')
WIDTH_LABEL = _tr('Width:')
WIDTH_TOOLTIP = _tr('New image width in pixels')
HEIGHT_LABEL = _tr('Height:')
HEIGHT_TOOLTIP = _tr('New image height in pixels')
X_OFFSET_LABEL = _tr('X Offset:')
X_OFFSET_TOOLTIP = _tr('Distance in pixels from the left edge of the resized canvas to the left edge of the current'
                       ' image content')
Y_OFFSET_LABEL = _tr('Y Offset:')
Y_OFFSET_TOOLTIP = _tr('Distance in pixels from the top edge of the resized canvas to the top edge of the current '
                       'image content')

CENTER_BUTTON_LABEL = _tr('Center')
CANCEL_BUTTON_LABEL = _tr('Cancel')
RESIZE_BUTTON_LABEL = _tr('Resize image canvas')

MIN_PX_VALUE = 1


class ResizeCanvasModal(QDialog):
    """Popup modal window used for cropping or extending the edited image without scaling its contents."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__()
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        initial_size = image_stack.size

        self._resize = False
        self.setModal(True)
        self.setWindowTitle(WINDOW_TITLE)

        max_size: QSize = cast(QSize, AppConfig().get(AppConfig.MAX_IMAGE_SIZE))

        # Main controls:
        current_width = initial_size.width()
        current_height = initial_size.height()

        self._width_slider = IntSliderSpinbox(current_width, self, WIDTH_LABEL)
        self._width_slider.setToolTip(WIDTH_TOOLTIP)
        self._width_slider.setRange(MIN_PX_VALUE, max_size.width())

        self._height_slider = IntSliderSpinbox(current_height, self, HEIGHT_LABEL)
        self._height_slider.setToolTip(HEIGHT_TOOLTIP)
        self._height_slider.setRange(MIN_PX_VALUE, max_size.height())

        self._x_offset_slider = IntSliderSpinbox(0, self, X_OFFSET_LABEL)
        self._x_offset_slider.setToolTip(X_OFFSET_TOOLTIP)
        self._x_offset_slider.setRange(-max_size.width(), max_size.width())

        self._y_offset_slider = IntSliderSpinbox(0, self, Y_OFFSET_LABEL)
        self._y_offset_slider.setToolTip(Y_OFFSET_TOOLTIP)
        self._y_offset_slider.setRange(-max_size.height(), max_size.height())

        cache = Cache()
        self._layer_mode_label = QLabel(cache.get_label(Cache.CANVAS_RESIZE_LAYER_MODE))
        self._layer_mode_dropdown = cache.get_control_widget(Cache.CANVAS_RESIZE_LAYER_MODE)
        self._layer_mode_row = QWidget(self)
        self._layer_mode_row.setToolTip(cache.get_tooltip(Cache.CANVAS_RESIZE_LAYER_MODE))
        layer_mode_row_layout = QHBoxLayout(self._layer_mode_row)
        layer_mode_row_layout.addWidget(self._layer_mode_label)
        layer_mode_row_layout.addWidget(self._layer_mode_dropdown, stretch=1)

        self._crop_checkbox = cache.get_control_widget(Cache.CANVAS_RESIZE_CROP_LAYERS)
        self._crop_checkbox.setText(cache.get_label(Cache.CANVAS_RESIZE_CROP_LAYERS))
        self._crop_checkbox.setParent(self)
        self._crop_checkbox.valueChanged.connect(self.update)

        self._preview = CanvasChangePreviewWidget(image_stack)

        for input_field in (self._width_slider, self._height_slider, self._x_offset_slider, self._y_offset_slider):
            input_field.valueChanged.connect(self._update_preview)

        self._resize_button = QPushButton(self)
        self._resize_button.setText(RESIZE_BUTTON_LABEL)
        self._resize_button.clicked.connect(self._confirm)

        center_button = QPushButton(self)
        center_button.setText(CENTER_BUTTON_LABEL)

        def center() -> None:
            """Adjust offsets to center existing image content in the brush."""
            width = self._width_slider.value()
            height = self._height_slider.value()
            x_off = (width // 2) - (current_width // 2)
            y_off = (height // 2) - (current_height // 2)
            self._x_offset_slider.setValue(x_off)
            self._y_offset_slider.setValue(y_off)

        center_button.clicked.connect(center)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setText(CANCEL_BUTTON_LABEL)
        self._cancel_button.clicked.connect(self._cancel)

        option_bar = QWidget(self)
        layout = QHBoxLayout(option_bar)
        layout.addWidget(self._resize_button)
        layout.addWidget(self._cancel_button)

        self._layout = QVBoxLayout()
        ordered_widgets = [
            self._width_slider,
            self._height_slider,
            self._x_offset_slider,
            self._y_offset_slider,
            self._layer_mode_row,
            self._crop_checkbox,
            self._preview,
            center_button,
            option_bar
        ]

        for widget in ordered_widgets:
            self._layout.addWidget(widget)
        self._layout.setStretch(self._layout.indexOf(self._preview), 1)
        self.setLayout(self._layout)
        self.resizeEvent(None)

    def _update_preview(self, _) -> None:
        canvas_bounds = QRect(-self._x_offset_slider.value(),
                              -self._y_offset_slider.value(),
                              self._width_slider.value(),
                              self._height_slider.value())
        self._preview.set_new_bounds(canvas_bounds)

    def _confirm(self) -> None:
        self._resize = True
        self.hide()

    def _cancel(self) -> None:
        self._resize = False
        self.hide()

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Recalculate preview bounds on resize."""
        min_preview = math.ceil(min(self.width(), self.height()) * 0.8)
        self._preview.setMinimumSize(QSize(min_preview, min_preview))
        IntSliderSpinbox.align_slider_spinboxes([self._width_slider, self._height_slider,
                                                 self._x_offset_slider, self._y_offset_slider])

    def show_resize_modal(self) -> tuple[QSize, QPoint] | tuple[None, None]:
        """Show this modal, returning QSize new_size and QPoint offset if changes are confirmed."""
        self.exec()
        if self._resize:
            new_size = QSize(self._width_slider.value(), self._height_slider.value())
            offset = QPoint(self._x_offset_slider.value(), self._y_offset_slider.value())
            return new_size, offset
        return None, None
