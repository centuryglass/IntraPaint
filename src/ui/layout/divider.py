"""Minimal horizontal or vertical divider widgets"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame


class Divider(QFrame):
    """Divider widget that can be initialized as horizontal or vertical."""

    def __init__(self, orientation: Qt.Orientation):
        super().__init__()
        self.setFrameShape(QFrame.Shape.HLine if orientation == Qt.Orientation.Horizontal else QFrame.Shape.VLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)
