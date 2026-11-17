"""A combo box listing the layer blend modes in families, with the Porter-Duff compositing operators last.

Each item's data is its `CompositeMode`, and its text is the mode's name. Separators and the compositing heading are
disabled items, so keyboard navigation and selection skip them.

While the popup is open, highlighting a mode emits `preview_requested`, and closing the popup emits `preview_ended`.
The owner shows the preview and restores the layer's own mode. Choosing a mode also changes the current index, and Qt
doesn't fix the order of that and `preview_ended`, so the owner handles either order.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QApplication, QComboBox, QWidget

from src.image.composite_mode import CompositeMode

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.panel.layer_ui.blend_mode_combo_box'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


COMPOSITING_HEADING = _tr('Compositing (alpha only)')
MODE_TOOLTIP = _tr('Layer blend mode')

# Blend mode families in Krita and Photoshop order, each separated from the next:
MODE_FAMILIES: tuple[tuple[CompositeMode, ...], ...] = (
    (CompositeMode.NORMAL,),
    (CompositeMode.MULTIPLY, CompositeMode.DARKEN, CompositeMode.COLOR_BURN),
    (CompositeMode.SCREEN, CompositeMode.LIGHTEN, CompositeMode.COLOR_DODGE, CompositeMode.PLUS),
    (CompositeMode.OVERLAY, CompositeMode.SOFT_LIGHT, CompositeMode.HARD_LIGHT),
    (CompositeMode.DIFFERENCE,),
    (CompositeMode.HUE, CompositeMode.SATURATION, CompositeMode.COLOR, CompositeMode.LUMINOSITY),
)
# Porter-Duff operators, listed last under COMPOSITING_HEADING:
COMPOSITING_MODES = (CompositeMode.DESTINATION_IN, CompositeMode.DESTINATION_OUT, CompositeMode.SOURCE_ATOP,
                     CompositeMode.DESTINATION_ATOP)


class BlendModeComboBox(QComboBox):
    """Chooses a layer's `CompositeMode`, and reports the mode highlighted in its open popup for previewing."""

    preview_requested = Signal(CompositeMode)
    preview_ended = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setToolTip(MODE_TOOLTIP)
        self.setAccessibleName(MODE_TOOLTIP)
        for index, family in enumerate(MODE_FAMILIES):
            if index > 0:
                self.insertSeparator(self.count())
            for mode in family:
                self.addItem(mode, mode)
        self.insertSeparator(self.count())
        self.addItem(COMPOSITING_HEADING)
        model = self.model()
        assert isinstance(model, QStandardItemModel)
        heading = model.item(self.count() - 1)
        heading.setFlags(Qt.ItemFlag.NoItemFlags)
        for mode in COMPOSITING_MODES:
            self.addItem(mode, mode)
        self._popup_open = False
        self.highlighted.connect(self._highlighted_slot)

    def mode(self) -> Optional[CompositeMode]:
        """Returns the chosen mode."""
        data = self.currentData()
        return CompositeMode(data) if data is not None else None

    def set_mode(self, mode: CompositeMode) -> None:
        """Shows a mode as chosen, without previewing it."""
        index = self.findData(mode)
        if index >= 0 and index != self.currentIndex():
            self.setCurrentIndex(index)

    def showPopup(self) -> None:  # pylint: disable=invalid-name
        """Starts reporting highlighted modes for preview."""
        self._popup_open = True
        super().showPopup()

    def hidePopup(self) -> None:  # pylint: disable=invalid-name
        """Ends any preview."""
        super().hidePopup()
        self.end_preview()

    def end_preview(self) -> None:
        """Stops reporting highlighted modes, and emits `preview_ended` if the popup was open."""
        if self._popup_open:
            self._popup_open = False
            self.preview_ended.emit()

    def _highlighted_slot(self, index: int) -> None:
        data = self.itemData(index)
        if self._popup_open and data is not None:
            self.preview_requested.emit(CompositeMode(data))
