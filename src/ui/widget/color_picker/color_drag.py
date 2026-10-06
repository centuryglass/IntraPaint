"""Drags that carry a color as `QMimeData` color data, shared by the color widgets that send and accept them."""
from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QColor, QDrag, QDragEnterEvent, QPixmap
from PySide6.QtWidgets import QWidget

DRAG_PIXMAP_SIZE = 24


def start_color_drag(source: QWidget, color: QColor, actions: Qt.DropAction = Qt.DropAction.CopyAction) -> None:
    """Starts a drag carrying a color, shown as a swatch under the cursor. Returns once the drag ends."""
    mime_data = QMimeData()
    mime_data.setColorData(color)
    pixmap = QPixmap(DRAG_PIXMAP_SIZE, DRAG_PIXMAP_SIZE)
    pixmap.fill(color)
    drag = QDrag(source)
    drag.setMimeData(mime_data)
    drag.setPixmap(pixmap)
    drag.exec(actions, Qt.DropAction.CopyAction)


def accept_color_drag_enter(event: QDragEnterEvent) -> None:
    """Accepts a drag entering a widget if it carries a color, and ignores it otherwise."""
    if event.mimeData().hasColor():
        event.acceptProposedAction()
    else:
        event.ignore()
