"""Control panel widget for the clone stamp tool."""

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtWidgets import QWidget, QApplication, QLabel, QHBoxLayout, QSpinBox

from src.config.cache import Cache
from src.ui.layout.divider import Divider
from src.ui.panel.tool_control_panels.brush_tool_panel import BrushToolPanel
from src.util.shared_constants import SHORT_LABEL_X_POS, INT_MAX, INT_MIN, SHORT_LABEL_Y_POS

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.clone_stamp_tool_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


LABEL_TEXT_OFFSET = _tr('Offset:')
LABEL_TEXT_SELECTION_ONLY = _tr('Update selection only')


class CloneStampToolPanel(BrushToolPanel):
    """Control panel widget for the clone stamp tool."""

    offset_changed = Signal(QPoint)

    def __init__(self) -> None:
        self._offset_row = QWidget()
        super().__init__(size_key=Cache.CLONE_STAMP_TOOL_BRUSH_SIZE,
                         pressure_size_key=Cache.CLONE_STAMP_TOOL_PRESSURE_SIZE,
                         opacity_key=Cache.CLONE_STAMP_TOOL_OPACITY,
                         pressure_opacity_key=Cache.CLONE_STAMP_TOOL_PRESSURE_OPACITY,
                         hardness_key=Cache.CLONE_STAMP_TOOL_HARDNESS,
                         pressure_hardness_key=Cache.CLONE_STAMP_TOOL_PRESSURE_HARDNESS,
                         selection_only_label=LABEL_TEXT_SELECTION_ONLY,
                         added_rows=[self._offset_row, Divider(Qt.Orientation.Horizontal)])
        self._offset = QPoint()
        self._offset_layout = QHBoxLayout(self._offset_row)
        self._offset_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._offset_layout.addWidget(QLabel(SHORT_LABEL_X_POS))
        self._x_spinbox = QSpinBox()
        self._offset_layout.addWidget(self._x_spinbox, stretch=1)
        self._offset_layout.addWidget(QLabel(SHORT_LABEL_Y_POS))
        self._y_spinbox = QSpinBox()
        self._offset_layout.addWidget(self._y_spinbox, stretch=1)
        for spinbox in (self._x_spinbox, self._y_spinbox):
            spinbox.setValue(0)
            spinbox.setRange(INT_MIN, INT_MAX)

        def _update_x(new_x: int) -> None:
            if new_x == self._offset.x():
                return
            self._offset.setX(new_x)
            self.offset_changed.emit(QPoint(self._offset))

        self._x_spinbox.valueChanged.connect(_update_x)

        def _update_y(new_y: int) -> None:
            if new_y == self._offset.y():
                return
            self._offset.setY(new_y)
            self.offset_changed.emit(QPoint(self._offset))

        self._y_spinbox.valueChanged.connect(_update_y)

    @property
    def offset(self) -> QPoint:
        """Accesses the current offset value."""
        return QPoint(self._offset)

    @offset.setter
    def offset(self, new_offset: QPoint) -> None:
        self._x_spinbox.setValue(new_offset.x())
        self._y_spinbox.setValue(new_offset.y())
