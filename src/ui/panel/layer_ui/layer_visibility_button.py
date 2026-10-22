"""Icon button used to show or hide an image layer."""
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication

from src.image.layers.layer import Layer
from src.ui.panel.layer_ui.layer_toggle_button import LayerToggleButton
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.palette_icon import palette_icon


# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.panel.layer.layer_visibility_button'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


VISIBILITY_TOOLTIP = _tr('Toggle layer visibility')
PARENT_HIDDEN_TOOLTIP = _tr('Toggle layer visibility. The layer is visible, but the group "{group_name}" hides it.')
ICON_PATH_VISIBLE_LAYER = f'{PROJECT_DIR}/resources/icons/layer/visible.svg'
ICON_PATH_HIDDEN_LAYER = f'{PROJECT_DIR}/resources/icons/layer/hidden.svg'
ICON_PATH_PARENT_HIDDEN_LAYER = f'{PROJECT_DIR}/resources/icons/layer/visible_parent_hidden.svg'


class LayerVisibilityButton(LayerToggleButton):
    """Shows or hides one layer, leaving the groups it is in unchanged.

    A layer that is visible inside a hidden group gets its own icon, and a tooltip naming that group.
    """

    def __init__(self, connected_layer: Layer) -> None:
        """Connect to the layer and load the initial icon."""
        super().__init__(connected_layer, ICON_PATH_VISIBLE_LAYER, ICON_PATH_HIDDEN_LAYER, disable_when_locked=False,
                         palette_icons=True)

    def _update_icon(self) -> None:
        hidden_parent = self._layer.hidden_parent if self._layer.visible else None
        if hidden_parent is None:
            super()._update_icon()
            self.setToolTip(VISIBILITY_TOOLTIP)
        else:
            self.setIcon(palette_icon(ICON_PATH_PARENT_HIDDEN_LAYER))
            self.setToolTip(PARENT_HIDDEN_TOOLTIP.format(group_name=hidden_parent.name))

    def _get_boolean(self, layer: Layer) -> bool:
        return layer.visible

    def _set_boolean(self, layer: Layer, value: bool) -> None:
        layer.visible = value

    def _get_signal(self, layer: Layer) -> Signal:
        return layer.visibility_changed
