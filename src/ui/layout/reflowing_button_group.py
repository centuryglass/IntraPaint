"""A group of buttons shown in one row when they fit at full size, and stacked in a column otherwise."""
from typing import Optional

from PySide6.QtCore import QEvent, QObject, QSize
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QWidget, QBoxLayout, QAbstractButton, QLayout, QSizePolicy

ROW_SPACING = 10


class ReflowingButtonGroup(QWidget):
    """Lays out buttons in a row when the group is wide enough for every visible button's size hint, or in a column.

    The group's minimum width is the column layout's, so a parent layout can always shrink it far enough to switch to a
    column. Showing or hiding a button re-checks the layout.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
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

    def row_width(self) -> int:
        """Returns the width the visible buttons need to fit in one row at their size hints."""
        visible = [button for button in self._buttons if not button.isHidden()]
        if len(visible) == 0:
            return 0
        return sum(button.sizeHint().width() for button in visible) + ROW_SPACING * (len(visible) - 1)

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
