"""
Interact with edited image layers through the Qt6 2D graphics engine.
"""
import math
from typing import Optional

from PySide6.QtCore import Qt, QRect, QRectF, QSize, QPoint, QPointF
from PySide6.QtGui import QPainter, QColor, QTransform
from PySide6.QtWidgets import QWidget, QSizePolicy

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.transform_layer import TransformLayer
from src.ui.graphics_items.border import Border
from src.ui.graphics_items.layer_graphics_item import LayerGraphicsItem
from src.ui.graphics_items.outline import Outline
from src.ui.graphics_items.selection_outline import SelectionOutline
from src.ui.widget.image_graphics_view import ImageGraphicsView
from src.util.visual.graphics_scene_utils import get_view_bounds_of_scene_item_rect
from src.util.visual.image_utils import get_transparency_tile_pixmap, tile_pattern_fill, TRANSPARENCY_PATTERN_TILE_DIM

GENERATION_AREA_BORDER_OPACITY = 0.6
IMAGE_BORDER_OPACITY = 0.2
GENERATION_AREA_BORDER_COLOR = Qt.GlobalColor.black
MIN_OUTLINE_PIXEL_SIZE = 8.0


class ImageViewer(ImageGraphicsView):
    """Shows the image being edited, and allows the user to select sections."""

    def __init__(self, parent: Optional[QWidget], image_stack: ImageStack, use_keybindings=True) -> None:
        super().__init__(parent, use_keybindings)
        hotkey_filter = HotkeyFilter.instance()
        if hotkey_filter.default_focus() is None:
            hotkey_filter.set_default_focus(self)
        config = AppConfig()

        self._image_stack = image_stack
        self._generation_area = image_stack.generation_area
        self._layer_items: dict[int, 'LayerGraphicsItem'] = {}
        self.content_size = image_stack.size
        self.background = get_transparency_tile_pixmap()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        self._follow_generation_area = False
        self._hidden: set[int] = set()
        self._selection_poly_outline = SelectionOutline(self)

        # Generation area and border rectangle setup:
        scene = self.scene()
        assert scene is not None
        self._image_outline = Outline(scene, self)
        self._image_border = Border(scene, self)
        self._image_border.windowed_area = image_stack.bounds
        self._image_border.color = QColor(GENERATION_AREA_BORDER_COLOR)
        self._image_border.setOpacity(IMAGE_BORDER_OPACITY)
        self._image_border.setVisible(True)
        self._image_outline.dash_pattern = [1, 0]  # solid line
        self._generation_area_outline = Outline(scene, self)

        # "inpaint selected only" generation area outline:
        self._generation_area_selection_outline = Outline(scene, self)
        self._generation_area_selection_outline.setOpacity(GENERATION_AREA_BORDER_OPACITY)
        selection_layer = image_stack.selection_layer
        selection_layer.content_changed.connect(self._selection_content_change_slot)
        Cache().connect(self, Cache.INPAINT_FULL_RES, self._selection_content_change_slot)
        Cache().connect(self, Cache.INPAINT_FULL_RES_PADDING, self._selection_content_change_slot)

        # pixel outline
        self._pixel_outline = Outline(scene, self, cosmetic_line_draw=True)
        self._pixel_outline.setVisible(False)
        self.scale_changed.connect(self._scale_change_slot)

        # animate gen area/selected content borders based on config:
        def _update_outline_animation(is_animating: bool) -> None:
            self._generation_area_selection_outline.animated = is_animating
            self._generation_area_outline.animated = is_animating
            self._pixel_outline.animated = is_animating
        config.connect(self, AppConfig.ANIMATE_OUTLINES_AND_PREVIEWS, _update_outline_animation)
        _update_outline_animation(config.get(AppConfig.ANIMATE_OUTLINES_AND_PREVIEWS))

        # active layer outline:
        self._active_layer_id = -1
        self._active_layer_outline = Outline(scene, self)
        self._active_layer_outline.dash_pattern = [5, 1]  # nearly solid line
        image_stack.active_layer_changed.connect(self._active_layer_change_slot)

        # border drawn when zoomed to image generation area:
        self._generation_area_border = Border(scene, self)
        self._generation_area_border.color = QColor(GENERATION_AREA_BORDER_COLOR)
        self._generation_area_border.setOpacity(GENERATION_AREA_BORDER_OPACITY)
        self._generation_area_border.setVisible(False)

        # Connect image stack event handlers:
        image_stack.content_changed.connect(self._update_drawn_borders)
        image_stack.size_changed.connect(self._image_size_changed_slot)
        image_stack.generation_area_bounds_changed.connect(self._image_generation_area_change_slot)

        # Manually trigger signal handlers to set up the initial state:
        self._image_size_changed_slot(self.content_size)
        self._add_layer_item(image_stack.selection_layer)
        self._add_layer_item(image_stack.layer_stack)
        self._image_generation_area_change_slot(image_stack.generation_area)
        self.resizeEvent(None)

    def set_generation_area_visible(self, visible: bool) -> None:
        """Set whether the image generation area will be visible as an outline within the view."""
        self._generation_area_outline.setVisible(visible)
        selection_layer = self._image_stack.selection_layer
        self._generation_area_selection_outline.setVisible(visible and selection_layer.visible
                                                           and selection_layer.get_selection_gen_area() is not None)
        if visible and self._follow_generation_area:
            self.follow_generation_area = True

    def zoom_to_generation_area(self) -> None:
        """Adjust viewport scale and offset to center the selected editing area in the view. Does nothing if the
           image generation area is hidden."""
        if self._generation_area_outline.isVisible():
            self.zoom_to_bounds(self._image_stack.generation_area)

    def toggle_zoom(self) -> None:
        """Toggles between zooming in on the image generation area and zooming out to the full image view."""
        self.follow_generation_area = not self._follow_generation_area
        if not self.follow_generation_area:
            self.reset_scale()

    @property
    def follow_generation_area(self) -> bool:
        """Returns whether the view is tracking the image generation area."""
        return self._follow_generation_area and self._generation_area_outline.isVisible()

    @follow_generation_area.setter
    def follow_generation_area(self, should_follow) -> None:
        """Sets whether the view should follow the image generation area. The view updates in response only when it is
           set to true and the generation area is not hidden."""
        self._follow_generation_area = should_follow
        if self._generation_area_outline.isVisible():
            self._generation_area_outline.animated = not should_follow and AppConfig().get(
                AppConfig.ANIMATE_OUTLINES_AND_PREVIEWS)
            self._generation_area_border.setVisible(should_follow)
            if should_follow:
                self.zoom_to_generation_area()

    def sizeHint(self) -> QSize:
        """Returns a null size to ensure the image viewer can be reduced as far as necessary."""
        return QSize()

    def drawBackground(self, painter: Optional[QPainter], rect: QRectF) -> None:
        """Draw the background as a fixed size tiling image."""
        assert painter is not None
        painter.save()
        painter.setTransform(QTransform())
        content_bounds = get_view_bounds_of_scene_item_rect(self._image_outline.boundingRect(),
                                                            self._image_outline).toAlignedRect()
        tile_size = TRANSPARENCY_PATTERN_TILE_DIM
        tile_pattern_fill(painter, content_bounds, tile_size, Qt.GlobalColor.lightGray, Qt.GlobalColor.darkGray)
        painter.restore()

    def scroll_content(self, dx: int | float, dy: int | float) -> bool:
        """Scroll the image generation area by the given offset, returning whether it was able to move."""
        generation_area = self._image_stack.generation_area
        self._image_stack.generation_area = generation_area.translated(int(dx), int(dy))
        self.resizeEvent(None)
        return self._image_stack.generation_area != generation_area

    def _update_pixel_outline(self, cursor_pos: QPoint) -> None:
        scene_pos = self.widget_point_to_scene(cursor_pos)
        outline_rect = (QRectF(float(math.floor(scene_pos.x())), float(math.floor(scene_pos.y())), 1.0, 1.0)
                        .adjusted(0.1, 0.1, -0.1, -0.1))
        self._pixel_outline.outlined_region = outline_rect
        self._pixel_outline.setVisible(self.scene_scale >= MIN_OUTLINE_PIXEL_SIZE)

    def _scale_change_slot(self, scale: float) -> None:
        self._pixel_outline.setVisible(scale >= MIN_OUTLINE_PIXEL_SIZE)

    def set_cursor_pos(self, widget_cursor_pos: Optional[QPoint | QPointF]) -> None:
        """Updates the last cursor position within the widget so that pixmap cursor rendering stays active."""
        if widget_cursor_pos is None:
            self._pixel_outline.setVisible(False)
        else:
            self._update_pixel_outline(widget_cursor_pos if isinstance(widget_cursor_pos, QPoint)
                                       else widget_cursor_pos.toPoint())
        super().set_cursor_pos(widget_cursor_pos)

    def _update_drawn_borders(self):
        """Make sure that the image generation area and layer borders are in the right place in the scene."""
        generation_area = QRectF(self._generation_area.x(), self._generation_area.y(), self._generation_area.width(),
                                 self._generation_area.height())
        image_loaded = self._image_stack.has_image
        self._image_outline.setVisible(image_loaded)
        self._generation_area_outline.outlined_region = generation_area
        self._generation_area_border.windowed_area = generation_area.toAlignedRect()
        self._generation_area_selection_outline.setVisible(
            image_loaded and Cache().get(Cache.INPAINT_OPTIONS_AVAILABLE) and Cache().get(Cache.INPAINT_FULL_RES)
            and self._generation_area_outline.isVisible())
        self._active_layer_outline.setVisible(True)
        self._active_layer_outline.outlined_region = QRectF(self._image_stack.active_layer.bounds)
        selection_layer = self._image_stack.selection_layer
        bounds = selection_layer.get_selection_gen_area()
        if bounds is not None:
            self._generation_area_selection_outline.setVisible(self._generation_area_outline.isVisible()
                                                               and selection_layer.visible)
            self._generation_area_selection_outline.outlined_region = QRectF(bounds)
        else:
            self._generation_area_selection_outline.setVisible(False)

    # Signal handlers: sync with image/layer changes:
    # noinspection PyUnusedLocal
    def _active_layer_bounds_changed_slot(self, *args) -> None:
        active_layer = self._image_stack.active_layer
        self._active_layer_outline.outlined_region = QRectF(active_layer.bounds)

    # noinspection PyUnusedLocal
    def _active_layer_change_slot(self, new_active_layer: Layer, *args) -> None:
        active_id = None if new_active_layer is None else new_active_layer.id
        if active_id != self._active_layer_id:
            last_active = self._image_stack.get_layer_by_id(self._active_layer_id)
            if last_active is not None:
                if isinstance(last_active, TransformLayer):
                    last_active.transform_changed.disconnect(self._layer_transform_change_slot)
                last_active.size_changed.disconnect(self._active_layer_bounds_changed_slot)
            self._active_layer_id = active_id
            if new_active_layer is not None:
                new_active_layer.size_changed.connect(self._active_layer_bounds_changed_slot)
                if isinstance(new_active_layer, TransformLayer):
                    new_active_layer.transform_changed.connect(self._layer_transform_change_slot)
                    self._active_layer_outline.setTransform(new_active_layer.transform)
                else:
                    self._active_layer_outline.setTransform(QTransform())
                self._active_layer_outline.outlined_region = QRectF(new_active_layer.bounds)
                self._active_layer_outline.setVisible(True)
            else:
                self._active_layer_outline.setVisible(False)

    # noinspection PyUnusedLocal
    def _selection_content_change_slot(self, *args) -> None:
        """Sync 'inpaint masked only' bounds with selection layer changes."""
        selection_layer = self._image_stack.selection_layer
        bounds = selection_layer.get_selection_gen_area()
        if bounds is not None:
            self._generation_area_selection_outline.setVisible(self._generation_area_outline.isVisible()
                                                               and selection_layer.visible)
            self._generation_area_selection_outline.outlined_region = QRectF(bounds)
        else:
            self._generation_area_selection_outline.setVisible(False)
        self._selection_poly_outline.setZValue(2)
        self._selection_poly_outline.load_polygons(selection_layer.outline)

    def _image_size_changed_slot(self, new_size: QSize) -> None:
        """Update bounds and background when the image size changes."""
        if new_size.width() <= 0 or new_size.height() <= 0:
            return
        self.content_size = new_size

        self._update_drawn_borders()
        self._image_border.windowed_area = self._image_stack.bounds
        self._image_outline.outlined_region = self._image_border.windowed_area
        self.resizeEvent(None)

    def _image_generation_area_change_slot(self, new_rect: QRect) -> None:
        """Update the viewer content when the image generation area changes."""
        self._generation_area = new_rect
        self._update_drawn_borders()
        self.resetCachedContent()
        if self.follow_generation_area:
            self.zoom_to_generation_area()
        self.update()

    # noinspection PyUnusedLocal
    def _layer_transform_change_slot(self, layer: Layer, transform: QTransform) -> None:
        """Apply layer transformations to outlines."""
        assert isinstance(layer, TransformLayer)
        if layer == self._image_stack.active_layer:
            self._active_layer_outline.setTransform(layer.transform)

    def _add_layer_item(self, new_layer: Layer) -> None:
        """Adds a new image layer into the view."""
        if self._image_border.windowed_area.isEmpty() and self._image_stack.has_image:
            self._image_border.windowed_area = self._image_stack.bounds if self._image_stack.has_image else QRect()
            self._image_outline.outlined_region = self._image_border.windowed_area
        assert new_layer.id not in self._layer_items
        layer_item = LayerGraphicsItem(new_layer)
        scene = self.scene()
        assert scene is not None
        self._layer_items[new_layer.id] = layer_item
        scene.addItem(layer_item)
        assert new_layer.id in self._layer_items
        if layer_item.isVisible():
            self.resetCachedContent()
            self.update()
        for outline in (self._generation_area_outline, self._generation_area_selection_outline,
                        self._active_layer_outline, self._generation_area_border):
            assert isinstance(outline, (Outline, Border))
            outline.setZValue(max(self._generation_area_outline.zValue(), new_layer.z_value + 1))

    def _layer_removed_slot(self, removed_layer: Layer) -> None:
        """Removes an image layer from the view."""
        if not self._image_stack.has_image:
            self._image_border.windowed_area = QRect()
        if removed_layer.id not in self._layer_items:
            return
        layer_item = self._layer_items[removed_layer.id]
        layer_was_visible = layer_item.isVisible()
        scene = self.scene()
        assert scene is not None
        scene.removeItem(layer_item)
        del self._layer_items[removed_layer.id]
        if layer_was_visible:
            self.update()
