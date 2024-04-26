from PyQt5.QtWidgets import QSpinBox, QDoubleSpinBox, QLineEdit, QCheckBox, QComboBox, QPlainTextEdit, QHBoxLayout, QLabel
from PyQt5.QtGui import QTextCursor, QFont, QFontMetrics
from ui.widget.big_int_spinbox import BigIntSpinbox

"""
Creates UI input components linked to inpainting.data_model.config values.
- Initial component values are read from config.
- Changes to the component update the corresponding config value.
- Changes to the config value are applied to the input (if necessary).
"""

def connectedSpinBox(parent, config, key, minKey=None, maxKey=None, stepSizeKey=None):
    initialValue = config.get(key)
    spinBox = QDoubleSpinBox(parent) if type(initialValue) is float else BigIntSpinbox(parent)
    if (initialValue < spinBox.minimum() or initialValue > spinBox.maximum()):
        spinBox.setRange(min(spinBox.minimum(), initialValue), max(spinBox.maximum(), initialValue))
    minWidth = spinBox.sizeHint().width()
    spinBox.setValue(initialValue)
    if stepSizeKey is not None:
        step = config.get(stepSizeKey)
        spinBox.setSingleStep(step)
        config.connect(spinBox, stepSizeKey, lambda newVal: spinBox.setSingleStep(newVal))
    def applyChangeToSpinbox(newValue):
        if spinBox.value() != newValue:
            spinBox.setValue(newValue)
    config.connect(spinBox, key, lambda newValue: spinBox.setValue(newValue))
    def applyChangeToConfig(newValue):
        numValue = int(newValue) if type(initialValue) is int else float(newValue)
        if config.get(key) != numValue:
            config.set(key, numValue)
    spinBox.valueChanged.connect(applyChangeToConfig)
    if maxKey is not None:
        minVal = 0 if minKey is None else config.get(minKey)
        maxVal = config.get(maxKey)
        spinBox.setRange(minVal, maxVal)
        if minKey is not None:
            config.connect(spinBox, minKey, lambda newMin: spinBox.setRange(newMin, spinBox.maximum())) 
        config.connect(spinBox, maxKey, lambda newMax: spinBox.setRange(spinBox.minimum(), newMax))
    font = QFont()
    font.setPointSize(config.get("fontPointSize"))
    longestStr = str(initialValue if maxKey is None else config.get(maxKey))
    if type(initialValue) is float and "." not in longestStr:
        longestStr += ".00"
    minSize = QFontMetrics(font).boundingRect(longestStr).size()
    minSize.setWidth(minSize.width() + minWidth)
    spinBox.setMinimumSize(minSize)
    return spinBox

def connectedTextEdit(parent, config, key, multiLine=False):
    textEdit = QLineEdit(config.get(key), parent) if not multiLine else QPlainTextEdit(config.get(key), parent)
    if multiLine:
        textEdit.textChanged.connect(lambda: config.set(key, textEdit.toPlainText()))
        def setText(newText):
            if newText != textEdit.toPlainText():
                textEdit.setPlainText(newText)
        config.connect(textEdit, key, setText)
    else:
        textEdit.textChanged.connect(lambda newContent: config.set(key, newContent))
        def setText(newText):
            if newText != textEdit.text():
                textEdit.setText(newText)
        config.connect(textEdit, key, setText)
    return textEdit

def connectedCheckBox(parent, config, key, text=None, tooltip=None):
    checkBox = QCheckBox(parent)
    checkBox.setChecked(config.get(key))
    checkBox.stateChanged.connect(lambda isChecked: config.set(key, bool(isChecked)))
    config.connect(checkBox, key, lambda isChecked: checkBox.setChecked(bool(isChecked)))
    if text is not None:
        checkBox.setText(text)
    if tooltip is not None:
        checkBox.setToolTip(tooltip)
    return checkBox

def connectedComboBox(parent, config, key, text=None):
    comboBox = QComboBox(parent)
    options = config.getOptions(key)
    for option in options:
        comboBox.addItem(option)
    defaultValue = config.get(key)
    comboBox.setCurrentIndex(options.index(defaultValue))
    def updateConfigValue(index):
        value = comboBox.itemText(index)
        config.set(key, value)
    comboBox.currentIndexChanged.connect(updateConfigValue)
    config.connect(comboBox, key, lambda newValue: comboBox.setCurrentIndex(options.index(newValue)))
    if text is not None:
        label = QLabel(text)
        layout = QHBoxLayout()
        layout.addWidget(label)
        layout.addWidget(comboBox)
        return comboBox, layout
    else:
        return comboBox
