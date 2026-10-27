"""One layer's row in the layer list, and the thumbnail and name editor it shares with the selected-layer header.

Every row has the same anatomy, left to right, so columns line up down the list whatever the layer type:

- the eye, in a fixed column at the left edge;
- the indent, `INDENT` per level of nesting, with a guide line for each level;
- the disclosure triangle for a group, or an empty slot of the same width;
- the thumbnail, marked "Aa" for a text layer;
- the name, ellipsized with the full name as its tooltip, over an optional meta line;
- the state icons (`LayerStateIcon`), drawn only while on, or as faint slots while the row is hovered.

The active row has the selection fill and a stripe on its left edge, in the selected-layer header's stripe color. A row
never changes size when it becomes active, so the list doesn't shift.
"""
from typing import Optional

from PySide6.QtCore import QEvent, QMimeData, QPoint, QRect, QSize, Qt, QTimer, Signal, QObject
from PySide6.QtGui import (QColor, QDrag, QEnterEvent, QFont, QImage, QKeyEvent, QMouseEvent, QPainter, QPaintEvent,
                           QPalette, QPen, QPixmap, QTransform)
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLineEdit, QMenu, QSizePolicy, QToolButton,
                               QVBoxLayout, QWidget)

from src.image.composite_mode import CompositeMode
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.text_layer import TextLayer
from src.image.layers.transform_layer import TransformLayer
from src.ui.ink_style import ROW_HOVER, ink_colors
from src.ui.panel.layer_ui.layer_flags import LAYER_FLAGS, LayerStateIcon
from src.ui.panel.layer_ui.layer_menu import build_layer_menu
from src.ui.panel.layer_ui.layer_visibility_button import LayerVisibilityButton
from src.ui.widget.elided_label import ElidedLabel
from src.util.visual.geometry_utils import get_scaled_placement
from src.util.visual.image_utils import crop_to_content, get_transparency_tile_pixmap

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.panel.layer_ui.layer_row'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


META_SEPARATOR = _tr(' · ', 'separates the parts of a layer row\'s meta line')
META_OPACITY = _tr('{percent}%')
META_ONE_LAYER = _tr('1 layer')
META_LAYER_COUNT = _tr('{count} layers')
TEXT_LAYER_MARK = _tr('Aa', 'marks text layer thumbnails')
EXPAND_TOOLTIP = _tr('Show or hide the layers in this group')

# Indent per level of nesting:
INDENT = 14
DISCLOSURE_SIZE = 16
ROW_PADDING = 2
ROW_SPACING = 4
# Width of the selection stripe on the left edge of the active row and the selected-layer header:
SELECTION_STRIPE_WIDTH = 3
SMALL_THUMBNAIL_SIZE = 28
LARGE_THUMBNAIL_SIZE = 48
# Previews of images larger than this on their short side render at a quarter of the size:
PREVIEW_DOWNSCALE_THRESHOLD = 1000
PREVIEW_RENDER_DELAY_MS = 500
HIDDEN_LAYER_SHADE = QColor(0, 0, 0, 100)
# The narrowest a name gets, measured in the row's font:
MIN_NAME_TEXT = 'Mmm…'


def selection_stripe_color(widget: QWidget) -> QColor:
    """Returns the color of the stripe marking the active row and the selected-layer header."""
    return widget.palette().color(QPalette.ColorRole.Highlight)


def selection_fill_color(widget: QWidget) -> QColor:
    """Returns the fill behind the active row: the Ink theme's accent wash, or a faint highlight in other styles."""
    colors = ink_colors()
    if colors is not None:
        return colors.accent_wash
    color = QColor(widget.palette().color(QPalette.ColorRole.Highlight))
    color.setAlpha(60)
    return color


def layer_meta_text(layer: Layer) -> str:
    """Returns a row's meta line: opacity below 100%, a blend mode other than Normal, and a group's layer count."""
    parts: list[str] = []
    if layer.opacity < 1.0:
        parts.append(META_OPACITY.format(percent=round(layer.opacity * 100)))
    if layer.composition_mode != CompositeMode.NORMAL:
        parts.append(str(layer.composition_mode))
    if isinstance(layer, LayerGroup):
        parts.append(META_ONE_LAYER if layer.count == 1 else META_LAYER_COUNT.format(count=layer.count))
    return META_SEPARATOR.join(parts)


