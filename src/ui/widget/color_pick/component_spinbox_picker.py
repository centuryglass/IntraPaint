"""Select colors via HSV, RGBA, or HTML inputs, adapted from the Qt library's internal QColorShower found within
     QColorDialog."""
from typing import Optional, Tuple

from PySide6.QtCore import Signal, QPoint, QMimeData, QSignalBlocker, QRegularExpression
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QMouseEvent, Qt, QPixmap, QDrag, QDragEnterEvent, QDropEvent, \
    QRegularExpressionValidator
from PySide6.QtWidgets import QApplication, QWidget, QGridLayout, QLabel, QFrame, QSpinBox, QLineEdit

from src.ui.widget.color_pick.screen_color import ScreenColorWidget

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.color_picker.component_spinbox_picker'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


LABEL_HUE = _tr('Hu&e:')
LABEL_SATURATION = _tr('&Sat:')
LABEL_VALUE = _tr('&Val:')

LABEL_RED = _tr('&Red:')
LABEL_GREEN = _tr('&Green:')
LABEL_BLUE = _tr('Bl&ue:')
LABEL_ALPHA = _tr('A&lpha channel:')
LABEL_HTML = _tr('&HTML:')


class _ColorShowLabel(QFrame):

    color_dropped = Signal(QColor)

    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.Shape.Panel)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setAcceptDrops(True)
        self._mouse_pressed = False
        self._color = QColor()
        self._mouse_pos: Optional[QPoint] = None

    @property
    def color(self) -> QColor:
        """Access the displayed color."""
        return QColor(self._color)

    @color.setter
    def color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draw the color preview."""
        painter = QPainter(self)
        self.drawFrame(painter)
        painter.fillRect(self.contentsRect(), self._color)

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Keep track of click positions."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.LeftButton:
            self._mouse_pressed = True
            self._mouse_pos = event.pos()

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Handle color value drag and drop."""
        assert event is not None
        if not self._mouse_pressed:
            return
        assert self._mouse_pos is not None
        if (self._mouse_pos - event.pos()).manhattanLength() > QApplication.startDragDistance():
            mime_data = QMimeData()
            mime_data.setColorData(self._color)
            drag_pixmap = QPixmap(30, 20)
            drag_pixmap.fill(self._color)
            painter = QPainter(drag_pixmap)
            painter.drawRect(0, 0, drag_pixmap.width() - 1, drag_pixmap.height() - 1)
            painter.end()
            drag = QDrag(self)
            drag.setMimeData(mime_data)
            drag.setPixmap(drag_pixmap)
            self._mouse_pressed = False
            drag.exec(Qt.DropAction.CopyAction)

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Clear mouse state on mouse release."""
        self._mouse_pressed = False
        self._mouse_pos = None

    def dragEnterEvent(self, event: Optional[QDragEnterEvent]) -> None:
        """Accept drag events that contain color data."""
        mime_data = event.mimeData()
        if mime_data.hasColor():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: Optional[QDropEvent]) -> None:
        """Apply dropped color data."""
        color = QColor(event.mimeData().colorData())
        if color.isValid():
            self._color = color
            self.repaint()
            self.color_dropped.emit(color)
            event.accept()
        else:
            event.ignore()


class _QColSpinBox(QSpinBox):

    def __init__(self) -> None:
        super().__init__()
        self.setRange(0, 255)

    def setValue(self, value: int) -> None:
        """Set the value, suppressing signals."""
        blocker = QSignalBlocker(self)
        super().setValue(value)


class ComponentSpinboxPicker(QWidget):
    """Select colors via HSV, RGBA, or HTML inputs, adapted from the Qt library's internal QColorShower found within
     QColorDialog."""

    color_selected = Signal(QColor)

    def __init__(self) -> None:
        super().__init__()
        self._color = QColor()
        self._layout = QGridLayout(self)

        self._color_label = _ColorShowLabel()
        self._color_label.setMinimumHeight(60)
        self._color_label.setMinimumWidth(60)

        self._hue_box = _QColSpinBox()
        self._hue_box.setMaximum(359)
        self._sat_box = _QColSpinBox()
        self._val_box = _QColSpinBox()
        self._r_box = _QColSpinBox()
        self._g_box = _QColSpinBox()
        self._b_box = _QColSpinBox()
        self._a_box = _QColSpinBox()
        self._html_edit = QLineEdit()
        html_re = QRegularExpression('#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})')
        html_validator = QRegularExpressionValidator(html_re, self)
        self._html_edit.setValidator(html_validator)

        self._hue_label = QLabel(LABEL_HUE)
        self._sat_label = QLabel(LABEL_SATURATION)
        self._val_label = QLabel(LABEL_VALUE)
        self._r_label = QLabel(LABEL_RED)
        self._g_label = QLabel(LABEL_GREEN)
        self._b_label = QLabel(LABEL_BLUE)
        self._a_label = QLabel(LABEL_ALPHA)

        self._html_label = QLabel(LABEL_HTML)

        for label, widget in self._label_input_pairs:
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            label.setBuddy(widget)

        self._hue_box.valueChanged.connect(self._hue_slot)
        self._sat_box.valueChanged.connect(self._sat_slot)
        self._val_box.valueChanged.connect(self._val_slot)
        self._r_box.valueChanged.connect(self._r_slot)
        self._g_box.valueChanged.connect(self._g_slot)
        self._b_box.valueChanged.connect(self._b_slot)
        self._a_box.valueChanged.connect(self._a_slot)
        self._html_edit.textChanged.connect(self._text_change_slot)
        self._color_label.color_dropped.connect(self._color_drop_slot)

        spacing = self._layout.spacing()
        self._layout.setContentsMargins(spacing, spacing, spacing, spacing)
        self._layout.addWidget(self._color_label, 0, 0, -1, 1)

        self._layout.addWidget(self._hue_label, 0, 1)
        self._layout.addWidget(self._hue_box, 0, 2)
        self._layout.addWidget(self._sat_label, 1, 1)
        self._layout.addWidget(self._sat_box, 1, 2)
        self._layout.addWidget(self._val_label, 2, 1)
        self._layout.addWidget(self._val_box, 2, 2)

        self._layout.addWidget(self._r_label, 0, 3)
        self._layout.addWidget(self._r_box, 0, 4)
        self._layout.addWidget(self._g_label, 1, 3)
        self._layout.addWidget(self._g_box, 1, 4)
        self._layout.addWidget(self._b_label, 2, 3)
        self._layout.addWidget(self._b_box, 2, 4)

        self._layout.addWidget(self._a_label, 3, 1, 1, 3)
        self._layout.addWidget(self._a_box, 3, 4)

        self._layout.addWidget(self._html_label, 5, 1)
        self._layout.addWidget(self._html_edit, 5, 2, 1, 3)

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

    @property
    def color(self) -> QColor:
        """Access the widget's color value."""
        return self._color

    @color.setter
    def color(self, color: QColor) -> None:
        self._color = color
        hsv_color = color.toHsv()
        self._hue_box.setValue(hsv_color.hue())
        self._sat_box.setValue(hsv_color.saturation())
        self._val_box.setValue(hsv_color.value())
        rgb_color = color.toRgb()
        self._r_box.setValue(rgb_color.red())
        self._g_box.setValue(rgb_color.green())
        self._b_box.setValue(rgb_color.blue())
        self._a_box.setValue(rgb_color.alpha())
        self._html_edit.textChanged.disconnect(self._text_change_slot)
        self._html_edit.setText(rgb_color.name(QColor.NameFormat.HexArgb))
        self._html_edit.textChanged.connect(self._text_change_slot)
        self._color_label.color = rgb_color

    @property
    def _label_input_pairs(self) -> Tuple[Tuple[QLabel, QWidget], ...]:
        return ((self._hue_label, self._hue_box),
                (self._sat_label, self._sat_box),
                (self._val_label, self._val_box),
                (self._r_label, self._r_box),
                (self._g_label, self._g_box),
                (self._b_label, self._b_box),
                (self._a_label, self._a_box),
                (self._html_label, self._html_edit))

    def _hue_slot(self, hue: int) -> None:
        color = QColor(self._color.toHsv())
        color.setHsv(hue, color.saturation(), color.value())
        self.color = color

    def _sat_slot(self, sat: int) -> None:
        color = QColor(self._color.toHsv())
        color.setHsv(color.hue(), sat, color.value())
        self.color = color

    def _val_slot(self, val: int) -> None:
        color = QColor(self._color.toHsv())
        color.setHsv(color.hue(), color.saturation(), val)
        self.color = color

    def _r_slot(self, r: int) -> None:
        color = QColor(self._color.toRgb())
        color.setRed(r)
        self.color = color

    def _g_slot(self, g: int) -> None:
        color = QColor(self._color.toRgb())
        color.setGreen(g)
        self.color = color

    def _b_slot(self, b: int) -> None:
        color = QColor(self._color.toRgb())
        color.setBlue(b)
        self.color = color

    def _a_slot(self, a: int) -> None:
        color = QColor(self._color.toRgb())
        color.setAlpha(a)
        self.color = color

    def _text_change_slot(self, color_text: str) -> None:
        color = QColor(color_text)
        if color.isValid():
            self.color = color

    def _color_drop_slot(self, color: QColor) -> None:
        self.color = color

    def _started_color_picking_slot(self) -> None:
        for _, widget in self._label_input_pairs:
            widget.setEnabled(False)

    def _color_preview_slot(self, _, color: QColor) -> None:
        hsv_color = color.toHsv()
        self._hue_box.setValue(hsv_color.hue())
        self._sat_box.setValue(hsv_color.saturation())
        self._val_box.setValue(hsv_color.value())
        rgb_color = color.toRgb()
        self._r_box.setValue(rgb_color.red())
        self._g_box.setValue(rgb_color.green())
        self._b_box.setValue(rgb_color.blue())
        self._a_box.setValue(rgb_color.alpha())
        self._html_edit.textChanged.disconnect(self._text_change_slot)
        self._html_edit.setText(rgb_color.name(QColor.NameFormat.HexArgb))
        self._html_edit.textChanged.connect(self._text_change_slot)
        self._color_label.color = rgb_color

    def _screen_color_selected_slot(self, color: QColor) -> None:
        self.color = color

    def _stopped_color_picking_slot(self):
        for _, widget in self._label_input_pairs:
            widget.setEnabled(True)
        self.color = self._color
