"""Represents an image layer within the layer panel."""

from typing import Optional, cast, Callable

from PySide6.QtCore import QSize, Qt, QRect, QPoint, QMimeData, Signal
from PySide6.QtGui import (QPixmap, QImage, QPainter, QTransform, QResizeEvent, QPaintEvent, QColor, QMouseEvent, QDrag,
                           QAction)
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSizePolicy, QMenu, QApplication

from src.config.cache import Cache
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_stack import LayerStack
from src.image.layers.transform_layer import TransformLayer
from src.tools.selection_tool import LABEL_TEXT_SELECTION_TOOL
from src.ui.input_fields.editable_label import EditableLabel
from src.ui.layout.bordered_widget import BorderedWidget
from src.ui.panel.layer_ui.layer_alpha_lock_button import LayerAlphaLockButton
from src.ui.panel.layer_ui.layer_lock_button import LayerLockButton
from src.ui.panel.layer_ui.layer_toggle_button import ICON_SIZE
from src.ui.panel.layer_ui.layer_visibility_button import LayerVisibilityButton
from src.util.display_size import find_text_size, get_window_size
from src.util.geometry_utils import get_scaled_placement
from src.util.image_utils import get_transparency_tile_pixmap, crop_to_content

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.panel.layer.image_layer_widget'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


PREVIEW_SIZE = QSize(80, 80)
SMALL_PREVIEW_SIZE = QSize(40, 40)
LAYER_PADDING = 10
MAX_WIDTH = PREVIEW_SIZE.width() + ICON_SIZE.width() + LAYER_PADDING * 2 + 400
MENU_OPTION_MOVE_UP = _tr('Move up')
MENU_OPTION_MOVE_DOWN = _tr('Move down')
MENU_OPTION_COPY = _tr('Copy')
MENU_OPTION_DELETE = _tr('Delete')
MENU_OPTION_MERGE_DOWN = _tr('Merge down')
MENU_OPTION_CLEAR_SELECTED = _tr('Clear selected')
MENU_OPTION_COPY_SELECTED = _tr('Copy selected to new layer')
MENU_OPTION_LAYER_TO_IMAGE_SIZE = _tr('Layer to image size')
MENU_OPTION_CROP_TO_CONTENT = _tr('Crop layer to content')
MENU_OPTION_CLEAR_SELECTION = _tr('Clear selection')
MENU_OPTION_SELECT_ALL = _tr('Select all in active layer')
MENU_OPTION_INVERT_SELECTION = _tr('Invert selection')
MENU_OPTION_MIRROR_VERTICAL = _tr('Mirror vertically')
MENU_OPTION_MIRROR_HORIZONTAL = _tr('Mirror horizontally')
COPIED_LAYER_NAME = _tr('{src_layer_name} copied content')


def _preview_size() -> QSize:
    window_size = get_window_size()
    min_dim = min(window_size.width(), window_size.height())
    if min_dim > 1200:
        return QSize(PREVIEW_SIZE)
    return QSize(SMALL_PREVIEW_SIZE)


