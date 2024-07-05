"""A layer used to mark masked regions for inpainting."""
from sys import version_info

from src.image.mypaint.numpy_image_utils import is_fully_transparent, AnyNpArray, image_data_as_numpy_8bit

if version_info[1] >= 11:
    from typing import Optional, List
else:
    from typing import Optional, List
import logging
from PyQt5.QtGui import QImage, QPolygonF, QPainter
from PyQt5.QtCore import QRect, QPoint, QSize, pyqtSignal, QPointF, Qt
import numpy as np
import cv2
from PIL import Image
from src.image.layers.image_layer import ImageLayer
from src.config.application_config import AppConfig
from src.util.image_utils import qimage_to_pil_image, image_content_bounds

logger = logging.getLogger(__name__)

SELECTION_LAYER_NAME = 'Selection'

MASK_OPACITY_DEFAULT = 0.2
ALPHA_THRESHOLD = 1
ALPHA_SELECTED = 180
ALPHA_UNSELECTED = 150


class SelectionLayer(ImageLayer):
    """A layer used to select regions for editing or inpainting.

    The selection layer has the following properties:

    - Only one selection layer ever exists, and its size always matches the image size.
    - Layer data is effectively 1-bit, with all pixels being either ARGB #00000000 or #FFFF0000
    - The layer cannot be copied.
    - Selection bounds are available as polygons through the `outline` property
    - When the "inpaint selected area only" option is checked, the mask layer pixmap will track the masked area bounds.
    - Functions are provided to adjust the selection area.

    The following properties can't be defined within this class itself, but should be enforced by the image stack:
    - The selection layer is always above all other layers.
    - The selection layer cannot be deleted, copied, or moved.
    - The selection layer can't be set as the active layer.
    - Contents are not saved unless the image is saved in the .inpt format to preserve layers.
    """

    def __init__(self, size: QSize, generation_window_signal: pyqtSignal) -> None:
        """
        Initializes a new selection layer.
        """
        self._outline_polygons: List[QPolygonF] = []
        self._generation_area = QRect()
        super().__init__(size, SELECTION_LAYER_NAME)
        self.opacity = MASK_OPACITY_DEFAULT
        self._bounding_box: Optional[QRect] = None
        self.transform_changed.connect(lambda layer, matrix: self._update_bounds())
        generation_window_signal.connect(self.update_generation_area)

    def update_generation_area(self, new_area: QRect) -> None:
        """Update the area marked for image generation."""
        self._generation_area = QRect(new_area)
        self._update_bounds()
        self.content_changed.emit(self)

    # Disabling unwanted layer functionality:
    def copy(self) -> 'SelectionLayer':
        """Disallow selection layer copies."""
        raise RuntimeError('The selection layer cannot be copied.')

    @property
    def saved(self) -> bool:
        """The selection layer is never saved with the image."""
        return False

    @saved.setter
    def saved(self, saved: bool):
        """Sets whether this layer is saved when visible and image data is saved."""
        raise RuntimeError('The selection layer is never saved with the rest of the image.')

    @property
    def outline(self) -> List[QPolygonF]:
        """Access the selection outline polygons directly."""
        return self._outline_polygons

    # Updating cached selection

    # Enforcing image properties:

    def _update_bounds(self, np_image: Optional[np.ndarray] = None) -> None:
        """Update saved selection bounds within the generation window."""
        if np_image is None:
            image = self.get_qimage()
            if image.size().isEmpty():
                return
            image_ptr = image.bits()
            assert image_ptr is not None, 'Selection layer image was invalid'
            image_ptr.setsize(image.byteCount())
            np_image = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)
        pos = self.position
        generation_area = QRect(self._generation_area).translated(-pos.x(), -pos.y())
        bounds = image_content_bounds(np_image, generation_area)
        bounds.translate(pos.x(), pos.y())
        if bounds.isNull():
            self._bounding_box = None
        else:
            self._bounding_box = bounds

    def generation_area_is_empty(self) -> bool:
        """Returns whether the current selection mask is empty."""
        self._update_bounds()
        return self._bounding_box is None or self._bounding_box.isEmpty()

    def generation_area_fully_selected(self) -> bool:
        """Returns whether the generation area is 100% selected."""
        np_image = image_data_as_numpy_8bit(self.get_qimage())
        bounds = QRect(self._generation_area)
        pos = self.position
        bounds.translate(-pos.x(), -pos.y())
        gen_area_np_image = np_image[bounds.y():bounds.y() + bounds.height(), bounds.x():bounds.x() + bounds.width(), :]
        return bool(np.all(gen_area_np_image[:, :, 3] > ALPHA_THRESHOLD))

    def select_all(self) -> None:
        """Selects the entire image."""
        full_selection = QImage(self.size, QImage.Format_ARGB32_Premultiplied)
        full_selection.fill(Qt.red)
        self.image = full_selection

    def invert_selection(self) -> None:
        """Select all unselected areas, and unselect all selected areas."""
        inverted = QImage(self.size, QImage.Format_ARGB32_Premultiplied)
        inverted.fill(Qt.GlobalColor.red)
        painter = QPainter(inverted)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
        painter.drawImage(QRect(QPoint(), self.size), self.image)
        painter.end()
        self.image = inverted

    def grow_or_shrink_selection(self, num_pixels: int) -> None:
        """Expand the selection outwards a given amount, or shrink it if num_pixels is negative."""
        image = self.image
        image_ptr = image.bits()
        assert image_ptr is not None, 'Selection layer image was invalid'
        image_ptr.setsize(image.byteCount())
        np_image: AnyNpArray = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)

        masked = np_image[:, :, 3] >= ALPHA_THRESHOLD
        mask_uint8 = masked.astype(np.uint8) * 255
        if num_pixels == 0:
            adjusted_mask = masked
        else:
            kernel_size = abs(num_pixels * 3)
            kernel = np.ones((kernel_size, kernel_size), np.uint8)
            if num_pixels > 0:
                adjusted_mask = cv2.dilate(mask_uint8, kernel, iterations=1)
            else:
                adjusted_mask = cv2.erode(mask_uint8, kernel, iterations=1)
        adjusted_mask = adjusted_mask > 0
        adjusted_image = np.zeros_like(np_image)
        adjusted_image[adjusted_mask, 0] = 0  # blue
        adjusted_image[adjusted_mask, 1] = 0  # green
        adjusted_image[adjusted_mask, 2] = 255  # red
        adjusted_image[adjusted_mask, 3] = 255
        qimage = QImage(adjusted_image.data, adjusted_image.shape[1], adjusted_image.shape[0],
                        QImage.Format_ARGB32)
        self.image = qimage

    @property
    def mask_image(self) -> QImage:
        """Gets the generation area mask content as a QImage"""
        bounds = self.map_rect_from_image(self._generation_area)
        return self.cropped_image_content(bounds)

    @property
    def pil_mask_image(self) -> Image.Image:
        """Gets the generation area mask content as a PIL image mask"""
        return qimage_to_pil_image(self.mask_image)

    def _handle_content_change(self, image: QImage, change_bounds: Optional[QRect] = None) -> None:
        """When the image updates, ensure that it meets requirements, and recalculate bounds."""
        # Enforce fixed colors, alpha thresholds:
        if image.size().isEmpty():
            return
        image_ptr = image.bits()
        assert image_ptr is not None, 'Selection layer image was invalid'
        image_ptr.setsize(image.byteCount())
        np_image: AnyNpArray = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)

        # Update selection bounds, skip extra processing if selection is empty:
        self._update_bounds(np_image)
        if is_fully_transparent(np_image):
            self._outline_polygons = []
            return

        if change_bounds is not None:
            cropped_image = np_image[change_bounds.y():change_bounds.y() + change_bounds.height(),
                                     change_bounds.x():change_bounds.x() + change_bounds.width(), :]
        else:
            cropped_image = np_image

        # Areas under ALPHA_THRESHOLD set to (0, 0, 0, 0), areas within the threshold set to #FF0000:
        masked = cropped_image[:, :, 3] >= ALPHA_THRESHOLD
        unmasked = ~masked
        for i in range(4):
            cropped_image[unmasked, i] = 0
        cropped_image[masked, 0] = 0  # blue
        cropped_image[masked, 1] = 0  # green
        cropped_image[masked, 2] = 255  # red
        cropped_image[masked, 3] = 255

        # Find edge polygons, using image coordinates:
        # Extra 0.5 offset puts lines through the center of pixels instead of on left edges.
        pos = self.position
        x_offset = 0.5 + pos.x()
        y_offset = 0.5 + pos.y()
        if change_bounds is not None:
            final_bounds = QRect(change_bounds)
            final_bounds.translate(-pos.x(), -pos.y())
            polys_to_remove = []
            for poly in self._outline_polygons:
                if poly.boundingRect().toAlignedRect().intersects(change_bounds):
                    final_bounds = final_bounds.united(poly.boundingRect().toAlignedRect().adjusted(-1, -1, 1, 1))
                    polys_to_remove.append(poly)
            for poly in polys_to_remove:
                self._outline_polygons.remove(poly)
            final_bounds = final_bounds.intersected(QRect(0, 0, self.width, self.height))
            cropped_image = np_image[final_bounds.y():final_bounds.y() + final_bounds.height(),
                                     final_bounds.x():final_bounds.x() + final_bounds.width(), :]
            x_offset += final_bounds.x()
            y_offset += final_bounds.y()
        else:
            self._outline_polygons = []
        gray = cv2.cvtColor(cropped_image[:, :, :3], cv2.COLOR_BGR2GRAY)
        contours, _ = cv2.findContours(gray, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
        for contour in contours:
            polygon = QPolygonF()
            for point in contour:
                polygon.append(QPointF(point[0][0] + x_offset, point[0][1] + y_offset))
            self._outline_polygons.append(polygon)

    def get_content_bounds(self) -> QRect:
        """Returns a rectangle containing all selected content within the image."""
        bounds = QRect()
        for polygon in self._outline_polygons:
            polygon_bounds = polygon.boundingRect().toAlignedRect()
            if bounds.isNull():
                bounds = polygon_bounds
            else:
                bounds = bounds.intersected(polygon_bounds)
        return bounds

    def get_selection_gen_area(self, ignore_config: bool = False) -> Optional[QRect]:
        """Returns the smallest QRect within the generation area containing all masked areas, plus padding.

        Used for showing the actual area visible to the image model when the Config.INPAINT_FULL_RES config option is
        set to true. The padding amount is set by the Config.INPAINT_FULL_RES_PADDING config option, measured in
        pixels.

        Parameters
        ----------
        ignore_config : bool
            If true, return the masked area bounds even when Config.INPAINT_FULL_RES is disabled in config.
        Returns
        -------
        QRect or None
           Rectangle containing all non-transparent mask canvas content plus padding, or None if the canvas is empty
           or config.get(Config.INPAINT_FULL_RES) is false and ignore_config is false.
        """
        config = AppConfig()
        if (not ignore_config and not config.get(AppConfig.INPAINT_FULL_RES)) or self._bounding_box is None:
            return None
        padding = config.get(AppConfig.INPAINT_FULL_RES_PADDING)
        top = self._bounding_box.top()
        bottom = self._bounding_box.bottom()
        left = self._bounding_box.left()
        right = self._bounding_box.right()
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
            target_height = width // image_ratio
            height_to_add = target_height - height
            assert height_to_add >= 0
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
        return self.full_image_bounds.topLeft()
