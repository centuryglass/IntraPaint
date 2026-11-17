"""The scrolling controls column that dialogs with a preview share.

The column has a fixed width beside the preview. `set_stacked(True)` lets it span the dialog's width instead, for a
dialog laid out top to bottom.
"""
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QBoxLayout, QDialog, QScrollArea, QSizePolicy, QWidget

QWIDGETSIZE_MAX = 16777215
# A dialog opens no larger than this fraction of the screen:
MAX_SCREEN_FRACTION = 0.8


class ControlsColumn(QScrollArea):
    """A frameless vertical scroll area of fixed width around a dialog's controls."""

    def __init__(self, controls: QWidget, width: int) -> None:
        super().__init__()
        self._column_width = width
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(controls)
        self.setFixedWidth(width)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def set_stacked(self, stacked: bool) -> None:
        """Widens the column to the dialog's width when stacked, or fixes it to its column width."""
        self.setMinimumWidth(0 if stacked else self._column_width)
        self.setMaximumWidth(QWIDGETSIZE_MAX if stacked else self._column_width)
        self.setSizePolicy(QSizePolicy.Policy.Expanding if stacked else QSizePolicy.Policy.Fixed,
                           QSizePolicy.Policy.Preferred if stacked else QSizePolicy.Policy.Expanding)


def stack_body_for_size(body: QBoxLayout, column: ControlsColumn, width: int, height: int) -> None:
    """Lays `body` out top to bottom while the dialog is taller than it is wide, and left to right otherwise."""
    stacked = height > width
    direction = QBoxLayout.Direction.TopToBottom if stacked else QBoxLayout.Direction.LeftToRight
    if body.direction() != direction:
        body.setDirection(direction)
        column.set_stacked(stacked)


def fit_dialog_to_screen(dialog: QDialog, preferred: QSize) -> None:
    """Resizes a dialog to `preferred`, bounded by a fraction of the screen but never below its minimum size."""
    size = preferred
    screen = dialog.screen()
    if screen is not None:
        available = screen.availableGeometry().size()
        size = size.boundedTo(QSize(round(available.width() * MAX_SCREEN_FRACTION),
                                    round(available.height() * MAX_SCREEN_FRACTION)))
    dialog.resize(size.expandedTo(dialog.minimumSizeHint()))