class LayerWidget(BorderedWidget):
    """A single layer's representation in the list"""

    dragging = Signal()
    drag_ended = Signal()

    # Shared transparency background pixmap. The first LayerGraphicsItem created initializes it, after that access is
    # strictly read-only.
    _layer_transparency_background: Optional[QPixmap] = None

    def __init__(self, layer: Layer, image_stack: ImageStack, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layer = layer
        self._image_stack = image_stack
        self._layout = QHBoxLayout(self)
        self._layout.addSpacing(_preview_size().width())
        self._layer_image = QImage()
        self._preview_pixmap = QPixmap()
        self._clicking = False
        self._click_pos = QPoint()
        if layer == image_stack.selection_layer:
            self._label = QLabel(layer.name, self)
        else:
            self._label = EditableLabel(layer.name, self)
            self._label.text_changed.connect(self.rename_layer)
        text_alignment = Qt.AlignmentFlag.AlignCenter
        self._label.setAlignment(text_alignment)
        self._label.setWordWrap(True)

        self._layout.addWidget(self._label, stretch=40)
        image_stack.active_layer_changed.connect(self._active_layer_change_slot)
        self._layer.content_changed.connect(self._layer_content_change_slot)
        self._layer.name_changed.connect(self._layer_name_change_slot)
        self._layer.visibility_changed.connect(self.update)
        if isinstance(self._layer, TransformLayer):
            self._layer.transform_changed.connect(self._layer_content_change_slot)
        self._active = False
        self._active_color = self.color
        self._inactive_color = self._active_color.darker() if self._active_color.lightness() > 100 \
            else self._active_color.lighter()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum))
        if LayerWidget._layer_transparency_background is None:
            LayerWidget._layer_transparency_background = get_transparency_tile_pixmap(QSize(64, 64))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        if isinstance(layer, ImageLayer):
            self._alpha_lock_button = LayerAlphaLockButton(layer)
            self._layout.addWidget(self._alpha_lock_button, stretch=10)
        if layer != image_stack.layer_stack:
            self._lock_button = LayerLockButton(self._layer)
            self._layout.addWidget(self._lock_button, stretch=10)
        self._visibility_button = LayerVisibilityButton(self._layer)
        self._layout.addWidget(self._visibility_button, stretch=10)
        # Prepare initial layer image:
        self._layer_content_change_slot()

    def _layer_preview_bounds(self) -> QRect:
        preview_bounds = QRect(LAYER_PADDING, LAYER_PADDING, self._label.x() - LAYER_PADDING * 2,
                               self.height() - LAYER_PADDING * 2)
        if not self._layer_image.isNull() and not self._layer_image.size().isEmpty():
            preview_bounds = get_scaled_placement(preview_bounds, self._layer_image.size(), 2)
        return preview_bounds

    def _update_pixmap(self, ignore_if_same_size=False):
        if self._layer_image.isNull():
            return
        paint_bounds = self._layer_preview_bounds()
        if paint_bounds.size() != self._preview_pixmap.size():
            self._preview_pixmap = QPixmap(paint_bounds.size())
        elif ignore_if_same_size:
            return
        if paint_bounds.size().isEmpty() or self._preview_pixmap.isNull() or self._preview_pixmap.size().isEmpty():
            return
        painter = QPainter(self._preview_pixmap)
        paint_bounds = QRect(QPoint(), paint_bounds.size())
        if self._layer != self._image_stack.selection_layer:
            assert LayerWidget._layer_transparency_background is not None
            painter.drawTiledPixmap(paint_bounds, LayerWidget._layer_transparency_background)
        else:
            painter.fillRect(paint_bounds, Qt.GlobalColor.darkGray)
        scale = paint_bounds.width() / self._layer_image.width()
        painter.setTransform(QTransform.fromScale(scale, scale))
        painter.drawImage(QPoint(), self._layer_image)
        painter.end()
        self.update()

    # noinspection PyUnusedLocal
    def _layer_content_change_slot(self, *args) -> None:
        if isinstance(self._layer, TransformLayer):
            layer_image, _ = self._layer.transformed_image()
        else:
            layer_image = self._layer.image
        self._layer_image = crop_to_content(layer_image)
        self._update_pixmap()

    def _layer_name_change_slot(self, _, name: str) -> None:
        self._label.set_text(name)

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Resize the layer pixmap on resize"""
        self._update_pixmap(True)

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draws the scaled layer contents to the widget."""
        paint_bounds = self._layer_preview_bounds()
        painter = QPainter(self)
        if not paint_bounds.isEmpty():
            painter.setPen(Qt.GlobalColor.black)
            painter.drawRect(paint_bounds)
            painter.save()
            painter.setOpacity(self._layer.opacity)
            qt_composite_mode = self._layer.composition_mode.qt_composite_mode()
            if qt_composite_mode is not None:
                painter.setCompositionMode(qt_composite_mode)
            painter.drawPixmap(paint_bounds, self._preview_pixmap)
            painter.restore()
            if not self._layer.visible:
                painter.fillRect(paint_bounds, QColor.fromRgb(0, 0, 0, 100))
        if self._clicking:
            painter.setTransform(QTransform())
            painter.fillRect(QRect(QPoint(), self.size()), QColor.fromRgb(0, 0, 0, 100))
        painter.end()
        super().paintEvent(event)

    def rename_layer(self, new_name: str) -> None:
        """Update the layer name."""
        self._layer.name = new_name

    def sizeHint(self) -> QSize:
        """Returns a reasonable default size."""
        text_size = find_text_size(self.layer.name)
        layer_width = text_size.width()
        layer_height = text_size.height()
        layer_width += _preview_size().width() + ICON_SIZE.width()
        layer_width = min(layer_width, MAX_WIDTH)
        layer_height = max(layer_height, ICON_SIZE.height(), _preview_size().height())
        return QSize(layer_width, layer_height)

    @property
    def layer(self) -> Layer:
        """Return the connected layer."""
        return self._layer

    @property
    def active(self) -> bool:
        """Returns whether this layer is active."""
        return self._active

    @active.setter
    def active(self, is_active: bool) -> None:
        """Updates whether this layer is active."""
        if is_active != self._active:
            self.color = self._active_color if is_active else self._inactive_color
            self.line_width = 10 if is_active else 1
            self._active = is_active
            self.update()

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Activate layer on click."""
        assert event is not None
        self._clicking = True
        self._click_pos = event.pos()
        if self._layer == self._image_stack.selection_layer:
            Cache().set(Cache.LAST_ACTIVE_TOOL, LABEL_TEXT_SELECTION_TOOL)
        elif not self.active and event.button() == Qt.MouseButton.LeftButton:
            self._image_stack.active_layer = self._layer
            self.active = True
            self.update()

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Allow click and drag."""
        assert event is not None
        drag_distance = (self._click_pos - event.pos()).manhattanLength()

        if drag_distance > QApplication.startDragDistance() and self._layer != self._image_stack.layer_stack:
            self.update()
            self.dragging.emit()
            drag = QDrag(self)
            drag.setMimeData(QMimeData())
            drag.setPixmap(self._preview_pixmap)
            drag.exec(Qt.DropAction.MoveAction)
            self._clicking = False
            self._click_pos = QPoint()
            self.drag_ended.emit()
            self.update()

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Exit dragging state."""
        self._clicking = False
        self._click_pos = QPoint()
        self.drag_ended.emit()
        self.update()

    def _active_layer_change_slot(self, active_layer: Layer) -> None:
        self.active = active_layer == self._layer

    def _menu(self, pos: QPoint) -> None:
        menu = QMenu()
        menu.setTitle(self._layer.name)

        def _add_action(name: str, action_callback: Callable[..., None], disable_if_locked=False) -> QAction:
            action = menu.addAction(name)
            assert action is not None
            action.triggered.connect(action_callback)
            if disable_if_locked:
                action.setEnabled(not self._layer.locked and not self._layer.parent_locked)
            return action

        if self._layer != self._image_stack.selection_layer and self._layer.layer_parent is not None:
            index = None
            parent = cast(LayerStack, self._layer.layer_parent)
            if parent is not None:
                index = parent.get_layer_index(self._layer)

            if index is not None:
                _add_action(MENU_OPTION_MOVE_UP, lambda: self._image_stack.move_layer_by_offset(-1, self.layer))

                if index < self._image_stack.count - 1:
                    _add_action(MENU_OPTION_MOVE_DOWN, lambda: self._image_stack.move_layer_by_offset(1, self.layer))

            _add_action(MENU_OPTION_COPY, lambda: self._image_stack.copy_layer(self.layer))
            _add_action(MENU_OPTION_DELETE, lambda: self._image_stack.remove_layer(self.layer), True)

            if index is not None and index < self._image_stack.count - 1:
                merge_option = _add_action(MENU_OPTION_MERGE_DOWN,
                                           lambda: self._image_stack.merge_layer_down(self.layer), True)
                next_layer = self._image_stack.next_layer(self._layer)
                if next_layer is None or next_layer.locked or not next_layer.visible:
                    merge_option.setEnabled(False)

            _add_action(MENU_OPTION_CLEAR_SELECTED, lambda: self._image_stack.cut_selected(self.layer), True)

            def do_copy() -> None:
                """Make the copy, then add it as a new layer."""
                masked = self._image_stack.copy_selected(self.layer)
                self._image_stack.create_layer(COPIED_LAYER_NAME.format(src_layer_name=self._layer.name), masked,
                                               layer_index=index)
            _add_action(MENU_OPTION_COPY_SELECTED, do_copy)
            _add_action(MENU_OPTION_LAYER_TO_IMAGE_SIZE, lambda: self._image_stack.layer_to_image_size(self.layer),
                        True)

        else:
            _add_action(MENU_OPTION_INVERT_SELECTION, self._image_stack.selection_layer.invert_selection)
            _add_action(MENU_OPTION_CLEAR_SELECTION, self._image_stack.selection_layer.clear)
            _add_action(MENU_OPTION_SELECT_ALL, self._image_stack.select_active_layer_content)

        if isinstance(self._layer, ImageLayer):
            _add_action(MENU_OPTION_CROP_TO_CONTENT, self._layer.crop_to_content, True)

        if isinstance(self._layer, TransformLayer):
            _add_action(MENU_OPTION_MIRROR_HORIZONTAL, self._layer.flip_horizontal, True)
            _add_action(MENU_OPTION_MIRROR_VERTICAL, self._layer.flip_vertical, True)

        menu.exec(self.mapToGlobal(pos))
