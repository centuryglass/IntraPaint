"""A label widget with connected content, to be displayed in a tabbed interface.

Tabs have the following properties:
- Tabs contain a Label, so they may show a short piece of text and an icon, and their orientation can change.
- Every tab has an associated content widget, to be displayed in whatever container is holding the tab.
- Tabs optionally may have any number of tab bar widgets, to be displayed only when the content widget is hidden.
- Tabs can be dragged, but it is up to the containing class to handle accepting the tab, moving it, and moving its
  associated widgets.
"""
import datetime
from typing import Optional, List

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
    tab_bar_widget_added = Signal(QWidget)
    tab_bar_widget_removed = Signal(QWidget)
    tab_bar_widget_order_changed = Signal()

    def __init__(self, text: str, widget: Optional[QWidget] = None) -> None:
        super().__init__(text, size=AppConfig().get(AppConfig.TAB_FONT_POINT_SIZE))
        self.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Plain)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Mid, palette.color(self.foregroundRole()))
        self.setPalette(palette)
        self._content_widget: Optional[QWidget] = widget
        self._tab_bar_widgets: List[QWidget] = []
        self._container: Optional[QWidget] = None
        self._clicking = False
        self._dragging = False
        self._click_time = 0.0
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)

    @property
    def content_widget(self):
        """Return's the tab's associated widget"""
        return self._content_widget

    @content_widget.setter
    def content_widget(self, widget: Optional[QWidget]):
        if widget == self._content_widget:
            return
        self._content_widget = widget
        self.tab_content_replaced.emit(self, widget)

    @property
    def tab_bar_widgets(self) -> List[QWidget]:
        """Returns the list of widgets this tab provides that should be displayed on the tab bar when the content
           widget is hidden."""
        return list(self._tab_bar_widgets)

    def add_tab_bar_widget(self, widget: QWidget, index: Optional[int] = None) -> None:
        """Adds a new widget to the list of tab bar widgets."""
        if widget in self._tab_bar_widgets:
            return
        if index is None:
            index = len(self._tab_bar_widgets)
        self._tab_bar_widgets.insert(index, widget)
        self.tab_bar_widget_added.emit(widget)

    def remove_tab_bar_widget(self, widget: QWidget) -> None:
        """Removes a widget from the list of tab bar widgets."""
        if widget not in self._tab_bar_widgets:
            return
        self._tab_bar_widgets.remove(widget)
        self.tab_bar_widget_removed.emit(widget)

    def move_tab_bar_widget(self, widget: QWidget, index: int) -> None:
        """Updates the index of a tab bar widget."""
        assert widget in self._tab_bar_widgets
        current_index = self._tab_bar_widgets.index(widget)
        if index in (current_index, current_index + 1):
            return
        if index > current_index:
            index -= 1
        self._tab_bar_widgets.remove(widget)
        self._tab_bar_widgets.insert(index, widget)
        self.tab_bar_widget_order_changed.emit()

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        super().set_orientation(orientation)
        if not hasattr(self, '_widget'):
            return
        if self._content_widget is not None and hasattr(self._content_widget, 'set_orientation'):
            self._content_widget.set_orientation(orientation)

    def mouseDoubleClickEvent(self, event: Optional[QMouseEvent]) -> None:
        """Send the double click signal on left-click."""
        assert event is not None
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
