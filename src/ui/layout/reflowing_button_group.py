"""A group of buttons shown in one row when they fit at full size, and stacked in a column otherwise."""
from typing import Callable, Optional

from PySide6.QtCore import QEvent, QObject, QSize
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QWidget, QBoxLayout, QAbstractButton, QLayout, QSizePolicy

ROW_SPACING = 10


class _HeightForWidthBoxLayout(QBoxLayout):
    """A box layout whose height for a width comes from a function.

    Qt asks a widget's layout for its height for a width, not the widget, whenever the widget has a layout.
    """

    def __init__(self, height_for_width: Callable[[int], int], parent: QWidget) -> None:
        super().__init__(QBoxLayout.Direction.LeftToRight, parent)
        self._height_for_width = height_for_width

    def hasHeightForWidth(self) -> bool:
        """Returns true, so parent layouts ask for the height at each width."""
        return True

    def heightForWidth(self, width: int) -> int:
        """Returns the height from the layout's height function."""
        return self._height_for_width(width)


class ReflowingButtonGroup(QWidget):
    """Lays out buttons in a row when the group is wide enough for every visible button's size hint, or in a column.

    The group's minimum width is the column layout's, so a parent layout can always shrink it far enough to switch to a
    column. Its height depends on its width, which parent layouts read through heightForWidth. Showing or hiding a
    button re-checks the layout.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self._layout = _HeightForWidthBoxLayout(self.heightForWidth, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(ROW_SPACING)
        self._layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self._buttons: list[QAbstractButton] = []

    def add_button(self, button: QAbstractButton) -> None:
        """Adds a button after all previously added buttons."""
        self._buttons.append(button)
        self._layout.addWidget(button)
        button.installEventFilter(self)
        self._update_direction()

    @property
    def is_row(self) -> bool:
        """Returns whether the buttons are currently laid out in a single row."""
        return self._layout.direction() == QBoxLayout.Direction.LeftToRight

    def _visible_buttons(self) -> list[QAbstractButton]:
        return [button for button in self._buttons if not button.isHidden()]

    def row_width(self) -> int:
        """Returns the width the visible buttons need to fit in one row at their size hints."""
        visible = self._visible_buttons()
        if len(visible) == 0:
            return 0
        return sum(button.sizeHint().width() for button in visible) + ROW_SPACING * (len(visible) - 1)

    def heightForWidth(self, width: int) -> int:
        """Returns the height of one row if the buttons fit in it at this width, or of the column if they don't."""
        heights = [button.sizeHint().height() for button in self._visible_buttons()]
        if len(heights) == 0:
            return 0
        if width >= self.row_width():
            return max(heights)
        return sum(heights) + ROW_SPACING * (len(heights) - 1)

    def minimumSizeHint(self) -> QSize:
        """Returns the column layout's minimum width, and the current layout's minimum height."""
        width = max((button.minimumSizeHint().width() for button in self._buttons if not button.isHidden()), default=0)
        return QSize(width, self._layout.minimumSize().height())

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Switches between row and column layouts to fit the new width."""
        super().resizeEvent(event)
        self._update_direction()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Re-checks the layout when a button is shown or hidden."""
        if event.type() in (QEvent.Type.ShowToParent, QEvent.Type.HideToParent):
            self._update_direction()
        return super().eventFilter(watched, event)

    def _update_direction(self) -> None:
        direction = QBoxLayout.Direction.LeftToRight if self.width() >= self.row_width() \
            else QBoxLayout.Direction.TopToBottom
        if direction != self._layout.direction():
            self._layout.setDirection(direction)
            self.updateGeometry()
