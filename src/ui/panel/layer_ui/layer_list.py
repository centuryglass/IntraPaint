"""The scrolling layer list: the image strip for the root group, then one `LayerRow` per layer in stack order.

- Rows sit in one flat column, indented by depth (see `layer_row.py`). A row shows while every group above it is
  expanded.
- The list rebuilds its row order from the layer stack on every structural signal (`_sync`), creating rows for new
  layers and deleting rows for removed ones, so nested changes and undo can't leave it out of step.
- Activating a layer, or adding one, expands the groups above it. Locking a group collapses it and the groups in it.
- Dragging a row onto the list moves its layer. The upper half of a row inserts above it, and the lower half below it,
  or into an expanded group at its top. A marker shows where the layer lands, indented to its depth.
"""
from typing import Optional

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QDragMoveEvent, QDropEvent, QMouseEvent, QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QMenu, QScrollArea, QSizePolicy, \
    QVBoxLayout, QWidget

from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.ui.ink_style import ROW_HOVER
from src.ui.panel.layer_ui.layer_menu import build_layer_menu
from src.ui.panel.layer_ui.layer_row import (INDENT, MIN_NAME_TEXT, ROW_PADDING, ROW_SPACING, SELECTION_STRIPE_WIDTH,
                                             LayerNameLabel, LayerRow, selection_fill_color, selection_stripe_color)
from src.ui.panel.layer_ui.layer_visibility_button import LayerVisibilityButton
from src.ui.widget.panel_header import GlyphButton

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.panel.layer_ui.layer_list'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


IMAGE_SIZE_TEXT = _tr('{width} x {height}')
IMAGE_MENU_TOOLTIP = _tr('Image commands')
IMAGE_STRIP_TOOLTIP = _tr('The whole image. Click to select it.')

# Rows the list keeps room for, under the image strip:
MIN_VISIBLE_ROWS = 2
# Text whose width `LayerList.set_readable_names` keeps room for in a row's name:
READABLE_NAME_TEXT = 'Background'
INSERT_MARKER_HEIGHT = 2
SCROLL_TIMER_INTERVAL_MS = 50
SCROLL_HEIGHT_THRESHOLD = 1 / 8
MIN_SCROLL_SPEED = 2
MAX_SCROLL_SPEED = 10


