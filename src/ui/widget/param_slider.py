"""
Provides an extended QSlider widget with integrated Config value connection.
"""
from typing import Optional
import logging
from PyQt5.QtWidgets import QWidget, QSlider, QSizePolicy, QDoubleSpinBox
from PyQt5.QtCore import Qt, QSize, QEvent
from PyQt5.QtGui import QFont, QFontMetrics
from src.ui.config_control_setup import connected_spinbox
from src.ui.widget.label import Label
from src.ui.widget.big_int_spinbox import BigIntSpinbox
from src.config.application_config import AppConfig

logger = logging.getLogger(__name__)


class ParamSlider(QWidget):
    """ParamSlider is an extended QSlider widget with integrated data_model/config connection."""

    def __init__(self,
                 parent: Optional[QWidget],
                 label_text: Optional[str],
                 key: str,
                 min_val: Optional[int | float] = None,
                 max_val: Optional[int | float] = None,
                 step_val: Optional[int | float] = None,
                 inner_key: Optional[str] = None,
                 orientation: Qt.Orientation = Qt.Orientation.Horizontal,
                 vertical_text_pt: Optional[int] = None) -> None:
        """Initializes the slider, setting connected config property and other settings.

        Parameters
        ----------
        parent : QWidget, optional
            Parent widget.
        label_text : str
            Displayed label text.
        key : str
            Initial config value key.
        min_val : int or float, optional
            Initial minimum value. If not provided, attempts to use the minimum associated with the config key.
        max_val : int or float, optional
            Initial maximum value. If not provided, attempts to use the maximum associated with the config key.
        step_val : int or float, optional
            Initial step value. If not provided, attempts to use the step value associated with the config key.
        inner_key : str, optional
            Inner config key, to be provided when linking the widget to an inner property of a dict config value.
        orientation : Qt.Orientation, default=Horizontal
            Whether the slider is vertical or horizontal
        vertical_text_pt : int, optional
            Alternate font size to use when the slider is in vertical mode.
        """
        super().__init__(parent)
        self._key: Optional[str] = None
        self._inner_key: Optional[str] = None
        self._float_mode: Optional[bool] = None
        self._orientation: Optional[Qt.Orientation] = None
        self._step_box: Optional[BigIntSpinbox | QDoubleSpinBox] = None
        config = AppConfig.instance()

        self._label_text = None
        if label_text is not None:
            self._label: Optional[Label] = Label(label_text, self, size=vertical_text_pt, orientation=orientation)
            if label_text != config.get_label(key):
                self._label_text = label_text
        else:
            self._label = None
        self._horizontal_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._vertical_slider = QSlider(Qt.Orientation.Vertical, self)

        self._horizontal_slider.setTickPosition(QSlider.TickPosition.TicksAbove)
        self._vertical_slider.setTickPosition(QSlider.TickPosition.TicksRight)
        self._horizontal_slider.valueChanged.connect(self._on_slider_change)
        self._vertical_slider.valueChanged.connect(self._on_slider_change)

        font = QFont()
        font.setPointSize(config.get("font_point_size"))
        self._spinbox_measurements = QFontMetrics(font).boundingRect("9999").size() * 1.5
        if key is not None:
            self.connect_key(key, min_val, max_val, step_val, inner_key)
        self.set_orientation(orientation)

    def disconnect_config(self) -> None:
        """Disconnects the slider from any config values."""
        if self._key is not None:
            try:
                AppConfig.instance().disconnect(self, self._key)
            except KeyError as err:
                logger.error(f"Disconnecting slider from {self._key} failed: {err}")
            if self._step_box is not None:
                step_box = self._step_box
                try:
                    AppConfig.instance().disconnect(step_box, self._key)
                except KeyError as err:
                    logger.error(f"Disconnecting step box from {self._key} failed: {err}")
                step_box.valueChanged.disconnect()
                step_box.setParent(None)
                step_box.deleteLater()
            self._key = None
            self._inner_key = None

    def connect_key(self,
                    key: str,
                    min_val: Optional[int | float] = None,
                    max_val: Optional[int | float] = None,
                    step_val: Optional[int | float] = None,
                    inner_key: Optional[str] = None) -> None:
        """Connects the slider to a new config value.

        Parameters
        ----------
        key : str
            Initial config value key.
        min_val : int or float, optional
            Initial minimum value. If not provided, attempts to use the minimum associated with the config key.
        max_val : int or float, optional
            Initial maximum value. If not provided, attempts to use the maximum associated with the config key.
        step_val : int or float, optional
            Initial step value. If not provided, attempts to use the step value associated with the config key.
        inner_key : str, optional
            Inner config key, to be provided when linking the widget to an inner property of a dict config value.
        """
        if self._key == key and self._inner_key == key:
            return
        self.disconnect_config()
        self._key = key
        self._inner_key = inner_key
        config = AppConfig.instance()
        if inner_key is None:
            if self._label is not None and self._label_text is None:
                self._label.setText(config.get_label(key))
            self.setToolTip(config.get_tooltip(key))
        initial_value = config.get(key, inner_key)
        self._float_mode = isinstance(initial_value, float)
        min_val = config.get(key, inner_key="min") if min_val is None else min_val
        max_val = config.get(key, inner_key="max") if max_val is None else max_val

        full_range = max_val - min_val
        tick_interval = 1 if (full_range < 20) else (5 if full_range < 50 else 10)
        if self._float_mode:
            tick_interval *= 100
        step = config.get(key, inner_key="step") if step_val is None else step_val
        for slider in (self._horizontal_slider, self._vertical_slider):
            slider.setMinimum(int(min_val * 100) if self._float_mode else int(min_val))
            slider.setMaximum(int(max_val * 100) if self._float_mode else int(max_val))
            slider.setSingleStep(int(step * 100) if self._float_mode else int(step))
            slider.setValue(int(initial_value * 100) if self._float_mode else int(initial_value))
            slider.setTickInterval(tick_interval)

        def on_config_change(new_value: int | float) -> None:
            """Update the slider when the connected config value changes."""
            if new_value is None:
                return
            value = int(new_value * 100) if self._float_mode else int(new_value)
            if value != self._horizontal_slider.value():
                self._horizontal_slider.setValue(value)
            if value != self._vertical_slider.value():
                self._vertical_slider.setValue(value)

        AppConfig.instance().connect(self, key, on_config_change, inner_key)
        self._step_box = connected_spinbox(self, self._key, min_val=min_val, max_val=max_val, step_val=step,
                                           dict_key=inner_key)
        self.resizeEvent(None)
        self._step_box.show()

    def sizeHint(self) -> QSize:
        """Returns ideal widget size based on contents."""
        label_height = 0 if self._label is None else self._label.sizeHint().height()
        label_width = 0 if self._label is None else self._label.sizeHint().width()
        if self._orientation == Qt.Orientation.Vertical:
            return QSize(max(self._vertical_slider.sizeHint().width(), label_width, self._spinbox_measurements.width()),
                         self._vertical_slider.sizeHint().height() + label_height + self._spinbox_measurements.height())
        # horizontal
        return QSize(self._horizontal_slider.sizeHint().width() + label_width + self._spinbox_measurements.width(),
                     max(self._horizontal_slider.sizeHint().height(), label_height,
                         self._spinbox_measurements.height()))

    def resizeEvent(self, unused_event: Optional[QEvent]) -> None:
        """Recalculates slider geometry when the widget size changes."""
        if self._step_box is None:
            return
        if self._orientation == Qt.Orientation.Vertical:
            label_height = 0 if self._label is None else self._label.sizeHint().height()
            number_height = self._step_box.sizeHint().height()
            if self._label is not None:
                self._label.setGeometry(0, 0, self.width(), label_height)
            self._step_box.setGeometry(0, self.height() - number_height, self.width(), number_height)
            self._vertical_slider.setGeometry(0, label_height, self.width(),
                                              self.height() - label_height - number_height - 5)
        else:  # horizontal
            label_width = 0 if self._label is None else self._label.sizeHint().width()
            number_width = self._spinbox_measurements.width()
            if self._label is not None:
                self._label.setGeometry(0, 0, label_width, self.height())
            self._step_box.setGeometry(self.width() - number_width, 0, number_width, self.height())
            self._horizontal_slider.setGeometry(label_width, 0, self.width() - label_width - number_width - 5,
                                                self.height())

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Sets vertical or horizontal orientation."""
        if self._orientation == orientation:
            return
        self._orientation = orientation
        if self._orientation == Qt.Orientation.Vertical:
            self._horizontal_slider.setVisible(False)
            self._vertical_slider.setVisible(True)
            self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Ignored))
        else:  # horizontal
            self._horizontal_slider.setVisible(True)
            self._vertical_slider.setVisible(False)
            self.setSizePolicy(QSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed))
        if self._label is not None:
            self._label.set_orientation(orientation)
        self.update()

    def _on_slider_change(self, new_value: int) -> None:
        """Handle slider value changes."""
        if self._key is None:
            return
        AppConfig.instance().set(self._key, (float(new_value) / 100) if self._float_mode else new_value,
                                 inner_key=self._inner_key)
        self.resizeEvent(None)
