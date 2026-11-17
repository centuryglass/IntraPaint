"""Popup modal window used for cropping or extending the edited image without scaling its contents.

Size and offset live in a `GeometryBlock` (X/Y are the offset, W/H the new size), an `AnchorGrid` places the old
content at a corner, edge or the center, and dragging in the preview moves the offset. The preview takes the space the
controls leave and never sets the window's minimum size.
"""
from typing import Optional, cast
from PySide6.QtWidgets import (QApplication, QBoxLayout, QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget)
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QIcon, QResizeEvent

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.image.layers.image_stack import ImageStack
from src.ui.input_fields import geometry_block
from src.ui.input_fields.field_factory import create_control_widget
from src.ui.input_fields.geometry_block import GeometryBlock
from src.ui.modal.controls_column import ControlsColumn, fit_dialog_to_screen, stack_body_for_size
from src.ui.modal.dialog_footer import DialogFooter
from src.ui.modal.modal_parent import modal_parent
from src.ui.widget.anchor_grid import AnchorGrid, GRID_SIDE
from src.ui.widget.canvas_change_preview_widget import CanvasChangePreviewWidget
from src.ui.widget.panel_section import PanelSection
from src.util.layout import add_layout
from src.util.shared_constants import APP_ICON_PATH

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.resize_canvas_modal'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


WINDOW_TITLE = _tr('Resize image canvas')
SIZE_SECTION_TITLE = _tr('Size and position')
LAYERS_SECTION_TITLE = _tr('Layers')
OFFSET_HINT = _tr('Drag the preview to move the image.')
X_OFFSET_LABEL = _tr('X-offset')
Y_OFFSET_LABEL = _tr('Y-offset')
X_OFFSET_TOOLTIP = _tr('Horizontal offset of the image within the resized canvas')
Y_OFFSET_TOOLTIP = _tr('Vertical offset of the image within the resized canvas')
NEW_SIZE_TEXT = _tr('New size: {width} x {height} ({width_change} x {height_change})')
RESIZE_BUTTON_LABEL = _tr('Resize image canvas')

MIN_PX_VALUE = 1
CONTROLS_COLUMN_WIDTH = 350
MIN_WINDOW_SIZE = QSize(360, 360)


def _signed(value: int) -> str:
    return f'{value:+d}'


