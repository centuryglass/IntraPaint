"""`FieldPair`, the two-form control the Stable Diffusion panel's action block and sections use for related fields."""
from typing import Callable, Optional

from PySide6.QtWidgets import QBoxLayout, QWidget

from src.ui.input_fields.number_field import NumberField
from src.ui.layout.panel_fit import held_weakly, limit_field_width


class FieldPair(QWidget):
    """Two fields side by side, or stacked when they don't fit that way. Used as a control with two forms. The pair is
    capped at `field_max_width`, so its right edge lines up with the other fields' in a wide side panel."""

    def __init__(self, first: QWidget, second: QWidget, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        limit_field_width(self)
        self._layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(first)
        self._layout.addWidget(second)
        self._fields = (first, second)

    def set_stacked(self, stacked: bool) -> None:
        """Stacks the fields, or puts them side by side."""
        self._layout.setDirection(QBoxLayout.Direction.TopToBottom if stacked else QBoxLayout.Direction.LeftToRight)

    def is_stacked(self) -> bool:
        """Returns whether the fields are stacked."""
        return self._layout.direction() == QBoxLayout.Direction.TopToBottom

    def fits_side_by_side(self, width: int) -> bool:
        """Returns whether both fields fit side by side in `width` without eliding their labels or values."""
        widths = [field.unelided_width() if isinstance(field, NumberField) else field.sizeHint().width()
                  for field in self._fields]
        return sum(widths) + max(self._layout.spacing(), 0) <= width

    def forms(self, column_width: Callable[[], Optional[int]]) -> tuple[Callable[[], None], Callable[[], None]]:
        """Returns the callbacks that put the pair side by side and stacked, for `DockSection.add`.

        `column_width` returns the width of the strip column the pair sits in, or None in a side panel. A side panel
        stacks the fields when the panel is too narrow for them side by side. A strip has a fixed column width, so it
        stacks them in both forms when the column is too narrow for both fields' text side by side. A bound method
        `column_width` is held weakly.
        """
        column_width = held_weakly(column_width)

        def _side_by_side() -> None:
            width = column_width()
            self.set_stacked(width is not None and not self.fits_side_by_side(width))

        def _stacked() -> None:
            self.set_stacked(True)

        return _side_by_side, _stacked
