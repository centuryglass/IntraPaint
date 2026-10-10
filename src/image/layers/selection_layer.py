"""A layer used to mark masked regions for inpainting."""
import logging
from typing import Any, Optional

import cv2
import numpy as np
from PIL import Image
from PySide6.QtCore import QRect, QPoint, QSize, Signal, QPointF, SignalInstance
from PySide6.QtGui import QImage, QPolygonF, QPainter, QColor
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.image.layers.image_layer import ImageLayer, ImageLayerState
from src.undo_stack import UndoStack
from src.util.visual.image_utils import NpAnyArray
from src.util.visual.pil_image_utils import qimage_to_pil_image

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'image.layers.selection_layer'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


logger = logging.getLogger(__name__)

SELECTION_LAYER_NAME = _tr('Selection')
DEFAULT_BRUSH_COLOR_STR = '#55ff0000'

# Pixels around a bounded change whose outline polygons are re-traced, in addition to the change itself.
OUTLINE_RETRACE_MARGIN = 10


def _mask_array(mask: QImage) -> NpAnyArray:
    """Returns a writable (height, width) view of an Alpha8 image, without the padding at the end of each row.

    The view doesn't keep the image alive, so the caller must hold a reference to it while using the view.
    """
    assert mask.format() == QImage.Format.Format_Alpha8
    image_ptr = mask.bits()
    assert image_ptr is not None, 'Selection mask was invalid'
    return np.ndarray(shape=(mask.height(), mask.bytesPerLine()), dtype=np.uint8, buffer=image_ptr)[:, :mask.width()]


def _binary_mask(image: QImage) -> QImage:
    """Returns a new Alpha8 image that is 255 wherever the image has any alpha, and 0 elsewhere."""
    if image.format() == QImage.Format.Format_Alpha8:
        mask = image.copy()
        array = _mask_array(mask)
        array[array > 0] = 255
        return mask
    if image.format() not in (QImage.Format.Format_ARGB32_Premultiplied, QImage.Format.Format_ARGB32):
        image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    image_ptr = image.constBits()
    assert image_ptr is not None, 'Selection image was invalid'
    alpha = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)[:, :, 3]
    mask = QImage(image.size(), QImage.Format.Format_Alpha8)
    _mask_array(mask)[...] = np.where(alpha > 0, 255, 0)
    return mask


def _array_bounds(array: NpAnyArray) -> QRect:
    """Returns the smallest rectangle containing every nonzero element of a 2D array, or a null QRect if none."""
    rows = np.flatnonzero(array.any(axis=1))
    if rows.size == 0:
        return QRect()
    cols = np.flatnonzero(array.any(axis=0))
    return QRect(int(cols[0]), int(rows[0]), int(cols[-1] - cols[0] + 1), int(rows[-1] - rows[0] + 1))


def _area(array: NpAnyArray, rect: QRect) -> NpAnyArray:
    return array[rect.y():rect.y() + rect.height(), rect.x():rect.x() + rect.width()]


