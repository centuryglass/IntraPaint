"""Previews the current color, supporting drag and drop."""

from typing import Optional

from PySide6.QtCore import Signal, QPoint, QMimeData, QSize
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QMouseEvent, Qt, QPixmap, QDrag, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QFrame, QApplication, QSizePolicy

from src.ui.widget.color_picker.palette_widget import CELL_WIDTH, NUM_COLUMNS, CELL_HEIGHT


class ColorShowLabel(QFrame):
    """Previews the current color, supporting drag and drop."""

    color_dropped = Signal(QColor)

    def __init__(self) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.Panel)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setAcceptDrops(True)
        self._mouse_pressed = False
        self._color = QColor()
        self._mouse_pos: Optional[QPoint] = None

    @property
    def color(self) -> QColor:
        """Access the displayed color."""
        return QColor(self._color)

    @color.setter
    def color(self, color: QColor) -> None:
        if color != self.color:
            self._color = color
            self.update()

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draw the color preview."""
        painter = QPainter(self)
        self.drawFrame(painter)
        painter.fillRect(self.contentsRect(), self._color)

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Keep track of click positions."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.LeftButton:
            self._mouse_pressed = True
            self._mouse_pos = event.pos()

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Handle color value drag and drop."""
        assert event is not None
        if not self._mouse_pressed:
            return
        assert self._mouse_pos is not None
        if (self._mouse_pos - event.pos()).manhattanLength() > QApplication.startDragDistance():
            mime_data = QMimeData()
            mime_data.setColorData(self._color)
            drag_pixmap = QPixmap(30, 20)
            drag_pixmap.fill(self._color)
            painter = QPainter(drag_pixmap)
            painter.drawRect(0, 0, drag_pixmap.width() - 1, drag_pixmap.height() - 1)
            painter.end()
            drag = QDrag(self)
            drag.setMimeData(mime_data)
            drag.setPixmap(drag_pixmap)
            self._mouse_pressed = False
            drag.exec(Qt.DropAction.CopyAction)

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Clear mouse state on mouse release."""
        self._mouse_pressed = False
        self._mouse_pos = None

    def dragEnterEvent(self, event: Optional[QDragEnterEvent]) -> None:
        """Accept drag events that contain color data."""
        assert event is not None
        mime_data = event.mimeData()
        if mime_data.hasColor():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: Optional[QDropEvent]) -> None:
        """Apply dropped color data."""
        assert event is not None
        color = QColor(event.mimeData().colorData())
        if color.isValid():
            self._color = color
            self.repaint()
            self.color_dropped.emit(color)
            event.accept()
        else:
            event.ignore()


class PaletteColorShowLabel(ColorShowLabel):
    """ColorShowLabel sized for palette previews."""

    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:
        """Sized to match a single palette widget row."""
        return QSize(CELL_WIDTH * NUM_COLUMNS, CELL_HEIGHT)
