"""A Qt5 color dialog with alternate reduced layouts."""
from typing import Optional, cast, Tuple

from PySide6.QtCore import QSize, Signal, QTimer
from PySide6.QtWidgets import QColorDialog, QWidget, QVBoxLayout, QHBoxLayout, \
    QTabWidget, QBoxLayout, QSizePolicy, QPushButton, QLabel, QApplication

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.color_picker'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


BASIC_PALETTE_TITLE = _tr('Basic Palette')
CUSTOM_PALETTE_TITLE = _tr('Custom Palette')
SPECTRUM_TAB_TITLE = _tr('Spectrum')
PALETTE_TAB_TITLE = _tr('Palette')
COMPONENT_TAB_TITLE = _tr('Color Component')

MODE_2X2 = '2x2'
MODE_4X1 = '4x1'
MODE_1X4 = '1x4'
MODE_2X1 = '2x1'
MODE_1X2 = '1x2'
MODE_1X1 = '1x1'

TIMER_INTERVAL = 100


class ColorPicker(QColorDialog):
    """A Qt5 color dialog with alternate reduced layouts.

    This relies a lot on digging into non-public aspects of QColorDialog: it would probably be a good idea to rethink
    this at some point.
    """

    _screen_color_picker_text_changed = Signal(str)
    _stopped_color_picking = Signal()

    def __init__(self, parent: Optional[QWidget] = None, always_show_pick_color_button=True) -> None:
        super().__init__(parent)
        self.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        self.setOption(QColorDialog.ColorDialogOption.NoButtons, True)
        self.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        self._size_policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setSizePolicy(self._size_policy)
        self._main_layout: Optional[QBoxLayout] = None
        self._mode = ''
        self._always_show_pick_color_button = always_show_pick_color_button

        assert isinstance(self.children()[0], QVBoxLayout)
        self._outer_layout = cast(QVBoxLayout, self.children()[0])

        assert isinstance(self._outer_layout.children()[0], QHBoxLayout)
        main_layout = cast(QHBoxLayout, self._outer_layout.children()[0])

        def _move_first_item(source_layout: QBoxLayout, destination_layout: QBoxLayout) -> None:
            item = source_layout.takeAt(0)
            if item is None:
                return
            item_widget = item.widget()
            item_layout = item.layout()
            if item_widget is not None:
                destination_layout.addWidget(item_widget)
            elif item_layout is not None:
                destination_layout.addLayout(item_layout)

        # Divide palettes into basic and custom palette panels:
        assert isinstance(main_layout.children()[0], QVBoxLayout)
        palette_layout = cast(QVBoxLayout, main_layout.children()[0])

        self._basic_palette_panel = QWidget()
        self._basic_palette_panel.setSizePolicy(self._size_policy)
        self._basic_palette_layout = QVBoxLayout(self._basic_palette_panel)

        # Save "pick screen color" button and connected label:
        button_item = palette_layout.itemAt(2)
        assert button_item is not None
        button_widget = button_item.widget()
        assert isinstance(button_widget, QPushButton)
        self._pick_color_button = button_widget

        pick_color_label_item = palette_layout.itemAt(3)
        assert pick_color_label_item is not None
        pick_color_label = pick_color_label_item.widget()
        assert isinstance(pick_color_label, QLabel)
        self._pick_color_label = pick_color_label

        # Handle transmitting label changes to duplicate labels:
        self._update_timer = QTimer(self)
        self._last_text = pick_color_label.text()

        def _check_text() -> None:
            label_text = self._pick_color_label.text()
            if label_text == self._last_text:
                return
            if label_text != self._last_text:
                self._last_text = label_text
                self._screen_color_picker_text_changed.emit(self._last_text)
            if self._pick_color_button.isEnabled():
                self._update_timer.stop()
                self._stopped_color_picking.emit()

        self._update_timer.timeout.connect(_check_text)
        self._pick_color_button.clicked.connect(lambda: self._update_timer.start(TIMER_INTERVAL))

        for _ in range(3):
            _move_first_item(palette_layout, self._basic_palette_layout)

        self._custom_palette_panel = QWidget()
        self._custom_palette_panel.setSizePolicy(self._size_policy)
        self._custom_palette_layout = QVBoxLayout(self._custom_palette_panel)
        while palette_layout.count() > 0:
            _move_first_item(palette_layout, self._custom_palette_layout)

        # Divide color control into spectrum and component panels:
        assert isinstance(main_layout.children()[1], QVBoxLayout)
        component_layout = cast(QVBoxLayout, main_layout.children()[1])

        self._spectrum_panel = QWidget()
        self._spectrum_panel.setSizePolicy(self._size_policy)
        self._spectrum_panel_layout = QVBoxLayout(self._spectrum_panel)
        for _ in range(2):
            _move_first_item(component_layout, self._spectrum_panel_layout)

        self._component_panel = QWidget()
        self._component_panel.setSizePolicy(self._size_policy)
        self._component_panel_layout = QVBoxLayout(self._component_panel)
        while component_layout.count() > 0:
            _move_first_item(component_layout, self._component_panel_layout)

        self._tab_panel = QTabWidget()
        self._tab_panel.setSizePolicy(self._size_policy)
        self._outer_layout.insertWidget(0, self._tab_panel)
        self._outer_layout.addStretch(10)
        self._tab_panel.setEnabled(False)
        self._tab_panel.setVisible(False)

        # Discard original layout:
        # main_layout.removeItem(component_layout)
        # component_layout.setParent(None)
        # main_layout.removeItem(palette_layout)
        # palette_layout.setParent(None)
        # self._outer_layout.removeItem(main_layout)
        # main_layout.setParent(None)
        self.set_default_mode()

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
        tab_names = (SPECTRUM_TAB_TITLE, COMPONENT_TAB_TITLE, BASIC_PALETTE_TITLE, CUSTOM_PALETTE_TITLE)
        for title, tab in zip(tab_names, self._panels()):
            if self._always_show_pick_color_button and title != BASIC_PALETTE_TITLE:
                widget = QWidget()
                layout = QVBoxLayout(widget)
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

        class _LinkedButton(QPushButton):
            def __init__(self, source_button: QPushButton, finish_signal: Signal) -> None:
                super().__init__(source_button.text())
                self.clicked.connect(source_button.clicked)
                source_button.clicked.connect(self._button_clicked_slot)
                finish_signal.connect(self._color_picking_ended_slot)

            def _button_clicked_slot(self) -> None:
                self.setEnabled(False)

            def _color_picking_ended_slot(self) -> None:
                self.setEnabled(True)

        button = _LinkedButton(self._pick_color_button, self._stopped_color_picking)
        label = QLabel()
        self._screen_color_picker_text_changed.connect(label.setText)
        return button, label

    def _use_linear_layout(self, layout_class) -> None:
        self._clear_layouts()
        self._main_layout = layout_class()
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
