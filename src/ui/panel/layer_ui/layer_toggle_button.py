"""Icon button used to toggle a boolean layer attribute."""
from typing import Optional

from PySide6.QtCore import QSize, SignalInstance
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtWidgets import QToolButton, QSizePolicy

from src.image.layers.layer import Layer
from src.util.shared_constants import SMALL_ICON_SIZE
from src.util.visual.palette_icon import palette_icon

BUTTON_MARGIN = 4


class LayerToggleButton(QToolButton):
    """Toggles a boolean layer property."""

    def __init__(self, connected_layer: Layer, true_icon_path: str, false_icon_path: str,
                 disable_when_locked: bool = True, palette_icons: bool = False, signal_true_icon: bool = False) -> None:
        """Connect to the layer and load the initial icon.

        With palette_icons, icons load through `palette_icon`. With signal_true_icon, the icon shown while the property
        is true loads as a signal icon.
        """
        super().__init__()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed))
        self.setIconSize(QSize(SMALL_ICON_SIZE, SMALL_ICON_SIZE))
        self._layer = connected_layer
        self._get_signal(self._layer).connect(self._update_icon)
        load_icon = palette_icon if palette_icons else QIcon
        self._true_icon = palette_icon(true_icon_path, signal=True) if signal_true_icon else load_icon(true_icon_path)
        self._false_icon = load_icon(false_icon_path)
        self._update_icon()
        self._disable_when_locked = disable_when_locked

        if disable_when_locked:
            connected_layer.lock_changed.connect(self._update_enabled)
        self._update_enabled()

    def _update_enabled(self, *_) -> None:
        # The lock signal's arguments may describe a parent group's lock, so read the state from the layer instead.
        self.setEnabled(self._can_toggle(self._layer))

    def _can_toggle(self, layer: Layer) -> bool:
        """Returns whether clicking the button can change the property."""
        return not self._disable_when_locked or (not layer.locked and not layer.parent_locked)

    # noinspection PyMethodMayBeStatic
    def sizeHint(self):
        """Use a fixed size for icons."""
        return QSize(SMALL_ICON_SIZE + BUTTON_MARGIN, SMALL_ICON_SIZE + BUTTON_MARGIN)

    def _update_icon(self):
        self.setIcon(self._true_icon if self._get_boolean(self._layer) else self._false_icon)

    def mousePressEvent(self, unused_event: Optional[QMouseEvent]) -> None:
        """Toggle the boolean property on click."""
        self._set_boolean(self._layer, not self._get_boolean(self._layer))

    def _get_boolean(self, layer: Layer) -> bool:
        raise NotImplementedError()

    def _set_boolean(self, layer: Layer, value: bool) -> None:
        raise NotImplementedError()

    def _get_signal(self, layer: Layer) -> SignalInstance:
        raise NotImplementedError
