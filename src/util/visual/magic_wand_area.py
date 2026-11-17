"""Which area the magic wand tool selects around a click. The persisted choice is `Cache.SELECTION_FILL_AREA`."""
from enum import Enum
from typing import Optional

from PySide6.QtWidgets import QApplication

from src.config.cache import Cache

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'util.visual.magic_wand_area'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


class FillArea(Enum):
    """The area a click selects. Values match the `Cache.SELECTION_FILL_AREA` options."""
    CONNECTED = 'Connected'
    BY_COLOR = 'By color'
    HOLES = 'Holes'

    @property
    def label(self) -> str:
        """Returns the translated name."""
        return FILL_AREA_LABELS[self]

    @property
    def tooltip(self) -> str:
        """Returns the translated description."""
        return FILL_AREA_TOOLTIPS[self]


FILL_AREA_LABELS = {
    FillArea.CONNECTED: _tr('Connected'),
    FillArea.BY_COLOR: _tr('By color'),
    FillArea.HOLES: _tr('Holes')
}
FILL_AREA_TOOLTIPS = {
    FillArea.CONNECTED: _tr('Select the connected area around the click that matches its color.'),
    FillArea.BY_COLOR: _tr('Select every pixel in the image that matches the clicked color, connected or not.'),
    FillArea.HOLES: _tr('Select the gaps enclosed by the current selection, ignoring image content.')
}


def stored_fill_area() -> FillArea:
    """Returns the area saved in `Cache.SELECTION_FILL_AREA`, or CONNECTED if the saved value is unrecognized."""
    try:
        return FillArea(Cache().get(Cache.SELECTION_FILL_AREA))
    except ValueError:
        return FillArea.CONNECTED
