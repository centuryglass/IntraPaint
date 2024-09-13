"""A Qt color picker widget with multiple layouts, heavily based on QColorDialog."""
from typing import Optional, Tuple

from PySide6.QtCore import QSize, QPoint
from PySide6.QtGui import QColor, QResizeEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, \
    QTabWidget, QBoxLayout, QSizePolicy, QPushButton, QLabel, QApplication

from src.ui.widget.color_picker.color_show_label import ColorShowLabel, PaletteColorShowLabel
from src.ui.widget.color_picker.component_spinbox_picker import ComponentSpinboxPicker
from src.ui.widget.color_picker.hsv_picker import HsvPicker
from src.ui.widget.color_picker.palette_widget import StandardColorPaletteWidget, CustomColorPaletteWidget
from src.ui.widget.color_picker.screen_color import ScreenColorWidget

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.color_picker'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


BASIC_PALETTE_TITLE = _tr('&Basic colors')
CUSTOM_PALETTE_TITLE = _tr('&Custom colors')
SPECTRUM_TAB_TITLE = _tr('&Spectrum')
PALETTE_TAB_TITLE = _tr('Pa&lette')
COMPONENT_TAB_TITLE = _tr('C&olor Component')

BUTTON_LABEL_PICK_SCREEN_COLOR = _tr('&Pick Screen Color')
BUTTON_LABEL_ADD_CUSTOM_COLOR = _tr('&Add to Custom Colors')

LABEL_TEXT_PICK_SCREEN_COLOR_INFO = _tr('Cursor at {x},{y}\nPress ESC to cancel')

MODE_2X2 = '2x2'
MODE_4X1 = '4x1'
MODE_1X4 = '1x4'
MODE_2X1 = '2x1'
MODE_1X2 = '1x2'
MODE_1X1 = '1x1'

TIMER_INTERVAL = 100