class LayerThumbnail(QWidget):
    """A square preview of a layer's content, cropped to content, over a transparency pattern.

    Previews update on a timer after the layer's content changes, so a stroke doesn't render one per change. A hidden
    layer's preview is shaded, and a text layer's is marked "Aa".
    """

    # Shared transparency background pixmap, created by the first thumbnail:
    _transparency_background: Optional[QPixmap] = None

    def __init__(self, layer: Optional[Layer] = None, edge_length: int = SMALL_THUMBNAIL_SIZE,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layer: Optional[Layer] = None
        self._layer_image = QImage()
        if LayerThumbnail._transparency_background is None:
            LayerThumbnail._transparency_background = get_transparency_tile_pixmap(QSize(64, 64))
        self._preview_render_timer = QTimer(self)
        self._preview_render_timer.setSingleShot(True)
        self._preview_render_timer.setInterval(PREVIEW_RENDER_DELAY_MS)
        self._preview_render_timer.timeout.connect(self._update_layer_preview_image)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.set_edge_length(edge_length)
        self.set_layer(layer)

    @property
    def layer(self) -> Optional[Layer]:
        """The layer the thumbnail shows."""
        return self._layer

    def set_edge_length(self, edge_length: int) -> None:
        """Sets the thumbnail's width and height."""
        self.setFixedSize(edge_length, edge_length)

    def set_layer(self, layer: Optional[Layer]) -> None:
        """Shows a new layer's content, or nothing."""
        if layer is self._layer:
            return
        if self._layer is not None:
            self._layer.content_changed.disconnect(self._layer_content_change_slot)
            self._layer.visibility_changed.disconnect(self._visibility_change_slot)
            if isinstance(self._layer, TransformLayer):
                self._layer.transform_changed.disconnect(self._layer_content_change_slot)
        self._layer = layer
        if layer is not None:
            layer.content_changed.connect(self._layer_content_change_slot)
            layer.visibility_changed.connect(self._visibility_change_slot)
            if isinstance(layer, TransformLayer):
                layer.transform_changed.connect(self._layer_content_change_slot)
        self._update_layer_preview_image()

    def _layer_content_change_slot(self, *_args) -> None:
        self._preview_render_timer.start()

    def _visibility_change_slot(self, *_args) -> None:
        self.update()

    def _update_layer_preview_image(self) -> None:
        self._preview_render_timer.stop()
        layer = self._layer
        if layer is None:
            self._layer_image = QImage()
        else:
            if isinstance(layer, TransformLayer):
                layer_image, _ = layer.transformed_image()
            elif isinstance(layer, LayerGroup):
                layer_image = layer.preview_image()
            else:
                layer_image = layer.image
            if min(layer_image.width(), layer_image.height()) > PREVIEW_DOWNSCALE_THRESHOLD:
                layer_image = layer_image.scaled(layer_image.width() // 4, layer_image.height() // 4)
            self._layer_image = crop_to_content(layer_image)
        self.update()

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the preview inside an outlined square."""
        painter = QPainter(self)
        frame = QRect(QPoint(), self.size()).adjusted(0, 0, -1, -1)
        assert LayerThumbnail._transparency_background is not None
        painter.drawTiledPixmap(frame, LayerThumbnail._transparency_background)
        if not self._layer_image.isNull() and not self._layer_image.size().isEmpty():
            bounds = get_scaled_placement(frame, self._layer_image.size(), 1)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            scale = bounds.width() / self._layer_image.width()
            painter.save()
            painter.setTransform(QTransform.fromScale(scale, scale).translate(bounds.x() / scale, bounds.y() / scale))
            painter.drawImage(QPoint(), self._layer_image)
            painter.restore()
        if self._layer is not None and not self._layer.shown:
            painter.fillRect(frame, HIDDEN_LAYER_SHADE)
        painter.setPen(QPen(self.palette().color(QPalette.ColorRole.Mid), 1))
        painter.drawRect(frame)
        if isinstance(self._layer, TextLayer):
            self._paint_text_mark(painter, frame)
        painter.end()

    def _paint_text_mark(self, painter: QPainter, frame: QRect) -> None:
        font = QFont(self.font())
        font.setPixelSize(max(frame.height() // 3, 8))
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        mark = QRect(0, 0, metrics.horizontalAdvance(TEXT_LAYER_MARK) + 4, metrics.height())
        mark.moveBottomRight(frame.bottomRight())
        palette = self.palette()
        painter.fillRect(mark, palette.color(QPalette.ColorRole.Window))
        painter.setPen(palette.color(QPalette.ColorRole.WindowText))
        painter.drawText(mark, Qt.AlignmentFlag.AlignCenter, TEXT_LAYER_MARK)


class LayerNameLabel(QWidget):
    """A layer name that ellipsizes to fit, and becomes a text field on double-click.

    Enter or leaving the field applies the new name, and Escape restores the old one. `renamed` carries a changed name.
    """

    renamed = Signal(str)

    def __init__(self, text: str = '', parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = ElidedLabel(text)
        self._field = QLineEdit(text)
        self._field.hide()
        self._field.installEventFilter(self)
        self._field.editingFinished.connect(self.apply_changes)
        layout.addWidget(self._label)
        layout.addWidget(self._field)
        self._changes_allowed = True
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns room for the start of a name and an ellipsis, so a narrow row never drops the name entirely."""
        hint = super().minimumSizeHint()
        return QSize(self.fontMetrics().horizontalAdvance(MIN_NAME_TEXT), hint.height())

    def text(self) -> str:
        """Returns the name shown, ignoring unconfirmed input."""
        return self._label.full_text

    def shown_text(self) -> str:
        """Returns the name as drawn, which is ellipsized when it doesn't fit."""
        return self._label.text()

    def set_text(self, text: str) -> None:
        """Shows a new name."""
        self._label.set_full_text(text)
        if not self.is_requesting_input():
            self._field.setText(text)

    def set_changes_allowed(self, allowed: bool) -> None:
        """Sets whether double-clicking edits the name. Ends editing in progress when disallowed."""
        self._changes_allowed = allowed
        if not allowed:
            self.discard_changes()

    def is_requesting_input(self) -> bool:
        """Returns whether the name is being edited."""
        return not self._field.isHidden()

    def activate_input_mode(self) -> None:
        """Starts editing the name, if allowed."""
        if self.is_requesting_input() or not self._changes_allowed or not self.isVisible():
            return
        self._field.setText(self._label.full_text)
        self._label.hide()
        self._field.show()
        self._field.selectAll()
        self._field.setFocus(Qt.FocusReason.OtherFocusReason)

    def apply_changes(self) -> None:
        """Ends editing, emitting `renamed` if the name changed."""
        if not self.is_requesting_input():
            return
        new_name = self._field.text()
        self._end_input()
        if self._changes_allowed and new_name != self._label.full_text and new_name != '':
            self._label.set_full_text(new_name)
            self.renamed.emit(new_name)

    def discard_changes(self) -> None:
        """Ends editing, keeping the old name."""
        if self.is_requesting_input():
            self._end_input()

    def _end_input(self) -> None:
        self._field.hide()
        self._label.show()
        self._field.setText(self._label.full_text)

    def mouseDoubleClickEvent(self, _event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name
        """Starts editing."""
        self.activate_input_mode()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name
        """Cancels editing on Escape."""
        if watched is self._field and event.type() == QEvent.Type.KeyPress:
            assert isinstance(event, QKeyEvent)
            if event.key() == Qt.Key.Key_Escape:
                self.discard_changes()
                return True
        return super().eventFilter(watched, event)


class _DisclosureButton(QToolButton):
    """The triangle that opens and closes a group's row, smaller than the style's tool button minimum."""

    def __init__(self) -> None:
        super().__init__()
        self.setAutoRaise(True)
        self.setFixedSize(DISCLOSURE_SIZE, DISCLOSURE_SIZE)

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the fixed size."""
        return QSize(DISCLOSURE_SIZE, DISCLOSURE_SIZE)

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the fixed size."""
        return self.sizeHint()


class LayerRow(QWidget):
    """One layer in the layer list. See the module docstring for its anatomy."""

    # Emitted when the disclosure triangle opens or closes a group's row:
    expanded_changed = Signal(bool)
    drag_started = Signal()
    drag_ended = Signal()

    def __init__(self, layer: Layer, image_stack: ImageStack, depth: int = 0,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layer = layer
        self._image_stack = image_stack
        self._depth = depth
        self._active = False
        self._hovered = False
        self._expanded = True
        self._dragging = False
        self._press_pos: Optional[QPoint] = None
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SELECTION_STRIPE_WIDTH + ROW_PADDING, ROW_PADDING, ROW_PADDING, ROW_PADDING)
        layout.setSpacing(ROW_SPACING)
        self._eye = LayerVisibilityButton(layer)
        layout.addWidget(self._eye)
        # The indent and a missing triangle's slot are widgets, which the layout spaces like the triangle at any width:
        self._indent = QWidget()
        self._indent.setFixedSize(depth * INDENT, 0)
        layout.addWidget(self._indent)
        self._disclosure: Optional[QToolButton] = None
        if isinstance(layer, LayerGroup):
            self._disclosure = _DisclosureButton()
            self._disclosure.setArrowType(Qt.ArrowType.DownArrow)
            self._disclosure.setToolTip(EXPAND_TOOLTIP)
            self._disclosure.setAccessibleName(EXPAND_TOOLTIP)
            self._disclosure.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._disclosure.clicked.connect(self._disclosure_clicked_slot)
            layout.addWidget(self._disclosure)
        else:
            slot = QWidget()
            slot.setFixedSize(DISCLOSURE_SIZE, 0)
            layout.addWidget(slot)
        self._thumbnail = LayerThumbnail(layer)
        layout.addWidget(self._thumbnail)

        # A widget, not a nested layout, so planning's fresh measurements reach the meta line's visibility:
        name_column_widget = QWidget()
        name_column = QVBoxLayout(name_column_widget)
        name_column.setContentsMargins(0, 0, 0, 0)
        name_column.setSpacing(0)
        self._name = LayerNameLabel(layer.name)
        self._name.renamed.connect(self._rename_slot)
        self._meta = ElidedLabel()
        self._meta.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        name_column.addStretch()
        name_column.addWidget(self._name)
        name_column.addWidget(self._meta)
        name_column.addStretch()
        layout.addWidget(name_column_widget, stretch=1)

        self._state_icons = [LayerStateIcon(flag, layer) for flag in LAYER_FLAGS if flag.applies(layer)]
        for icon in self._state_icons:
            layout.addWidget(icon)

        layer.name_changed.connect(self._name_change_slot)
        layer.lock_changed.connect(self._lock_change_slot)
        layer.opacity_changed.connect(self._update_meta)
        layer.composition_mode_changed.connect(self._update_meta)
        if isinstance(layer, LayerGroup):
            layer.layer_added.connect(self._update_meta)
            layer.layer_removed.connect(self._update_meta)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu_slot)
        self._lock_change_slot()
        self._update_meta()

    @property
    def layer(self) -> Layer:
        """The layer the row shows."""
        return self._layer

    @property
    def depth(self) -> int:
        """The number of groups between the row's layer and the root."""
        return self._depth

    @property
    def eye_button(self) -> LayerVisibilityButton:
        """The visibility toggle in the row's first column."""
        return self._eye

    @property
    def disclosure_button(self) -> Optional[QToolButton]:
        """The triangle that opens and closes a group's row, or None for other layers."""
        return self._disclosure

    @property
    def thumbnail(self) -> LayerThumbnail:
        """The layer's preview."""
        return self._thumbnail

    @property
    def name_label(self) -> LayerNameLabel:
        """The layer's name, which edits in place."""
        return self._name

    @property
    def meta_label(self) -> ElidedLabel:
        """The line under the name with the layer's opacity, mode and layer count."""
        return self._meta

    @property
    def state_icons(self) -> list[LayerStateIcon]:
        """The row's state icons, one per flag its layer has."""
        return list(self._state_icons)

    @property
    def active(self) -> bool:
        """Whether the row's layer is the active layer."""
        return self._active

    def set_active(self, active: bool) -> None:
        """Shows or hides the selection fill and stripe."""
        if active != self._active:
            self._active = active
            self.update()

    def set_depth(self, depth: int) -> None:
        """Indents the row for a layer nested `depth` groups below the root."""
        if depth != self._depth:
            self._depth = depth
            self._indent.setFixedWidth(depth * INDENT)
            self.update()

    def guide_line_xs(self) -> list[int]:
        """Returns the x of each nesting level's guide line, outermost first."""
        start = self._indent.x() + ROW_SPACING + DISCLOSURE_SIZE // 2
        return [start + level * INDENT for level in range(self._depth)]

    def is_expanded(self) -> bool:
        """Whether a group's row shows the rows of its layers. Other rows always count as expanded."""
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        """Opens or closes a group's row, without emitting `expanded_changed`."""
        self._expanded = expanded
        if self._disclosure is not None:
            self._disclosure.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def set_large(self, large: bool) -> None:
        """Uses the large thumbnail, or the small one."""
        self._thumbnail.set_edge_length(LARGE_THUMBNAIL_SIZE if large else SMALL_THUMBNAIL_SIZE)

    def set_meta_shown(self, shown: bool) -> None:
        """Shows or hides the meta line. A shown meta line keeps its height while empty, so every row is as tall."""
        self._meta.setVisible(shown)

    def _disclosure_clicked_slot(self) -> None:
        self.set_expanded(not self._expanded)
        self.expanded_changed.emit(self._expanded)

    def _rename_slot(self, name: str) -> None:
        self._layer.name = name

    def _name_change_slot(self, _layer: Layer, name: str) -> None:
        self._name.set_text(name)

    def _lock_change_slot(self, *_args) -> None:
        # The signal's arguments may describe a parent group's lock, so read the lock state from the layer instead.
        self._name.set_changes_allowed(not self._layer.locked and not self._layer.parent_locked)

    def _update_meta(self, *_args) -> None:
        self._meta.set_full_text(layer_meta_text(self._layer))

    def build_menu(self) -> QMenu:
        """Returns the row's context menu."""
        return build_layer_menu(self._layer, self._image_stack, self._name.activate_input_mode)

    def _menu_slot(self, pos: QPoint) -> None:
        self.build_menu().exec(self.mapToGlobal(pos))

    def enterEvent(self, event: QEnterEvent) -> None:  # pylint: disable=invalid-name
        """Shows the state icons' slots."""
        super().enterEvent(event)
        self._set_hovered(True)

    def leaveEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """Hides the state icons' slots."""
        super().leaveEvent(event)
        self._set_hovered(False)

    def _set_hovered(self, hovered: bool) -> None:
        if hovered != self._hovered:
            self._hovered = hovered
            for icon in self._state_icons:
                icon.set_slot_shown(hovered)
            self.update()

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the selection or hover fill, the selection stripe and the guide lines."""
        painter = QPainter(self)
        if self._active:
            painter.fillRect(self.rect(), selection_fill_color(self))
            painter.fillRect(QRect(0, 0, SELECTION_STRIPE_WIDTH, self.height()), selection_stripe_color(self))
        elif self._hovered:
            painter.fillRect(self.rect(), ROW_HOVER)
        if self._dragging:
            painter.fillRect(self.rect(), HIDDEN_LAYER_SHADE)
        painter.setPen(QPen(self.palette().color(QPalette.ColorRole.Mid), 1))
        for x in self.guide_line_xs():
            painter.drawLine(x, 0, x, self.height())
        painter.end()

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name
        """Makes the row's layer active on a left click."""
        assert event is not None
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            if self._image_stack.active_layer is not self._layer:
                self._image_stack.active_layer = self._layer

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name
        """Drags the row's layer once the pointer moves far enough with the left button down."""
        assert event is not None
        if self._press_pos is None or event.buttons() != Qt.MouseButton.LeftButton or self._layer.parent_locked:
            return
        if (self._press_pos - event.position().toPoint()).manhattanLength() <= QApplication.startDragDistance():
            return
        self._press_pos = None
        self._dragging = True
        self.update()
        self.drag_started.emit()
        drag = QDrag(self)
        drag.setMimeData(QMimeData())
        drag.setPixmap(self._thumbnail.grab())
        drag.exec(Qt.DropAction.MoveAction)
        self._dragging = False
        self.update()
        self.drag_ended.emit()

    def mouseReleaseEvent(self, _event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name
        """Ends a click."""
        self._press_pos = None
