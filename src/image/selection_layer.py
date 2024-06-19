"""A layer used to mark masked regions for inpainting."""
from sys import version_info

from src.image.mypaint.numpy_image_utils import is_fully_transparent

if version_info[1] >= 11:
    from typing import Self, Optional, List
else:
    from typing import Optional, List
    from typing_extensions import Self
import logging
from PyQt5.QtGui import QImage, QPolygonF, QPainter
from PyQt5.QtCore import QRect, QPoint, QSize, pyqtSignal, QPointF, Qt
import numpy as np
import cv2
from PIL import Image
from src.image.image_layer import ImageLayer
from src.config.application_config import AppConfig
from src.util.image_utils import qimage_to_pil_image, image_content_bounds

logger = logging.getLogger(__name__)

SELECTION_LAYER_NAME = "Selection"

MASK_OPACITY_DEFAULT = 0.2
ALPHA_THRESHOLD = 1
ALPHA_SELECTED = 180
ALPHA_UNSELECTED = 150


class SelectionLayer(ImageLayer):
    """A layer used to select regions for editing or inpainting.

    The selection layer has the following properties:

    - Only one selection layer ever exists, and its size always matches the image size.
    - Layer data is effectively 1-bit, with all pixels being either ARGB #00000000 or $FFFF0000
    - The layer cannot be copied.
    - Selection bounds are available as polygons through the `outline` property
    - When the "inpaint selected area only" option is checked, the mask layer pixmap will track the masked area bounds.
    - Functions are provided to adjust the selection area.

    The following properties can't be defined within this class itself, but should be enforced by the layer stack:
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
        super().__init__(size, SELECTION_LAYER_NAME, False)
        self.opacity = MASK_OPACITY_DEFAULT
        self._bounding_box = None
        self._outer_bounds = QRect()
        generation_window_signal.connect(self.update_generation_area)

    def update_generation_area(self, new_area: QRect) -> None:
        """Update the area marked for image generation."""
        self._generation_area = new_area
        self._update_bounds()
        self.content_changed.emit(self)

    # Disabling unwanted layer functionality:
    def copy(self) -> Self:
        """Disallow selection layer copies."""
        raise RuntimeError("The selection layer cannot be copied.")

    @property
    def saved(self) -> bool:
        """The selection layer is never saved with the image."""
        return False

    @saved.setter
    def saved(self, saved: bool):
        """Sets whether this layer is saved when visible and image data is saved."""
        raise RuntimeError("The selection layer is never saved with the rest of the image.")

    @property
    def outline(self) -> List[QPolygonF]:
        """Access the selection outline polygons directly."""
        return self._outline_polygons

    # Updating cached selection

    # Enforcing image properties:
    def _update_bounds(self, np_image: Optional[np.ndarray] = None) -> None:
        """Update saved selection bounds within the generation window."""
        if np_image is None:
            image = self.qimage
            image_ptr = image.bits()
            image_ptr.setsize(image.byteCount())
            np_image = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)
        generation_area = self._generation_area
        self._outer_bounds = image_content_bounds(np_image, QRect(QPoint(), self.size), ALPHA_THRESHOLD)
        bounds = image_content_bounds(np_image, generation_area, ALPHA_THRESHOLD)
        if bounds.isNull():
            self._bounding_box = None
        else:
            self._bounding_box = bounds

    def generation_area_is_empty(self) -> bool:
        """Returns whether the current selection mask is empty."""
        self._update_bounds()
        return self._bounding_box is None or self._bounding_box.isEmpty()

    def select_all(self) -> None:
        """Selects the entire image."""
        full_selection = QImage(self.size, QImage.Format_ARGB32_Premultiplied)
        full_selection.fill(Qt.red)
        self.qimage = full_selection

    def invert_selection(self) -> None:
        """Select all unselected areas, and unselect all selected areas."""
        inverted = QImage(self.size, QImage.Format_ARGB32_Premultiplied)
        inverted.fill(Qt.GlobalColor.red)
        painter = QPainter(inverted)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
        painter.drawImage(QRect(QPoint(), self.size), self.qimage)
        painter.end()
        self.qimage = inverted

    def grow_or_shrink_selection(self, num_pixels: int) -> None:
        """Expand the selection outwards a given amount, or shrink it if num_pixels is negative."""
        image = self.qimage
        image_ptr = image.bits()
        image_ptr.setsize(image.byteCount())
        np_image = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)

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
        qimage.save('test.png')
        self.qimage = qimage

    @property
    def pil_mask_image(self) -> Image.Image:
        """Gets the selection mask as a PIL image mask."""
        return qimage_to_pil_image(self.cropped_image_content(self._generation_area))

    def _handle_content_change(self, image: QImage) -> None:
        """When the image updates, ensure that it meets requirements, and recalculate bounds."""
        # Enforce fixed colors, alpha thresholds:
        image_ptr = image.bits()
        image_ptr.setsize(image.byteCount())
        np_image = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)

        # Update selection bounds, skip extra processing if selection is empty:
        self._update_bounds(np_image)
        if is_fully_transparent(np_image):
            self._outline_polygons = []
            return

        # Areas under ALPHA_THRESHOLD set to (0, 0, 0, 0), areas within the threshold set to #FF0000:
        masked = np_image[:, :, 3] >= ALPHA_THRESHOLD
        unmasked = ~masked
        for i in range(4):
            np_image[unmasked, i] = 0
        np_image[masked, 0] = 0  # blue
        np_image[masked, 1] = 0  # green
        np_image[masked, 2] = 255  # red
        np_image[masked, 3] = 255

        cropped = np_image[self._outer_bounds.y():self._outer_bounds.height() + self._outer_bounds.y(),
                           self._outer_bounds.x():self._outer_bounds.width() + self._outer_bounds.x(), :]
        # Find edge polygons:
        self._outline_polygons = []
        gray = cv2.cvtColor(cropped[:, :, :3], cv2.COLOR_BGR2GRAY)
        contours, _ = cv2.findContours(gray, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
        for contour in contours:
            polygon = QPolygonF()
            for point in contour:
                polygon.append(QPointF(point[0][0] + 0.5 + self._outer_bounds.x(),
                                       point[0][1] + 0.5 + self._outer_bounds.y()))
            self._outline_polygons.append(polygon)

    def get_selection_gen_area(self, ignore_config: bool = False) -> Optional[QRect]:
        """Returns the smallest QRect containing all masked areas, plus padding.

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
        config = AppConfig.instance()
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

        try:
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
                top -= d_top
                bottom += d_bottom
        except AssertionError:
            # Weird edge cases that pop up sometimes when you try to do unreasonable things like change size to 500x8
            selection_rect = QRect(QPoint(int(left), int(top)), QPoint(int(right), int(bottom)))
            logger.error(f'Border calc bug: calculated rect was {selection_rect}, ratio was {image_ratio}')
        selection_rect = QRect(QPoint(int(left), int(top)), QPoint(int(right), int(bottom)))
        return selection_rect
