"""Icon button used to show or hide an image layer."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication

from src.image.layers.layer import Layer
from src.ui.panel.layer_ui.layer_toggle_button import LayerToggleButton
from src.util.shared_constants import PROJECT_DIR


# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.panel.layer.layer_visibility_button'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


VISIBILITY_TOOLTIP = _tr('Toggle layer visibility')
ICON_PATH_VISIBLE_LAYER = f'{PROJECT_DIR}/resources/icons/layer/visible.svg'
ICON_PATH_HIDDEN_LAYER = f'{PROJECT_DIR}/resources/icons/layer/hidden.svg'


class LayerVisibilityButton(LayerToggleButton):
    """Show/hide layer button."""

    def __init__(self, connected_layer: Layer) -> None:
        """Connect to the layer and load the initial icon."""
        super().__init__(connected_layer, ICON_PATH_VISIBLE_LAYER, ICON_PATH_HIDDEN_LAYER)
        self.setToolTip(VISIBILITY_TOOLTIP)

    def _get_boolean(self, layer: Layer) -> bool:
        return layer.visible

    def _set_boolean(self, layer: Layer, value: bool) -> None:
        layer.visible = value

    def _get_signal(self, layer: Layer) -> Signal:
        return layer.visibility_changed
