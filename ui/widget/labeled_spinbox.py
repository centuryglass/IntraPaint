"""
Minimal wrapper class for creating a labeled spinbox widget.
"""
from PyQt5.QtWidgets import QWidget, QDialog, QDoubleSpinBox, QLabel, QHBoxLayout
from ui.widget.big_int_spinbox import BigIntSpinbox

class LabeledSpinbox(QWidget):

    def __init__(self, parent, label_text, tooltip, min_value, default_value, max_value):
        super().__init__(parent)
        self.setToolTip(tooltip)
        self.layout = QHBoxLayout()
        self.label = QLabel(self)
        self.label.setText(label_text)
        self.spinbox = QDoubleSpinBox(self) if type(default_value) is float else BigIntSpinbox(self)
        self.spinbox.setRange(min_value, max_value)
        self.spinbox.setValue(default_value)
        self.layout.addWidget(self.label, 1)
        self.layout.addWidget(self.spinbox, 2)
        self.setLayout(self.layout)
