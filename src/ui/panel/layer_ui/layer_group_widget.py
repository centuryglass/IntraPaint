"""Represents an image layer group."""
import logging
from typing import Dict, Optional, List

from PySide6.QtCore import QPointF, QPoint, QLine, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent, QPaintEvent, QPainter, \
    QResizeEvent
from PySide6.QtWidgets import QWidget, QHBoxLayout, QToolButton, QGridLayout

from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_stack import LayerStack
from src.ui.layout.bordered_widget import BorderedWidget
from src.ui.panel.layer_ui.layer_widget import LayerWidget
from src.util.layout import clear_layout
from src.util.signals_blocked import signals_blocked

logger = logging.getLogger(__name__)


class LayerGroupWidget(BorderedWidget):
    """Represents a group of layers"""

    dragging = Signal(QPointF)
    drag_ended = Signal()

    def __init__(self, layer_stack: LayerStack, image_stack: ImageStack) -> None:
        super().__init__()
        self._layout = QGridLayout(self)
        self._layout.setSpacing(4)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layer = layer_stack
        self._image_stack = image_stack
        self._layer_items: Dict[Layer, LayerGroupWidget | LayerWidget] = {}

        # Own layer item and toggle switch:
        self._parent_frame = BorderedWidget(self)
        parent_frame_layout = QHBoxLayout(self._parent_frame)
        parent_frame_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._toggle_button = QToolButton()
        self._toggle_button.setCheckable(True)
        self._toggle_button.setChecked(True)
        self._toggle_button.setStyleSheet('QToolButton { border: none; }')
        self._toggle_button.setArrowType(Qt.ArrowType.DownArrow)
        self._toggle_button.toggled.connect(self.set_expanded)
        self._parent_item = LayerWidget(layer_stack, image_stack, self)
        parent_frame_layout.addWidget(self._toggle_button)
        parent_frame_layout.addWidget(self._parent_item)
        self._layout.addWidget(self._parent_frame, 0, 0, 1, 2)

        # If dragging the main layer item, close the group:
        def _on_drag() -> None:
            if self.is_expanded():
                self.set_expanded(False)
        self._parent_item.dragging.connect(_on_drag)
        self._parent_item.drag_ended.connect(self.drag_ended)

        # Tracking where drag and drop would insert child items:
        self._insert_parent: Optional[LayerStack] = None
        self._insert_index = -1
        self._insert_pos = -1

        for layer in layer_stack.child_layers:
            self.add_child_layer(layer)
        layer_stack.layer_added.connect(self.add_child_layer)
        layer_stack.layer_removed.connect(self.remove_child_layer)
        layer_stack.lock_changed.connect(self._update_layer_lock_slot)
        self.setAcceptDrops(True)

    def _update_insert_params(self, point: QPointF) -> None:
        """When dragging another layer over this one, track where that new layer would be inserted if dropped."""
        if 0 < point.y() < self._parent_item.height() + self._layout.spacing():
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
            y_min = offset + layer_item.y() - (self._layout.spacing() // 2)
            y_max = offset + layer_item.y() + layer_item.height() + (self._layout.spacing() // 2)
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

    def is_expanded(self) -> bool:
        """Return whether the widget is expanded to show child layers."""
        return self._toggle_button.isChecked()

    def _refresh_layout(self) -> None:
        """Refresh the layout by removing and replacing this widget within its parent."""
        # TODO: Sometimes the outer layer refuses to update when a group is expanded or collapsed or when child items
        #  change. The normal methods for fixing this kind of issue (updateGeometry, adjustSize, update,
        #  layout.invalidate) all make no difference, but removing and re-inserting the widget fixes the problem.
        #  This is an acceptable solution for now, but there really should be a better way to fix this.
        parent_widget = self.parentWidget()
        if parent_widget is None:
            return
        parent_layout = parent_widget.layout()
        if not isinstance(parent_layout, QGridLayout):
            return
        own_index = parent_layout.indexOf(self)
        if own_index < 0:
            return
        row, col, row_stretch, col_stretch = parent_layout.getItemPosition(own_index)
        parent_layout.removeWidget(self)
        parent_layout.addWidget(self, row, col, row_stretch, col_stretch)

    def set_expanded(self, expanded: bool) -> None:
        """Open or close the widget."""
        if expanded != self._toggle_button.isChecked():
            with signals_blocked(self._toggle_button):
                self._toggle_button.setChecked(expanded)
        self._toggle_button.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        for child_item in self.child_items:
            child_item.setVisible(expanded)
        self._refresh_layout()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Keep child layers in line with the parent group layer"""
        self._layout.setColumnMinimumWidth(0, self._parent_item.x())

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
    def layer_item(self) -> LayerWidget:
        """Access the group's parent layer item"""
        return self._parent_item

    @property
    def child_items(self) -> List[QWidget]:
        """Returns the list widgets for all child layers."""
        return list(self._layer_items.values())

    def get_child_item(self, child_layer: Layer) -> LayerWidget:
        """Finds the layer widget for a child layer, or throws ValueError if child_layer isn't a direct child of this
           widget's layer group."""
        if child_layer not in self._layer_items:
            raise ValueError(f'{child_layer.name} not a child layer of {self._layer.name}')
        return self._layer_items[child_layer]

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
        self._layout.addWidget(child_widget, index + 1, 1)
        child_widget.setVisible(self.is_expanded())
        self._refresh_layout()

    def remove_child_layer(self, layer: Layer) -> None:
        """Remove one of the group's child layers from the list."""
        if layer not in self._layer_items:
            logger.warning(f'Tried to remove layer {layer.name}:{layer.id} from group'
                           f' {self._layer.name}:{self._layer.id} not containing that layer')
            return
        layer_item = self._layer_items[layer]
        index = self._layout.indexOf(layer_item)
        if index >= 0:
            self._layout.takeAt(index)
        del self._layer_items[layer]
        layer_item.deleteLater()
        self._refresh_layout()

    def reorder_child_layers(self) -> None:
        """Update child layer order based on layer z-values."""
        clear_layout(self._layout, unparent=False)
        self._layout.addWidget(self._parent_frame, 0, 0, 1, 2)
        child_items = list(self._layer_items.values())
        child_items.sort(key=lambda layer_widget: layer_widget.layer.z_value, reverse=True)
        for i, widget in enumerate(child_items):
            self._layout.addWidget(widget, i + 1, 1)
            widget.setVisible(self.is_expanded())
            if isinstance(widget, LayerGroupWidget):
                widget.reorder_child_layers()

    def _update_layer_lock_slot(self, layer: Layer, locked: bool) -> None:
        assert layer == self._layer or layer.contains_recursive(self._layer)
        if locked and self.is_expanded():
            self.set_expanded(False)
