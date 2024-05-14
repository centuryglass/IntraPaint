"""
Provides an extended QSlider widget with integrated data_model/config connection.
"""
from PyQt5.QtWidgets import QWidget, QSlider, QSizePolicy
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QFontMetrics
from ui.config_control_setup import connected_spinbox
from ui.widget.label import Label

class ParamSlider(QWidget):
    """ParamSlider is an extended QSlider widget with integrated data_model/config connection."""

    def __init__(self,
            parent,
            label_text,
            config,
            key,
            min_val=None,
            max_val=None,
            step_val=None,
            inner_key=None,
            orientation=Qt.Orientation.Horizontal,
            vertical_text_pt=None):
        """Initializes the slider, setting connected config property and other settings.

        Parameters
        ----------
        parent : QWidget, optional
            Optional parent widget.
        label_text : str
            Displayed label text.
        config : data_model.Config
            Config object used to connect a property to the slider.
        key : str
            Initial config value key.
        min_val : int or float, optional
            Optional initial minimum value. If not provided, attempts to use the minimum associated with the config
            key.
        max_val : int or float, optional
            Optional initial maximum value. If not provided, attempts to use the maximum associated with the config
            key.
        step_val : int or float, optional
            Optional initial step value. If not provided, attempts to use the step value associated with the config
            key.
        inner_key : str, optional
            Inner config key, to be provided when linking the widget to an inner property of a dict config value.
        orientation : Qt.Orientation, default=Horizontal
            Whether the slider is vertical or horizontal
        vertical_text_pt : int, optional
            Optional alternate font size to use when the slider is in vertical mode.
        """
        super().__init__(parent)
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
        self._horizontal_slider.valueChanged.connect(self._on_slider_change)
        self._vertical_slider.valueChanged.connect(self._on_slider_change)

        font = QFont()
        font.setPointSize(config.get("font_point_size"))
        self._spinbox_measurements = QFontMetrics(font).boundingRect("9999").size() * 1.5
        self._stepbox = None
        if key is not None:
            self.connect_key(key, min_val, max_val, step_val, inner_key)
        self.set_orientation(orientation)


    def disconnect_config(self):
        """Disconnects the slider from any config values."""
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


    def connect_key(self, key, min_val=None, max_val=None, step_val=None, inner_key=None):
        """Connects the slider to a new config value.

        Parameters
        ----------
        key : str
            Initial config value key.
        min_val : int or float, optional
            Optional initial minimum value. If not provided, attempts to use the minimum associated with the config
            key.
        max_val : int or float, optional
            Optional initial maximum value. If not provided, attempts to use the maximum associated with the config
            key.
        step_val : int or float, optional
            Optional initial step value. If not provided, attempts to use the step value associated with the config
            key.
        inner_key : str, optional
            Inner config key, to be provided when linking the widget to an inner property of a dict config value.
        """
        if self._key == key and self._inner_key == key:
            return
        self.disconnect_config()
        self._key = key
        self._inner_key = inner_key
        if inner_key is None:
            self._label.setText(self._config.get_label(key))
            self.setToolTip(self._config.get_tooltip(key))
        initial_value = self._config.get(key, inner_key)
        self._float_mode = isinstance(initial_value, float)
        min_val = self._config.get(key, inner_key="min") if min_val is None else min_val
        max_val = self._config.get(key, inner_key="max") if max_val is None else max_val

        full_range = max_val - min_val
        tick_interval = 1 if (full_range < 20) else (5 if full_range < 50 else 10)
        if self._float_mode:
            tick_interval *= 100
        step = self._config.get(key, inner_key="step") if step_val is None else step_val
        for slider in (self._horizontal_slider, self._vertical_slider):
            slider.setMinimum(int(min_val * 100) if self._float_mode else min_val)
            slider.setMaximum(int(max_val * 100) if self._float_mode else max_val)
            slider.setSingleStep(int(step * 100) if self._float_mode else step)
            slider.setValue(int(initial_value * 100) if self._float_mode else initial_value)
            slider.setTickInterval(tick_interval)
        def on_config_change(new_value):
            if new_value is None:
                return
            value = int(new_value * 100) if self._float_mode else new_value
            if value != self._horizontal_slider.value():
                self._horizontal_slider.setValue(value)
            if value != self._vertical_slider.value():
                self._vertical_slider.setValue(value)
        self._config.connect(self, key, on_config_change, inner_key)
        self._stepbox = connected_spinbox(self, self._config, self._key, min_val=min_val, max_val=max_val,
            step_val=step, dict_key=inner_key)
        self.resizeEvent(None)
        self._stepbox.show()


    def sizeHint(self):
        """Returns ideal widget size based on contents."""
        if self._orientation == Qt.Orientation.Vertical:
            return QSize(max(self._vertical_slider.sizeHint().width(),
                        self._label.sizeHint().width(),
                        self._spinbox_measurements.width()),
                    self._vertical_slider.sizeHint().height() + self._label.sizeHint().height() + \
                    self._spinbox_measurements.height())
        #horizontal
        return QSize(self._horizontal_slider.sizeHint().width() + self._label.sizeHint().width() + \
                self._spinbox_measurements.width(), \
                max(self._horizontal_slider.sizeHint().height(),
                    self._label.sizeHint().height(),
                    self._spinbox_measurements.height()))


    def resizeEvent(self, unused_event):
        """Recalculates slider geometry when the widget size changes."""
        if self._stepbox is None:
            return
        if self._orientation == Qt.Orientation.Vertical:
            label_height = self._label.sizeHint().height()
            number_height = self._stepbox.sizeHint().height()
            self._label.setGeometry(0, 0, self.width(), label_height)
            self._stepbox.setGeometry(0, self.height() - number_height, self.width(), number_height)
            self._vertical_slider.setGeometry(0, label_height, self.width(),
                    self.height() - label_height - number_height - 5)
        else: #horizontal
            label_width = self._label.sizeHint().width()
            number_width = self._spinbox_measurements.width()
            self._label.setGeometry(0, 0, label_width, self.height())
            self._stepbox.setGeometry(self.width() - number_width, 0, number_width, self.height())
            self._horizontal_slider.setGeometry(label_width, 0, self.width() - label_width - number_width - 5,
                    self.height())


    def set_orientation(self, orientation):
        """Sets vertical or horizontal orientation."""
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
        """Handle slider value changes."""
        if self._key is None:
            return
        self._config.set(self._key, (float(new_value) / 100) if self._float_mode else new_value,
                inner_key=self._inner_key)
        self.resizeEvent(None)
