"""
A PyQt5 widget wrapper for the LayerStack class.
"""
from typing import Optional, Dict

from PyQt5.QtCore import Qt, QRect, QRectF, QSize, QPointF, QSizeF
from PyQt5.QtGui import QPainter, QMouseEvent
from PyQt5.QtWidgets import QWidget, QSizePolicy, QGraphicsPixmapItem

from src.config.application_config import AppConfig
from src.hotkey_filter import HotkeyFilter
from src.image.image_layer import ImageLayer
from src.image.layer_stack import LayerStack
from src.ui.graphics_items.border import Border
from src.ui.graphics_items.outline import Outline
from src.ui.util.tile_pattern_fill import get_transparency_tile_pixmap
from src.ui.widget.image_graphics_view import ImageGraphicsView
from src.util.validation import assert_type

SELECTION_BORDER_OPACITY = 0.6
SELECTION_BORDER_COLOR = Qt.GlobalColor.black


class ImageViewer(ImageGraphicsView):
    """Shows the image being edited, and allows the user to select sections."""

    def __init__(self, parent: Optional[QWidget], layer_stack: LayerStack, config: AppConfig) -> None:
        super().__init__(config, parent)
        HotkeyFilter.instance().set_default_focus(self)

        self._layer_stack = layer_stack
        self._config = config
        self._selection = layer_stack.selection
        self._layer_items: Dict[int, '_LayerItem'] = {}
        self.content_size = layer_stack.size
        self.background = get_transparency_tile_pixmap()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self._follow_selection = False
        self._hidden = set()

        # Selection and border rectangle setup:
        self._scene_outline = Outline(self.scene(), self)
        self._scene_outline.dash_pattern = [1, 0]  # solid line
        self._selection_outline = Outline(self.scene(), self)
        self._selection_outline.animated = True

        # "inpaint masked only" selection outline:
        self._masked_selection_outline = Outline(self.scene(), self)
        self._masked_selection_outline.setOpacity(0.9)
        self._masked_selection_outline.animated = True
        mask_layer = layer_stack.mask_layer
        mask_layer.content_changed.connect(self._mask_content_change_slot)
        config.connect(self, AppConfig.INPAINT_FULL_RES, self._mask_content_change_slot)
        config.connect(self, AppConfig.INPAINT_FULL_RES_PADDING, self._mask_content_change_slot)

        # active layer outline:
        self._active_layer_id = -1
        self._active_layer_outline = Outline(self.scene(), self)
        self._active_layer_outline.dash_pattern = [5, 1]  # nearly solid line
        layer_stack.active_layer_changed.connect(self._active_layer_change_slot)

        # border drawn when zoomed to selection:
        self._border = Border(self.scene(), self)
        self._border.color = SELECTION_BORDER_COLOR
        self._border.setOpacity(SELECTION_BORDER_OPACITY)
        self._border.setVisible(False)

        # Connect layer stack event handlers:
        layer_stack.visible_content_changed.connect(self._update_drawn_borders)
        layer_stack.size_changed.connect(self._image_size_changed_slot)
        layer_stack.selection_bounds_changed.connect(self._image_selection_change_slot)
        layer_stack.layer_added.connect(self._layer_added_slot)
        layer_stack.layer_removed.connect(self._layer_removed_slot)

        # Manually trigger signal handlers to set up the initial state:
        self._image_size_changed_slot(self.content_size)
        self._layer_added_slot(layer_stack.mask_layer, -1)
        for i in range(layer_stack.count):
            self._layer_added_slot(layer_stack.get_layer_by_index(i), i)
        self._image_selection_change_slot(layer_stack.selection, None)
        self.resizeEvent(None)

    def zoom_to_selection(self) -> None:
        """Adjust viewport scale and offset to center the selected editing area in the view."""
        self.zoom_to_bounds(self._layer_stack.selection)

    def toggle_zoom(self) -> None:
        """Toggles between zooming in on the selection and zooming out to the full image view."""
        self.follow_selection = not self._follow_selection
        if not self.follow_selection:
            self.reset_scale()

    def stop_rendering_layer(self, layer: ImageLayer) -> None:
        """Makes the ImageViewer stop direct rendering of a particular layer until further notice."""
        self._hidden.add(layer.id)
        if layer.id in self._layer_items:
            self._layer_items[layer.id].hidden = True
        self.update()

    def resume_rendering_layer(self, layer: ImageLayer) -> None:
        """Makes the ImageViewer resume normal rendering for a layer."""
        self._hidden.discard(layer.id)
        if layer.id in self._layer_items:
            self._layer_items[layer.id].hidden = False
        self.update()

    def set_layer_opacity(self, layer: ImageLayer, opacity: float) -> None:
        """Updates the rendered opacity of a layer."""
        if layer not in self._layer_items:
            raise KeyError('Layer not yet present in the imageViewer')
        self._layer_items[layer.id].setOpacity(opacity)

    @property
    def follow_selection(self) -> bool:
        """Returns whether the view is tracking the image generation area."""
        return self._follow_selection

    @follow_selection.setter
    def follow_selection(self, should_follow) -> None:
        """Sets whether the view should follow the image generation area. Setting to true updates the view, setting to
           false does not."""
        self._follow_selection = should_follow
        self._selection_outline.animated = not should_follow
        self._border.setVisible(should_follow)
        if should_follow:
            self.zoom_to_selection()

    def sizeHint(self) -> QSize:
        """Returns image size as ideal widget size."""
        return self.content_size

    # noinspection PyMethodOverriding
    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Select the area in the image to be edited."""
        if super().mousePressEvent(event, True):
            return
        if not self._layer_stack.has_image or event is None:
            return
        if event.button() == Qt.LeftButton:
            image_coordinates = self.widget_to_scene_coordinates(event.pos())
            selection = self._layer_stack.selection
            selection.moveTopLeft(image_coordinates.toPoint())
            self._layer_stack.selection = selection

    # noinspection PyMethodOverriding
    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Adjust the offset when the widget is dragged with ctrl+LMB or MMB."""
        if super().mouseMoveEvent(event, True):
            return

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        """Draw the background as a fixed size tiling image."""
        if painter is None:
            return
        painter.drawTiledPixmap(rect, self.background)

    def scroll_content(self, dx: int | float, dy: int | float) -> bool:
        """Scroll the selection by the given offset, returning whether it was able to move."""
        selection = self._layer_stack.selection
        self._layer_stack.selection = selection.translated(int(dx), int(dy))
        self.resizeEvent(None)
        return self._layer_stack.selection != selection

    def _update_drawn_borders(self):
        """Make sure that the selection and image borders are in the right place in the scene."""
        scene_rect = QRectF(0.0, 0.0, float(self.content_size.width()), float(self.content_size.height()))
        selection = QRectF(self._selection.x(), self._selection.y(), self._selection.width(), self._selection.height())
        self._scene_outline.outlined_region = scene_rect
        image_loaded = self._layer_stack.has_image
        self._scene_outline.setVisible(image_loaded)
        self._selection_outline.outlined_region = selection
        self._border.windowed_area = selection.toAlignedRect()
        self._selection_outline.setVisible(image_loaded)
        self._masked_selection_outline.setVisible(image_loaded and self._config.get(AppConfig.INPAINT_FULL_RES))
        if self._layer_stack.active_layer is not None:
            self._active_layer_outline.setVisible(True)
            self._active_layer_outline.outlined_region = QRectF(QPointF(self._layer_stack.active_layer.position),
                                                                QSizeF(self._layer_stack.active_layer.size))
        else:
            self._active_layer_outline.setVisible(False)
        mask_layer = self._layer_stack.mask_layer
        bounds = mask_layer.get_masked_area()
        if bounds is not None:
            self._masked_selection_outline.setVisible(mask_layer.visible)
            self._masked_selection_outline.outlined_region = QRectF(bounds)
        else:
            self._masked_selection_outline.setVisible(False)

    def _update_layer_z_values(self) -> None:
        """Ensure layer item zValues are in sync with the layer stack state."""
        for layer_id, layer_item in self._layer_items.items():
            if layer_id == self._layer_stack.mask_layer.id:
                continue
            index = self._layer_stack.get_layer_index(layer_id)
            assert index is not None, f'Layer {layer_id} found in view but not in layer stack.'
            layer_item.setZValue(-index)

    # Signal handlers: sync with image/layer changes:
    def _active_layer_bounds_changed_slot(self, _, new_bounds: QRect) -> None:
        self._active_layer_outline.outlined_region = QRectF(new_bounds)

    def _active_layer_change_slot(self, active_id: int, _) -> None:
        if active_id != self._active_layer_id:
            last_active = self._layer_stack.get_layer_by_id(self._active_layer_id)
            if last_active is not None:
                last_active.bounds_changed.disconnect(self._active_layer_bounds_changed_slot)
            self._active_layer_id = active_id
            if active_id is not None:
                new_active_layer = self._layer_stack.get_layer_by_id(active_id)
                if new_active_layer is not None:
                    new_active_layer.bounds_changed.connect(self._active_layer_bounds_changed_slot)
                    self._active_layer_outline.outlined_region = QRectF(new_active_layer.geometry)
                    self._active_layer_outline.setVisible(True)
            else:
                self._active_layer_outline.setVisible(False)
        self._update_layer_z_values()

    def _mask_content_change_slot(self) -> None:
        """Sync 'inpaint masked only' bounds with mask layer changes."""
        mask_layer = self._layer_stack.mask_layer
        bounds = mask_layer.get_masked_area()
        if bounds is not None:
            self._masked_selection_outline.setVisible(mask_layer.visible)
            self._masked_selection_outline.outlined_region = QRectF(bounds)
        else:
            self._masked_selection_outline.setVisible(False)

    def _image_size_changed_slot(self, new_size: QSize) -> None:
        """Update bounds and background when the image size changes."""
        if new_size.width() <= 0 or new_size.height() <= 0:
            return
        self.content_size = new_size
        self._update_drawn_borders()
        self.resizeEvent(None)

    def _image_selection_change_slot(self, new_rect: QRect, _: Optional[QRect]) -> None:
        """Update the viewer content when the selection changes."""
        self._selection = new_rect
        self._update_drawn_borders()
        self.resetCachedContent()
        if self.follow_selection:
            self.zoom_to_selection()
        self.update()

    def _layer_added_slot(self, new_layer: ImageLayer, index: int) -> None:
        """Adds a new image layer into the view."""
        layer_item = _LayerItem(new_layer)
        layer_item.setZValue(-index)
        layer_item.setPos(new_layer.position)
        self._layer_items[new_layer.id] = layer_item
        self.scene().addItem(layer_item)
        for outline in (self._selection_outline, self._masked_selection_outline, self._active_layer_outline,
                        self._border):
            outline.setZValue(max(self._selection_outline.zValue(), index + 1))
        if new_layer.id in self._hidden:
            layer_item.hidden = True
        self._update_layer_z_values()
        if layer_item.isVisible():
            self.resetCachedContent()
            self.update()

    def _layer_removed_slot(self, removed_layer: ImageLayer) -> None:
        """Removes an image layer from the view."""
        layer_item = self._layer_items[removed_layer.id]
        layer_was_visible = layer_item.isVisible()
        self.scene().removeItem(layer_item)
        del self._layer_items[removed_layer.id]
        self._update_layer_z_values()
        if layer_was_visible:
            self.update()


