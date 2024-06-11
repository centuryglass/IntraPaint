"""A layer used to mark masked regions for inpainting."""
from sys import version_info

if version_info[1] >= 11:
    from typing import Self, Optional, List
else:
    from typing import Optional
    from typing_extensions import Self
import logging
from PyQt5.QtGui import QImage, QPolygon
from PyQt5.QtCore import QRect, QPoint, QSize, pyqtSignal
import numpy as np
import cv2
from PIL import Image
from src.image.image_layer import ImageLayer
from src.config.application_config import AppConfig
from src.util.image_utils import qimage_to_pil_image, image_content_bounds

logger = logging.getLogger(__name__)

MASK_LAYER_NAME = "Inpainting Mask"
MASK_OPACITY_DEFAULT = 0.3
ALPHA_THRESHOLD = 1
ALPHA_SELECTED = 180
ALPHA_UNSELECTED = 150


class MaskLayer(ImageLayer):
    """A layer used to mark masked regions for inpainting.

    The mask layer has the following properties:

    - The mask layer is never saved.
    - Opacity defaults to 0.6
    - The mask layer cannot be copied.
    - Mask layer content is always of uniform opacity and color.
    - When rendered to a pixmap, masked regions are outlined.
    - When the "inpaint masked only" option is checked, the mask layer pixmap will track the masked area bounds.
    - Masked areas within the image generation selection are drawn at a higher opacity.

    The following properties can't be defined within this class itself, but should be enforced by the layer stack:
    - The mask layer is always above all other layers.
    - The mask layer cannot be deleted, copied, or moved.
    - The mask layer can't be set as the active layer.
    """

    def __init__(self, size: QSize, config: AppConfig, selection_signal: pyqtSignal) -> None:
        """
        Initializes a new mask layer.
        """
        self._outline_polygons: List[QPolygon] = []
        self._selection = QRect()
        super().__init__(size, MASK_LAYER_NAME, False)
        self.opacity = MASK_OPACITY_DEFAULT
        self._config = config
        self._bounding_box = None
        selection_signal.connect(self.update_selection)

    def update_selection(self, new_selection: QRect) -> None:
        """Update the area marked for image generation."""
        self._selection = new_selection
        self._update_bounds()
        self.content_changed.emit(self)

    # Disabling unwanted layer functionality:
    def copy(self) -> Self:
        """Disallow mask copies."""
        raise RuntimeError("The mask layer cannot be copied.")

    @property
    def saved(self) -> bool:
        """The mask layer is never saved with the image."""
        return False

    @saved.setter
    def saved(self, saved: bool):
        """Sets whether this layer is saved when visible and image data is saved."""
        raise RuntimeError("The mask layer is never saved with the rest of the image.")

    @property
    def outline(self) -> List[QPolygon]:
        """Access the selection outline polygons directly."""
        return self._outline_polygons

    # Updating cached selection

    # Enforcing image properties:
    def _update_bounds(self, np_image: Optional[np.ndarray] = None) -> None:
        """Update saved mask bounds within the selection."""
        if np_image is None:
            image = self.qimage
            image_ptr = image.bits()
            image_ptr.setsize(image.byteCount())
            np_image = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)
        selection = self._selection
        bounds = image_content_bounds(np_image, selection, ALPHA_THRESHOLD)
        if bounds.isNull():
            self._bounding_box = None
        else:
            self._bounding_box = bounds

    def selection_is_empty(self) -> bool:
        """Returns whether the current selection mask is empty."""
        self._update_bounds()
        return self._bounding_box is None or self._bounding_box.isEmpty()

    @property
    def pil_mask_image(self) -> Image.Image:
        """Gets the selection mask as a PIL image mask."""
        return qimage_to_pil_image(self.cropped_image_content(self._selection))

    def _handle_content_change(self, image: QImage) -> None:
        """When the image updates, ensure that it meets requirements, and recalculate bounds."""

        # Enforce fixed colors, alpha thresholds:
        image_ptr = image.bits()
        image_ptr.setsize(image.byteCount())
        np_image = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)

        # Update selection bounds, skip extra processing if selection is empty:
        if self.selection_is_empty():
            self._outline_polygons.clear()
            return

        # Areas under ALPHA_THRESHOLD set to (0, 0, 0, 0), areas within the threshold set to #FF0000 with opacity
        # varying based on the selection bounds:
        masked = np_image[:, :, 3] >= ALPHA_THRESHOLD
        unmasked = ~masked
        np_image[unmasked, 0] = 0
        np_image[masked, 0] = 0  # blue
        np_image[masked, 1] = 0  # green
        np_image[masked, 2] = 255  # red
        np_image[masked, 3] = 255

        # Find edge polygons:
        gray = cv2.cvtColor(np_image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        self._outline_polygons.clear()
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            polygon = QPolygon()
            for point in contour:
                polygon.append(QPoint(point[0][0], point[0][1]))
            self._outline_polygons.append(polygon)

    def get_masked_area(self, ignore_config: bool = False) -> Optional[QRect]:
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
        if (not ignore_config and not self._config.get(AppConfig.INPAINT_FULL_RES)) or self._bounding_box is None:
            return None
        padding = self._config.get(AppConfig.INPAINT_FULL_RES_PADDING)
        top = self._bounding_box.top()
        bottom = self._bounding_box.bottom()
        left = self._bounding_box.left()
        right = self._bounding_box.right()
        if top >= bottom:
            return None  # mask was empty

        # Add padding:
        selection = self._selection
        selection_left = selection.x()
        selection_right = selection_left + selection.width() - 1
        selection_top = selection.y()
        selection_bottom = selection_top + selection.height() - 1
        top = max(selection_top, top - padding)
        bottom = min(selection_bottom, bottom + padding)
        left = max(selection_left, left - padding)
        right = min(selection_right, right + padding)
        height = bottom - top
        width = right - left

        # Expand to match image section's aspect ratio:
        image_ratio = selection.width() / selection.height()
        bounds_ratio = width / height

        try:
            if image_ratio > bounds_ratio:
                target_width = int(image_ratio * height)
                width_to_add = target_width - width
                assert width_to_add >= 0
                d_left = min(left - selection_left, width_to_add // 2)
                width_to_add -= d_left
                d_right = min(selection_right - right, width_to_add)
                width_to_add -= d_right
                if width_to_add > 0:
                    d_left = min(left - selection_left, d_left + width_to_add)
                left -= d_left
                right += d_right
            else:
                target_height = width // image_ratio
                height_to_add = target_height - height
                assert height_to_add >= 0
                d_top = min(top - selection_top, height_to_add // 2)
                height_to_add -= d_top
                d_bottom = min(selection_bottom - bottom, height_to_add)
                height_to_add -= d_bottom
                if height_to_add > 0:
                    d_top = min(top - selection_top, d_top + height_to_add)
                top -= d_top
                bottom += d_bottom
        except AssertionError:
            # Weird edge cases that pop up sometimes when you try to do unreasonable things like change size to 500x8
            mask_rect = QRect(QPoint(int(left), int(top)), QPoint(int(right), int(bottom)))
            logger.error(f'Border calc bug: calculated rect was {mask_rect}, ratio was {image_ratio}')
        mask_rect = QRect(QPoint(int(left), int(top)), QPoint(int(right), int(bottom)))
        return mask_rect
