"""Tab that can be dragged between TabBox widgets."""
import datetime
from typing import Optional

from PySide6.QtCore import Signal, Qt, QMimeData
from PySide6.QtGui import QPalette, QMouseEvent, QDrag
from PySide6.QtWidgets import QWidget, QFrame

from src.config.application_config import AppConfig
from src.ui.widget.label import Label


SECONDS_UNTIL_DRAG_START = 0.3


class Tab(Label):
    """Tab label that can be dragged between CollapsibleBox widgets."""

    clicked = Signal(QWidget)
    double_clicked = Signal(QWidget)
    tab_content_replaced = Signal(QWidget, QWidget)

    def __init__(self, text: str, widget: Optional[QWidget] = None) -> None:
        super().__init__(text, size=AppConfig().get(AppConfig.TAB_FONT_POINT_SIZE))
        self.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Plain)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Mid, palette.color(self.foregroundRole()))
        self.setPalette(palette)
        self._widget: Optional[QWidget] = widget
        self._container: Optional[QWidget] = None
        self._clicking = False
        self._dragging = False
        self._click_time = 0.0

    @property
    def content_widget(self):
        """Return's the tab's associated widget"""
        return self._widget

    @content_widget.setter
    def content_widget(self, widget: Optional[QWidget]):
        if widget == self._widget:
            return
        self._widget = widget
        self.tab_content_replaced.emit(self, widget)

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        super().set_orientation(orientation)
        if not hasattr(self, '_widget'):
            return
        if self._widget is not None and hasattr(self._widget, 'set_orientation'):
            self._widget.set_orientation(orientation)

    def mouseDoubleClickEvent(self, event: Optional[QMouseEvent]) -> None:
        """Send the double-click signal on left-click."""
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self)

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Prepare to activate or drag on click."""
        assert event is not None
        self._dragging = False
        self._clicking = event.buttons() == Qt.MouseButton.LeftButton
        self._click_time = datetime.datetime.now().timestamp()

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Allow click and drag."""
        assert event is not None
        click_duration = datetime.datetime.now().timestamp() - self._click_time
        if self._clicking and click_duration > SECONDS_UNTIL_DRAG_START:
            self._dragging = True
            drag = QDrag(self)
            drag.setMimeData(QMimeData())
            if self._image is not None:
                drag.setPixmap(self._image)
            self.set_inverted(True)
            drag.exec(Qt.DropAction.MoveAction)
            self.set_inverted(False)
            self._clicking = False
            self._click_time = 0.0

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Send the click signal if the tab was clicked and the widget wasn't dragged."""
        if self._clicking and not self._dragging:
            self.clicked.emit(self)
        self._clicking = False
        self._dragging = False
