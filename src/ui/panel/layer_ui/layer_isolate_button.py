"""Icon button used to activate or deactivate layer group isolation."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication

from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.ui.panel.layer_ui.layer_toggle_button import LayerToggleButton
from src.util.shared_constants import PROJECT_DIR

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.panel.layer.layer_isolate_button'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ISOLATE_TOOLTIP = _tr('Toggle layer group isolation')
ICON_PATH_ISOLATE_ON = f'{PROJECT_DIR}/resources/icons/layer/isolate_on.svg'
ICON_PATH_ISOLATE_OFF = f'{PROJECT_DIR}/resources/icons/layer/isolate_off.svg'


class LayerIsolateButton(LayerToggleButton):
    """Layer lock/unlock button."""

    def __init__(self, connected_layer: Layer) -> None:
        """Connect to the layer and load the initial icon."""
        assert isinstance(connected_layer, LayerGroup)
        super().__init__(connected_layer, ICON_PATH_ISOLATE_ON, ICON_PATH_ISOLATE_OFF)
        self.setToolTip(ISOLATE_TOOLTIP)

    def _get_boolean(self, layer: Layer) -> bool:
        assert isinstance(layer, LayerGroup)
        return layer.isolate

    def _set_boolean(self, layer: Layer, value: bool) -> None:
        assert isinstance(layer, LayerGroup)
        layer.isolate = value

    def _get_signal(self, layer: Layer) -> Signal:
        assert isinstance(layer, LayerGroup)
        return layer.isolate_changed
