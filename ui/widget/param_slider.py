"""
Provides an extended QSlider widget with integrated data_model/config connection.
"""
from PyQt5.QtWidgets import QWidget, QSlider, QLabel, QSizePolicy
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QFontMetrics
from ui.config_control_setup import connected_spinbox
from ui.widget.label import Label

class ParamSlider(QWidget):
    def __init__(self,
            parent,
            label_text,
            config,
            key,
            min_key,
            max_key,
            step_key=None,
            inner_key=None,
            orientation=Qt.Orientation.Horizontal,
            vertical_text_pt=None):
        super().__init__(parent)
        is_vertical = (orientation == Qt.Orientation.Vertical)

        self._key = None
        self._inner_key = None
        self._float_mode = None
        self._orientation = None
        self._config = config

        self._label = Label(label_text, config, self, size=vertical_text_pt, orientation=orientation)
        self._horizontal_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._vertical_slider = QSlider(Qt.Orientation.Vertical, self)

        self._horizontal_slider.setTickPosition(QSlider.TickPosition.TicksAbove)
        self._vertical_slider.setTickPosition(QSlider.TickPosition.TicksRight)
        self._horizontal_slider.valueChanged.connect(lambda newValue: self._on_slider_change(newValue))
        self._vertical_slider.valueChanged.connect(lambda newValue: self._on_slider_change(newValue))

        font = QFont()
        font.setPointSize(config.get("fontPointSize"))
        self._spinboxMeasurements = QFontMetrics(font).boundingRect("9999").size() * 1.5
        
        number_text = str(config.get(key, inner_key=inner_key))
        self._stepbox = None
        if key is not None:
            self.connect_key(key, min_key, max_key, step_key, inner_key)
        self.set_orientation(orientation)

    def disconnect_config(self):
        if self._key is not None:
            try:
                self._config.disconnect(self, self._key)
            except KeyError as err:
                    print(f"Disconnecting slider from {self._key} failed: {err}")
            if self._stepbox is not None:
                stepbox = self._stepbox
                try:
                    self._config.disconnect(stepbox, self._key)
                except KeyError as err:
                    print(f"Disconnecting stepbox from {self._key} failed: {err}")
                stepbox.valueChanged.disconnect()
                stepbox.setParent(None)
                stepbox.deleteLater()
            self._key = None
            self._inner_key = None

    def connect_key(self, key, min_key, max_key, step_key, inner_key=None):
        if self._key == key and self._inner_key == key:
            return
        self.disconnect_config()
        self._key = key
        self._inner_key = inner_key
        initial_value = self._config.get(key, inner_key)
        self._float_mode = (type(initial_value) is float)
        min_val = self._config.get(min_key) if isinstance(min_key, str) else min_key
        max_val = self._config.get(max_key) if isinstance(max_key, str) else max_key
        
        full_range = max_val - min_val
        tick_interval = 1 if (full_range < 20) else (5 if full_range < 50 else 10)
        if self._float_mode:
            tick_interval *= 100
        step = 1 if step_key is None else self._config.get(step_key) if isinstance(step_key, str) else step_key
        for slider in (self._horizontal_slider, self._vertical_slider):
            slider.setMinimum(int(min_val * 100) if self._float_mode else min_val)
            slider.setMaximum(int(max_val * 100) if self._float_mode else max_val)
            slider.setSingleStep(int(step * 100) if self._float_mode else step)
            slider.setValue(int(initial_value * 100) if self._float_mode else initial_value)
            slider.setTickInterval(tick_interval)
        def onConfigChange(new_value):
            if new_value is None:
                return
            value = int(new_value * 100) if self._float_mode else new_value
            if value != self._horizontal_slider.value():
                self._horizontal_slider.setValue(value)
            if value != self._vertical_slider.value():
                self._vertical_slider.setValue(value)
        self._config.connect(self, key, onConfigChange, inner_key)
        self._stepbox = connected_spinbox(self, self._config, key, min_key, max_key, step_key, inner_key)
        self.resizeEvent(None)
        self._stepbox.show()

    def sizeHint(self):
        if self._orientation == Qt.Orientation.Vertical:
            return QSize(max(self._vertical_slider.sizeHint().width(), self._label.sizeHint().width(), self._spinboxMeasurements.width()),\
                    self._vertical_slider.sizeHint().height() + self._label.sizeHint().height() + self._spinboxMeasurements.height())
        else: #horizontal
            return QSize(self._horizontal_slider.sizeHint().width() + self._label.sizeHint().width() + self._spinboxMeasurements.width(), \
                    max(self._horizontal_slider.sizeHint().height(), self._label.sizeHint().height(), self._spinboxMeasurements.height()))
            
    def resizeEvent(self, event):
        if self._stepbox is None:
           return
        if self._orientation == Qt.Orientation.Vertical:
            label_height = self._label.sizeHint().height()
            number_height = self._stepbox.sizeHint().height()
            self._label.setGeometry(0, 0, self.width(), label_height)
            self._stepbox.setGeometry(0, self.height() - number_height, self.width(), number_height)
            self._vertical_slider.setGeometry(0, label_height, self.width(), self.height() - label_height - number_height - 5)
        else: #horizontal
            label_width = self._label.sizeHint().width()
            number_width = self._spinboxMeasurements.width()
            self._label.setGeometry(0, 0, label_width, self.height())
            self._stepbox.setGeometry(self.width() - number_width, 0, number_width, self.height())
            self._horizontal_slider.setGeometry(label_width, 0, self.width() - label_width - number_width - 5, self.height())

    def set_orientation(self, orientation):
        if self._orientation == orientation:
            return
        self._orientation = orientation
        if self._orientation == Qt.Orientation.Vertical:
            self._horizontal_slider.setVisible(False)
            self._vertical_slider.setVisible(True)
            self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Ignored))
        else: #horizontal
            self._horizontal_slider.setVisible(True)
            self._vertical_slider.setVisible(False)
            self.setSizePolicy(QSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed))
        self._label.set_orientation(orientation)
        self.update()

    def _on_slider_change(self, new_value):
        if self._key is None:
            return
        self._config.set(self._key, (float(new_value) / 100) if self._float_mode else new_value,
                inner_key=self._inner_key)
        self.resizeEvent(None)
