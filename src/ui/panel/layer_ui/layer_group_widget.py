"""Represents an image layer group."""
from typing import Dict, Optional, List
import logging

from PySide6.QtCore import QPointF, QPoint, QLine, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent, QPaintEvent, QPainter, \
    QResizeEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget, QSizePolicy

from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_stack import LayerStack
from src.ui.panel.layer_ui.layer_widget import LayerWidget
from src.ui.layout.collapsible_box import CollapsibleBox


logger = logging.getLogger(__name__)


class LayerGroupWidget(CollapsibleBox):
    """Represents a group of layers"""

    dragging = Signal(QPointF)
    drag_ended = Signal()

    def __init__(self, layer_stack: LayerStack, image_stack: ImageStack) -> None:
        super().__init__(scrolling=False)
        self.set_expanded_size_policy(QSizePolicy.Policy.Fixed)
        self._layer = layer_stack
        self._image_stack = image_stack
        self._layer_items: Dict[Layer, LayerGroupWidget | LayerWidget] = {}
        self._parent_item = LayerWidget(layer_stack, image_stack, self)

        def _on_drag() -> None:
            if self.is_expanded():
                self.set_expanded(False)
        self._parent_item.dragging.connect(_on_drag)
        self._parent_item.drag_ended.connect(self.drag_ended)
        self._child_list = CollapsibleBox()
        self._list_layout = QVBoxLayout()
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Tracking where drag and drop would insert child items:
        self._insert_parent: Optional[LayerStack] = None
        self._insert_index = -1
        self._insert_pos = -1

        self.add_button_bar_widget(self._parent_item, False)
        self.set_content_layout(self._list_layout)

        for layer in layer_stack.child_layers:
            self.add_child_layer(layer)
        layer_stack.layer_added.connect(self.add_child_layer)
        layer_stack.layer_removed.connect(self.remove_child_layer)
        layer_stack.lock_changed.connect(self._update_layer_lock_slot)
        self.setAcceptDrops(True)

    def _update_insert_params(self, point: QPointF) -> None:
        if 0 < point.y() < self._parent_item.height() + self._list_layout.spacing():
            if self._insert_parent != self._parent_item.layer or self._insert_index != 0:
                self._insert_parent = self._parent_item.layer
                self._insert_index = 0
                self._insert_pos = self.mapFromGlobal(self._parent_item.mapToGlobal(
                    QPoint(0, self._parent_item.height()))).y()
                self.update()
        top_y = self.height()
        for layer, layer_item in self._layer_items.items():
            parent_item = layer_item.parent()
            assert parent_item is not None and isinstance(parent_item, QWidget)
            offset = self.mapFromGlobal(parent_item.mapToGlobal(QPoint())).y()
            y_min = offset + layer_item.y() - (self._list_layout.spacing() // 2)
            y_max = offset + layer_item.y() + layer_item.height() + (self._list_layout.spacing() // 2)
            top_y = min(y_min, top_y)
            if y_min <= point.y() <= y_max:
                midpoint = y_min + (y_max - y_min) // 2
                parent = layer.layer_parent
                if parent is None:
                    continue
                assert isinstance(parent, LayerStack)
                insert_index = parent.get_layer_index(layer)
                assert insert_index is not None
                insert_pos = y_min
                if point.y() > midpoint:
                    insert_pos = y_max
                    insert_index += 1
                if self._insert_parent != parent or self._insert_index != insert_index \
                        or self._insert_pos != insert_pos:
                    self._insert_parent = parent
                    self._insert_index = insert_index
                    self._insert_pos = insert_pos
                    self.update()
                return
        if point.y() < top_y:
            if self._insert_parent != self._parent_item.layer or self._insert_index != 0:
                self._insert_parent = self._parent_item.layer
                self._insert_index = 0
                self._insert_pos = top_y
                self.update()
        elif self._insert_parent is not None:
            self._insert_parent = None
            self._insert_index = -1
            self._insert_pos = -1
            self.update()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Keep child layers in line with the parent group layer"""
        x_offset = self._parent_item.x() - self.x()
        self._list_layout.setContentsMargins(x_offset + 2, 2, 2, 2)

    def dragEnterEvent(self, event: Optional[QDragEnterEvent]) -> None:
        """Accept drag events from layer widgets."""
        assert event is not None
        moved_layer_item = event.source()
        if not isinstance(moved_layer_item, (LayerGroupWidget, LayerWidget)) or self._layer.locked \
                or self._layer.parent_locked:
            return
        event.accept()
        self._update_insert_params(event.position())

    def dragMoveEvent(self, event: Optional[QDragMoveEvent]) -> None:
        """Track where a dragged layer would be inserted."""
        assert event is not None
        self._update_insert_params(event.position())
        self.dragging.emit(event.position())

    def dragLeaveEvent(self, event: Optional[QDragLeaveEvent]) -> None:
        """Clear the insert marker on drag exit."""
        if self._insert_pos > 0:
            self._insert_parent = None
            self._insert_pos = -1
            self._insert_index = -1
            self.update()

    def dropEvent(self, event: Optional[QDropEvent]) -> None:
        """Drag and drop layers to reorder them."""
        assert event is not None
        moved_layer_item = event.source()
        if not isinstance(moved_layer_item, (LayerGroupWidget, LayerWidget)):
            return
        self.drag_ended.emit()
        moved_layer = moved_layer_item.layer
        new_parent = self._insert_parent
        insert_index = self._insert_index
        self._insert_parent = None
        self._insert_pos = -1
        self._insert_index = -1
        if new_parent is None:
            return  # Not a valid insert position.
        if new_parent == moved_layer or isinstance(moved_layer, LayerStack) and moved_layer.contains_recursive(
                new_parent):
            return  # Layer can't move inside itself.
        if new_parent == moved_layer.layer_parent:
            current_index = new_parent.get_layer_index(moved_layer)
            assert current_index is not None
            if insert_index > current_index:
                insert_index -= 1
        assert isinstance(new_parent, LayerStack)
        self._image_stack.move_layer(moved_layer, new_parent, insert_index)
        self.update()

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draw the insert position on drag and drop."""
        super().paintEvent(event)
        if self._insert_pos < 0:
            return
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawLine(QLine(0, self._insert_pos, self.width(), self._insert_pos))
        painter.end()

    @property
    def layer_item(self) -> 'LayerWidget':
        """Access the group's parent layer item"""
        return self._parent_item

    @property
    def child_items(self) -> List[QWidget]:
        """Returns the list widgets for all child layers."""
        return list(self._layer_items.values())

    @property
    def layer(self) -> LayerStack:
        """Return the connected layer."""
        return self._layer

    def add_child_layer(self, layer: Layer) -> None:
        """Add one of the group's child layers into the list."""
        if layer in self._layer_items:
            assert self._layer_items[layer].isVisible()
            return  # Layer is already there.
        index = self._layer.get_layer_index(layer)
        if index is None:
            # Signal was probably passed on from a nested group, ignore it unless that's not true:
            if not self._layer.contains_recursive(layer):
                logger.warning(f'Tried to add layer {layer.name}:{layer.id} to unrelated group'
                               f' {self._layer.name}:{self._layer.id}')
            return
        if isinstance(layer, LayerStack):
            child_widget = LayerGroupWidget(layer, self._image_stack)

            def _handle_drag(pos: QPointF) -> None:
                self.dragging.emit(QPointF(self.mapFromGlobal(child_widget.mapToGlobal(pos))))
            child_widget.dragging.connect(_handle_drag)
        else:
            child_widget = LayerWidget(layer, self._image_stack)
        child_widget.drag_ended.connect(self.drag_ended)
        self._layer_items[layer] = child_widget
        self._list_layout.insertWidget(index, child_widget)

    def remove_child_layer(self, layer: Layer) -> None:
        """Remove one of the group's child layers from the list."""
        if layer not in self._layer_items:
            logger.warning(f'Tried to remove layer {layer.name}:{layer.id} from group'
                           f' {self._layer.name}:{self._layer.id} not containing that layer')
            return
        layer_item = self._layer_items[layer]
        index = self._list_layout.indexOf(layer_item)
        if index >= 0:
            self._list_layout.takeAt(index)
        del self._layer_items[layer]
        layer_item.deleteLater()

    def reorder_child_layers(self) -> None:
        """Update child layer order based on layer z-values."""
        while self._list_layout.count() < 0:
            self._list_layout.takeAt(0)
        child_items = list(self._layer_items.values())
        child_items.sort(key=lambda layer_widget: layer_widget.layer.z_value, reverse=True)
        for widget in child_items:
            self._list_layout.addWidget(widget)
            if isinstance(widget, LayerGroupWidget):
                widget.reorder_child_layers()

    def _update_layer_lock_slot(self, layer: Layer, locked: bool) -> None:
        assert layer == self._layer
        if locked and self.is_expanded():
            self.set_expanded(False)
