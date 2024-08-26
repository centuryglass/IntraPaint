"""Interface for graphics items that support open raster composition modes"""
import datetime
from typing import Set, Tuple, Dict, Optional

from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPolygonF, QPainterPath, QPainter

from src.image.composite_mode import CompositeMode
from src.util.image_utils import create_transparent_image, image_is_fully_transparent


class ComposableItem:
    """Interface for graphics items that support open raster composition modes"""

    def __init__(self) -> None:
        self._bounds_change_timestamp = datetime.datetime.now().timestamp()
        self._change_timestamp = datetime.datetime.now().timestamp()

        self._cache_image = QImage()
        self._cache_timestamp = 0.0

        self._background_cache_image = QImage()
        self._background_cache_timestamp = 0.0
        self._background_cache_items: Set[ComposableItem] = set()
        self._mode = CompositeMode.NORMAL

    @property
    def change_timestamp(self) -> float:
        """Returns the last timestamp when this item changed in a visible way."""
        return self._change_timestamp

    def update_change_timestamp(self) -> None:
        """Resets the change timestamp to the current time."""
        self._change_timestamp = datetime.datetime.now().timestamp()

    def update_bounds_change_timestamp(self) -> None:
        """Resets the bounds change timestamp to the current time."""
        self.update_change_timestamp()
        self._bounds_change_timestamp = datetime.datetime.now().timestamp()

    def update_cached_image(self, image: QImage) -> None:
        """Updates the cached image, resetting the cached image timestamp."""
        self._cache_image = image
        self._cache_timestamp = datetime.datetime.now().timestamp()

    def render_background(self) -> Tuple[QImage, bool]:
        """Renders everything behind this item into a QImage, returning the image and whether the image was not from
        cache."""
        assert isinstance(self, QGraphicsItem)
        scene = self.scene()
        assert scene is not None
        updated_cache = False
        local_bounds = self.boundingRect()
        scene_poly = self.sceneTransform().map(QPolygonF(local_bounds))
        scene_path = QPainterPath()
        scene_path.addPolygon(scene_poly)

        # Hide all items above this one before rendering. Check whether the set of rendered items is the same as it
        # was at the last render_background, and if any of the items have changed since then, and just use the
        # cached background if nothing has changed.
        opacity_map: Dict[QGraphicsItem, float] = {}
        changed_since_last_cache = 0
        render_bounds = self.sceneBoundingRect()
        cache_items: Set[ComposableItem] = set()
        for item in scene.items(scene_path):
            if item.zValue() >= self.zValue() or not isinstance(item, ComposableItem):
                opacity_map[item] = item.opacity()
                item.setOpacity(0.0)
            else:
                cache_items.add(item)
                assert isinstance(self, ComposableItem)
                if item.change_timestamp > self._background_cache_timestamp:
                    changed_since_last_cache += 1
                assert isinstance(item, QGraphicsItem)
                render_bounds = render_bounds.united(item.sceneBoundingRect())
        if self._background_cache_image.isNull():
            self._background_cache_image = create_transparent_image(local_bounds.size().toSize())
            updated_cache = True
        if self._bounds_change_timestamp < self._background_cache_timestamp \
                and cache_items == self._background_cache_items and changed_since_last_cache == 0:
            background = self._background_cache_image
        else:
            background = create_transparent_image(local_bounds.size().toSize())
            painter = QPainter(background)
            paint_transform = self.sceneTransform().inverted()[0]
            painter.setTransform(paint_transform)
            scene.render(painter, render_bounds, render_bounds)
            painter.end()
            self._background_cache_image = background
            updated_cache = True
        if updated_cache:
            self._background_cache_timestamp = datetime.datetime.now().timestamp()
            self._background_cache_items = cache_items

        for item, opacity in opacity_map.items():
            item.setOpacity(opacity)
        return background, updated_cache

    @property
    def composition_mode(self) -> CompositeMode:
        """Access the graphics item composition mode."""
        return self._mode

    @composition_mode.setter
    def composition_mode(self, new_mode: CompositeMode) -> None:
        """Updates the graphics item composition mode."""
        if new_mode != self._mode:
            self._mode = new_mode
            self.update_change_timestamp()
            assert isinstance(self, QGraphicsItem)
            self.update()

    def get_composite_source_image(self) -> QImage:
        """Return the item's contents as a composable QImage."""
        raise NotImplementedError()

    def get_composited_image(self) -> Tuple[QImage, Optional[QPainter.CompositionMode]]:
        """Gets the image after applying custom composition adjustments as needed, along with the appropriate QPainter
        composition mode."""
        qt_composite_mode = self.composition_mode.qt_composite_mode()
        if qt_composite_mode is not None:
            composite_image = self.get_composite_source_image()
        else:
            background_image, background_updated = self.render_background()
            if not background_updated and not self._cache_image.isNull() and \
                    self._cache_timestamp > self._change_timestamp:
                composite_image = self._cache_image
            else:
                composite_image = self.get_composite_source_image()
                composite_op = self._mode.custom_composite_op()
                assert isinstance(self, QGraphicsItem)
                if self.isVisible() and self.opacity() > 0 and not image_is_fully_transparent(composite_image):
                    composite_op(composite_image, background_image, QRect(), QRect(), None)
                self._cache_image = composite_image
                self._cache_timestamp = datetime.datetime.now().timestamp()
        return composite_image, qt_composite_mode
