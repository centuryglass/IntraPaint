"""Groups the image viewer's on-canvas markers by category, so each category can be hidden without touching its items.

Registering an item makes it a child of its category's container item. Hiding a container hides its items while each
item keeps its own visibility, so owners keep calling `setVisible` on their items and a container shown again restores
whatever state they last set.

A registered item's z-value orders it only among its category's items. `CATEGORY_Z_VALUES` sets where each category
sits against the rest of the scene. Items that are never registered (layers, the brush outline, the crosshair, alerts,
toasts and tool previews) keep their scene z-values.

Hide mode hides every category except those the active tool needs, and those only while the cursor is over the
view. A widget that draws extras outside the scene follows `CanvasExtras.shown_changed` for its category.

Hazard: a registered item's `isVisible()` is False while its category is hidden. Code that asks whether its own item
is shown, as opposed to drawn right now, reads `isVisibleTo(item.parentItem())` or keeps its own flag.
"""
from enum import Enum
from typing import Iterable, Optional

from PySide6.QtCore import QEvent, QObject, QRectF, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QStyleOptionGraphicsItem, QWidget


class CanvasExtraCategory(Enum):
    """Kinds of on-canvas markers, used to decide which ones a tool needs to see."""
    CANVAS = 'canvas'  # The image outline, the veil outside the image and the active layer outline.
    SELECTION = 'selection'  # The selection outline and overlay.
    GENERATION_AREA = 'generation_area'  # Generation area outlines, context pins and the generation area veil.
    GUIDES = 'guides'  # Ruler guide lines.
    TOOL = 'tool'  # Markers a tool creates for its own use, such as handles and placement outlines.


# Every value is above the composited layer stack (z 0) and the selection layer item (z 1, which draws nothing).
# CANVAS sits below 1 so that the layer transform tool's preview image (z 1) still covers the image veil.
CATEGORY_Z_VALUES: dict[CanvasExtraCategory, float] = {
    CanvasExtraCategory.CANVAS: 0.5,
    CanvasExtraCategory.SELECTION: 2.0,
    CanvasExtraCategory.GENERATION_AREA: 3.0,
    CanvasExtraCategory.GUIDES: 3.5,
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


class CanvasExtras(QObject):
    """Holds one container item per `CanvasExtraCategory` in a scene, and shows or hides each category's markers.

    Every category shows while `hide_mode` is off. While it is on, a category shows only if it is in
    `tool_categories` and the cursor is over the watched view. Qt delivers a view's leave event only once every mouse
    button is released, so a drag that leaves the view keeps its category shown until it ends.

    `shown_changed` fires with a category and whether it now shows, each time that changes.
    """

    shown_changed = Signal(object, bool)  # CanvasExtraCategory, shown

    def __init__(self, scene: QGraphicsScene, view: Optional[QWidget] = None) -> None:
        super().__init__()
        self._containers: dict[CanvasExtraCategory, _ExtrasContainer] = {}
        self._hide_mode = False
        self._tool_categories: frozenset[CanvasExtraCategory] = frozenset()
        self._cursor_over_view = False
        for category in CanvasExtraCategory:
            container = _ExtrasContainer()
            container.setZValue(CATEGORY_Z_VALUES[category])
            scene.addItem(container)
            self._containers[category] = container
        if view is not None:
            view.installEventFilter(self)

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

    @property
    def hide_mode(self) -> bool:
        """Returns whether categories the active tool doesn't need are hidden."""
        return self._hide_mode

    @hide_mode.setter
    def hide_mode(self, hide_mode: bool) -> None:
        self._hide_mode = hide_mode
        self._update_containers()

    @property
    def tool_categories(self) -> frozenset[CanvasExtraCategory]:
        """Returns the categories that stay shown in hide mode while the cursor is over the view."""
        return self._tool_categories

    @tool_categories.setter
    def tool_categories(self, categories: Iterable[CanvasExtraCategory]) -> None:
        self._tool_categories = frozenset(categories)
        self._update_containers()

    @property
    def cursor_over_view(self) -> bool:
        """Returns whether the cursor is over the watched view, as of its last enter or leave event."""
        return self._cursor_over_view

    def eventFilter(self, _watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name  # Qt override
        """Tracks whether the cursor is over the view. Never consumes the event."""
        if event.type() in (QEvent.Type.Enter, QEvent.Type.Leave):
            self._cursor_over_view = event.type() == QEvent.Type.Enter
            self._update_containers()
        return False

    def _update_containers(self) -> None:
        for category, container in self._containers.items():
            shown = not self._hide_mode or (self._cursor_over_view and category in self._tool_categories)
            if shown != container.isVisible():
                container.setVisible(shown)
                self.shown_changed.emit(category, shown)
