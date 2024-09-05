"""Icon button used to toggle a boolean layer attribute."""
from typing import Optional

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtWidgets import QToolButton, QSizePolicy

from src.image.layers.layer import Layer
from src.util.shared_constants import ICON_SIZE


class LayerToggleButton(QToolButton):
    """Toggles a boolean layer property."""

    def __init__(self, connected_layer: Layer, true_icon_path: str, false_icon_path: str,
                 disable_when_locked: bool = True) -> None:
        """Connect to the layer and load the initial icon."""
        super().__init__()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed))
        self._layer = connected_layer
        self._get_signal(self._layer).connect(self._update_icon)
        self._true_icon = QIcon(true_icon_path)
        self._false_icon = QIcon(false_icon_path)
        self._update_icon()
        self._disable_when_locked = disable_when_locked

        if disable_when_locked:
            connected_layer.lock_changed.connect(self._lock_change_slot)
            if connected_layer.locked:
                self.setEnabled(False)

    def _lock_change_slot(self, _, is_locked: bool) -> None:
        self.setEnabled(not is_locked)

    # noinspection PyMethodMayBeStatic
    def sizeHint(self):
        """Use a fixed size for icons."""
        return QSize(ICON_SIZE, ICON_SIZE)

    def _update_icon(self):
        self.setIcon(self._true_icon if self._get_boolean(self._layer) else self._false_icon)

    def mousePressEvent(self, unused_event: Optional[QMouseEvent]) -> None:
        """Toggle the boolean property on click."""
        self._set_boolean(self._layer, not self._get_boolean(self._layer))

    def _get_boolean(self, layer: Layer) -> bool:
        raise NotImplementedError()

    def _set_boolean(self, layer: Layer, value: bool) -> None:
        raise NotImplementedError()

    def _get_signal(self, layer: Layer) -> Signal:
        raise NotImplementedError
