"""
A PyQt5 widget wrapper for the LayerStack class.
"""
import math
from typing import Optional, cast

from PyQt5.QtCore import Qt, QRect, QRectF, QSize, QPoint, QPointF, QEvent, pyqtSignal, QSizeF
from PyQt5.QtGui import QPainter, QMouseEvent, QWheelEvent
from PyQt5.QtWidgets import QWidget, QSizePolicy, QGraphicsPixmapItem, QApplication

from src.image.border import Border
from src.image.image_layer import ImageLayer
from src.image.layer_stack import LayerStack
from src.image.outline import Outline
from src.ui.util.get_scaled_placement import get_scaled_placement
from src.ui.util.tile_pattern_fill import get_transparency_tile_pixmap
from src.ui.widget.fixed_aspect_graphics_view import FixedAspectGraphicsView
from src.util.validation import assert_type
from src.config.application_config import AppConfig
from src.hotkey_filter import HotkeyFilter


SELECTION_BORDER_OPACITY = 0.6
SELECTION_BORDER_COLOR = Qt.GlobalColor.black


class ImageViewer(FixedAspectGraphicsView):
    """Shows the image being edited, and allows the user to select sections."""

    # Emits the visible section of the edited image as it changed.
    visible_section_changed = pyqtSignal(QRect)

    class LayerItem(QGraphicsPixmapItem):
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

    def __init__(self, parent: Optional[QWidget], layer_stack: LayerStack, config: AppConfig) -> None:
        super().__init__(parent)
        HotkeyFilter.instance().set_default_focus(self)
        HotkeyFilter.instance().register_keybinding(lambda: self.toggle_zoom() is None, Qt.Key_Z,
                                                    Qt.KeyboardModifier.NoModifier, self)
        self._layer_stack = layer_stack
        self._config = config
        self._selection = layer_stack.selection
        self._layer_items = {}
        self.content_size = layer_stack.size
        self.background = get_transparency_tile_pixmap()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.installEventFilter(self)
        self._follow_selection = False
        self._hidden = set()
        # TODO: Hidden layers either need to be cleared periodically or tracked by other means, or else memory taken
        #      by removed layers will never be cleared.

        # View offset handling:
        self._drag_pt: Optional[QPoint] = None

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

        # active layer outline:
        self._active_layer_id = -1
        self._active_layer_outline = Outline(self.scene(), self)
        self._active_layer_outline.dash_pattern = [5, 1]  # nearly solid line

        def _update_active_layer_border(_, new_bounds: QRect) -> None:
            self._active_layer_outline.outlined_region = QRectF(new_bounds)

        def _update_active_layer_tracking(active_id: int, _) -> None:
            if active_id != self._active_layer_id:
                last_active = layer_stack.get_layer_by_id(self._active_layer_id)
                if last_active is not None:
                    last_active.bounds_changed.disconnect(_update_active_layer_border)
                self._active_layer_id = active_id
                if active_id is not None:
                    new_active_layer = layer_stack.get_layer_by_id(active_id)
                    if new_active_layer is not None:
                        new_active_layer.bounds_changed.connect(_update_active_layer_border)
                        self._active_layer_outline.outlined_region = QRectF(new_active_layer.geometry)
                        self._active_layer_outline.setVisible(True)
                else:
                    self._active_layer_outline.setVisible(False)
        layer_stack.active_layer_changed.connect(_update_active_layer_tracking)

        # border drawn when zoomed to selection:
        self._border = Border(self.scene(), self)
        self._border.color = SELECTION_BORDER_COLOR
        self._border.setOpacity(SELECTION_BORDER_OPACITY)
        self._border.setVisible(False)

        def update_selection_only_bounds():
            """Sync 'inpaint masked only' bounds with mask layer changes."""
            bounds = mask_layer.get_masked_area()
            if bounds is not None:
                self._masked_selection_outline.setVisible(mask_layer.visible)
                self._masked_selection_outline.outlined_region = QRectF(bounds)
            else:
                self._masked_selection_outline.setVisible(False)
        mask_layer.content_changed.connect(update_selection_only_bounds)

        def update_masked_selection_visibility(visible):
            """Sync visibility between outline and mask layer."""
            self._masked_selection_outline.setVisible(visible)
            if visible:
                update_selection_only_bounds()
        config.connect(self, AppConfig.INPAINT_FULL_RES, update_masked_selection_visibility)
        config.connect(self, AppConfig.INPAINT_FULL_RES_PADDING, update_selection_only_bounds)

        # Connect layer stack event handlers:
        layer_stack.visible_content_changed.connect(self._update_drawn_borders)

        def set_size(new_size: QSize) -> None:
            """Update bounds and background when the image size changes."""
            if new_size.width() <= 0 or new_size.height() <= 0:
                return
            self.content_size = new_size
            self._update_drawn_borders()
            self.resizeEvent(None)

        layer_stack.size_changed.connect(set_size)
        set_size(self.content_size)

        def update_selection(new_rect: QRect, _: Optional[QRect]) -> None:
            """Update the viewer content when the selection changes."""
            self._selection = new_rect
            self._update_drawn_borders()
            self.resetCachedContent()
            if self.follow_selection:
                self.zoom_to_selection()
            self.update()

        layer_stack.selection_bounds_changed.connect(update_selection)

        def add_layer(new_layer: ImageLayer, index: int) -> None:
            """Adds an image layer into the view."""
            layer_item = ImageViewer.LayerItem(new_layer)
            layer_item.setZValue(-index)
            layer_item.setPos(new_layer.position)
            self._layer_items[new_layer] = layer_item
            self.scene().addItem(layer_item)
            for outline in self._selection_outline, self._masked_selection_outline, self._active_layer_outline, self._border:
                outline.setZValue(max(self._selection_outline.zValue(), index + 1))
            if new_layer in self._hidden:
                layer_item.hidden = True
            if layer_item.isVisible():
                self.resetCachedContent()
                self.update()

        layer_stack.layer_added.connect(add_layer)
        add_layer(layer_stack.mask_layer, -1)
        for i in range(layer_stack.count):
            add_layer(layer_stack.get_layer_by_index(i), i)

        def remove_layer(removed_layer: ImageLayer) -> None:
            """Removes an image layer from the view."""
            layer_item = self._layer_items[removed_layer]
            layer_was_visible = layer_item.isVisible()
            self.scene().removeItem(layer_item)
            for item in self._layer_items.values():
                if item.zValue() < layer_item.zValue():
                    item.setZValue(item.zValue() + 1)
            del self._layer_items[removed_layer]
            if layer_was_visible:
                self.update()
        layer_stack.layer_removed.connect(remove_layer)

        self.resizeEvent(None)
        # Add initial layers to the view:
        for i in range(layer_stack.count):
            layer = self._layer_stack.get_layer_by_index(i)
            add_layer(layer, i)
        update_selection(layer_stack.selection, None)

    def zoom_to_selection(self) -> None:
        """Adjust viewport scale and offset to center the selected editing area in the view."""
        super().reset_scale()  # Reset zoom without clearing 'follow_selection' flag.
        selection = self._layer_stack.selection
        margin = max(int(selection.width() / 20), int(selection.height() / 20), 10)
        self.offset = QPoint(int(selection.center().x() - (self.content_size.width() // 2)),
                             int(selection.center().y() - (self.content_size.height() // 2)))
        self.scene_scale = get_scaled_placement(QRect(QPoint(0, 0), self.size()),
                                                selection.size(), 0).width() / (selection.width() + margin)

    def toggle_zoom(self) -> None:
        """Toggles between zooming in on the selection and zooming out to the full image view."""
        self.follow_selection = not self._follow_selection
        if not self.follow_selection:
            self.reset_scale()

    def stop_rendering_layer(self, layer: ImageLayer) -> None:
        """Makes the ImageViewer stop direct rendering of a particular layer until further notice."""
        self._hidden.add(layer)
        if layer in self._layer_items:
            self._layer_items[layer].hidden = True
        self.update()

    def resume_rendering_layer(self, layer: ImageLayer) -> None:
        """Makes the ImageViewer resume normal rendering for a layer."""
        self._hidden.discard(layer)
        if layer in self._layer_items:
            self._layer_items[layer].hidden = False
        self.update()

    def set_layer_opacity(self, layer: ImageLayer, opacity: float) -> None:
        """Updates the rendered opacity of a layer."""
        if layer not in self._layer_items:
            raise KeyError('Layer not yet present in the imageViewer')
        self._layer_items[layer].setOpacity(opacity)

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

    def reset_scale(self) -> None:
        """If the scale resets, stop tracking the selection."""
        self._follow_selection = False
        super().reset_scale()

    def sizeHint(self) -> QSize:
        """Returns image size as ideal widget size."""
        return self.content_size

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Select the area in the image to be edited."""
        if super().mousePressEvent(event, True):
            return
        if not self._layer_stack.has_image or event is None:
            return
        key_modifiers = QApplication.keyboardModifiers()
        if event.buttons() == Qt.MouseButton.MiddleButton or (event.buttons() == Qt.MouseButton.LeftButton
                                                              and key_modifiers == Qt.ControlModifier):
            self._drag_pt = event.pos()
        elif event.button() == Qt.LeftButton and self._layer_stack.has_image:
            image_coordinates = self.widget_to_scene_coordinates(event.pos())
            selection = self._layer_stack.selection
            selection.moveTopLeft(image_coordinates.toPoint())
            self._layer_stack.selection = selection

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Adjust the offset when the widget is dragged with ctrl+LMB or MMB."""
        if super().mouseMoveEvent(event, True):
            return
        if self._drag_pt is not None and event is not None:
            key_modifiers = QApplication.keyboardModifiers()
            if event.buttons() == Qt.MouseButton.MiddleButton or (event.buttons() == Qt.MouseButton.LeftButton
                                                                  and key_modifiers == Qt.ControlModifier):
                mouse_pt = event.pos()
                scale = self.scene_scale
                x_off = (self._drag_pt.x() - mouse_pt.x()) / scale
                y_off = (self._drag_pt.y() - mouse_pt.y()) / scale
                distance = math.sqrt(x_off**2 + y_off**2)
                if distance < 1:
                    return
                self.offset = QPointF(self.offset.x() + x_off, self.offset.y() + y_off)
                self._drag_pt = mouse_pt
            else:
                self._drag_pt = None

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        """Draw the background as a fixed size tiling image."""
        if painter is None:
            return
        painter.drawTiledPixmap(rect, self.background)

    def eventFilter(self, source, event: QEvent):
        """Intercept mouse wheel events, use for scrolling in zoom mode:"""
        if event.type() == QEvent.Wheel:
            event = cast(QWheelEvent, event)
            if event.angleDelta().y() > 0:
                self.scene_scale = self.scene_scale + 0.05
            elif event.angleDelta().y() < 0 and self.scene_scale > 0.05:
                self.scene_scale = self.scene_scale - 0.05
            self.resizeEvent(None)
            return True
        return False

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
        if self._layer_stack.active_layer_id is not None:
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
