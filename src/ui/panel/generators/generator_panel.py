"""Parent class of all image generator panel widgets. Provides no functionality, its only purpose is to provide an
   easy way to identify a widget as a generator control panel and to define the tab bar widget interface."""

from PySide6.QtWidgets import QWidget

from src.ui.layout.bordered_widget import BorderedWidget


class GeneratorPanel(BorderedWidget):
    """Parent class of all image generator panel widgets. Provides no functionality, its only purpose is to provide an
       easy way to identify a widget as a generator control panel and to define the tab bar widget interface."""

    def get_tab_bar_widgets(self) -> list[QWidget]:
        """Returns an empty list as the list of generator tab bar widgets, to be overridden by implementations."""
        return []
