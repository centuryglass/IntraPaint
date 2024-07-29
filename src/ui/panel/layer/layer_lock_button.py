"""Icon button used to lock or unlock an image layer."""

from PyQt6.QtCore import QSize, pyqtSignal, pyqtBoundSignal
from PyQt6.QtWidgets import QApplication

from src.image.layers.layer import Layer
from src.ui.panel.layer.layer_toggle_button import LayerToggleButton
from src.util.shared_constants import PROJECT_DIR

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.panel.layer.layer_lock_button'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


LOCK_TOOLTIP = _tr('Toggle layer lock')
ICON_PATH_LOCKED_LAYER = f'{PROJECT_DIR}/resources/icons/layer/lock_closed.svg'
ICON_PATH_UNLOCKED_LAYER = f'{PROJECT_DIR}/resources/icons/layer/lock_open.svg'


class LayerLockButton(LayerToggleButton):
    """Layer lock/unlock button."""

    def __init__(self, connected_layer: Layer) -> None:
        """Connect to the layer and load the initial icon."""
        super().__init__(connected_layer, ICON_PATH_LOCKED_LAYER, ICON_PATH_UNLOCKED_LAYER)
        self.setToolTip(LOCK_TOOLTIP)

    def _get_boolean(self, layer: Layer) -> bool:
        return layer.locked

    def _set_boolean(self, layer: Layer, value: bool) -> None:
        layer.locked = value

    def _get_signal(self, layer: Layer) -> pyqtSignal | pyqtBoundSignal:
        return layer.lock_changed