class TabbedColorPicker(ScreenColorWidget):
    """A Qt color picker widget with multiple layouts, heavily based on QColorDialog."""

    def __init__(self, always_show_pick_color_button=True) -> None:
        super().__init__()
        self._color = QColor()
        self._size_policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setSizePolicy(self._size_policy)
        self._outer_layout = QVBoxLayout(self)
        self._main_layout: Optional[QBoxLayout] = None
        self._mode = ''
        self._always_show_pick_color_button = always_show_pick_color_button

        self._basic_palette_panel = QWidget()
        self._basic_palette_panel.setSizePolicy(self._size_policy)
        self._basic_palette_layout = QVBoxLayout(self._basic_palette_panel)
        self._basic_palette_label = QLabel(BASIC_PALETTE_TITLE)
        self._basic_palette_layout.addWidget(self._basic_palette_label)

        self._basic_palette = StandardColorPaletteWidget()
        self._basic_palette_label.setBuddy(self._basic_palette_label)
        self._basic_palette_layout.addWidget(self._basic_palette)
        self._basic_palette.connect_screen_color_picker(self)
        self._basic_palette.color_selected.connect(self.set_current_color)

        self._basic_palette_preview = PaletteColorShowLabel()
        self._basic_palette_layout.addWidget(self._basic_palette_preview)
        self._basic_palette_preview.color_dropped.connect(self.set_current_color)

        self._pick_color_button = QPushButton()
        self._pick_color_button.setText(BUTTON_LABEL_PICK_SCREEN_COLOR)
        self._pick_color_button.clicked.connect(self.start_screen_color_picking)
        self._basic_palette_layout.addWidget(self._pick_color_button)

        self._custom_palette_panel = QWidget()
        self._custom_palette_panel.setSizePolicy(self._size_policy)
        self._custom_palette_layout = QVBoxLayout(self._custom_palette_panel)
        self._custom_palette_label = QLabel(CUSTOM_PALETTE_TITLE)
        self._custom_palette_layout.addWidget(self._custom_palette_label)

        self._custom_palette = CustomColorPaletteWidget()
        self._custom_palette_label.setBuddy(self._custom_palette)
        self._custom_palette.connect_screen_color_picker(self)
        self._custom_palette.color_selected.connect(self.set_current_color)
        self._custom_palette_layout.addWidget(self._custom_palette)

        self._custom_palette_preview = PaletteColorShowLabel()
        self._custom_palette_layout.addWidget(self._custom_palette_preview)
        self._custom_palette_preview.color_dropped.connect(self.set_current_color)

        self._add_custom_color_button = QPushButton()
        self._add_custom_color_button.setText(BUTTON_LABEL_ADD_CUSTOM_COLOR)
        self._add_custom_color_button.clicked.connect(lambda: self._custom_palette.add_color(self._color))
        self._custom_palette_layout.addWidget(self._add_custom_color_button)

        self._screen_preview_label = QLabel()
        self._screen_preview_label.setText('')
        self._screen_preview_label.setVisible(False)

        def _set_label_pos(pos: QPoint, _) -> None:
            self._screen_preview_label.setVisible(True)
            self._screen_preview_label.setText(LABEL_TEXT_PICK_SCREEN_COLOR_INFO.format(x=pos.x(), y=pos.y()))

        def _clear_label() -> None:
            self._screen_preview_label.setText('')
            self._screen_preview_label.setVisible(False)

        self.color_previewed.connect(_set_label_pos)
        self.stopped_color_picking.connect(_clear_label)
        self._custom_palette_layout.addWidget(self._screen_preview_label)

        # Divide color control into spectrum and component panels:
        self._spectrum_panel = QWidget()
        self._spectrum_panel.setSizePolicy(self._size_policy)
        self._spectrum_panel_layout = QVBoxLayout(self._spectrum_panel)
        self._hsv_picker = HsvPicker()
        self._hsv_picker.color_selected.connect(self.set_current_color)
        self._hsv_picker.connect_screen_color_picker(self)
        self._spectrum_panel_layout.addWidget(self._hsv_picker)

        self._component_panel = QWidget()
        self._component_panel.setSizePolicy(self._size_policy)
        self._component_panel_layout = QVBoxLayout(self._component_panel)
        self._component_picker = ComponentSpinboxPicker()
        self._component_picker.color_selected.connect(self.set_current_color)
        self._component_picker.connect_screen_color_picker(self)
        self._component_panel_layout.addWidget(self._component_picker)

        self._tab_panel = QTabWidget()
        self._tab_panel.setSizePolicy(self._size_policy)
        self._outer_layout.insertWidget(0, self._tab_panel)
        self._outer_layout.addStretch(10)
        self._tab_panel.setEnabled(False)
        self._tab_panel.setVisible(False)
        self.set_default_mode()

    def selected_color(self) -> QColor:
        """Gets the current selected color."""
        return QColor(self._color)

    def set_current_color(self, color: QColor) -> None:
        """Sets the current selected color."""
        if color == self._color:
            return
        self._color = color
        self._basic_palette.color_selected.disconnect(self.set_current_color)
        self._custom_palette.color_selected.disconnect(self.set_current_color)
        self._hsv_picker.color_selected.disconnect(self.set_current_color)
        self._component_picker.color_selected.disconnect(self.set_current_color)

        self._basic_palette_preview.color = color
        self._custom_palette_preview.color = color
        self._basic_palette.select_color_if_present(color)
        self._custom_palette.select_color_if_present(color)
        self._hsv_picker.color = color
        self._component_picker.color = color

        self._basic_palette.color_selected.connect(self.set_current_color)
        self._custom_palette.color_selected.connect(self.set_current_color)
        self._hsv_picker.color_selected.connect(self.set_current_color)
        self._component_picker.color_selected.connect(self.set_current_color)
        self.color_selected.emit(color)

    def panel_size(self) -> QSize:
        """Returns the expected size of one of the four color control panels."""
        panel_width = 0
        panel_height = 0
        for panel in self._panels():
            panel_size = panel.sizeHint()
            panel_width = max(panel_width, panel_size.width())
            panel_height = max(panel_height, panel_size.height())
        return QSize(panel_width, panel_height)

    def set_default_mode(self) -> None:
        """Restores the default 2x2 QColorDialog layout."""
        if self._mode == MODE_2X2:
            return
        self._mode = MODE_2X2
        self._clear_layouts()
        self._main_layout = QHBoxLayout()
        self._outer_layout.insertLayout(1, self._main_layout)
        palette_layout = QVBoxLayout()
        palette_layout.addWidget(self._basic_palette_panel)
        palette_layout.addWidget(self._custom_palette_panel)
        self._main_layout.addLayout(palette_layout)
        component_layout = QVBoxLayout()
        component_layout.addWidget(self._spectrum_panel)
        component_layout.addWidget(self._component_panel)
        self._main_layout.addLayout(component_layout)
        for panel in self._panels():
            panel.show()

    def set_horizontal_mode(self) -> None:
        """Displays the color picker in a wide 4x1 layout"""
        if self._mode == MODE_4X1:
            return
        self._mode = MODE_4X1
        self._use_linear_layout(QHBoxLayout)

    def set_vertical_mode(self) -> None:
        """Displays the color picker in a tall 1x4 layout"""
        if self._mode == MODE_1X4:
            return
        self._mode = MODE_1X4
        self._use_linear_layout(QVBoxLayout)

    def set_vertical_two_tab_mode(self) -> None:
        """Splits the dialog in half vertically, using two tabs."""
        if self._mode == MODE_1X2:
            return
        self._mode = MODE_1X2
        self._use_two_tab_layout(QVBoxLayout)

    def set_horizontal_two_tab_mode(self) -> None:
        """Splits the dialog in half vertically, using two tabs."""
        if self._mode == MODE_2X1:
            return
        self._mode = MODE_2X1
        self._use_two_tab_layout(QHBoxLayout)

    def set_four_tab_mode(self) -> None:
        """Put each of the four quadrants of the dialog in its own tab."""
        if self._mode == MODE_1X1:
            return
        self._mode = MODE_1X1
        self._clear_layouts()
        self._basic_palette_preview.setVisible(True)
        self._custom_palette_preview.setVisible(True)
        tab_names = (SPECTRUM_TAB_TITLE, COMPONENT_TAB_TITLE, BASIC_PALETTE_TITLE, CUSTOM_PALETTE_TITLE)
        for title, tab in zip(tab_names, self._panels()):
            if self._always_show_pick_color_button and title != BASIC_PALETTE_TITLE:
                widget = QWidget()
                layout = QVBoxLayout(widget)
                layout.setContentsMargins(1, 1, 1, 1)
                layout.setSpacing(1)
                layout.addWidget(tab)
                pick_button, pick_label = self._new_pick_screen_color_button()
                if title != CUSTOM_PALETTE_TITLE:
                    layout.addWidget(pick_label)
                layout.addWidget(pick_button)
                tab = widget
            self._tab_panel.addTab(tab, title)
        self._tab_panel.show()
        self._tab_panel.setEnabled(True)

    def _new_pick_screen_color_button(self) -> Tuple[QPushButton, QLabel]:
        """Make a new 'pick screen color' button"""
        pick_color_button = QPushButton()
        pick_color_button.setText(BUTTON_LABEL_PICK_SCREEN_COLOR)
        pick_color_button.clicked.connect(self.start_screen_color_picking)

        screen_preview_label = QLabel()
        screen_preview_label.setText('')
        screen_preview_label.setVisible(False)

        def _set_label_pos(pos: QPoint, _) -> None:
            screen_preview_label.setVisible(True)
            screen_preview_label.setText(LABEL_TEXT_PICK_SCREEN_COLOR_INFO.format(x=pos.x(), y=pos.y()))
        self.color_previewed.connect(_set_label_pos)

        def _clear_label() -> None:
            screen_preview_label.setText('')
            screen_preview_label.setVisible(False)
        self.stopped_color_picking.connect(_clear_label)
        return pick_color_button, screen_preview_label

    def _use_linear_layout(self, layout_class) -> None:
        self._clear_layouts()
        self._main_layout = layout_class()
        self._basic_palette_preview.setVisible(False)
        self._custom_palette_preview.setVisible(False)
        self._outer_layout.addLayout(self._main_layout)
        for panel in self._panels():
            assert self._main_layout is not None
            self._main_layout.addWidget(panel)
            panel.show()

    def _use_two_tab_layout(self, layout_class) -> None:
        self._clear_layouts()
        if self._always_show_pick_color_button:
            pick_color_button, pick_color_label = self._new_pick_screen_color_button()
        else:
            pick_color_button = None
            pick_color_label = None
        component_widget = QWidget()
        component_widget.setSizePolicy(self._size_policy)
        component_layout = layout_class(component_widget)
        component_layout.setSpacing(0)
        component_layout.setContentsMargins(1, 1, 1, 1)
        self._basic_palette_preview.setVisible(False)
        self._custom_palette_preview.setVisible(True)
        if layout_class == QHBoxLayout and pick_color_button is not None and pick_color_label is not None:
            left_panel_layout = QVBoxLayout()
            left_panel_layout.setSpacing(0)
            left_panel_layout.setContentsMargins(1, 1, 1, 1)
            left_panel_layout.addWidget(self._spectrum_panel)
            left_panel_layout.addWidget(pick_color_label)
            component_layout.addLayout(left_panel_layout)

            right_panel_layout = QVBoxLayout()
            right_panel_layout.setSpacing(0)
            right_panel_layout.setContentsMargins(1, 1, 1, 1)
            right_panel_layout.addWidget(self._component_panel)
            right_panel_layout.addWidget(pick_color_button)
            component_layout.addLayout(right_panel_layout)
        else:
            component_layout.addWidget(self._spectrum_panel)
            component_layout.addWidget(self._component_panel)
            if pick_color_label is not None and pick_color_button is not None:
                component_layout.addWidget(pick_color_label)
                component_layout.addWidget(pick_color_button)
        self._tab_panel.addTab(component_widget, COMPONENT_TAB_TITLE)
        palette_tab = QWidget()
        palette_tab.setSizePolicy(self._size_policy)
        palette_layout = layout_class(palette_tab)
        palette_layout.addWidget(self._basic_palette_panel)
        palette_layout.addWidget(self._custom_palette_panel)
        self._tab_panel.addTab(palette_tab, PALETTE_TAB_TITLE)
        self._tab_panel.show()
        for panel in self._panels():
            panel.show()
        self._tab_panel.setEnabled(True)

    def keyPressEvent(self, a0) -> None:
        """Override to prevent closing with escape."""

    def _panels(self) -> tuple[QWidget, QWidget, QWidget, QWidget]:
        return self._spectrum_panel, self._component_panel, self._basic_palette_panel, self._custom_palette_panel

    def _clear_layouts(self) -> None:
        for panel in self._panels():
            panel.setParent(self)

        while self._tab_panel.count() > 0:
            self._tab_panel.removeTab(0)
        self._tab_panel.hide()
        if self._main_layout is not None:
            self._outer_layout.removeItem(self._main_layout)
            self._main_layout = None
