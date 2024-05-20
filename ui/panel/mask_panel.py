"""
Panel used to edit the selected area of the edited image.
"""
from PyQt5.QtWidgets import QWidget, QPushButton, QColorDialog, QGridLayout
from PyQt5.QtCore import Qt, QSize, QEvent
from PyQt5.QtGui import QPainter, QPen, QCursor, QPixmap, QIcon, QColor

from ui.mask_creator import MaskCreator
from ui.config_control_setup import connected_checkbox
from ui.util.equal_margins import get_equal_margins
from ui.util.contrast_color import contrast_color
from ui.widget.dual_toggle import DualToggle
from ui.widget.param_slider import ParamSlider
try:
    from ui.widget.brush_picker import BrushPicker
except ImportError:
    BrushPicker = None
from data_model.config import Config
from data_model.layer_stack import LayerStack
from data_model.canvas.canvas import Canvas


class MaskPanel(QWidget):
    """MaskPanel is used to edit the selected area of the edited image."""

    def __init__(self,
            config: Config,
            mask_canvas: Canvas,
            sketch_canvas: Canvas,
            layer_stack: LayerStack):
        """Initialize the panel with the edited image and config values.

        Parameters
        ----------
        config : data_model.config.Config
            Shared config data object.
        mask_canvas : data_model.canvas.canvas.Canvas
            Canvas used for selecting inpainting areas.
        sketch_canvas : data_model.canvas.canvas.Canvas
            Canvas used for directly painting on the image.
        layer_stack : data_model.layer_stack.LayerStack
            Image layers being edited.
        """
        super().__init__()

        self._cursor_pixmap = QPixmap('./resources/cursor.png')
        small_cursor_pixmap = QPixmap('./resources/minCursor.png')
        self._small_cursor = QCursor(small_cursor_pixmap)
        eyedropper_icon = QPixmap('./resources/eyedropper.png')
        self._eyedropper_cursor = QCursor(eyedropper_icon, hotX=0, hotY=eyedropper_icon.height())
        self._last_cursor_size = None
        self._config = config
        self._pressure_size_checkbox = None
        self._pressure_opacity_checkbox = None
        self._color_picker_button = None
        self._brush_picker_button = None
        self._mask_canvas = mask_canvas
        self._sketch_canvas = sketch_canvas

        self._mask_creator = MaskCreator(self, mask_canvas, sketch_canvas, layer_stack, config)
        self._mask_creator.setMinimumSize(QSize(256, 256))
        def set_sketch_color(color: QColor):
            self._mask_creator.set_sketch_color(color)
            if self._color_picker_button is not None:
                icon = QPixmap(QSize(64, 64))
                icon.fill(color)
                self._color_picker_button.setIcon(QIcon(icon))
            self.update()
        self._mask_creator.color_selected.connect(set_sketch_color)

        self._mask_brush_size = mask_canvas.brush_size()
        self._sketch_brush_size = sketch_canvas.brush_size()
        self._layer_stack = layer_stack


        self._brush_size_slider = ParamSlider(self, 'Brush size', config, Config.MASK_BRUSH_SIZE)
        def update_brush_size(mode: MaskCreator.DrawMode, size: QSize):
            if mode == MaskCreator.DrawMode.MASK:
                self._mask_brush_size = size
                mask_canvas.set_brush_size(size)
            else:
                self._sketch_brush_size = size
                sketch_canvas.set_brush_size(size)
            self._update_brush_cursor()

        config.connect(self, Config.MASK_BRUSH_SIZE, lambda s: update_brush_size(MaskCreator.DrawMode.MASK, s))
        config.connect(self, Config.SKETCH_BRUSH_SIZE, lambda s: update_brush_size(MaskCreator.DrawMode.SKETCH, s))
        layer_stack.selection_bounds_changed.connect(lambda: self.resizeEvent(None))

        self._tool_toggle = DualToggle(self, [MaskCreator.ToolMode.PEN, MaskCreator.ToolMode.ERASER], config)
        self._tool_toggle.set_icons('./resources/pen.png', 'resources/eraser.png')
        self._tool_toggle.set_selected(MaskCreator.ToolMode.PEN)
        def set_drawing_tool(selection: MaskCreator.ToolMode):
            self._mask_creator.set_tool_mode(selection)
        self._tool_toggle.value_changed.connect(set_drawing_tool)

        self._clear_mask_button = QPushButton(self)
        self._clear_mask_button.setText('clear')
        self._clear_mask_button.setIcon(QIcon(QPixmap('./resources/clear.png')))
        def clear_mask():
            self._mask_creator.clear()
            self._tool_toggle.set_selected(MaskCreator.ToolMode.PEN)
        self._clear_mask_button.clicked.connect(clear_mask)

        self._fill_mask_button = QPushButton(self)
        self._fill_mask_button.setText('fill')
        self._fill_mask_button.setIcon(QIcon(QPixmap('./resources/fill.png')))
        def fill_mask():
            self._mask_creator.fill()
        self._fill_mask_button.clicked.connect(fill_mask)

        self._mask_sketch_toggle = DualToggle(self, [MaskCreator.DrawMode.MASK, MaskCreator.DrawMode.SKETCH], config)
        self._mask_sketch_toggle.set_icons('./resources/mask.png', 'resources/sketch.png')
        self._mask_sketch_toggle.set_tooltips('Draw over the area to be inpainted',
                'Add details to help guide inpainting')
        self._mask_sketch_toggle.value_changed.connect(lambda m: self.set_draw_mode(m if m != '' else None))


        self._color_picker_button = QPushButton(self)
        self._color_picker_button.setText('Color')
        self._color_picker_button.setToolTip('Select sketch brush color')
        self._color_picker_button.clicked.connect(lambda: set_sketch_color(QColorDialog.getColor()))
        set_sketch_color(self._mask_creator.get_sketch_color())
        self._color_picker_button.setVisible(False)

        if BrushPicker is not None:
            self._brush_picker_button = QPushButton(self)
            self._brush_picker = None
            self._brush_picker_button.setText('Brush')
            self._brush_picker_button.setToolTip('Select sketch brush type')
            self._brush_picker_button.setIcon(QIcon(QPixmap('./resources/brush.png')))
            def open_brush_picker():
                if self._brush_picker is None:
                    self._brush_picker = BrushPicker(self._config)
                self._brush_picker.show()
                self._brush_picker.raise_()
            self.open_brush_picker = open_brush_picker
            self._brush_picker_button.clicked.connect(open_brush_picker)
            self._brush_picker_button.setVisible(False)


        self._layout = QGridLayout()
        self._border_size = 2
        self._mask_creator.setContentsMargins(get_equal_margins(0))
        self.setLayout(self._layout)
        self._layout_type = None
        self._setup_correct_layout()

        # Enable/disable controls as appropriate when sketch or mask mode are enabled or disabled:
        def handle_sketch_mode_enabled_change(enabled: bool):
            self._mask_sketch_toggle.setEnabled(enabled and self._mask_canvas.enabled())
            if not enabled and self._mask_canvas.enabled():
                self.set_draw_mode(MaskCreator.DrawMode.MASK)
            elif enabled and not self._mask_canvas.enabled():
                self.set_draw_mode(MaskCreator.DrawMode.SKETCH)
            elif not enabled:
                self.set_draw_mode(MaskCreator.DrawMode.SKETCH if enabled else None)
            self.setEnabled(enabled or self._mask_canvas.enabled())
            self.resizeEvent(None)
        sketch_canvas.enabled_state_changed.connect(handle_sketch_mode_enabled_change)
        handle_sketch_mode_enabled_change(self._sketch_canvas.enabled())

        def handle_mask_mode_enabled_change(enabled: bool):
            self._mask_sketch_toggle.setEnabled(enabled and self._sketch_canvas.enabled())
            if not enabled and self._sketch_canvas.enabled():
                self.set_draw_mode(MaskCreator.DrawMode.SKETCH)
            elif enabled and not self._sketch_canvas.enabled():
                self.set_draw_mode(MaskCreator.DrawMode.MASK)
            else:
                self.set_draw_mode(MaskCreator.DrawMode.MASK if enabled else None)

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
        if self._pressure_size_checkbox is not None:
            widgets.append(self._pressure_size_checkbox)
            widgets.append(self._pressure_opacity_checkbox)
        if self._brush_picker_button is not None:
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
        if self._brush_picker_button is not None:
            self._layout.addWidget(self._brush_picker_button, 1, 1, 1, 2)
        else:
            self._layout.setRowStretch(1, 0)
        if not self._color_picker_button.isVisible():
            self._layout.setRowStretch(0, 0)
            self._layout.setRowStretch(1, 0)

        self._layout.addWidget(self._mask_sketch_toggle, 2, 1, 2, 1)
        self._layout.addWidget(self._tool_toggle, 4, 1, 2, 1)
        self._layout.addWidget(self._brush_size_slider, 2, 2, 4, 1)
        if self._pressure_size_checkbox is not None:
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
        if self._brush_picker_button is not None:
            self._layout.addWidget(self._color_picker_button, 2, 2)
            self._layout.addWidget(self._brush_picker_button, 2, 3)
        else:
            self._layout.addWidget(self._color_picker_button, 2, 2, 1, 2)
        if not self._color_picker_button.isVisible():
            self._layout.setRowStretch(2, 0)
        if self._pressure_size_checkbox is not None:
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
        edit_size = self._config.get(Config.EDIT_SIZE)
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


    def tabletEvent(self, unused_tablet_event):
        """Enable tablet controls on first tablet event"""
        if self._pressure_size_checkbox is None:
            config = self._config
            self._pressure_size_checkbox = connected_checkbox(self, config, Config.PRESSURE_SIZE)
            self._pressure_size_checkbox.setIcon(QIcon(QPixmap('./resources/pressureSize.png')))
            config.connect(self, Config.PRESSURE_SIZE, self._mask_creator.set_pressure_size_mode)
            self._mask_creator.set_pressure_size_mode(config.get(Config.PRESSURE_SIZE))

            self._pressure_opacity_checkbox = connected_checkbox(self, config, Config.PRESSURE_OPACITY)
            config.connect(self, Config.PRESSURE_OPACITY, self._mask_creator.set_pressure_opacity_mode)
            self._pressure_opacity_checkbox.setIcon(QIcon(QPixmap('./resources/pressureOpacity.png')))
            self._mask_creator.set_pressure_opacity_mode(config.get(Config.PRESSURE_OPACITY))
            # Re-apply visibility and layout based on current mode:
            self.set_draw_mode(self._mask_creator.get_draw_mode(), False)


    def set_draw_mode(self, mode: MaskCreator.DrawMode, ignore_if_unchanged: bool = True):
        """Sets whether the panel is sketching into the image or masking off an area for inpainting.

        Parameters
        ----------
        mode : MaskCreator.DrawMode
            Selected drawing mode.
        ignore_if_unchanged : bool, default=True
            If false, reload the appropriate layout for the selected mode even if that mode is already chosen.
        """
        if mode == self._mask_creator.get_draw_mode() and ignore_if_unchanged:
            return
        self._mask_creator.set_draw_mode(mode)
        self._mask_sketch_toggle.set_selected(mode)
        self._mask_creator.set_draw_mode(mode)
        self._color_picker_button.setVisible(mode == MaskCreator.DrawMode.SKETCH)
        if self._brush_picker_button is not None:
            self._brush_picker_button.setVisible(mode == MaskCreator.DrawMode.SKETCH)
            if self._pressure_opacity_checkbox is not None:
                self._pressure_size_checkbox.setVisible(mode == MaskCreator.DrawMode.MASK)
                self._pressure_opacity_checkbox.setVisible(False)
        elif self._pressure_size_checkbox is not None:
            self._pressure_size_checkbox.setVisible(True)
            self._pressure_opacity_checkbox.setVisible(mode == MaskCreator.DrawMode.SKETCH)

        self._brush_size_slider.connect_key(Config.MASK_BRUSH_SIZE if mode == MaskCreator.DrawMode.MASK
                else Config.SKETCH_BRUSH_SIZE)
        self._layout_type = None
        self.resizeEvent(None)
        self.update()


    def toggle_draw_mode(self):
        """Switches drawing mode to whatever mode isn't currently active."""
        self.set_draw_mode(MaskCreator.DrawMode.MASK \
                if self._mask_creator.get_draw_mode() == MaskCreator.DrawMode.SKETCH else MaskCreator.DrawMode.SKETCH)


    def get_brush_size(self) -> int:
        """Returns the current brush size in pixels."""
        return self._config.get(Config.MASK_BRUSH_SIZE \
                if self._mask_creator.get_draw_mode() == MaskCreator.DrawMode.MASK else Config.SKETCH_BRUSH_SIZE)


    def set_brush_size(self, size: int):
        """Sets the current brush size in pixels."""
        self._config.set(Config.MASK_BRUSH_SIZE if self._mask_creator.get_draw_mode() == MaskCreator.DrawMode.MASK
                else Config.SKETCH_BRUSH_SIZE, size)


    def paintEvent(self, event: QEvent):
        """Draws a border around the panel."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(contrast_color(self), self._border_size//2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawRect(1, 1, self.width() - 2, self.height() - 2)
        if not self._color_picker_button.isHidden():
            painter.setPen(QPen(self._mask_creator.get_sketch_color(), self._border_size//2, Qt.SolidLine, Qt.RoundCap,
                        Qt.RoundJoin))
            painter.drawRect(self._color_picker_button.geometry())


    def resizeEvent(self, unused_event: QEvent):
        """Selects the most appropriate layout based on available space whenever the panel size changes."""
        self._setup_correct_layout()
        self._update_brush_cursor()


    def eventFilter(self, unused_source, event: QEvent) -> bool:
        """Draw straight lines when shift is held, use the eyedropper tool when control is held in sketch mode."""
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Control and not self._mask_creator.get_draw_mode() == MaskCreator.DrawMode.MASK:
                self._mask_creator.set_line_mode(False)
                self._mask_creator.setCursor(self._eyedropper_cursor)
            elif event.key() == Qt.Key_Shift:
                self._mask_creator.set_line_mode(True)
        elif event.type() == QEvent.KeyRelease:
            if event.key() == Qt.Key_Control:
                self._last_cursor_size = None
                self._update_brush_cursor()
            elif event.key() == Qt.Key_Shift:
                self._mask_creator.set_line_mode(False)
        return False


    def select_pen_tool(self):
        """Switches to the pen tool if the eraser tool is currently selected."""
        self._tool_toggle.set_selected(MaskCreator.ToolMode.PEN)


    def select_eraser_tool(self):
        """Switches to the eraser tool if the pen tool is currently selected."""
        self._tool_toggle.set_selected(MaskCreator.ToolMode.ERASER)


    def swap_draw_tool(self):
        """Toggles between the pen and eraser tools."""
        self._tool_toggle.toggle()


    def undo(self):
        """Reverses the last drawing operation in the active canvas."""
        self._mask_creator.undo()


    def redo(self):
        """Restores an undone drawing operation in the active canvas."""
        self._mask_creator.redo()


    def _update_brush_cursor(self):
        """Recalculate brush cursor based on panel and brush sizes."""
        if not hasattr(self, '_mask_creator'):
            return
        brush_size = self.get_brush_size()
        scale =  max(self._mask_creator.get_image_display_size().width(), 1) / max(self._mask_canvas.width(), 1)
        scaled_size = max(int(brush_size * scale), 9)
        if scaled_size == self._last_cursor_size:
            return
        if scaled_size <= 10:
            self._mask_creator.setCursor(self._small_cursor)
        else:
            new_cursor = QCursor(self._cursor_pixmap.scaled(QSize(scaled_size, scaled_size)))
            self._mask_creator.setCursor(new_cursor)
        self._last_cursor_size = scaled_size
