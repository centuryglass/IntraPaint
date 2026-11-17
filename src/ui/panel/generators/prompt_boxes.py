"""The prompt box and the negative prompt fold under it, sharing the height they get in whole text lines.

Each box has a minimum and a maximum line count. Spare height goes to the boxes a line at a time,
`PROMPT_LINE_WEIGHT` lines to the prompt box for every `NEGATIVE_PROMPT_LINE_WEIGHT` to an open negative prompt box
(`src.ui.layout.line_share_layout`). The boxes' text never changes their heights, so a panel shrinks them to their
minimums before it scrolls, and they stay at their minimums while it scrolls.
"""
from typing import Optional

from PySide6.QtCore import QEvent, QObject, Signal
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from src.ui.layout.line_share_layout import LineShareLayout
from src.ui.widget.panel_section import PanelSection

# The prompt boxes show at most this many lines at once, and scroll their text past it:
PROMPT_MAX_LINES = 20
NEGATIVE_PROMPT_MAX_LINES = 10
# The prompt boxes never shrink below this many lines. A panel without room for them scrolls instead:
PROMPT_MIN_LINES = 4
NEGATIVE_PROMPT_MIN_LINES = 2
# An open negative prompt box takes one spare line for every two the prompt box takes:
PROMPT_LINE_WEIGHT = 2
NEGATIVE_PROMPT_LINE_WEIGHT = 1


class PromptBoxes(QWidget):
    """Stacks the prompt box over the negative prompt fold, with the parent layout's spacing between them.

    Layouts don't pass a maximum height up to their widgets, so the widget caps its own height and the fold's at what
    the boxes' maximum line counts allow. A parent that should leave the spare height past that below the boxes caps
    itself with `spare_height`. `limits_changed` is emitted when a style, font or fold change moves either cap.
    """

    limits_changed = Signal()

    def __init__(self, prompt_textbox: QPlainTextEdit, negative_textbox: QPlainTextEdit,
                 negative_fold: PanelSection, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._prompt_textbox = prompt_textbox
        self._negative_textbox = negative_textbox
        self._negative_fold = negative_fold
        self._layout = LineShareLayout(lambda: prompt_textbox.fontMetrics().lineSpacing(), self)
        self._layout.add_widget(prompt_textbox, PROMPT_LINE_WEIGHT)
        self._layout.add_widget(negative_fold, NEGATIVE_PROMPT_LINE_WEIGHT)
        negative_fold.expanded_changed.connect(self._fold_toggled)
        prompt_textbox.installEventFilter(self)
        self._size_boxes()

    def line_count(self, textbox: QPlainTextEdit) -> float:
        """Returns how many text lines fit in one of the boxes at its current height."""
        return (textbox.height() - self._box_height(0)) / textbox.fontMetrics().lineSpacing()

    def spare_height(self) -> int:
        """Returns how much taller than their minimum heights the boxes can grow."""
        return self._layout.maximumSize().height() - self._layout.minimumSize().height()

    def _box_height(self, lines: int) -> int:
        """Returns the height of a box that shows `lines` whole text lines."""
        textbox = self._prompt_textbox
        margin = round(textbox.document().documentMargin())
        return textbox.fontMetrics().lineSpacing() * lines + 2 * (textbox.frameWidth() + margin)

    def _size_boxes(self) -> None:
        """Sets each box's height limits to whole lines, the spacing to the parent layout's, and the caps to match."""
        self._prompt_textbox.setMinimumHeight(self._box_height(PROMPT_MIN_LINES))
        self._prompt_textbox.setMaximumHeight(self._box_height(PROMPT_MAX_LINES))
        self._negative_textbox.setMinimumHeight(self._box_height(NEGATIVE_PROMPT_MIN_LINES))
        self._negative_textbox.setMaximumHeight(self._box_height(NEGATIVE_PROMPT_MAX_LINES))
        parent = self.parentWidget()
        if parent is not None and parent.layout() is not None:
            self._layout.setSpacing(max(parent.layout().spacing(), 0))
        self._cap()

    def _cap(self) -> None:
        header = self._negative_fold.header_button.sizeHint().height()
        box = 0 if self._negative_fold.is_collapsed() else self._negative_textbox.maximumHeight()
        self._negative_fold.setMaximumHeight(header + box)
        self.setMaximumHeight(self._layout.maximumSize().height())
        self.limits_changed.emit()

    def _fold_toggled(self, _expanded: bool) -> None:
        self._cap()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name
        """Sizes the boxes again after the prompt box's font or frame changes."""
        if watched is self._prompt_textbox and event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._size_boxes()
        return super().eventFilter(watched, event)

    def changeEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """Takes the spacing of a new parent's layout."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.ParentChange:
            self._size_boxes()
