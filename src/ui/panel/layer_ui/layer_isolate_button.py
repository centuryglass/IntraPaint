"""Icon button used to activate or deactivate layer group isolation."""
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication

from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.ui.panel.layer_ui.layer_toggle_button import LayerToggleButton
from src.util.shared_constants import PROJECT_DIR

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.panel.layer.layer_isolate_button'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


ISOLATE_TOOLTIP = _tr('Toggle layer group isolation')
ISOLATION_FORCED_TOOLTIP = _tr('Layer groups below full opacity or outside Normal mode are always isolated')
ICON_PATH_ISOLATE_ON = f'{PROJECT_DIR}/resources/icons/layer/isolate_on.svg'
ICON_PATH_ISOLATE_OFF = f'{PROJECT_DIR}/resources/icons/layer/isolate_off.svg'


class LayerIsolateButton(LayerToggleButton):
    """Layer group isolation button. It shows isolation as on, and can't be toggled, while the group's opacity or
       mode forces isolation (see `LayerGroup.isolation_forced`)."""

    def __init__(self, connected_layer: Layer) -> None:
        """Connect to the layer and load the initial icon."""
        assert isinstance(connected_layer, LayerGroup)
        super().__init__(connected_layer, ICON_PATH_ISOLATE_ON, ICON_PATH_ISOLATE_OFF)
        connected_layer.opacity_changed.connect(self._isolation_forced_change_slot)
        connected_layer.composition_mode_changed.connect(self._isolation_forced_change_slot)
        self._update_tooltip()

    def _isolation_forced_change_slot(self, *_) -> None:
        self._update_icon()
        self._update_enabled()
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        assert isinstance(self._layer, LayerGroup)
        self.setToolTip(ISOLATION_FORCED_TOOLTIP if self._layer.isolation_forced else ISOLATE_TOOLTIP)

    def _can_toggle(self, layer: Layer) -> bool:
        assert isinstance(layer, LayerGroup)
        return super()._can_toggle(layer) and not layer.isolation_forced

    def _get_boolean(self, layer: Layer) -> bool:
        assert isinstance(layer, LayerGroup)
        return layer.renders_isolated

    def _set_boolean(self, layer: Layer, value: bool) -> None:
        assert isinstance(layer, LayerGroup)
        layer.isolate = value

    def _get_signal(self, layer: Layer) -> Signal:
        assert isinstance(layer, LayerGroup)
        return layer.isolate_changed