class _LayerItem(QGraphicsPixmapItem):
    """Renders an image layer into a QGraphicsScene."""

    def __init__(self, layer: ImageLayer):
        super().__init__()
        assert_type(layer, ImageLayer)
        self._layer = layer
        self._hidden = False

        layer.visibility_changed.connect(self._update_visibility)
        layer.content_changed.connect(self._update_pixmap)
        layer.opacity_changed.connect(self.setOpacity)
        layer.bounds_changed.connect(self._update_position)
        self.setOpacity(layer.opacity)
        self.setVisible(layer.visible)
        self._update_pixmap(layer)

    def __del__(self):
        self._layer.visibility_changed.disconnect(self._update_visibility)
        self._layer.content_changed.disconnect(self._update_pixmap)
        self._layer.opacity_changed.disconnect(self.setOpacity)
        self._layer.bounds_changed.disconnect(self._update_position)

    @property
    def hidden(self) -> bool:
        """Returns whether this layer is currently hidden."""
        return self._hidden

    @hidden.setter
    def hidden(self, hidden: bool) -> None:
        """Sets whether the layer should be hidden in the view regardless of layer visibility."""
        self._hidden = hidden
        self.setVisible(self._layer.visible and not hidden)

    def _update_pixmap(self, _) -> None:
        self.setPixmap(self._layer.pixmap)
        self.update()

    def _update_visibility(self, _, visible: bool) -> None:
        self.setVisible(visible and not self.hidden)

    def _update_position(self, _, new_bounds: QRect) -> None:
        self.setPos(new_bounds.topLeft())