"""Widget holding multiple color options, largely ported from the internal QWellArray class within QColorDialog."""
from typing import Optional, List, Tuple, Set

from PySide6.QtCore import Qt, Signal, QRect, QSize, QPoint, QMimeData, QTimer
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QMouseEvent, QFocusEvent, QKeyEvent, QPixmap, QDrag, \
    QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QWidget, QStyleOptionFrame, QStyle, QStyleOptionFocusRect, QSizePolicy, QApplication, \
    QColorDialog

from src.config.application_config import AppConfig
from src.ui.widget.color_picker.screen_color import ScreenColorWidget
from src.undo_stack import UndoStack
from src.util.signals_blocked import signals_blocked

CELL_WIDTH = 28
CELL_HEIGHT = 24
NUM_COLUMNS = 8
NUM_STANDARD_PALETTE_ROWS = 6
NUM_CUSTOM_PALETTE_ROWS = 3


class _PaletteGrid(QWidget):

    selected = Signal(int, int)
    current_changed = Signal(int, int)
    color_changed = Signal(int, QColor)

    def __init__(self, rows: int, columns: int) -> None:
        super().__init__()
        self._num_rows = rows
        self._num_cols = columns
        self._cell_w = CELL_WIDTH
        self._cell_h = CELL_HEIGHT
        self._cur_row = 0
        self._cur_col = 0
        self._sel_row = -1
        self._sel_col = -1
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def selected_column(self) -> int:
        """Returns the selected column."""
        return self._sel_col

    def selected_row(self) -> int:
        """Returns the selected row."""
        return self._sel_row

    def cell_width(self) -> int:
        """Returns the width of a single color cell."""
        return self._cell_w

    def cell_height(self) -> int:
        """Returns the height of a single color cell."""
        return self._cell_h

    def row_at(self, y: int) -> int:
        """Returns the row at the given y-position."""
        return int(y / self._cell_h)

    def column_at(self, x: int) -> int:
        """Returns the column at the given x-position."""
        if self.isRightToLeft():
            return self._num_cols - int(x / self._cell_w) - 1
        return int(x / self._cell_w)

    def row_y(self, row: int) -> int:
        """Returns the y-position of the given row."""
        return self._cell_h * row

    def column_x(self, col: int) -> int:
        """Returns the x-position of the given column."""
        if self.isRightToLeft():
            return self._cell_w * (self._num_cols - col - 1)
        return self._cell_w * col

    def num_rows(self) -> int:
        """Return the number of grid rows."""
        return self._num_rows

    def num_cols(self) -> int:
        """Return the number of grid columns."""
        return self._num_cols

    def color_index(self, row: int, col: int) -> int:
        """Returns the color index of a given row and column."""
        if not 0 <= row < self._num_rows and 0 <= col < self._num_cols:
            raise IndexError(f'{row},{col} out of bounds')
        return col + row * self._num_cols

    def color_position(self, idx: int) -> Tuple[int, int]:
        """Returns the row and column of a given color index"""
        assert 0 <= idx < self._num_cols * self._num_rows
        row = idx // self._num_cols
        col = idx % self._num_cols
        return row, col

    def _cell_rect(self) -> QRect:
        return QRect(0, 0, self._cell_w, self._cell_h)

    def grid_size(self) -> QSize:
        """Returns the size of the grid in pixels."""
        return QSize(self._num_cols * self._cell_w, self._num_rows * self._cell_h)

    def _cell_geometry(self, row: int, col: int) -> QRect:
        if 0 <= row < self.num_rows() and 0 <= col < self.num_cols():
            return QRect(self.column_x(col), self.row_y(row), self._cell_w, self._cell_h)
        return QRect()

    def _update_cell(self, row: int, col: int) -> None:
        self.update(self._cell_geometry(row, col))

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draw the palette colors individually."""
        assert event is not None
        r = event.rect()
        cx = r.x()
        cy = r.y()
        cw = r.width()
        ch = r.height()
        col_first = self.column_at(cx)
        col_last = self.column_at(cx + cw)
        row_first = self.row_at(cy)
        row_last = self.row_at(cy + ch)

        if self.isRightToLeft():
            temp = col_first
            col_first = col_last
            col_last = temp

        painter = QPainter(self)
        cell_rect = QRect(0, 0, self.cell_width(), self.cell_height())

        if col_last < 0 or col_last >= self.num_cols():
            col_last = self.num_cols() - 1
        if row_last < 0 or row_last >= self.num_rows():
            row_last = self.num_rows() - 1

        for row in range(row_first, row_last + 1, 1):
            row_y = self.row_y(row)
            for col in range(min(col_first, col_last), max(col_first, col_last) + 1, 1):
                col_x = self.column_x(col)
                cell_rect.translate(col_x, row_y)
                self._paint_cell(painter, row, col, cell_rect)
                cell_rect.translate(-col_x, -row_y)

    def sizeHint(self) -> QSize:
        """Use size based on the grid size, bounded by 640x480."""
        self.ensurePolished()
        return self.grid_size().boundedTo(QSize(640, 480))

    def _paint_cell(self, painter: QPainter, row: int, col: int, bounds: QRect) -> None:
        margin = 3
        palette = self.palette()
        opt = QStyleOptionFrame()
        opt.initFrom(self)
        dfw = self.style().pixelMetric(QStyle.PixelMetric.PM_DefaultFrameWidth, opt)
        opt.lineWidth = dfw
        opt.midLineWidth = 1
        opt.rect = bounds.adjusted(margin, margin, -margin, -margin)
        opt.palette = palette
        opt.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Sunken
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Frame, opt, painter, self)
        margin += dfw

        if row == self._cur_row and col == self._cur_col:
            if self.hasFocus():
                opt = QStyleOptionFocusRect()
                opt.palette = palette
                opt.rect = bounds
                opt.state = QStyle.StateFlag.State_None | QStyle.StateFlag.State_KeyboardFocusChange
                self.style().drawPrimitive(QStyle.PrimitiveElement.PE_FrameFocusRect, opt, painter, self)
        self._paint_cell_contents(painter, row, col, opt.rect.adjusted(dfw, dfw, -dfw, -dfw))

    def _paint_cell_contents(self, painter: QPainter, row: int, col: int, bounds: QRect) -> None:
        painter.fillRect(bounds, Qt.GlobalColor.white)
        painter.setPen(Qt.GlobalColor.black)
        painter.drawLine(bounds.topLeft(), bounds.bottomRight())
        painter.drawLine(bounds.topRight(), bounds.bottomLeft())

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Sets the clicked cell as current."""
        assert event is not None
        pos = event.pos()
        self.set_current(self.row_at(pos.y()), self.column_at(pos.x()))

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Sets the clicked cell as selected."""
        self.set_selected(self._cur_row, self._cur_col)

    def set_current(self, row: int, col: int) -> None:
        """Set the current focused cell."""
        if self._cur_row == row and self._cur_col == col:
            return
        if row < 0 or col < 0:
            row = col = -1
        old_row = self._cur_row
        old_col = self._cur_col
        self._cur_row = row
        self._cur_col = col
        self._update_cell(old_row, old_col)
        self._update_cell(self._cur_row, self._cur_col)
        self.current_changed.emit(self._cur_row, self._cur_col)

    def set_selected(self, row: int, col: int) -> None:
        """Set the selected cell."""
        old_row = self._sel_row
        old_col = self._sel_col
        self._update_cell(old_row, old_col)
        self._update_cell(row, col)
        if row >= 0:
            self.selected.emit(row, col)

    def focusInEvent(self, event: Optional[QFocusEvent]) -> None:
        """Update focused cell on focus in"""
        self._update_cell(self._cur_row, self._cur_col)
        self.current_changed.emit(self._cur_row, self._cur_col)

    def focusOutEvent(self, event: Optional[QFocusEvent]) -> None:
        """Update focused cell on focus out"""
        self._update_cell(self._cur_row, self._cur_col)

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:
        """Use arrow keys and space to adjust selection."""
        assert event is not None
        match event.key():
            case Qt.Key.Key_Left:
                if self._cur_col > 0:
                    self.set_current(self._cur_row, self._cur_col - 1)
            case Qt.Key.Key_Right:
                if self._cur_col < self.num_cols() - 1:
                    self.set_current(self._cur_row, self._cur_col + 1)
            case Qt.Key.Key_Up:
                if self._cur_row > 0:
                    self.set_current(self._cur_row - 1, self._cur_col)
            case Qt.Key.Key_Down:
                if self._cur_row < self.num_rows() - 1:
                    self.set_current(self._cur_row + 1, self._cur_col)
            case Qt.Key.Key_Space:
                self.set_selected(self._cur_row, self._cur_col)
            case _:
                event.ignore()


class PaletteWidget(_PaletteGrid):
    """Widget holding multiple color options, largely ported from the internal QWellArray class within QColorDialog."""

    color_changed = Signal(int, QColor)
    color_selected = Signal(QColor)

    def __init__(self, rows: int, columns: int, colors: List[QColor]) -> None:
        super().__init__(rows, columns)
        self._colors = colors
        assert len(colors) == rows * columns, f'Expected {rows * columns} colors, got {len(colors)}'
        self._mouse_pressed = False
        self._ignoring_inputs = False
        self._old_current = QPoint(-1, -1)
        self._press_pos = QPoint()
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.setAcceptDrops(True)
        self.selected.connect(self._color_selected_slot)

    def _color_selected_slot(self, row: int, col: int) -> None:
        if row < 0 or row >= self.num_rows() or col < 0 or col >= self.num_cols():
            return
        i = self.color_index(row, col)
        self.color_selected.emit(self._colors[i])

    def connect_screen_color_picker(self, screen_color_picker: ScreenColorWidget) -> None:
        """Connect signal handlers for a screen color picker."""
        screen_color_picker.started_color_picking.connect(self._started_color_picking_slot)
        screen_color_picker.stopped_color_picking.connect(self._stopped_color_picking_slot)
        screen_color_picker.color_previewed.connect(self._color_preview_slot)
        screen_color_picker.color_selected.connect(self._screen_color_selected_slot)

    def disconnect_screen_color_picker(self, screen_color_picker: ScreenColorWidget) -> None:
        """Disconnect signal handlers for a screen color picker."""
        screen_color_picker.started_color_picking.disconnect(self._started_color_picking_slot)
        screen_color_picker.stopped_color_picking.disconnect(self._stopped_color_picking_slot)
        screen_color_picker.color_previewed.disconnect(self._color_preview_slot)
        screen_color_picker.color_selected.disconnect(self._screen_color_selected_slot)

    def _paint_cell_contents(self, painter: QPainter, row: int, col: int, bounds: QRect) -> None:
        i = self.color_index(row, col)
        color = self._colors[i]
        if color.isValid():
            painter.fillRect(bounds, color)
        else:
            super()._paint_cell_contents(painter, row, col, bounds)

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Save old selection before changing selection as usual."""
        assert event is not None
        if self._ignoring_inputs:
            event.ignore()
            return
        self._old_current = QPoint(self.selected_row(), self.selected_column())
        super().mousePressEvent(event)
        self._mouse_pressed = True
        self._press_pos = event.pos()

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Support drag and drop colors."""
        assert event is not None
        if self._ignoring_inputs:
            event.ignore()
            return
        super().mouseMoveEvent(event)
        if not self._mouse_pressed:
            return
        if (self._press_pos - event.pos()).manhattanLength() > QApplication.startDragDistance():
            self.set_current(self._old_current.x(), self._old_current.y())
            row = self.row_at(self._press_pos.y())
            col = self.column_at(self._press_pos.x())
            i = self.color_index(row, col)
            color = self._colors[i]
            mime_data = QMimeData()
            mime_data.setColorData(color)
            pixmap = QPixmap(self.cell_width(), self.cell_height())
            pixmap.fill(color)
            painter = QPainter(pixmap)
            painter.drawRect(0, 0, pixmap.width() - 1, pixmap.height() - 1)
            painter.end()
            drag = QDrag(self)
            drag.setMimeData(mime_data)
            drag.setPixmap(pixmap)
            self._mouse_pressed = False
            drag.exec(Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event: Optional[QDragEnterEvent]) -> None:
        """Accept drag events containing color data."""
        assert event is not None
        if self._ignoring_inputs:
            event.ignore()
            return
        if event.mimeData().hasColor():
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: Optional[QDragLeaveEvent]) -> None:
        """Return focus to the parent on drag leave."""
        assert event is not None
        if self._ignoring_inputs:
            event.ignore()
            return
        if self.hasFocus():
            parent = self.parentWidget()
            if parent is not None:
                parent.setFocus()

    def dragMoveEvent(self, event: Optional[QDragMoveEvent]) -> None:
        """Prepare to update color when drag event contains color data."""
        assert event is not None
        if self._ignoring_inputs:
            event.ignore()
            return
        if event.mimeData().hasColor():
            self.set_current(self.row_at(event.pos().y()), self.column_at(event.pos().x()))
            event.accept()
        else:
            event.ignore()

    def set_color(self, i: int, color: QColor) -> None:
        """Changes one of the colors in the grid."""
        assert 0 <= i < len(self._colors)
        if self._colors[i].toRgb() != color.toRgb():
            last_color = QColor(self._colors[i])
            new_color = QColor(color)

            def _update(next_color: QColor, idx=i) -> None:
                self._colors[idx] = next_color
                QTimer.singleShot(0, lambda: self.color_changed.emit(idx, next_color))
            UndoStack().commit_action(lambda: _update(new_color), lambda: _update(last_color),
                                      'PaletteWidget.set_color')
        self.update()

    def get_color(self, i: int) -> QColor:
        """Reads one of the colors from the grid"""
        assert 0 <= i < len(self._colors)
        return QColor(self._colors[i])

    def color_count(self) -> int:
        """Returns the number of grid colors"""
        return len(self._colors)

    def dropEvent(self, event: Optional[QDropEvent]) -> None:
        """Apply new color when dropped."""
        assert event is not None
        if self._ignoring_inputs:
            event.ignore()
            return
        color = QColor(event.mimeData().colorData())
        if color.isValid():
            row = self.row_at(event.pos().y())
            col = self.column_at(event.pos().x())
            try:
                i = self.color_index(row, col)
            except IndexError:
                event.ignore()
                return
            self.set_color(i, color)
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Update mouse status and defer to superclass on mouse release."""
        assert event is not None
        if self._ignoring_inputs:
            event.ignore()
            return
        if not self._mouse_pressed:
            return
        super().mouseReleaseEvent(event)
        self._mouse_pressed = False

    def select_color_if_present(self, color: QColor):
        """Selects a particular color if it's present in the grid."""
        row, col = self._find_color_in_grid(color)
        if row >= 0 and col >= 0:
            with signals_blocked(self):
                self.set_selected(row, col)

    def _started_color_picking_slot(self) -> None:
        self._ignoring_inputs = True
        self._old_current = QPoint(self.selected_row(), self.selected_column())

    def _find_color_in_grid(self, color: QColor) -> Tuple[int, int]:
        rgb_color = color.toRgb()
        for i, grid_color in enumerate(self._colors):
            if grid_color != rgb_color:
                continue
            return self.color_position(i)
        return -1, -1

    def _color_preview_slot(self, _, color: QColor) -> None:
        row, col = self._find_color_in_grid(color)
        self.set_current(row, col)

    def _screen_color_selected_slot(self, color: QColor) -> None:
        self.select_color_if_present(color)

    def _stopped_color_picking_slot(self):
        self._ignoring_inputs = False


