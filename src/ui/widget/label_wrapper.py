"""
Convenience class for adding labels to the left of arbitrary widgets.
"""
from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout


class LabelWrapper(QWidget):
    """Displays label text to the left of some arbitrary widget."""

    def __init__(self, widget: QWidget, text: str) -> None:
        super().__init__()
        layout = QHBoxLayout()
        self.setLayout(layout)
        self.label = QLabel(text)
        layout.addWidget(self.label)
        self.widget = widget
        layout.addWidget(widget)
