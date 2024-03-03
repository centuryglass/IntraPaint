from PyQt5.QtWidgets import QWidget, QSlider, QLabel, QHBoxLayout, QVBoxLayout
from PyQt5.QtCore import Qt
from ui.config_control_setup import connectedSpinBox
from ui.widget.vertical_label import VerticalLabel

class ParamSlider(QWidget):
    def __init__(self,
            parent,
            labelText,
            config,
            key,
            minKey,
            maxKey,
            stepKey=None,
            orientation=Qt.Orientation.Horizontal,
            verticalTextPt=None):
        super().__init__(parent)
        isHorizontal = (orientation == Qt.Orientation.Horizontal)
        layout = QHBoxLayout() if isHorizontal else QVBoxLayout()
        self.setLayout(layout)

        label = QLabel(labelText) if isHorizontal else VerticalLabel(labelText, config, size=verticalTextPt)
        layout.addWidget(label, stretch=1, alignment=Qt.AlignCenter)
        initialVal = config.get(key)
        minVal = config.get(minKey)
        maxVal = config.get(maxKey)
        step = 1 if stepKey is None else config.get(stepKey)
        self._floatMode = (type(initialVal) is float)

        slider = QSlider(orientation, self)
        slider.setMinimum(int(minVal * 100) if self._floatMode else minVal)
        slider.setMaximum(int(maxVal * 100) if self._floatMode else maxVal)
        slider.setSingleStep(int(step * 100) if self._floatMode else step)
        slider.setValue(int(initialVal * 100) if self._floatMode else initialVal)
        slider.setTickPosition(QSlider.TickPosition.TicksAbove if isHorizontal else QSlider.TickPosition.TicksRight)
        fullRange = maxVal - minVal
        tickInterval = 1 if (fullRange < 20) else (5 if fullRange < 50 else 10)
        if self._floatMode:
            tickInterval *= 100
        slider.setTickInterval(tickInterval)
        def onConfigChange(newValue):
            slider.setValue((int(newValue * 100)) if self._floatMode else newValue)
        config.connect(slider, key, onConfigChange)
        def onSliderChange(newValue):
            config.set(key, (float(newValue) / 100) if self._floatMode else newValue)
        slider.valueChanged.connect(onSliderChange)
        layout.addWidget(slider, stretch=10)

        if isHorizontal:
            stepBox = connectedSpinBox(self, config, key, minKey, maxKey, stepKey)
            layout.addWidget(stepBox, stretch=1, alignment = Qt.AlignCenter)
        else:
            numberText = str(config.get(key))
            stepLabel = VerticalLabel(numberText, config, size=verticalTextPt)
            def onValueChange(newValue):
                stepLabel.setText(str(newValue))
            config.connect(stepLabel, key, onValueChange)
            layout.addWidget(stepLabel, stretch=1, alignment = Qt.AlignCenter)

        layout.setContentsMargins(0,0,0,0)
