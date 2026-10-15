"""A grid of toggle buttons that selects one option from a fixed list."""
from typing import Optional, cast

from PySide6.QtCore import Qt, QSize, Signal, QEvent
from PySide6.QtGui import QPixmap, QMouseEvent, QColor
from PySide6.QtWidgets import QWidget, QFrame, QSizePolicy, QApplication

from src.ui.widget.label import Label

# Space between adjacent option buttons:
BUTTON_SPACING = 2


class OptionToggle(QWidget):
    """A grid of toggle buttons that selects one option from a fixed list.

    Options fill the grid row by row, `columns` to a row. Every button gets an equal share of the widget. The
    highlighted button is the selected option unless a subclass overrides `highlighted_option`.
    """

    valueChanged = Signal(str)

    def __init__(self,
                 parent: Optional[QWidget],
                 options: list[str],
                 columns: int,
                 orientation: Qt.Orientation = Qt.Orientation.Horizontal,
                 display_names: Optional[list[str]] = None):
        """__init__.

        Parameters
        ----------
        parent : QWidget or None
            Optional parent widget.
        options : list of str
            Option names, at least one.
        columns : int
            Number of buttons in each row.
        orientation : Qt.Orientation
            Text orientation within each button.
        display_names : list of str, optional
            Button text for each option, in order. Defaults to the option strings.
        """
        super().__init__(parent)
        if len(options) == 0:
            raise ValueError('OptionToggle expects at least one option')
        if display_names is not None and len(display_names) != len(options):
            raise ValueError(f'Expected {len(options)} display names, got {display_names}')
        self._options = list(options)
        self._columns = max(1, columns)
        self._orientation: Optional[Qt.Orientation] = None
        self._selected: Optional[str] = None
        if parent is not None:
            bg_color = parent.palette().color(parent.backgroundRole())
        else:
            app = cast(QApplication, QApplication.instance())
            assert app is not None
            window = app.activeWindow()
            if window is not None:
                bg_color = app.palette().color(window.backgroundRole())
            else:
                bg_color = QColor(Qt.GlobalColor.gray)  # Fallback, should only happen during unit testing.
        label_text = display_names if display_names is not None else options
        self._labels = [Label(text, self, bg_color=bg_color, orientation=orientation) for text in label_text]
        self._label_orientation(orientation)
        self._apply_highlight(None)

    @property
    def options(self) -> list[str]:
        """Return accepted options."""
        return list(self._options)

    @property
    def _rows(self) -> int:
        return (len(self._options) + self._columns - 1) // self._columns

    def option_label(self, option: str) -> Label:
        """Returns the button that shows an option."""
        return self._labels[self._options.index(option)]

    def _label_orientation(self, orientation: Qt.Orientation) -> None:
        """Sets the text orientation of every button, and the size policy that suits it."""
        if self._orientation == orientation:
            return
        self._orientation = orientation
        for label in self._labels:
            label.set_orientation(orientation)
        if orientation == Qt.Orientation.Vertical:
            self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.MinimumExpanding))
        else:
            self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed))
        self.update()

    def _set_columns(self, columns: int) -> None:
        """Changes the number of buttons in each row."""
        self._columns = max(1, columns)
        self.updateGeometry()
        self._layout_buttons()

    def cell_size_hint(self) -> QSize:
        """Returns the size each button needs: the largest of the buttons' own size hints."""
        cell_size = QSize()
        for label in self._labels:
            cell_size = cell_size.expandedTo(label.sizeHint())
        return cell_size

    def sizeHint(self) -> QSize:
        """Returns room for equal buttons, each as large as the largest button."""
        cell_size = self.cell_size_hint()
        return QSize(cell_size.width() * self._columns + BUTTON_SPACING * (self._columns - 1),
                     cell_size.height() * self._rows + BUTTON_SPACING * (self._rows - 1))

    def cell_geometry(self, index: int) -> tuple[int, int, int, int]:
        """Returns the x, y, width and height of the button at an index in the option list."""
        row, column = divmod(index, self._columns)
        cell_width = (self.width() - BUTTON_SPACING * (self._columns - 1)) // self._columns
        cell_height = (self.height() - BUTTON_SPACING * (self._rows - 1)) // self._rows
        return (column * (cell_width + BUTTON_SPACING), row * (cell_height + BUTTON_SPACING), cell_width,
                cell_height)

    def _layout_buttons(self) -> None:
        for i, label in enumerate(self._labels):
            label.setGeometry(*self.cell_geometry(i))

    def resizeEvent(self, unused_event: Optional[QEvent]) -> None:
        """Divide space evenly between the option buttons on resize."""
        self._layout_buttons()

    def value(self) -> str | None:
        """Returns the current selected option string."""
        return self._selected

    # noinspection PyPep8Naming
    def setValue(self, selected_option: Optional[str]) -> None:
        """Set the selected option string. Raises ValueError if the choice isn't one of the available options."""
        if selected_option == self._selected:
            return
        if selected_option is not None and selected_option not in self._options:
            raise ValueError(f"invalid option {selected_option}")
        self._selected = selected_option
        self.update_highlight()
        self.valueChanged.emit(selected_option)

    def highlighted_option(self) -> Optional[str]:
        """Returns the option whose button is drawn pressed in."""
        return self._selected

    def update_highlight(self) -> None:
        """Draws the highlighted option's button pressed in and inverted, and every other button raised."""
        self._apply_highlight(self.highlighted_option())

    def _apply_highlight(self, highlighted: Optional[str]) -> None:
        for option, label in zip(self._options, self._labels):
            is_highlighted = option == highlighted
            label.setFrameStyle(QFrame.Shape.StyledPanel
                                | (QFrame.Shadow.Sunken if is_highlighted else QFrame.Shadow.Raised))
            label.set_inverted(is_highlighted)

    def set_icons(self, *icons: str | QPixmap) -> None:
        """Sets icons for the option buttons in order, as either pixmaps or image paths."""
        for label, icon in zip(self._labels, icons):
            label.setIcon(icon)

    def set_tooltips(self, *tooltips: str) -> None:
        """Set tooltip strings for the option buttons in order."""
        for label, tooltip in zip(self._labels, tooltips):
            label.setToolTip(tooltip)

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Selects the option under a left-click."""
        if event is None or event.button() != Qt.MouseButton.LeftButton:
            return
        pt = event.position().toPoint()
        column = min(pt.x() // max(self.width() // self._columns, 1), self._columns - 1)
        row = min(pt.y() // max(self.height() // self._rows, 1), self._rows - 1)
        index = row * self._columns + column
        if index < len(self._options):
            self.setValue(self._options[index])
