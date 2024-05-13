"""
Panel used to edit the selected area of the edited image.
"""
from PyQt5.QtWidgets import (QWidget, QLabel, QSpinBox, QCheckBox, QPushButton, QRadioButton,
        QColorDialog, QGridLayout, QSpacerItem)
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QBuffer, QEvent
from PyQt5.QtGui import QPainter, QPen, QCursor, QPixmap, QBitmap, QIcon
from PIL import Image

from ui.mask_creator import MaskCreator
from ui.util.get_scaled_placement import get_scaled_placement
from ui.config_control_setup import connected_checkbox
from ui.util.equal_margins import get_equal_margins
from ui.util.contrast_color import contrast_color
from ui.widget.dual_toggle import DualToggle
from ui.widget.param_slider import ParamSlider
import os, sys

class DRAW_MODES:
    MASK = "Mask"
    SKETCH = "Sketch"
    def is_valid(option):
        return option == DRAW_MODES.MASK or option == DRAW_MODES.SKETCH or option is None

class TOOL_MODES:
    PEN = "Pen"
    ERASER = "Eraser"
    def is_valid(option):
        return option == TOOL_MODES.PEN or option == TOOL_MODES.ERASER or option is None

class MaskPanel(QWidget):
    def __init__(self, config, mask_canvas, sketch_canvas, edited_image):
        super().__init__()

        self._cursor_pixmap = QPixmap('./resources/cursor.png')
        small_cursor_pixmap = QPixmap('./resources/minCursor.png')
        self._small_cursor = QCursor(small_cursor_pixmap)
        eyedropper_icon = QPixmap('./resources/eyedropper.png')
        self._eyedropper_cursor = QCursor(eyedropper_icon, hotX=0, hotY=eyedropper_icon.height())
        self._eyedropper_mode = False
        self._last_cursor_size = None
        self._config = config
        self._draw_mode = None

        def set_sketch_color(color):
            self._mask_creator.set_sketch_color(color)
            if hasattr(self, '_color_picker_button'):
                icon = QPixmap(QSize(64, 64))
                icon.fill(color)
                self._color_picker_button.setIcon(QIcon(icon))
            self.update()
        self._mask_creator = MaskCreator(self, mask_canvas, sketch_canvas, edited_image, config, set_sketch_color)
        self._mask_creator.setMinimumSize(QSize(256, 256))
        self._mask_canvas = mask_canvas
        self._sketch_canvas = sketch_canvas

        self._mask_brush_size = mask_canvas.brush_size()
        self._sketch_brush_size = sketch_canvas.brush_size()
        self._edited_image = edited_image


        self._brush_size_slider = ParamSlider(self, "Brush size", config, "mask_brush_size")
        def update_brush_size(mode, size):
            if mode == DRAW_MODES.MASK:
                self._mask_brush_size = size
                mask_canvas.set_brush_size(size)
            else:
                self._sketch_brush_size = size
                sketch_canvas.set_brush_size(size)
            self._update_brush_cursor()

        config.connect(self, "mask_brush_size", lambda s: update_brush_size(DRAW_MODES.MASK, s))
        config.connect(self, "sketch_brush_size", lambda s: update_brush_size(DRAW_MODES.SKETCH, s))
        edited_image.selection_changed.connect(lambda: self.resizeEvent(None))

        self._tool_toggle = DualToggle(self, TOOL_MODES.PEN, TOOL_MODES.ERASER, config)
        self._tool_toggle.setIcons('./resources/pen.png', 'resources/eraser.png')
        self._tool_toggle.set_selected(TOOL_MODES.PEN)
        def set_drawing_tool(selection):
            self._mask_creator.set_use_eraser(selection == TOOL_MODES.ERASER)
        self._tool_toggle.value_changed.connect(set_drawing_tool)

        self._clear_mask_button = QPushButton(self)
        self._clear_mask_button.setText("clear")
        self._clear_mask_button.setIcon(QIcon(QPixmap('./resources/clear.png')))
        def clear_mask():
            self._mask_creator.clear()
            self._tool_toggle.set_selected(TOOL_MODES.PEN)
        self._clear_mask_button.clicked.connect(clear_mask)

        self._fill_mask_button = QPushButton(self)
        self._fill_mask_button.setText("fill")
        self._fill_mask_button.setIcon(QIcon(QPixmap('./resources/fill.png')))
        def fill_mask():
            self._mask_creator.fill()
        self._fill_mask_button.clicked.connect(fill_mask)

        self._mask_sketch_toggle = DualToggle(self, DRAW_MODES.MASK, DRAW_MODES.SKETCH, config)
        self._mask_sketch_toggle.setIcons('./resources/mask.png', 'resources/sketch.png')
        self._mask_sketch_toggle.setToolTips("Draw over the area to be inpainted", "Add details to help guide inpainting")
        self._mask_sketch_toggle.value_changed.connect(lambda m: self.set_draw_mode(m if m != "" else None))


        self._color_picker_button = QPushButton(self)
        self._color_picker_button.setText("Color")
        self._color_picker_button.setToolTip("Select sketch brush color")
        self._color_picker_button.clicked.connect(lambda: set_sketch_color(QColorDialog.getColor()))
        set_sketch_color(self._mask_creator.get_sketch_color())
        self._color_picker_button.setVisible(False)

        try:
            from ui.widget.brush_picker import BrushPicker
            self._brush_picker_button = QPushButton(self)
            self._brush_picker = None
            self._brush_picker_button.setText("Brush")
            self._brush_picker_button.setToolTip("Select sketch brush type")
            self._brush_picker_button.setIcon(QIcon(QPixmap('./resources/brush.png')))
            def open_brush_picker():
                if self._brush_picker is None:
                    self._brush_picker = BrushPicker(self._config)
                self._brush_picker.show()
                self._brush_picker.raise_()
            self.open_brush_picker = open_brush_picker
            self._brush_picker_button.clicked.connect(open_brush_picker)
            self._brush_picker_button.setVisible(False)
        except ImportError as err:
            print(f"Skipping brush selection init, brushlib loading failed: {err}")


        self._layout = QGridLayout()
        self._border_size = 2
        self._mask_creator.setContentsMargins(get_equal_margins(0))
        self.setLayout(self._layout)
        self._layout_type = None
        self._setup_correct_layout()

        # Enable/disable controls as appropriate when sketch or mask mode are enabled or disabled:
        def handle_sketch_mode_enabled_change(enabled):
            self._mask_sketch_toggle.setEnabled(enabled and self._mask_canvas.enabled())
            if not enabled and self._mask_canvas.enabled():
                self.set_draw_mode(DRAW_MODES.MASK)
            elif enabled and not self._mask_canvas.enabled():
                self.set_draw_mode(DRAW_MODES.SKETCH)
            elif not enabled:
                self.set_draw_mode(DRAW_MODES.SKETCH if enabled else None)
            self.setEnabled(enabled or self._mask_canvas.enabled())
            self.resizeEvent(None)
        sketch_canvas.enabled_state_changed.connect(handle_sketch_mode_enabled_change)
        handle_sketch_mode_enabled_change(self._sketch_canvas.enabled())

        def handle_mask_mode_enabled_change(enabled):
            self._mask_sketch_toggle.setEnabled(enabled and self._sketch_canvas.enabled())
            if not enabled and self._sketch_canvas.enabled():
                self.set_draw_mode(DRAW_MODES.SKETCH)
            elif enabled and not self._sketch_canvas.enabled():
                self.set_draw_mode(DRAW_MODES.MASK)
            else:
                self.set_draw_mode(DRAW_MODES.MASK if enabled else None)

            self.setEnabled(enabled or self._mask_canvas.enabled())
            self.resizeEvent(None)
        mask_canvas.enabled_state_changed.connect(handle_mask_mode_enabled_change)
        handle_mask_mode_enabled_change(self._mask_canvas.enabled())


    def _clear_control_layout(self):
        widgets = [ 
            self._mask_creator,
            self._brush_size_slider,
            self._tool_toggle,
            self._clear_mask_button,
            self._fill_mask_button,
            self._mask_sketch_toggle,
            self._color_picker_button
        ]
        if hasattr(self, '_pressure_size_checkbox'):
            widgets.append(self._pressure_size_checkbox)
            widgets.append(self._pressure_opacity_checkbox)
        if hasattr(self, '_brush_picker_button'):
            widgets.append(self._brush_picker_button)
        for widget in widgets:
            if self._layout.indexOf(widget) != -1:
                self._layout.removeWidget(widget)
        for i in range(self._layout.rowCount()):
            self._layout.setRowStretch(i, 10)
        for i in range(self._layout.columnCount()):
            self._layout.setColumnStretch(i, 10)


    def _setup_vertical_layout(self):
        self._clear_control_layout()
        self._tool_toggle.set_orientation(Qt.Orientation.Vertical)
        self._mask_sketch_toggle.set_orientation(Qt.Orientation.Vertical)
        self._brush_size_slider.set_orientation(Qt.Orientation.Vertical)
        border_size = self._brush_size_slider.sizeHint().width() // 3
        self._layout.addWidget(self._color_picker_button, 0, 1, 1, 2)
        if hasattr(self, '_brush_picker_button'):
            self._layout.addWidget(self._brush_picker_button, 1, 1, 1, 2)
        else:
            self._layout.setRowStretch(1, 0)
        if not self._color_picker_button.isVisible():
            self._layout.setRowStretch(0, 0)
            self._layout.setRowStretch(1, 0)

        self._layout.addWidget(self._mask_sketch_toggle, 2, 1, 2, 1)
        self._layout.addWidget(self._tool_toggle, 4, 1, 2, 1)
        self._layout.addWidget(self._brush_size_slider, 2, 2, 4, 1)
        if hasattr(self, '_pressure_size_checkbox'):
            self._layout.addWidget(self._pressure_size_checkbox, 6, 1, 1, 2)
            self._layout.addWidget(self._pressure_opacity_checkbox, 7, 1, 1, 2)
            if not self._pressure_size_checkbox.isVisible():
                self._layout.setRowStretch(6, 0)
            if not self._pressure_opacity_checkbox.isVisible():
                self._layout.setRowStretch(7, 0)
        else:
            self._layout.setRowStretch(6, 0)
            self._layout.setRowStretch(7, 0)
        self._layout.addWidget(self._fill_mask_button, 8, 1, 1, 2)
        self._layout.addWidget(self._clear_mask_button, 9, 1, 1, 2)
        self._layout.addWidget(self._mask_creator, 0, 0, self._layout.rowCount(), 1)
        self._layout.setColumnStretch(0, 255)

        border_size = self._brush_size_slider.sizeHint().width() // 4
        self._layout.setVerticalSpacing(border_size)
        self._layout.setHorizontalSpacing(border_size)
        self._layout.setContentsMargins(get_equal_margins(border_size))
        self._layout_type = Qt.Orientation.Vertical

    def _setup_horizontal_layout(self):
        self._clear_control_layout()
        self._tool_toggle.set_orientation(Qt.Orientation.Horizontal)
        self._mask_sketch_toggle.set_orientation(Qt.Orientation.Horizontal)
        self._brush_size_slider.set_orientation(Qt.Orientation.Horizontal)
        self._layout.addWidget(self._tool_toggle, 1, 2)
        self._layout.addWidget(self._mask_sketch_toggle, 1, 3)
        if hasattr(self, '_brush_picker_button'):
            self._layout.addWidget(self._color_picker_button, 2, 2)
            self._layout.addWidget(self._brush_picker_button, 2, 3)
        else:
            self._layout.addWidget(self._color_picker_button, 2, 2, 1, 2)
        if not self._color_picker_button.isVisible():
            self._layout.setRowStretch(2, 0)
        if hasattr(self, '_pressure_size_checkbox'):
            if self._pressure_opacity_checkbox.isVisible():
                self._layout.addWidget(self._pressure_size_checkbox, 3, 2)
                self._layout.addWidget(self._pressure_opacity_checkbox, 3, 3)
                if not self._pressure_size_checkbox.isVisible():
                    self._layout.setRowStretch(3, 0)
            else:
                self._layout.addWidget(self._pressure_size_checkbox, 3, 2, 1, 2)
        else:
            self._layout.setRowStretch(3, 0)
        self._layout.addWidget(self._brush_size_slider, 4, 2, 1, 2)
        self._layout.addWidget(self._clear_mask_button, 5, 2)
        self._layout.addWidget(self._fill_mask_button, 5, 3)
        self._layout.setRowStretch(0, 255)
        self._layout.setColumnStretch(0, 0)
        self._layout.setColumnStretch(1, 1)
        self._layout.setColumnStretch(4, 1)
        self._layout.addWidget(self._mask_creator, 0, 1, 1, self._layout.columnCount() - 1)
        for i in range(7, self._layout.rowCount()):
            self._layout.setRowStretch(i, 0)
        for i in range(6, self._layout.columnCount()):
            self._layout.setColumnStretch(i, 0)

        border_size = self._brush_size_slider.sizeHint().height() // 3
        self._layout.setVerticalSpacing(border_size)
        self._layout.setHorizontalSpacing(border_size)
        self._layout.setContentsMargins(get_equal_margins(self._border_size))
        self._layout_type = Qt.Orientation.Horizontal

    def _setup_correct_layout(self):
        widget_aspect_ratio = self.width() / self.height()
        edit_size = self._config.get("edit_size")
        edit_aspect_ratio = edit_size.width() / edit_size.height()
        if self._layout_type is None or abs(widget_aspect_ratio - edit_aspect_ratio) > 0.2:
            if widget_aspect_ratio > edit_aspect_ratio:
                if self._layout_type != Qt.Orientation.Vertical:
                    self._setup_vertical_layout()
            else:
                if self._layout_type != Qt.Orientation.Horizontal:
                    self._setup_horizontal_layout()
            self.update()
            self._update_brush_cursor()


    def tabletEvent(self, tablet_event):
        """Enable tablet controls on first tablet event"""
        if not hasattr(self, '_pressure_size_checkbox'):
            config = self._config
            self._pressure_size_checkbox = connected_checkbox(self, config, 'pressure_size', 'size',
                    'Tablet pen pressure affects line width')
            self._pressure_size_checkbox.setIcon(QIcon(QPixmap('./resources/pressureSize.png')))
            config.connect(self, 'pressure_size', lambda enabled: self._mask_creator.set_pressure_size_mode(enabled))
            self._mask_creator.set_pressure_size_mode(config.get('pressure_size'))

            self._pressure_opacity_checkbox = connected_checkbox(self, config, 'pressure_opacity', 'opacity',
                    'Tablet pen pressure affects color opacity (sketch mode only)')
            config.connect(self, 'pressure_opacity', lambda enabled: self._mask_creator.set_pressure_opacity_mode(enabled))
            self._pressure_opacity_checkbox.setIcon(QIcon(QPixmap('./resources/pressureOpacity.png')))
            self._mask_creator.set_pressure_opacity_mode(config.get('pressure_opacity'))
            # Re-apply visibility and layout based on current mode:
            self.set_draw_mode(self._draw_mode, False)

    def set_draw_mode(self, mode, ignore_if_unchanged=True):
        if mode == self._draw_mode and ignore_if_unchanged:
            return
        if not DRAW_MODES.is_valid(mode):
            raise Exception(f"tried to set invalid drawing mode {mode}")
        if mode == DRAW_MODES.MASK and not self._mask_canvas.enabled():
            raise Exception("called setDrawMode(MASK) when mask mode is disabled")
        if mode == DRAW_MODES.SKETCH and not self._sketch_canvas.enabled():
            raise Exception("called setDrawMode(SKETCH) when sketch mode is disabled")
        self._draw_mode = mode
        self._mask_sketch_toggle.set_selected(mode)
        self._mask_creator.set_sketch_mode(mode == DRAW_MODES.SKETCH)
        self._color_picker_button.setVisible(mode == DRAW_MODES.SKETCH)
        if hasattr(self, '_brush_picker_button'):
            self._brush_picker_button.setVisible(mode == DRAW_MODES.SKETCH)
            if hasattr(self, '_pressure_opacity_checkbox'):
                self._pressure_size_checkbox.setVisible(mode == DRAW_MODES.MASK)
                self._pressure_opacity_checkbox.setVisible(False)
        elif hasattr(self, '_pressure_size_checkbox'):
            self._pressure_size_checkbox.setVisible(True)
            self._pressure_opacity_checkbox.setVisible(mode == DRAW_MODES.SKETCH)

        self._brush_size_slider.connect_key("mask_brush_size" if mode == DRAW_MODES.MASK else "sketch_brush_size")
        self._layout_type = None
        self.resizeEvent(None)
        self.update()

    def toggle_draw_mode(self):
        if self._draw_mode is not None:
            self.set_draw_mode(DRAW_MODES.MASK if self._draw_mode == DRAW_MODES.SKETCH else DRAW_MODES.SKETCH)

    def get_brush_size(self):
        return self._config.get("mask_brush_size" if self._draw_mode == DRAW_MODES.MASK else "sketch_brush_size")

    def set_brush_size(self, size):
        self._config.set("mask_brush_size" if self._draw_mode == DRAW_MODES.MASK else "sketch_brush_size", size)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(contrast_color(self), self._border_size//2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawRect(1, 1, self.width() - 2, self.height() - 2)
        if not self._color_picker_button.isHidden():
            painter.setPen(QPen(self._mask_creator.get_sketch_color(), self._border_size//2, Qt.SolidLine, Qt.RoundCap,
                        Qt.RoundJoin))
            painter.drawRect(self._color_picker_button.geometry())

    def resizeEvent(self, event):
        self._setup_correct_layout()
        self._update_brush_cursor()

    def eventFilter(self, source, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Control and not self._draw_mode == DRAW_MODES.MASK:
                self._eyedropper_mode = True
                self._mask_creator.set_eyedropper_mode(True)
                self._mask_creator.set_line_mode(False)
                self._mask_creator.setCursor(self._eyedropper_cursor)
            elif event.key() == Qt.Key_Shift:
                self._mask_creator.set_line_mode(True)
        elif event.type() == QEvent.KeyRelease:
            if event.key() == Qt.Key_Control and self._eyedropper_mode:
                self._eyedropper_mode = False
                self._mask_creator.set_eyedropper_mode(False)
                self._last_cursor_size = None
                self._update_brush_cursor()
            elif event.key() == Qt.Key_Shift:
                self._mask_creator.set_line_mode(False)
        return False

    def select_pen_tool(self):
        self._tool_toggle.set_selected(TOOL_MODES.PEN)

    def select_eraser_tool(self):
        self._tool_toggle.set_selected(TOOL_MODES.ERASER)

    def swap_draw_tool(self):
        self._tool_toggle.toggle()

    def undo(self):
        self._mask_creator.undo()

    def redo(self):
        self._mask_creator.redo()

    def _update_brush_cursor(self):
        if not hasattr(self, '_mask_creator'):
            return
        brush_size = self._config.get("mask_brush_size" if self._draw_mode == DRAW_MODES.MASK else "sketch_brush_size")
        scale = max(self._mask_creator.get_image_display_size().width(), 1) / max(self._mask_canvas.width(), 1)
        scaled_size = max(int(brush_size * scale), 9)
        if scaled_size == self._last_cursor_size:
            return
        if scaled_size <= 10:
            self._mask_creator.setCursor(self._small_cursor)
        else:
            new_cursor = QCursor(self._cursor_pixmap.scaled(QSize(scaled_size, scaled_size)))
            self._mask_creator.setCursor(new_cursor)
        self._last_cursor_size = scaled_size
