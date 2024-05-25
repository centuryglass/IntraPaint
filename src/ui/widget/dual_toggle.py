"""
A fancier Qt toggle button implementation that allows selecting between two options.
"""
from typing import Optional
from PyQt5.QtGui import QPixmap, QMouseEvent
from PyQt5.QtWidgets import QWidget, QFrame, QSizePolicy
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QEvent
from src.config.application_config import AppConfig
from src.ui.widget.label import Label


class DualToggle(QWidget):
    """A fancier Qt toggle button implementation that allows selecting between two options."""

    value_changed = pyqtSignal(str)

    def __init__(self,
                 parent: QWidget,
                 options: list[str],
                 config: Optional[AppConfig] = None,
                 orientation: Qt.Orientation = Qt.Orientation.Horizontal):
        """__init__.

        Parameters
        ----------
        parent : QWidget or None
            Optional parent widget.
        options : list of str
            Option names. Must be length 2, other lengths will raise ValueError.
        config : AppConfig
            Shared application configuration.
        orientation : Qt.Orientation
            Horizontal or vertical orientation.
        """
        super().__init__(parent)
        if len(options) != 2:
            raise ValueError(f"DualToggle expects two options, got {options}")
        self.option1 = options[0]
        self.option2 = options[1]
        self._orientation: Optional[Qt.Orientation] = None
        self._selected: Optional[str] = None
        bg_color = parent.palette().color(parent.backgroundRole())
        self.label1 = Label(options[0], config, self, bg_color=bg_color, orientation=orientation)
        self.label1.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.label1.set_inverted(True)
        self.label2 = Label(options[1], config, self, bg_color=bg_color, orientation=orientation)
        self.label2.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.set_orientation(orientation)

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Choose between horizontal and vertical orientation."""
        if self._orientation == orientation:
            return
        self._orientation = orientation
        self.label1.set_orientation(orientation)
        self.label2.set_orientation(orientation)
        if orientation == Qt.Orientation.Vertical:
            self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding))
        else:
            self.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))
        self.update()

    def sizeHint(self) -> QSize:
        """Return ideal size based on orientation and button size."""
        if self._orientation == Qt.Orientation.Vertical:
            return QSize(self.label1.sizeHint().width(),
                         self.label1.sizeHint().height() + self.label2.sizeHint().height() + 2)
        return QSize(self.label1.sizeHint().width() + self.label2.sizeHint().width() + 2,
                     self.label1.sizeHint().height())

    def resizeEvent(self, unused_event: Optional[QEvent]) -> None:
        """Divide space evenly between the two option buttons on resize."""
        if self._orientation == Qt.Orientation.Vertical:
            self.label1.setGeometry(0, 0, self.width(), (self.height() // 2) - 1)
            self.label2.setGeometry(0, (self.height() // 2) + 1, self.width(), (self.height() // 2) - 1)
        else:
            self.label1.setGeometry(0, 0, (self.width() // 2) - 1, self.height())
            self.label2.setGeometry((self.width() // 2) + 1, 0, (self.width() // 2) - 1, self.height())

    def toggle(self) -> None:
        """Selects whatever option isn't currently selected."""
        if self._selected == self.option1:
            self.set_selected(self.option2)
        elif self._selected == self.option2:
            self.set_selected(self.option1)

    def selected(self) -> str | None:
        """Returns the current selected option string."""
        return self._selected

    def set_selected(self, selection: Optional[str]) -> None:
        """Set the selected option string. Raises ValueError if the selection isn't one of the available options."""
        if selection == self._selected:
            return
        if selection != self.option1 and selection != self.option2 and selection is not None:
            raise ValueError(f"invalid option {selection}")
        self._selected = selection
        for label in (self.label1, self.label2):
            label.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
            label.set_inverted(False)
        if selection is not None:
            label = self.label1 if selection == self.option1 else self.label2
            label.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
            label.set_inverted(True)
        self.value_changed.emit(selection)

    def set_icons(self, icon1: str | QPixmap, icon2: str | QPixmap) -> None:
        """Sets icons for both option buttons, as either pixmaps or image paths."""
        self.label1.setIcon(icon1)
        self.label2.setIcon(icon2)

    def set_tooltips(self, text1: str, text2: str) -> None:
        """Set tooltip strings for both option buttons."""
        self.label1.setToolTip(text1)
        self.label2.setToolTip(text2)

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Toggle selection if an inactive options button is clicked with the left mouse button."""
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pt = event.pos()
            if self._orientation == Qt.Orientation.Vertical:
                self.set_selected(self.option1 if pt.y() < (self.height() // 2) else self.option2)
            else:
                self.set_selected(self.option1 if pt.x() < (self.width() // 2) else self.option2)