class ImageStrip(QWidget):
    """The root group's row: its eye, name and canvas size, and a menu with rename, crop to selection and mirror.

    Its eye lines up with the rows' eyes. Clicking it selects the root, and it shows the selection like a row.
    """

    def __init__(self, image_stack: ImageStack, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._image_stack = image_stack
        self._active = False
        self._hovered = False
        root = image_stack.layer_stack
        self.setToolTip(IMAGE_STRIP_TOOLTIP)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SELECTION_STRIPE_WIDTH + ROW_PADDING, ROW_PADDING, ROW_PADDING, ROW_PADDING)
        layout.setSpacing(ROW_SPACING)
        self._eye = LayerVisibilityButton(root)
        layout.addWidget(self._eye)
        self._name = LayerNameLabel(root.name)
        self._name.renamed.connect(self._rename_slot)
        layout.addWidget(self._name, stretch=1)
        self._size_label = QLabel()
        self._size_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        layout.addWidget(self._size_label)
        self._menu_button = GlyphButton(GlyphButton.MORE, IMAGE_MENU_TOOLTIP)
        self._menu_button.clicked.connect(self._show_menu_from_button)
        layout.addWidget(self._menu_button)
        root.name_changed.connect(self._name_change_slot)
        image_stack.size_changed.connect(self._size_change_slot)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu_slot)
        self._size_change_slot(image_stack.size)

    @property
    def eye_button(self) -> LayerVisibilityButton:
        """The root's visibility toggle, which hides or shows every layer."""
        return self._eye

    @property
    def name_label(self) -> LayerNameLabel:
        """The root's name."""
        return self._name

    @property
    def size_text(self) -> str:
        """The canvas size as shown."""
        return self._size_label.text()

    @property
    def menu_button(self) -> GlyphButton:
        """The button that opens `build_menu`."""
        return self._menu_button

    @property
    def active(self) -> bool:
        """Whether the root is the active layer."""
        return self._active

    def set_active(self, active: bool) -> None:
        """Shows or hides the selection fill and stripe."""
        if active != self._active:
            self._active = active
            self.update()

    def build_menu(self) -> QMenu:
        """Returns the root's menu: rename, crop to selection and mirror."""
        return build_layer_menu(self._image_stack.layer_stack, self._image_stack, self._name.activate_input_mode)

    def _show_menu_from_button(self) -> None:
        self.build_menu().exec(self._menu_button.mapToGlobal(QPoint(0, self._menu_button.height())))

    def _context_menu_slot(self, pos: QPoint) -> None:
        self.build_menu().exec(self.mapToGlobal(pos))

    def _rename_slot(self, name: str) -> None:
        self._image_stack.layer_stack.name = name

    def _name_change_slot(self, _layer: Layer, name: str) -> None:
        self._name.set_text(name)

    def _size_change_slot(self, size: QSize) -> None:
        self._size_label.setText(IMAGE_SIZE_TEXT.format(width=size.width(), height=size.height()))

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name
        """Selects the root on a left click."""
        assert event is not None
        if event.button() == Qt.MouseButton.LeftButton:
            self._image_stack.active_layer = self._image_stack.layer_stack

    def enterEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Shows the hover fill."""
        super().enterEvent(event)
        self._hovered = True
        self.update()

    def leaveEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Hides the hover fill."""
        super().leaveEvent(event)
        self._hovered = False
        self.update()

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the selection or hover fill, and a line under the strip."""
        painter = QPainter(self)
        if self._active:
            painter.fillRect(self.rect(), selection_fill_color(self))
            painter.fillRect(0, 0, SELECTION_STRIPE_WIDTH, self.height(), selection_stripe_color(self))
        elif self._hovered:
            painter.fillRect(self.rect(), ROW_HOVER)
        painter.setPen(self.palette().color(QPalette.ColorRole.Mid))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        painter.end()


class _InsertMarker(QWidget):
    """The line that shows where a dragged layer would land."""

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Fills the marker with the selection stripe color."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), selection_stripe_color(self))
        painter.end()


class LayerList(QScrollArea):
    """Shows the image strip and a row for every layer, and moves layers dropped onto it."""

    def __init__(self, image_stack: ImageStack, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._image_stack = image_stack
        self._rows: dict[Layer, LayerRow] = {}
        # Layers in display order, as last placed in the layout:
        self._order: list[Layer] = []
        self._large = False
        self._meta_shown = True
        self._readable_names = False
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self._content = QWidget()
        self._content.setAcceptDrops(True)
        self._content.installEventFilter(self)
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._strip = ImageStrip(image_stack)
        self._layout.addWidget(self._strip)
        self._layout.addStretch()
        self.setWidget(self._content)
        self._insert_marker = _InsertMarker(self._content)
        self._insert_marker.hide()
        # Where a drop would put the dragged layer: its new parent and index.
        self._drop_target: Optional[tuple[LayerGroup, int]] = None

        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(SCROLL_TIMER_INTERVAL_MS)
        self._scroll_timer.timeout.connect(self._scroll_timer_slot)
        self._scroll_offset = 0

        image_stack.layer_added.connect(self._layer_added_slot)
        image_stack.layer_removed.connect(self._sync)
        image_stack.layer_order_changed.connect(self._sync)
        image_stack.active_layer_changed.connect(self._active_layer_change_slot)
        self._sync()
        self._active_layer_change_slot(image_stack.active_layer)

    @property
    def image_strip(self) -> ImageStrip:
        """The root group's strip at the top of the list."""
        return self._strip

    @property
    def rows(self) -> list[LayerRow]:
        """Every layer's row in display order, including rows hidden in collapsed groups."""
        return [self._rows[layer] for layer in self._order]

    def row_for(self, layer: Layer) -> LayerRow:
        """Returns the row showing a layer. Raises KeyError for the root and for layers not in the stack."""
        return self._rows[layer]

    def set_large(self, large: bool) -> None:
        """Uses large thumbnails in every row, or small ones."""
        self._large = large
        for row in self._rows.values():
            row.set_large(large)
        self.updateGeometry()

    def set_readable_names(self, readable: bool) -> None:
        """Sets whether the list's minimum width leaves room to read the start of a layer name, instead of only its
        first letters and an ellipsis."""
        if readable != self._readable_names:
            self._readable_names = readable
            self.updateGeometry()

    def set_meta_shown(self, shown: bool) -> None:
        """Shows or hides every row's meta line."""
        self._meta_shown = shown
        for row in self._rows.values():
            row.set_meta_shown(shown)
        self.updateGeometry()

    def is_expanded(self, group: LayerGroup) -> bool:
        """Returns whether a group's row shows its layers. The root is always expanded."""
        if group is self._image_stack.layer_stack:
            return True
        return self._rows[group].is_expanded()

    def set_expanded(self, group: LayerGroup, expanded: bool) -> None:
        """Opens or closes a group's row."""
        if group is self._image_stack.layer_stack:
            return
        self._rows[group].set_expanded(expanded)
        self._update_row_visibility()

    def row_height(self) -> int:
        """Returns the height every row has."""
        if len(self._order) > 0:
            return self._rows[self._order[0]].sizeHint().height()
        return self._strip.sizeHint().height()

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns room for the strip and `MIN_VISIBLE_ROWS` rows, as wide as the widest row needs plus the scroll
        bar, and the room `set_readable_names` asks for."""
        width = self._strip.minimumSizeHint().width()
        for row in self._rows.values():
            width = max(width, row.minimumSizeHint().width())
        scroll_bar = self.verticalScrollBar()
        width += scroll_bar.sizeHint().width() + 2 * self.frameWidth()
        if self._readable_names:
            metrics = self.fontMetrics()
            width += metrics.horizontalAdvance(READABLE_NAME_TEXT) - metrics.horizontalAdvance(MIN_NAME_TEXT)
        height = self._strip.sizeHint().height() + MIN_VISIBLE_ROWS * self.row_height() + 2 * self.frameWidth()
        return QSize(width, height)

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns room for every row."""
        minimum = self.minimumSizeHint()
        rows_height = sum(self._rows[layer].sizeHint().height() for layer in self._order
                          if not self._rows[layer].isHidden())
        return QSize(minimum.width(), self._strip.sizeHint().height() + rows_height + 2 * self.frameWidth())

    # Rows:

    def _layers_in_order(self) -> list[tuple[Layer, int, bool]]:
        """Returns every layer under the root in display order, with its depth and whether its row shows."""
        return self._layers_under(self._image_stack.layer_stack, 0, True)

    def _layers_under(self, group: LayerGroup, depth: int, shown: bool) -> list[tuple[Layer, int, bool]]:
        result: list[tuple[Layer, int, bool]] = []
        for child in group.child_layers:
            result.append((child, depth, shown))
            if isinstance(child, LayerGroup):
                row = self._rows.get(child)
                result += self._layers_under(child, depth + 1, shown and (row is None or row.is_expanded()))
        return result

    def _create_row(self, layer: Layer, depth: int) -> LayerRow:
        row = LayerRow(layer, self._image_stack, depth)
        row.set_large(self._large)
        row.set_meta_shown(self._meta_shown)
        row.set_active(layer is self._image_stack.active_layer)
        row.expanded_changed.connect(self._update_row_visibility)
        row.drag_ended.connect(self._drag_ended_slot)
        if isinstance(layer, LayerGroup):
            layer.lock_changed.connect(self._group_lock_slot)
        self._rows[layer] = row
        return row

    def _sync(self, *_args) -> None:
        """Matches the rows to the layer stack: creates and deletes rows, sets depths, order and visibility."""
        layers = self._layers_in_order()
        present = {layer for layer, _, _ in layers}
        for layer in [layer for layer in self._rows if layer not in present]:
            row = self._rows.pop(layer)
            if isinstance(layer, LayerGroup):
                layer.lock_changed.disconnect(self._group_lock_slot)
            self._layout.removeWidget(row)
            row.hide()
            row.deleteLater()
        for layer, depth, _ in layers:
            if layer in self._rows:
                self._rows[layer].set_depth(depth)
            else:
                self._create_row(layer, depth)
        # New group rows are expanded, so walk again for visibility:
        layers = self._layers_in_order()
        order = [layer for layer, _, _ in layers]
        if order != self._order:
            for layer in order:
                self._layout.removeWidget(self._rows[layer])
            for index, layer in enumerate(order):
                self._layout.insertWidget(1 + index, self._rows[layer])
            self._order = order
        for layer, _, shown in layers:
            self._rows[layer].setVisible(shown)
        self.updateGeometry()

    def _update_row_visibility(self, *_args) -> None:
        for layer, _, shown in self._layers_in_order():
            self._rows[layer].setVisible(shown)
        self.updateGeometry()

    def _open_parent_groups(self, layer: Layer) -> None:
        parent = layer.layer_parent
        while isinstance(parent, LayerGroup) and parent in self._rows:
            self._rows[parent].set_expanded(True)
            parent = parent.layer_parent
        self._update_row_visibility()

    def _layer_added_slot(self, layer: Layer) -> None:
        self._sync()
        if layer in self._rows:
            self._open_parent_groups(layer)

    def _group_lock_slot(self, layer: Layer, locked: bool) -> None:
        """Collapses a group when it is locked, with the groups in it."""
        if not locked or not isinstance(layer, LayerGroup):
            return
        for group in (layer, *layer.recursive_child_layers):
            if isinstance(group, LayerGroup) and group in self._rows:
                self._rows[group].set_expanded(False)
        self._update_row_visibility()

    def _active_layer_change_slot(self, active_layer: Layer) -> None:
        """Highlights the active layer's row, expanding the groups above it and scrolling to it."""
        self._strip.set_active(active_layer is self._image_stack.layer_stack)
        for layer, row in self._rows.items():
            row.set_active(layer is active_layer)
        if active_layer in self._rows:
            self._open_parent_groups(active_layer)
            self.ensureWidgetVisible(self._rows[active_layer], 0, 0)

    # Drag and drop:

    def drop_target(self, y: int) -> Optional[tuple[LayerGroup, int, int, int]]:
        """Returns where a layer dropped at a y position in the list's content would land: its new parent and index,
        and the marker's y and nesting depth. Returns None where the target group is locked."""
        root = self._image_stack.layer_stack
        shown = [self._rows[layer] for layer in self._order if not self._rows[layer].isHidden()]
        target: tuple[LayerGroup, int, int, int]
        if len(shown) == 0 or y < shown[0].y():
            target = (root, 0, self._strip.geometry().bottom() + 1, 0)
        elif y >= shown[-1].geometry().bottom():
            target = (root, root.count, shown[-1].geometry().bottom() + 1, 0)
        else:
            row = next(row for row in shown if row.y() <= y <= row.geometry().bottom())
            layer = row.layer
            parent = layer.layer_parent
            assert isinstance(parent, LayerGroup)
            index = parent.get_layer_index(layer)
            assert index is not None
            if y < row.y() + row.height() // 2:
                target = (parent, index, row.y(), row.depth)
            elif isinstance(layer, LayerGroup) and row.is_expanded():
                target = (layer, 0, row.geometry().bottom() + 1, row.depth + 1)
            else:
                target = (parent, index + 1, row.geometry().bottom() + 1, row.depth)
        if target[0].locked or target[0].parent_locked:
            return None
        return target

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name
        """Handles layer rows dragged over and dropped on the list's content."""
        if watched is self._content:
            if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                assert isinstance(event, QDragMoveEvent)
                self.drag_move(event)
                return True
            if event.type() == QEvent.Type.DragLeave:
                self._clear_drop_target()
                return True
            if event.type() == QEvent.Type.Drop:
                assert isinstance(event, QDropEvent)
                self.drop(event)
                return True
        return super().eventFilter(watched, event)

    def drag_move(self, event: QDragMoveEvent) -> None:
        """Shows where a dragged row's layer would land, and scrolls near the list's ends."""
        source = event.source()
        if not isinstance(source, LayerRow):
            event.ignore()
            return
        event.accept()
        position = event.position().toPoint()
        target = self.drop_target(position.y())
        moved = source.layer
        if target is not None and (target[0] is moved
                                   or (isinstance(moved, LayerGroup) and moved.contains_recursive(target[0]))):
            target = None
        if target is None:
            self._clear_drop_target()
        else:
            parent, index, marker_y, depth = target
            self._drop_target = (parent, index)
            x = SELECTION_STRIPE_WIDTH + ROW_PADDING + depth * INDENT
            self._insert_marker.setGeometry(x, marker_y - INSERT_MARKER_HEIGHT // 2,
                                            max(self._content.width() - x, 0), INSERT_MARKER_HEIGHT)
            self._insert_marker.show()
            self._insert_marker.raise_()
        self._update_autoscroll(self._content.mapTo(self.viewport(), position).y())

    def drop(self, event: QDropEvent) -> None:
        """Moves a dropped row's layer to the target `drag_move` found."""
        source = event.source()
        target = self._drop_target
        self._clear_drop_target()
        self._stop_autoscroll()
        if not isinstance(source, LayerRow) or target is None:
            return
        event.accept()
        moved = source.layer
        new_parent, index = target
        if new_parent is moved.layer_parent:
            current_index = new_parent.get_layer_index(moved)
            assert current_index is not None
            if index > current_index:
                index -= 1
            if index == current_index:
                return
        self._image_stack.move_layer(moved, new_parent, index)

    def _clear_drop_target(self) -> None:
        self._drop_target = None
        self._insert_marker.hide()

    def _drag_ended_slot(self) -> None:
        self._clear_drop_target()
        self._stop_autoscroll()

    def _update_autoscroll(self, viewport_y: int) -> None:
        threshold = max(round(self.viewport().height() * SCROLL_HEIGHT_THRESHOLD), 1)
        scroll_bar = self.verticalScrollBar()
        if viewport_y < threshold and scroll_bar.value() > scroll_bar.minimum():
            fraction = (threshold - viewport_y) / threshold
            self._scroll_offset = -(MIN_SCROLL_SPEED + round((MAX_SCROLL_SPEED - MIN_SCROLL_SPEED) * fraction))
        elif viewport_y > self.viewport().height() - threshold and scroll_bar.value() < scroll_bar.maximum():
            fraction = (viewport_y - self.viewport().height() + threshold) / threshold
            self._scroll_offset = MIN_SCROLL_SPEED + round((MAX_SCROLL_SPEED - MIN_SCROLL_SPEED) * fraction)
        else:
            self._scroll_offset = 0
        if self._scroll_offset == 0:
            self._stop_autoscroll()
        elif not self._scroll_timer.isActive():
            self._scroll_timer.start()

    def _stop_autoscroll(self) -> None:
        self._scroll_offset = 0
        self._scroll_timer.stop()

    def _scroll_timer_slot(self) -> None:
        scroll_bar = self.verticalScrollBar()
        value = min(max(scroll_bar.value() + self._scroll_offset, scroll_bar.minimum()), scroll_bar.maximum())
        if value == scroll_bar.value():
            self._stop_autoscroll()
        else:
            scroll_bar.setValue(value)
