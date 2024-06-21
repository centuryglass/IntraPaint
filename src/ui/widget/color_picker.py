"""A Qt5 color dialog with alternate reduced layouts."""
from typing import Optional, cast

from PyQt5.QtWidgets import QColorDialog, QWidget, QLabel, QPushButton, QLineEdit, QSpinBox, QVBoxLayout, QHBoxLayout, \
    QTabWidget, QBoxLayout, QLayoutItem, QLayout


class ColorPicker(QColorDialog):
    """A Qt5 color dialog with alternate reduced layouts.

    This relies a lot on digging into non-public aspects of QColorDialog: it would probably be a good idea to rethink
    this at some point.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setOption(QColorDialog.ShowAlphaChannel, True)
        self.setOption(QColorDialog.NoButtons, True)
        self.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)

        self._labels = self.findChildren(QLabel)
        buttons = self.findChildren(QPushButton)
        spin_boxes = self.findChildren(QSpinBox)
        self._html_box = self.findChild(QLineEdit)
        self._others = [widget for widget in self.findChildren(QWidget)
                        if not isinstance(widget, (QSpinBox, QLabel, QPushButton, QLineEdit))]

        self._main_layout: Optional[QBoxLayout] = None

        assert isinstance(self.children()[0], QVBoxLayout)
        self._outer_layout = cast(QVBoxLayout, self.children()[0])

        assert isinstance(self._outer_layout.children()[0], QHBoxLayout)
        main_layout = cast(QHBoxLayout, self._outer_layout.children()[0])

        def _move_first_item(source_layout: QBoxLayout, destination_layout: QBoxLayout) -> None:
            item = source_layout.itemAt(0)
            source_layout.removeItem(item)
            if item.widget() is not None:
                item.widget().hide()
            destination_layout.addItem(item)

        # Divide palettes into basic and custom palette panels:
        assert isinstance(main_layout.children()[0], QVBoxLayout)
        palette_layout = cast(QVBoxLayout, main_layout.children()[0])

        self._basic_palette_panel = QWidget()
        self._basic_palette_layout = QVBoxLayout(self._basic_palette_panel)
        for i in range(5):
            _move_first_item(palette_layout, self._basic_palette_layout)

        self._custom_palette_panel = QWidget()
        self._custom_palette_layout = QVBoxLayout(self._custom_palette_panel)
        while palette_layout.count() > 0:
            _move_first_item(palette_layout, self._custom_palette_layout)

        # Divide color control into spectrum and component panels:
        assert isinstance(main_layout.children()[1], QVBoxLayout)
        component_layout = cast(QVBoxLayout, main_layout.children()[1])

        self._spectrum_panel = QWidget()
        self._spectrum_panel_layout = QVBoxLayout(self._spectrum_panel)
        for i in range(2):
            _move_first_item(component_layout, self._spectrum_panel_layout)

        self._component_panel = QWidget()
        self._component_panel_layout = QVBoxLayout(self._component_panel)
        while component_layout.count() > 0:
            _move_first_item(component_layout, self._component_panel_layout)

        self._tab_panel = QTabWidget()
        self._outer_layout.insertWidget(0, self._tab_panel)
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

    def _clear_layouts(self) -> None:
        def _clear_intermediate_item(inner_item: QWidget | QLayout | QLayoutItem) -> None:
            saved_items = (self._component_panel, self._spectrum_panel, self._basic_palette_panel,
                           self._custom_palette_panel)
            if inner_item in saved_items:
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
                layout = widget.layout()
            elif isinstance(inner_item, QLayout):
                widget = None
                layout = inner_item
            if widget is not None and widget in saved_items:
                widget.setParent(None)
                return
            if layout is not None:
                while layout.count() > 0:
                    item = layout.itemAt(0)
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

    def set_default_mode(self) -> None:
        """Restores the default QColorDialog layout."""
        self._clear_layouts()
        self._main_layout = QHBoxLayout()
        self._outer_layout.addLayout(self._main_layout)
        palette_layout = QVBoxLayout()
        palette_layout.addWidget(self._basic_palette_panel)
        palette_layout.addWidget(self._custom_palette_panel)
        self._main_layout.addLayout(palette_layout)
        component_layout = QVBoxLayout()
        component_layout.addWidget(self._spectrum_panel)
        component_layout.addWidget(self._component_panel)
        self._main_layout.addLayout(component_layout)
        for panel in (self._component_panel, self._spectrum_panel, self._basic_palette_panel,
                      self._custom_palette_panel):
            panel.show()

    def set_vertical_two_tab_mode(self) -> None:
        """Splits the dialog in half vertically, using two tabs."""
        self._tab_panel.clear()
        self._palette_layout.setParent(None)
        self._palette_tab.setLayout(self._palette_layout)
        self._tab_panel.addTab(self._palette_tab, 'Palettes')
        self._component_layout.setParent(None)
        self._component_tab.setLayout(self._component_layout)
        self._tab_panel.addTab(self._component_tab, "Color Component")
        self._outer_layout.removeItem(self._main_layout)
        self._main_layout = None
        self._tab_panel.show()

    def _get_label(self, widget: QWidget) -> Optional[QLabel]:
        for label in self._labels:
            if label.buddy() == widget:
                return label
        return None