def standard_colors() -> List[QColor]:
    """Returns the set of default color options."""
    colors = []
    for g in range(4):
        for r in range(4):
            for b in range(3):
                colors.append(QColor(r * 255 // 3, g * 255 // 3, b * 255 // 2))
    return colors


def config_colors(num_colors: int) -> List[QColor]:
    """Returns the set of configurable color options."""
    color_list = [QColor(color_str) for color_str in AppConfig().get(AppConfig.SAVED_COLORS)][:num_colors]
    while len(color_list) < num_colors:
        color_list.append(QColor())
    return color_list


class StandardColorPaletteWidget(PaletteWidget):
    """Select between predefined colors."""

    def __init__(self):
        super().__init__(NUM_STANDARD_PALETTE_ROWS, NUM_COLUMNS, standard_colors())
        self.setAcceptDrops(False)


class CustomColorPaletteWidget(PaletteWidget):
    """Select and update custom colors."""

    def __init__(self):
        colors = config_colors(NUM_CUSTOM_PALETTE_ROWS * NUM_COLUMNS)
        super().__init__(NUM_CUSTOM_PALETTE_ROWS, NUM_COLUMNS, colors)
        self.color_changed.connect(self._update_config_color_slot)
        AppConfig().connect(self, AppConfig.SAVED_COLORS, self._update_on_color_change)
        self._last_added_idx = -1
        for i, saved_color in enumerate(colors):
            if not saved_color.isValid():
                self._last_added_idx = i - 1
                break

    def _update_config_color_slot(self, idx: int, color: QColor) -> None:
        colors = config_colors(self.num_rows() * self.num_cols())
        colors[idx] = color
        AppConfig().set(AppConfig.SAVED_COLORS, [col.name(QColor.NameFormat.HexArgb) for col in colors])
        for i in range(self.num_cols() * 2):
            # QColorDialog is indexed by column instead of row.  This is intentional, it makes it less of a hassle
            # to keep them synchronized when CustomColorPaletteWidget adds extra rows. We do still need to recalculate
            # the index though:
            row, col = self.color_position(i)
            idx = row + col * self._num_rows
            QColorDialog.setCustomColor(idx, colors[i])

    def _update_on_color_change(self, color_list_str: str) -> None:
        color_list = [QColor(color_str) for color_str in color_list_str]
        for i, color in enumerate(color_list):
            self.set_color(i, color)

    def add_color(self, color: QColor) -> None:
        """Adds a new custom color.  This will replace the first duplicate color encountered, or the color after the
        previous changed index if no duplicates are found."""
        colors_traversed: Set[str] = set()
        next_idx = self._last_added_idx + 1
        for i in range(self.color_count()):
            prev_color = self.get_color(i).name(QColor.NameFormat.HexArgb)
            if prev_color in colors_traversed:
                next_idx = i
                break
            colors_traversed.add(prev_color)
        if next_idx >= self.color_count():
            next_idx = 0
        self.set_color(next_idx, color)
        self._last_added_idx = next_idx
