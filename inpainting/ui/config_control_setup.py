from PyQt5.QtWidgets import QSpinBox, QDoubleSpinBox, QLineEdit, QCheckBox

"""
Creates UI input components linked to inpainting.data_model.config values.
- Initial component values are read from config.
- Changes to the component update the corresponding config value.
- Changes to the config value are applied to the input (if necessary).
"""

def connectedSpinBox(parent, config, key, minKey=None, maxKey=None, stepSizeKey=None):
    initialValue = config.get(key)
    spinBox = QDoubleSpinBox(parent) if type(initialValue) is float else QSpinBox(parent)
    spinBox.setValue(initialValue)
    if stepSizeKey is not None:
        step = config.get(stepSizeKey)
        spinBox.setSingleStep(step)
        config.connect(spinBox, stepSizeKey, lambda newVal: spinBox.setSingleStep(newVal))
    def applyChangeToSpinbox(newValue):
        if spinBox.value() != newValue:
            spinBox.setValue(newValue)
    config.connect(spinBox, key, lambda newValue: spinBox.setValue(newValue))
    spinBox.valueChanged.connect(lambda newValue: config.set(key, newValue))
    if maxKey is not None:
        minVal = 0 if minKey is None else config.get(minKey)
        maxVal = config.get(maxKey)
        spinBox.setRange(minVal, maxVal)
        if minKey is not None:
            config.connect(spinBox, minKey, lambda newMin: spinBox.setRange(newMin, spinBox.maximum())) 
        config.connect(spinBox, maxKey, lambda newMax: spinBox.setRange(spinBox.minimum(), newMax))
    return spinBox

def connectedLineEdit(parent, config, key):
    lineEdit = QLineEdit(config.get(key), parent)
    lineEdit.textChanged.connect(lambda newValue: config.set(key, newValue))
    return lineEdit

def connectedCheckBox(parent, config, key):
    checkBox = QCheckBox(parent)
    checkBox.setChecked(config.get(key))
    checkBox.stateChanged.connect(lambda isChecked: config.set(key, bool(isChecked)))
    config.connect(checkBox, key, lambda isChecked: checkBox.setChecked(bool(isChecked)))
    return checkBox