class ResizeCanvasModal(QDialog):
    """Popup modal window used for cropping or extending the edited image without scaling its contents."""

    def __init__(self, image_stack: ImageStack, parent: Optional[QWidget] = None) -> None:
        super().__init__(modal_parent(parent))
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self._image_size = image_stack.size
        self._resize = False
        # The anchor grid cell the content is pinned to, or None once the offset is set by hand:
        self._anchor: Optional[tuple[int, int]] = (0, 0)
        self.setModal(True)
        self.setWindowTitle(WINDOW_TITLE)

        max_size: QSize = cast(QSize, AppConfig().get(AppConfig.MAX_IMAGE_SIZE))

        self._geometry = GeometryBlock(field_text={
            geometry_block.X: (X_OFFSET_LABEL, X_OFFSET_TOOLTIP),
            geometry_block.Y: (Y_OFFSET_LABEL, Y_OFFSET_TOOLTIP)}, parent=self)
        self._geometry.set_image_size(self._image_size)
        self._geometry.set_limits(geometry_block.WIDTH, MIN_PX_VALUE, max_size.width())
        self._geometry.set_limits(geometry_block.HEIGHT, MIN_PX_VALUE, max_size.height())
        self._geometry.set_limits(geometry_block.X, -max_size.width(), max_size.width())
        self._geometry.set_limits(geometry_block.Y, -max_size.height(), max_size.height())
        self._geometry.set_values(w=self._image_size.width(), h=self._image_size.height(), x=0, y=0)
        self._geometry.valueChanged.connect(self._geometry_changed)

        self._anchor_grid = AnchorGrid(self)
        self._anchor_grid.anchorSelected.connect(self._anchor_selected)

        self._size_label = QLabel(self)
        offset_hint = QLabel(OFFSET_HINT, self)
        offset_hint.setWordWrap(True)

        size_body = QWidget(self)
        size_layout = QVBoxLayout(size_body)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.addWidget(self._geometry)
        anchor_row = QHBoxLayout()
        add_layout(size_layout, anchor_row)
        anchor_row.addWidget(self._anchor_grid, alignment=Qt.AlignmentFlag.AlignTop)
        text_column = QVBoxLayout()
        add_layout(anchor_row, text_column, stretch=1)
        text_column.addWidget(self._size_label)
        text_column.addWidget(offset_hint)
        text_column.addStretch(1)

        cache = Cache()
        layer_mode_label = QLabel(cache.get_label(Cache.CANVAS_RESIZE_LAYER_MODE))
        layer_mode_dropdown = create_control_widget(cache, Cache.CANVAS_RESIZE_LAYER_MODE)
        layer_mode_row = QWidget(self)
        layer_mode_row.setToolTip(cache.get_tooltip(Cache.CANVAS_RESIZE_LAYER_MODE))
        layer_mode_layout = QHBoxLayout(layer_mode_row)
        layer_mode_layout.setContentsMargins(0, 0, 0, 0)
        layer_mode_layout.addWidget(layer_mode_label)
        layer_mode_layout.addWidget(layer_mode_dropdown, stretch=1)
        self._crop_checkbox = create_control_widget(cache, Cache.CANVAS_RESIZE_CROP_LAYERS)
        self._crop_checkbox.setText(cache.get_label(Cache.CANVAS_RESIZE_CROP_LAYERS))
        self._crop_checkbox.setParent(self)
        self._crop_checkbox.valueChanged.connect(self.update)
        layers_body = QWidget(self)
        layers_layout = QVBoxLayout(layers_body)
        layers_layout.setContentsMargins(0, 0, 0, 0)
        layers_layout.addWidget(layer_mode_row)
        layers_layout.addWidget(self._crop_checkbox)

        controls = QWidget(self)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.addWidget(PanelSection(SIZE_SECTION_TITLE, size_body))
        controls_layout.addWidget(PanelSection(LAYERS_SECTION_TITLE, layers_body))
        controls_layout.addStretch(1)

        scroll = ControlsColumn(controls, CONTROLS_COLUMN_WIDTH)
        self._controls = scroll

        self._preview = CanvasChangePreviewWidget(image_stack)
        self._preview.offsetDragged.connect(self._offset_dragged)

        self._footer = DialogFooter(RESIZE_BUTTON_LABEL, self)
        self._footer.accepted.connect(self._confirm)
        self._footer.rejected.connect(self._cancel)

        self._layout = QVBoxLayout(self)
        self._body = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        add_layout(self._layout, self._body, stretch=1)
        self._body.addWidget(scroll)
        self._body.addWidget(self._preview, stretch=1)
        self._layout.addWidget(self._footer)

        self.setMinimumSize(MIN_WINDOW_SIZE)
        self._update_preview()
        self._fit_to_screen()

    def _fit_to_screen(self) -> None:
        """Opens the dialog no larger than a fraction of the available screen."""
        fit_dialog_to_screen(self, self.sizeHint().expandedTo(QSize(CONTROLS_COLUMN_WIDTH + 320, 400)))

    def resizeEvent(self, event: QResizeEvent) -> None:  # pylint: disable=invalid-name
        """Stacks the preview below the controls while the window is taller than it is wide."""
        super().resizeEvent(event)
        stack_body_for_size(self._body, self._controls, event.size().width(), event.size().height())

    def _new_size(self) -> QSize:
        return QSize(int(self._geometry.value(geometry_block.WIDTH)), int(self._geometry.value(geometry_block.HEIGHT)))

    def _offset(self) -> QPoint:
        return QPoint(int(self._geometry.value(geometry_block.X)), int(self._geometry.value(geometry_block.Y)))

    def _anchor_offset(self, column: int, row: int) -> QPoint:
        """Returns the offset that places the current image at one cell of the anchor grid."""
        last = GRID_SIDE - 1
        new_size = self._new_size()
        return QPoint((new_size.width() - self._image_size.width()) * column // last,
                      (new_size.height() - self._image_size.height()) * row // last)

    def _geometry_changed(self, name: str, _value: object) -> None:
        """Keeps the selected anchor when the size changes, so the content stays at that corner or edge. Editing the
        offset by hand clears the anchor."""
        if name in (geometry_block.X, geometry_block.Y):
            self._anchor = None
        elif self._anchor is not None:
            offset = self._anchor_offset(*self._anchor)
            self._geometry.set_values(x=offset.x(), y=offset.y())
        self._update_preview()

    def _anchor_selected(self, column: int, row: int) -> None:
        self._anchor = (column, row)
        self._set_offset(self._anchor_offset(column, row))

    def _offset_dragged(self, offset: QPoint) -> None:
        self._anchor = None
        self._set_offset(offset)

    def _set_offset(self, offset: QPoint) -> None:
        self._geometry.set_values(x=offset.x(), y=offset.y())
        self._update_preview()

    def _update_preview(self) -> None:
        new_size = self._new_size()
        offset = self._offset()
        self._preview.set_new_bounds(QRect(-offset.x(), -offset.y(), new_size.width(), new_size.height()))
        self._size_label.setText(NEW_SIZE_TEXT.format(
            width=new_size.width(), height=new_size.height(),
            width_change=_signed(new_size.width() - self._image_size.width()),
            height_change=_signed(new_size.height() - self._image_size.height())))
        self._anchor_grid.set_anchor(self._anchor)

    def _confirm(self) -> None:
        self._resize = True
        self.hide()

    def _cancel(self) -> None:
        self._resize = False
        self.hide()

    def show_resize_modal(self) -> tuple[QSize, QPoint] | tuple[None, None]:
        """Show this modal, returning QSize new_size and QPoint offset if changes are confirmed."""
        self.exec()
        result: tuple[QSize, QPoint] | tuple[None, None] = (None, None)
        if self._resize:
            result = (self._new_size(), self._offset())
        self.deleteLater()
        return result
