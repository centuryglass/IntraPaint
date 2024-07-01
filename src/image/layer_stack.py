"""Represents a group of linked image layers that can be manipulated as one in limited ways."""
from typing import List

from PyQt5.QtCore import pyqtSignal

from src.image.image_layer import ImageLayer
from src.image.layer import Layer
from src.util.cached_data import CachedData


class LayerStack(Layer):
    """Represents a group of linked image layers that can be manipulated as one in limited ways."""
    layer_added = pyqtSignal(ImageLayer, int)
    layer_removed = pyqtSignal(ImageLayer)

    def __init__(self) -> None:
        super().__init__()
        """Initialize with no layer data."""
        self._image_cache = CachedData(None)
        self._layers: List[Layer] = []

    # PROPERTY DEFINITIONS:

    @property
    def count(self) -> int:
        """Returns the number of layers"""
        return len(self._layers)


# TODO:
# 1. Copy over all layer management functionality from image_stack, tweaking for compatibility with Layer
# 2. Rewrite ImageStack to use a LayerStack for layer management, while continuing to handle loading, gen area
#    management, selection management
# 3. Go over ImageStack, LayerStack functions, make sure none of them do anything unwanted to layers that aren't
#    imageLayer
# 4. Implement LayerStack layer groups:
#   a. creating new groups
#   b. creating layers within groups
#   c. deleting groups, warning if non-empty
#   d. moving layers into and out of groups
# 5. Review active layer use, make sure everything that uses image_stack.active_layer behaves correctly when that layer
#    is a LayerStack
