"""Control panel widget for the blur tool."""
from PySide6.QtWidgets import QWidget, QApplication

from src.image.mypaint.mypaint_brush import MyPaintBrush

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.draw_tool_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


class BlurToolPanel(QWidget):
    """Control panel widget for the blur tool."""

    def __init__(self, blur_brush: MyPaintBrush) -> None:
        super().__init__()
