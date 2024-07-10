"""A Qt5 color dialog with alternate reduced layouts."""
from typing import Optional, cast

from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QColorDialog, QWidget, QVBoxLayout, QHBoxLayout, \
    QTabWidget, QBoxLayout, QLayoutItem, QLayout, QSizePolicy

BASIC_PALETTE_TITLE = 'Basic Palette'

CUSTOM_PALETTE_TITLE = 'Custom Palette'

SPECTRUM_TAB_TITLE = 'Spectrum'

PALETTE_TAB_TITLE = 'Palette'

COMPONENT_TAB_TITLE = 'Color Component'

MODE_2X2 = '2x2'
MODE_4X1 = '4x1'
MODE_1X4 = '1x4'
MODE_2X1 = '2x1'
MODE_1X2 = '1x2'
MODE_1X1 = '1x1'


class ColorPicker(QColorDialog):
    """A Qt5 color dialog with alternate reduced layouts.

    This relies a lot on digging into non-public aspects of QColorDialog: it would probably be a good idea to rethink
    this at some point.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setOption(QColorDialog.ShowAlphaChannel, True)
        self.setOption(QColorDialog.NoButtons, True)
        self.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        self._size_policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setSizePolicy(self._size_policy)
        self._main_layout: Optional[QBoxLayout] = None
        self._mode = ''

        assert isinstance(self.children()[0], QVBoxLayout)
        self._outer_layout = cast(QVBoxLayout, self.children()[0])

        assert isinstance(self._outer_layout.children()[0], QHBoxLayout)
        main_layout = cast(QHBoxLayout, self._outer_layout.children()[0])

        def _move_first_item(source_layout: QBoxLayout, destination_layout: QBoxLayout) -> None:
            item = source_layout.itemAt(0)
            if item is None:
                return
            source_layout.removeItem(item)
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
        for i in range(2):
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
        main_layout.removeItem(component_layout)
        component_layout.setParent(None)
        main_layout.removeItem(palette_layout)
        palette_layout.setParent(None)
        self._outer_layout.removeItem(main_layout)
        main_layout.setParent(None)
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
            self._tab_panel.addTab(tab, title)
        self._tab_panel.show()
        self._tab_panel.setEnabled(True)

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
        component_widget = QWidget()
        component_widget.setSizePolicy(self._size_policy)
        component_layout = layout_class(component_widget)
        component_layout.addWidget(self._spectrum_panel)
        component_layout.addWidget(self._component_panel)
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

    def _panels(self) -> tuple[QWidget, QWidget, QWidget, QWidget]:
        return self._spectrum_panel, self._component_panel, self._basic_palette_panel, self._custom_palette_panel

    def _clear_layouts(self) -> None:
        def _clear_intermediate_item(inner_item: Optional[QWidget | QLayout | QLayoutItem]) -> None:
            if inner_item is None:
                return
            if inner_item in self._panels():
                inner_item.setParent(None)
                return
            widget = None
            layout = None
            if isinstance(inner_item, QLayoutItem):
                widget = inner_item.widget()
                layout = inner_item.layout()
                if widget is not None:
                    layout = widget.layout()
            elif isinstance(inner_item, QWidget):
                widget = inner_item
            elif isinstance(inner_item, QLayout):
                widget = None
                layout = inner_item
            if widget is not None and widget in self._panels():
                widget.setParent(None)
                return
            if layout is not None:
                while layout.count() > 0:
                    item = layout.itemAt(0)
                    assert item is not None
                    layout.removeItem(item)
                    _clear_intermediate_item(item)
                layout.setParent(None)
                layout.deleteLater()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        while self._tab_panel.count() > 0:
            tab = self._tab_panel.widget(0)
            self._tab_panel.removeTab(0)
            _clear_intermediate_item(tab)
        self._tab_panel.hide()
        if self._main_layout is not None:
            _clear_intermediate_item(self._main_layout)
            self._outer_layout.removeItem(self._main_layout)
            self._main_layout = None
