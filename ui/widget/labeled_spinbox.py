from PyQt5.QtWidgets import QWidget, QDialog, QDoubleSpinBox, QLabel, QHBoxLayout
from ui.widget.big_int_spinbox import BigIntSpinbox

class LabeledSpinbox(QWidget):

    def __init__(self, parent, labelText, toolTip, minVal, defaultVal, maxVal):
        super().__init__(parent)
        self.setToolTip(toolTip)
        self.layout = QHBoxLayout()
        self.label = QLabel(self)
        self.label.setText(labelText)
        self.spinbox = QDoubleSpinBox(self) if type(defaultVal) is float else BigIntSpinbox(self)
        self.spinbox.setRange(minVal, maxVal)
        self.spinbox.setValue(defaultVal)
        self.layout.addWidget(self.label, 1)
        self.layout.addWidget(self.spinbox, 2)
        self.setLayout(self.layout)
