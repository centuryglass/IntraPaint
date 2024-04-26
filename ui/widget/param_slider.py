from PyQt5.QtWidgets import QWidget, QSlider, QLabel, QSizePolicy
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QFontMetrics
from ui.config_control_setup import connectedSpinBox
from ui.widget.label import Label

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
        isVertical = (orientation == Qt.Orientation.Vertical)

        self._key = None
        self._floatMode = None
        self._orientation = None
        self._config = config

        self._label = Label(labelText, config, self, size=verticalTextPt, orientation=orientation)
        self._hSlider = QSlider(Qt.Orientation.Horizontal, self)
        self._vSlider = QSlider(Qt.Orientation.Vertical, self)

        self._hSlider.setTickPosition(QSlider.TickPosition.TicksAbove)
        self._vSlider.setTickPosition(QSlider.TickPosition.TicksRight)
        self._hSlider.valueChanged.connect(lambda newValue: self._onSliderChange(newValue))
        self._vSlider.valueChanged.connect(lambda newValue: self._onSliderChange(newValue))

        font = QFont()
        font.setPointSize(config.get("fontPointSize"))
        self._spinboxMeasurements = QFontMetrics(font).boundingRect("9999").size() * 1.5
        
        numberText = str(config.get(key))
        self._stepBox = None
        self.connectKey(key, minKey, maxKey, stepKey)
        self.setOrientation(orientation)

    def connectKey(self, key, minKey, maxKey, stepKey):
        if self._key == key:
            return
        if self._key is not None:
            self._config.disconnect(self, self._key)
            try:
                self._stepBox.valueChanged.disconnect()
            except TypeError:
                pass
        lastKey = self._key
        self._key = key
        initialVal = self._config.get(key)
        self._floatMode = (type(initialVal) is float)
        minVal = self._config.get(minKey)
        maxVal = self._config.get(maxKey)
        fullRange = maxVal - minVal
        tickInterval = 1 if (fullRange < 20) else (5 if fullRange < 50 else 10)
        if self._floatMode:
            tickInterval *= 100
        step = 1 if stepKey is None else self._config.get(stepKey)

        for slider in (self._hSlider, self._vSlider):
            slider.setMinimum(int(minVal * 100) if self._floatMode else minVal)
            slider.setMaximum(int(maxVal * 100) if self._floatMode else maxVal)
            slider.setSingleStep(int(step * 100) if self._floatMode else step)
            slider.setValue(int(initialVal * 100) if self._floatMode else initialVal)
            slider.setTickInterval(tickInterval)
        def onConfigChange(newValue):
            self._hSlider.setValue((int(newValue * 100)) if self._floatMode else newValue)
            self._vSlider.setValue((int(newValue * 100)) if self._floatMode else newValue)
        self._config.connect(self, key, onConfigChange)
        if self._stepBox is not None:
            stepBox = self._stepBox
            self._config.disconnect(stepBox, lastKey)
            stepBox.setParent(None)
            self._stepBox = None
            stepBox.deleteLater()
        self._stepBox = connectedSpinBox(self, self._config, key, minKey, maxKey, stepKey)
        self.resizeEvent(None)
        self._stepBox.show()

    def sizeHint(self):
        if self._orientation == Qt.Orientation.Vertical:
            return QSize(max(self._vSlider.sizeHint().width(), self._label.sizeHint().width(), self._spinboxMeasurements.width()),\
                    self._vSlider.sizeHint().height() + self._label.sizeHint().height() + self._spinboxMeasurements.height())
        else: #horizontal
            return QSize(self._hSlider.sizeHint().width() + self._label.sizeHint().width() + self._spinboxMeasurements.width(), \
                    max(self._hSlider.sizeHint().height(), self._label.sizeHint().height(), self._spinboxMeasurements.height()))
            
    def resizeEvent(self, event):
        if self._stepBox is None:
           return
        if self._orientation == Qt.Orientation.Vertical:
            labelHeight = self._label.sizeHint().height()
            numberHeight = self._stepBox.sizeHint().height()
            self._label.setGeometry(0, 0, self.width(), labelHeight)
            self._stepBox.setGeometry(0, self.height() - numberHeight, self.width(), numberHeight)
            self._vSlider.setGeometry(0, labelHeight, self.width(), self.height() - labelHeight - numberHeight - 5)
        else: #horizontal
            labelWidth = self._label.sizeHint().width()
            numberWidth = self._spinboxMeasurements.width()
            self._label.setGeometry(0, 0, labelWidth, self.height())
            self._stepBox.setGeometry(self.width() - numberWidth, 0, numberWidth, self.height())
            self._hSlider.setGeometry(labelWidth, 0, self.width() - labelWidth - numberWidth - 5, self.height())

    def setOrientation(self, orientation):
        if self._orientation == orientation:
            return
        self._orientation = orientation
        if self._orientation == Qt.Orientation.Vertical:
            self._hSlider.setVisible(False)
            self._vSlider.setVisible(True)
            self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Ignored))
        else: #horizontal
            self._hSlider.setVisible(True)
            self._vSlider.setVisible(False)
            self.setSizePolicy(QSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed))
        self._label.setOrientation(orientation)
        self.update()

    def _onSliderChange(self, newValue):
        if self._key is None:
            return
        self._config.set(self._key, (float(newValue) / 100) if self._floatMode else newValue)
        self.resizeEvent(None)
