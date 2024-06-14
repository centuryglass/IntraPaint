"""Displays the image panel with zoom controls and input hints."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QSlider, QPushButton
from src.image.layer_stack import LayerStack
from src.ui.image_viewer import ImageViewer


SCALE_SLIDER_LABEL = 'Zoom:'
SCALE_RESET_BUTTON_LABEL = 'Reset View'
SCALE_RESET_BUTTON_TOOLTIP = 'Restore default image zoom and offset'
SCALE_ZOOM_BUTTON_LABEL = 'Zoom to image generation area'
SCALE_ZOOM_BUTTON_TOOLTIP = 'Zoom in on the area selected for image generation'


class ImagePanel(QWidget):
    """Displays the image panel with zoom controls and input hints."""

    def __init__(self, layer_stack: LayerStack) -> None:
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._image_viewer = ImageViewer(self, layer_stack)
        self._layout.addWidget(self._image_viewer, stretch=255)
        self._control_bar = QWidget()
        self._layout.addWidget(self._control_bar, stretch=1)
        self._control_layout = QHBoxLayout(self._control_bar)
        self._control_hint_label = QLabel("")

        scale_reset_button = QPushButton()

        def toggle_scale():
            """Toggle between default zoom and zooming in on the image generation area."""
            if self._image_viewer.is_at_default_view and not self._image_viewer.follow_generation_area:
                self._image_viewer.follow_generation_area = True
                scale_reset_button.setText(SCALE_RESET_BUTTON_LABEL)
                scale_reset_button.setToolTip(SCALE_RESET_BUTTON_TOOLTIP)
            else:
                self._image_viewer.follow_generation_area = False
                self._image_viewer.reset_scale()
                scale_reset_button.setText(SCALE_ZOOM_BUTTON_LABEL)
                scale_reset_button.setToolTip(SCALE_ZOOM_BUTTON_TOOLTIP)

        scale_reset_button.setText(SCALE_ZOOM_BUTTON_LABEL)
        scale_reset_button.setToolTip(SCALE_ZOOM_BUTTON_TOOLTIP)
        scale_reset_button.clicked.connect(toggle_scale)
        self._control_layout.addWidget(scale_reset_button)
        # Zoom slider:
        self._control_layout.addWidget(QLabel(SCALE_SLIDER_LABEL))
        image_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self._control_layout.addWidget(image_scale_slider)
        image_scale_slider.setRange(1, 4000)
        image_scale_slider.setSingleStep(10)
        image_scale_slider.setValue(int(self._image_viewer.scene_scale * 100))
        image_scale_box = QDoubleSpinBox()
        self._control_layout.addWidget(image_scale_box)
        image_scale_box.setRange(0.001, 40)
        image_scale_box.setSingleStep(0.1)
        image_scale_box.setValue(self._image_viewer.scene_scale)

        scale_signals = [
            self._image_viewer.scale_changed,
            image_scale_slider.valueChanged,
            image_scale_box.valueChanged
        ]

        def on_scale_change(new_scale: float | int) -> None:
            """Synchronize slider, spin box, panel scale, and zoom button text:"""
            if isinstance(new_scale, int):
                float_scale = new_scale / 100
                int_scale = new_scale
            else:
                float_scale = new_scale
                int_scale = int(float_scale * 100)
            for scale_signal in scale_signals:
                scale_signal.disconnect(on_scale_change)
            if image_scale_box.value() != float_scale:
                image_scale_box.setValue(float_scale)
            if image_scale_slider.value() != int_scale:
                image_scale_slider.setValue(int_scale)
            if self._image_viewer.scene_scale != float_scale:
                self._image_viewer.scene_scale = float_scale
            for scale_signal in scale_signals:
                scale_signal.connect(on_scale_change)
            if self._image_viewer.is_at_default_view and not self._image_viewer.follow_generation_area:
                scale_reset_button.setText(SCALE_ZOOM_BUTTON_LABEL)
                scale_reset_button.setToolTip(SCALE_ZOOM_BUTTON_TOOLTIP)
            else:
                scale_reset_button.setText(SCALE_RESET_BUTTON_LABEL)
                scale_reset_button.setToolTip(SCALE_RESET_BUTTON_TOOLTIP)

        for signal in scale_signals:
            signal.connect(on_scale_change)

    @property
    def image_viewer(self) -> ImageViewer:
        """Returns the wrapped ImageViewer widget."""
        return self._image_viewer

    def set_control_hint(self, hint_text: str) -> None:
        """Add a message below the image viewer hinting at controls."""
        self._control_hint_label.setText(hint_text)