class SelectionLayer(ImageLayer):
    """A layer used to select regions for editing or inpainting.

    The selection layer has the following properties:

    - Only one selection layer ever exists, and its size always matches the image size.
    - Layer data is 1-bit, stored as an Alpha8 mask holding 0 or 255. `get_qimage`, `image` and `mask_image` build
      ARGB32_Premultiplied images from it on each read, with pixels either #00000000 or the opaque selection color.
      `set_image` and `borrow_image` accept any alpha content and keep every pixel with nonzero alpha.
    - The layer cannot be copied.
    - Selection bounds are available as polygons through the `outline` property
    - When the "inpaint selected area only" option is checked, the mask layer pixmap will track the masked area bounds.
    - Functions are provided to adjust the selection area.

    The following properties can't be defined within this class itself, but should be enforced by the image stack:
    - The selection layer is always above all other layers.
    - The selection layer cannot be deleted or moved.
    - The selection layer can't be set as the active layer.
    - Contents are not saved.

    The layer also holds context pins: image-space points that stretch the inpainting crop from
    `get_selection_gen_area` without being inpainted themselves. Pins are part of the saved layer state, so undoing a
    layer state change restores them, but they are never written to image files.
    """

    selection_cleared = Signal()
    context_pins_changed = Signal(list)

    def __init__(self, size: QSize, generation_window_signal: SignalInstance) -> None:
        """
        Initializes a new selection layer.
        """
        self._outline_polygons: list[QPolygonF] = []
        self._generation_area = QRect()
        self._context_pins: list[QPoint] = []
        self._bounding_box: Optional[QRect] = None
        self._selection_color = QColor()
        self._selected_count = 0  # Number of selected pixels in the mask
        self._borrowed: Optional[QImage] = None  # Scratch image handed out by borrow_image
        super().__init__(size, SELECTION_LAYER_NAME)

        def _update_color(color_str: str) -> None:
            if color_str == self._selection_color.name():
                return
            self._selection_color = QColor(color_str)
            if self._selection_color.alpha() == 0:
                logger.error(f'Invalid full-transparent selection color {self._selection_color.name()}'
                             f', restoring default {DEFAULT_BRUSH_COLOR_STR}')
                self._selection_color = QColor(DEFAULT_BRUSH_COLOR_STR)
                AppConfig().set(AppConfig.SELECTION_COLOR, DEFAULT_BRUSH_COLOR_STR)
            self.opacity = self._selection_color.alphaF()
            self.signal_content_changed(self.bounds)  # Images built from the mask use the new color
        _update_color(AppConfig().get(AppConfig.SELECTION_COLOR))
        AppConfig().connect(self, AppConfig.SELECTION_COLOR, _update_color)

        self.transform_changed.connect(lambda layer, matrix: self._update_bounds())
        generation_window_signal.connect(self.update_generation_area)

    def update_generation_area(self, new_area: QRect) -> None:
        """Update the area marked for image generation."""
        self._generation_area = QRect(new_area)
        self._update_bounds()
        self.signal_content_changed(self.bounds)

    # Disabling unwanted layer functionality:
    def copy(self) -> 'SelectionLayer':
        """Disallow selection layer copies."""
        raise RuntimeError('The selection layer cannot be copied.')

    @property
    def outline(self) -> list[QPolygonF]:
        """Access the selection outline polygons directly."""
        return [*self._outline_polygons]

    def _update_bounds(self) -> None:
        """Update saved selection bounds within the generation window."""
        if self._image.isNull() or self._image.size().isEmpty():
            return
        pos = self.position
        search_area = QRect(self._generation_area).translated(-pos.x(), -pos.y()).intersected(
            QRect(QPoint(), self._image.size()))
        if self._selected_count == 0 or search_area.isEmpty():
            self._bounding_box = None
            return
        bounds = _array_bounds(_area(_mask_array(self._image), search_area))
        if bounds.isNull():
            self._bounding_box = None
        else:
            self._bounding_box = bounds.translated(search_area.topLeft() + pos)

    @property
    def context_pins(self) -> list[QPoint]:
        """Returns a copy of the context pin list, in image coordinates."""
        return [QPoint(pin) for pin in self._context_pins]

    def set_context_pins(self, pins: list[QPoint], save_to_undo_history: bool = True) -> None:
        """Replaces all context pins, dropping duplicates."""
        new_pins: list[QPoint] = []
        for pin in pins:
            if pin not in new_pins:
                new_pins.append(QPoint(pin))
        if new_pins == self._context_pins:
            return
        if not save_to_undo_history:
            self._apply_context_pins(new_pins)
            return
        last_pins = self.context_pins
        UndoStack().commit_action(lambda: self._apply_context_pins(new_pins),
                                  lambda: self._apply_context_pins(last_pins),
                                  'SelectionLayer.set_context_pins')

    def record_context_pin_change(self, previous_pins: list[QPoint]) -> None:
        """Adds one undo step from previous_pins to the current pins, which are already applied.

        Used after a series of `set_context_pins(..., False)` calls, such as a pin drag, so the whole series undoes
        at once. Does nothing if the pins match previous_pins.
        """
        current_pins = self.context_pins
        if current_pins == previous_pins:
            return
        last_pins = [QPoint(pin) for pin in previous_pins]
        UndoStack().commit_action(lambda: self._apply_context_pins(current_pins),
                                  lambda: self._apply_context_pins(last_pins),
                                  'SelectionLayer.set_context_pins', skip_initial_call=True)

    def add_context_pin(self, pin: QPoint) -> None:
        """Adds a context pin at an image coordinate, as an undoable action."""
        self.set_context_pins([*self._context_pins, pin])

    def remove_context_pin(self, pin: QPoint) -> None:
        """Removes the context pin at an image coordinate, as an undoable action."""
        self.set_context_pins([existing for existing in self._context_pins if existing != pin])

    def clear_context_pins(self, save_to_undo_history: bool = True) -> None:
        """Removes all context pins."""
        self.set_context_pins([], save_to_undo_history)

    def _apply_context_pins(self, pins: list[QPoint]) -> None:
        self._context_pins = [QPoint(pin) for pin in pins]
        self.context_pins_changed.emit(self.context_pins)

    def save_state(self) -> 'SelectionLayerState':
        """Export the current layer state, including context pins."""
        image_state = super().save_state()
        assert isinstance(image_state, ImageLayerState)
        return SelectionLayerState(image_state, self.context_pins)

    def restore_state(self, saved_state: Any) -> None:
        """Restore the layer state and context pins from a previous saved state."""
        assert isinstance(saved_state, SelectionLayerState)
        super().restore_state(saved_state.image_state)
        self.set_context_pins(saved_state.context_pins, False)

    def generation_area_is_empty(self) -> bool:
        """Returns whether the current selection mask is empty."""
        self._update_bounds()
        return self._bounding_box is None or self._bounding_box.isEmpty()

    def generation_area_fully_selected(self) -> bool:
        """Returns whether the generation area is 100% selected."""
        bounds = QRect(self._generation_area)
        pos = self.position
        bounds.translate(-pos.x(), -pos.y())
        return bool(np.all(_area(_mask_array(self._image), bounds) > 0))

    def select_all(self) -> None:
        """Selects the entire image."""
        full_selection = QImage(self.size, QImage.Format.Format_Alpha8)
        full_selection.fill(255)
        self.image = full_selection

    def invert_selection(self) -> None:
        """Select all unselected areas, and unselect all selected areas."""
        inverted = self._image.copy()
        mask = _mask_array(inverted)
        np.bitwise_not(mask, out=mask)
        self.image = inverted

    def grow_or_shrink_selection(self, num_pixels: int) -> None:
        """Expand the selection outwards a given amount, or shrink it if num_pixels is negative.

        Every edge moves by abs(num_pixels) pixels, and corners stay square.
        """
        if num_pixels == 0:
            self.image = self._image.copy()
            return
        mask_uint8 = np.ascontiguousarray(_mask_array(self._image))
        kernel_size = 2 * abs(num_pixels) + 1
        kernel: NpAnyArray = np.ones((kernel_size, kernel_size), np.uint8)
        if num_pixels > 0:
            adjusted = cv2.dilate(mask_uint8, kernel, iterations=1)
        else:
            adjusted = cv2.erode(mask_uint8, kernel, iterations=1)
        height, width = adjusted.shape
        self.image = QImage(adjusted.data, width, height, width, QImage.Format.Format_Alpha8).copy()

    def clear(self, save_to_undo_history: bool = True) -> None:
        """Deselects everything."""
        cleared = QImage(self.size, QImage.Format.Format_Alpha8)
        cleared.fill(0)
        if save_to_undo_history:
            self.image = cleared
        else:
            self.set_image(cleared)

    @property
    def mask_image(self) -> QImage:
        """Gets the generation area mask content as a QImage"""
        return self.cropped_image_content(self.map_rect_from_image(self._generation_area))

    @property
    def pil_mask_image(self) -> Image.Image:
        """Gets the generation area mask content as a PIL image mask"""
        return qimage_to_pil_image(self.mask_image)

    # Mask storage. `_image` is the Alpha8 mask, and every other image the layer exposes is built from it.

    def get_qimage(self) -> QImage:
        """Builds the whole selection as an ARGB32_Premultiplied image. Prefer `cropped_image_content` for a region."""
        return self._argb_from_mask(QRect(QPoint(), self._image.size()))

    def cropped_image_content(self, bounds_rect: QRect) -> QImage:
        """Builds the selection within a rectangle as an ARGB32_Premultiplied image."""
        return self._argb_from_mask(bounds_rect)

    def is_empty(self, bounds: Optional[QRect] = None) -> bool:
        """Returns whether nothing is selected, optionally within a rectangle in layer coordinates."""
        if self._selected_count == 0:
            return True
        if bounds is None:
            return False
        area = bounds.intersected(QRect(QPoint(), self._image.size()))
        return area.isEmpty() or not _area(_mask_array(self._image), area).any()

    def _argb_from_mask(self, rect: QRect) -> QImage:
        rect = rect.intersected(QRect(QPoint(), self._image.size()))
        if rect.isEmpty():
            return QImage()
        image = QImage(rect.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor(self._selection_color.red(), self._selection_color.green(), self._selection_color.blue()))
        painter = QPainter(image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, self._image.copy(rect))
        painter.end()
        return image

    def set_qimage(self, image: QImage) -> None:
        """Replaces the selection, keeping every pixel of the image that has nonzero alpha."""
        assert not self.locked and not self.parent_locked, 'Tried to change image in a locked layer'
        previous = self._image
        mask = _binary_mask(image)
        change_bounds: Optional[QRect] = None
        if previous.size() == mask.size() and not previous.isNull():
            change_bounds = _array_bounds(_mask_array(previous) != _mask_array(mask))
        self._image = mask
        self._selected_count = int(np.count_nonzero(_mask_array(mask)))
        self._refresh_after_change(change_bounds)
        if self.size != image.size():
            self.set_size(image.size())

    def _undo_snapshot(self) -> QImage:
        return self._image.copy()

    def _content_copy(self, bounds: QRect) -> QImage:
        return self._argb_from_mask(bounds)

    def _borrow_target(self, change_bounds: QRect) -> QImage:
        """Hands out a full-size scratch image with only change_bounds filled in. Pixels elsewhere are not read."""
        scratch = QImage(self._image.size(), QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(scratch)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(change_bounds.topLeft(), self._argb_from_mask(change_bounds))
        painter.end()
        self._borrowed = scratch
        return scratch

    def _commit_borrowed(self, change_bounds: QRect) -> None:
        scratch = self._borrowed
        self._borrowed = None
        assert scratch is not None
        self._ingest(scratch.copy(change_bounds), change_bounds)

    def _apply_borrowed_content(self, content: QImage, bounds: QRect) -> None:
        self._ingest(content, bounds)
        self._refresh_after_change(bounds)
        self.invalidate_pixmap()
        self.signal_content_changed(bounds)

    def _ingest(self, content: QImage, bounds: QRect) -> None:
        """Replaces the mask within bounds with the thresholded content."""
        region = _area(_mask_array(self._image), bounds)
        new_mask = _binary_mask(content)  # The array doesn't keep its image alive
        new_content = _mask_array(new_mask)
        self._selected_count += int(np.count_nonzero(new_content)) - int(np.count_nonzero(region))
        region[...] = new_content

    def _handle_content_change(self, image: QImage, last_bounds_content: QImage,
                               change_bounds: Optional[QRect] = None) -> None:
        """Updates bounds and outline after `borrow_image` changed the mask within change_bounds."""
        self._refresh_after_change(change_bounds)

    def _refresh_after_change(self, change_bounds: Optional[QRect]) -> None:
        """Updates the selection bounds and outline after the mask changed.

        Parameters:
            change_bounds: Optional[QRect]
                The area (in local coordinates) where the mask changed. If None, the whole mask is treated as changed.
        """
        if self._image.isNull() or self._image.size().isEmpty():
            return
        self._update_bounds()
        if self._selected_count == 0:
            self._outline_polygons = []
            return
        if change_bounds is not None:
            change_bounds = change_bounds.intersected(QRect(QPoint(), self._image.size()))
            if change_bounds.isEmpty():
                return
        mask = _mask_array(self._image)

        # Find edge polygons, using image coordinates:
        pos = self.position
        x_offset = pos.x()
        y_offset = pos.y()
        if change_bounds is not None:
            # Re-trace the change bounds plus a margin, grown until it holds every polygon that touches it. A polygon
            # that touches the traced area but is only partly inside it would come back clipped or duplicated.
            final_image_bounds = QRect(change_bounds).translated(pos.x(), pos.y()).adjusted(
                -OUTLINE_RETRACE_MARGIN, -OUTLINE_RETRACE_MARGIN, OUTLINE_RETRACE_MARGIN, OUTLINE_RETRACE_MARGIN)
            polys_to_remove = []
            bounds_expanded = True
            while bounds_expanded:
                bounds_expanded = False
                for poly in self._outline_polygons:
                    if poly in polys_to_remove:
                        continue
                    poly_bounds = poly.boundingRect().toAlignedRect()
                    if poly_bounds.intersects(final_image_bounds):
                        final_image_bounds = final_image_bounds.united(poly_bounds.adjusted(-1, -1, 1, 1))
                        polys_to_remove.append(poly)
                        bounds_expanded = True
            for poly in polys_to_remove:
                self._outline_polygons.remove(poly)
            final_local_bounds = final_image_bounds.translated(-pos.x(), -pos.y())\
                .intersected(QRect(0, 0, self.width, self.height))
            mask = _area(mask, final_local_bounds)
            x_offset += final_local_bounds.x()
            y_offset += final_local_bounds.y()
        else:
            self._outline_polygons = []
        # Edge detection needs to scale the mask by 3 for cv2 to avoid approximating away the pixel edges:
        cv2_image = np.kron(mask, np.ones((3, 3), dtype=np.uint8))
        contours, _ = cv2.findContours(cv2_image, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
        for contour in contours:
            polygon = QPolygonF()
            for point in contour:
                polygon.append(QPointF(round(point[0][0] / 3) + x_offset, round(point[0][1] / 3) + y_offset))
            self._outline_polygons.append(polygon)

    def get_selection_bounds(self) -> Optional[QRect]:
        """Returns the bounds of all selected pixels in image coordinates, inside or outside the generation area.

        Returns None if nothing is selected.
        """
        bounds = self.get_content_bounds()
        return None if bounds.isEmpty() else bounds

    def get_content_bounds(self) -> QRect:
        """Returns the smallest rectangle containing every selected pixel, in image coordinates.

        The result covers the whole layer, not just the generation area. It is an empty QRect when nothing is selected.
        """
        if self._selected_count == 0 or self._image.isNull():
            return QRect()
        bounds = _array_bounds(_mask_array(self._image))
        if bounds.isEmpty():
            return QRect()
        return bounds.translated(self.position)

    def get_selection_gen_area(self, ignore_config: bool = False, include_context_pins: bool = True) -> Optional[QRect]:
        """Returns the smallest QRect within the generation area containing all masked areas and pins, plus padding.

        Used for showing the actual area visible to the image model when the Config.INPAINT_FULL_RES config option is
        set to true. The padding amount is set by the Config.INPAINT_FULL_RES_PADDING config option, measured in
        pixels. Context pins only count while some of the generation area is selected, and pins outside the generation
        area stretch the bounds to its edge. The returned rectangle uses image coordinates.

        Parameters
        ----------
        ignore_config : bool
            If true, return the masked area bounds even when Config.INPAINT_FULL_RES is disabled in config.
        include_context_pins : bool
            If false, return the bounds the selection would have without any context pins.
        Returns
        -------
        QRect or None
           Rectangle containing all non-transparent selected content plus padding, or None if the selection is empty
           or config.get(Config.INPAINT_FULL_RES) is false and ignore_config is false.
        """
        cache = Cache()
        if (not ignore_config and not cache.get(Cache.INPAINT_FULL_RES)) or self._bounding_box is None:
            return None
        padding = cache.get(Cache.INPAINT_FULL_RES_PADDING)
        top: int = self._bounding_box.top()
        bottom: int = self._bounding_box.bottom()
        left: int = self._bounding_box.left()
        right: int = self._bounding_box.right()
        if include_context_pins:
            for pin in self._context_pins:
                top = min(top, pin.y())
                bottom = max(bottom, pin.y())
                left = min(left, pin.x())
                right = max(right, pin.x())
        if top >= bottom:
            return None  # mask was empty

        # Add padding:
        generation_area = self._generation_area
        area_left = generation_area.x()
        area_right = area_left + generation_area.width() - 1
        area_top = generation_area.y()
        area_bottom = area_top + generation_area.height() - 1
        top = max(area_top, top - padding)
        bottom = min(area_bottom, bottom + padding)
        left = max(area_left, left - padding)
        right = min(area_right, right + padding)
        height = bottom - top
        width = right - left

        # Expand to match image section's aspect ratio:
        image_ratio = generation_area.width() / generation_area.height()
        bounds_ratio = width / height

        if image_ratio > bounds_ratio:
            target_width = int(image_ratio * height)
            width_to_add = target_width - width
            assert width_to_add >= 0
            d_left = min(left - area_left, width_to_add // 2)
            width_to_add -= d_left
            d_right = min(area_right - right, width_to_add)
            width_to_add -= d_right
            if width_to_add > 0:
                d_left = min(left - area_left, d_left + width_to_add)
            left -= d_left
            right += d_right
        else:
            target_height = int(width // image_ratio)
            if target_height < height:
                logger.warning(f'Target height < height! old size={width}x{height}, target_height={target_height},'
                               f' image_ratio={image_ratio}, bounds_ratio={bounds_ratio}')
            height_to_add = max(target_height - height, 0)
            d_top = min(top - area_top, height_to_add // 2)
            height_to_add -= d_top
            d_bottom = min(area_bottom - bottom, height_to_add)
            height_to_add -= d_bottom
            if height_to_add > 0:
                d_top = min(top - area_top, d_top + height_to_add)
            top -= int(d_top)
            bottom += int(d_bottom)
        selection_rect = QRect(QPoint(int(left), int(top)),
                               QPoint(int(right), int(bottom)))
        return selection_rect

    @property
    def position(self) -> QPoint:
        """Returns the mask layer's position relative to image bounds."""
        return self.transformed_bounds.topLeft()


class SelectionLayerState:
    """Preserves a copy of the selection layer's state, including its context pins."""

    def __init__(self, image_state: ImageLayerState, context_pins: list[QPoint]) -> None:
        self.image_state = image_state
        self.context_pins = context_pins
