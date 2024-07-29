"""Icon button used to lock or unlock image layer alpha."""

from PyQt6.QtCore import pyqtSignal, pyqtBoundSignal
from PyQt6.QtWidgets import QApplication

from src.image.layers.image_layer import ImageLayer
from src.image.layers.layer import Layer
from src.ui.panel.layer_ui.layer_toggle_button import LayerToggleButton
from src.util.shared_constants import PROJECT_DIR

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.panel.layer.layer_alpha_lock_button'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ALPHA_LOCK_TOOLTIP = _tr('Toggle layer transparency lock')
ICON_PATH_LOCKED_LAYER = f'{PROJECT_DIR}/resources/icons/layer/alpha_lock_closed.svg'
ICON_PATH_UNLOCKED_LAYER = f'{PROJECT_DIR}/resources/icons/layer/alpha_lock_open.svg'


class LayerAlphaLockButton(LayerToggleButton):
    """Layer lock/unlock button."""

    def __init__(self, connected_layer: Layer) -> None:
        """Connect to the layer and load the initial icon."""
        assert isinstance(connected_layer, ImageLayer)
        super().__init__(connected_layer, ICON_PATH_LOCKED_LAYER, ICON_PATH_UNLOCKED_LAYER)
        self.setToolTip(ALPHA_LOCK_TOOLTIP)

    def _get_boolean(self, layer: Layer) -> bool:
        assert isinstance(layer, ImageLayer)
        return layer.alpha_locked

    def _set_boolean(self, layer: Layer, value: bool) -> None:
        assert isinstance(layer, ImageLayer)
        layer.alpha_locked = value

    def _get_signal(self, layer: Layer) -> pyqtSignal | pyqtBoundSignal:
        assert isinstance(layer, ImageLayer)
        return layer.alpha_lock_changed
