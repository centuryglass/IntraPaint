"""Icon button used to show or hide an image layer."""
from typing import Optional

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon, QMouseEvent
from PyQt6.QtWidgets import QToolButton, QSizePolicy

from src.image.layers.layer import Layer
from src.util.shared_constants import PROJECT_DIR

ICON_SIZE = QSize(32, 32)
ICON_PATH_VISIBLE_LAYER = f'{PROJECT_DIR}/resources/icons/layer/visible.svg'
ICON_PATH_HIDDEN_LAYER = f'{PROJECT_DIR}/resources/icons/layer/hidden.svg'


class LayerVisibilityButton(QToolButton):
    """Show/hide layer button."""

    def __init__(self, connected_layer: Layer) -> None:
        """Connect to the layer and load the initial icon."""
        super().__init__()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed))
        self._layer = connected_layer
        connected_layer.visibility_changed.connect(self._update_icon)
        self._visible_icon = QIcon(ICON_PATH_VISIBLE_LAYER)
        self._hidden_icon = QIcon(ICON_PATH_HIDDEN_LAYER)
        self._update_icon()

    # noinspection PyMethodMayBeStatic
    def sizeHint(self):
        """Use a fixed size for icons."""
        return ICON_SIZE

    def _update_icon(self):
        """Loads the open eye icon if the layer is visible, the closed eye icon otherwise."""
        self.setIcon(self._visible_icon if self._layer.visible else self._hidden_icon)

    def mousePressEvent(self, unused_event: Optional[QMouseEvent]) -> None:
        """Toggle visibility on click."""
        self._layer.visible = not self._layer.visible
