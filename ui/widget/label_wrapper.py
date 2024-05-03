"""
Convenience function for adding labels to the left of arbitrary widgets.
"""
from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout

class LabelWrapper(QWidget):

    def __init__(self, widget, text):
        super().__init__()
        layout = QHBoxLayout()
        self.setLayout(layout)
        self.label = QLabel(text)
        layout.addWidget(self.label)
        self.widget = widget
        layout.addWidget(widget)
