"""Groups the image viewer's on-canvas markers by category, so each category can be hidden without touching its items.

Registering an item makes it a child of its category's container item. Hiding a container hides its items while each
item keeps its own visibility, so owners keep calling `setVisible` on their items and a container shown again restores
whatever state they last set.

A registered item's z-value orders it only among its category's items. `CATEGORY_Z_VALUES` sets where each category
sits against the rest of the scene. Items that are never registered (layers, the brush outline, the crosshair, alerts,
toasts and tool previews) keep their scene z-values.

Hazard: a registered item's `isVisible()` is False while its category is hidden. Code that asks whether its own item
is shown, as opposed to drawn right now, reads `isVisibleTo(item.parentItem())` or keeps its own flag.
"""
from enum import Enum
from typing import Optional

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QStyleOptionGraphicsItem, QWidget


class CanvasExtraCategory(Enum):
    """Kinds of on-canvas markers, used to decide which ones a tool needs to see."""
    CANVAS = 'canvas'  # The image outline, the veil outside the image and the active layer outline.
    SELECTION = 'selection'  # The selection outline and overlay.
    GENERATION_AREA = 'generation_area'  # Generation area outlines, context pins and the generation area veil.
    TOOL = 'tool'  # Markers a tool creates for its own use, such as handles and placement outlines.


# Every value is above the composited layer stack (z 0) and the selection layer item (z 1, which draws nothing).
# CANVAS sits below 1 so that the layer transform tool's preview image (z 1) still covers the image veil.
CATEGORY_Z_VALUES: dict[CanvasExtraCategory, float] = {
    CanvasExtraCategory.CANVAS: 0.5,
    CanvasExtraCategory.SELECTION: 2.0,
    CanvasExtraCategory.GENERATION_AREA: 3.0,
    CanvasExtraCategory.TOOL: 4.0,
}


class _ExtrasContainer(QGraphicsItem):
    """An empty item whose visibility and z-value apply to every marker in one category."""

    def __init__(self) -> None:
        super().__init__()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemHasNoContents)

    def boundingRect(self) -> QRectF:  # pylint: disable=invalid-name  # Qt override
        """Returns an empty rectangle, since the container draws nothing."""
        return QRectF()

    def paint(self,
              painter: Optional[QPainter],
              option: Optional[QStyleOptionGraphicsItem],
              widget: Optional[QWidget] = None) -> None:
        """Draws nothing."""


class CanvasExtras:
    """Holds one container item per `CanvasExtraCategory` in a scene, and shows or hides each category's markers."""

    def __init__(self, scene: QGraphicsScene) -> None:
        self._containers: dict[CanvasExtraCategory, _ExtrasContainer] = {}
        for category in CanvasExtraCategory:
            container = _ExtrasContainer()
            container.setZValue(CATEGORY_Z_VALUES[category])
            scene.addItem(container)
            self._containers[category] = container

    def register(self, item: QGraphicsItem, category: CanvasExtraCategory) -> None:
        """Moves an item into a category's container, adding it to the scene if needed. The item keeps its own
        visibility, position and z-value."""
        item.setParentItem(self._containers[category])

    def container(self, category: CanvasExtraCategory) -> QGraphicsItem:
        """Returns the item holding a category's markers."""
        return self._containers[category]

    def is_shown(self, category: CanvasExtraCategory) -> bool:
        """Returns whether a category's markers may draw."""
        return self._containers[category].isVisible()

    def set_shown(self, category: CanvasExtraCategory, shown: bool) -> None:
        """Shows or hides every marker in a category. Hidden markers return to their own visibility when shown."""
        self._containers[category].setVisible(shown)
