"""A layer used to mark masked regions for inpainting."""
from sys import version_info

if version_info[1] >= 11:
    from typing import Self, Optional
else:
    from typing import Optional
    from typing_extensions import Self
from collections.abc import Generator
from contextlib import contextmanager
import logging
from PyQt5.QtGui import QImage, QPainter, QPixmap, QPolygon, QPen
from PyQt5.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal
import numpy as np
import cv2
from PIL import Image
from src.util.validation import assert_type
from src.image.image_layer import ImageLayer
from src.config.application_config import AppConfig
from src.util.image_utils import qimage_to_pil_image

logger = logging.getLogger(__name__)

MASK_LAYER_NAME = "Inpainting Mask"
MASK_OPACITY_ACTIVE = 0.6
MASK_OPACITY_DEFAULT = 0.4
MASK_OPACITY_REDUCED = 0.3
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
        super().__init__(size, MASK_LAYER_NAME, False)
        self.opacity = MASK_OPACITY_DEFAULT
        self._config = config
        self._bounding_box = None
        self._selection = QRect()
        selection_signal.connect(self.update_selection)

    def update_selection(self, new_selection: QRect) -> None:
        """Update the area marked for image generation."""
        self._selection = new_selection
        self._update_bounds()
        self.content_changed.emit()

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

    # Updating cached selection

    # Enforcing image properties:
    def _update_bounds(self, np_image: Optional[np.ndarray] = None) -> None:
        """Update saved mask bounds within the selection."""
        if np_image is None:
            image = self.q_image
            image_ptr = image.bits()
            image_ptr.setsize(image.byteCount())
            np_image = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)
        selection = self._selection
        # Get a numpy array for just the selected region:
        selection_image = np_image[selection.y():selection.y() + selection.height(),
                          selection.x():selection.x() + selection.width(), :]
        # Find and save the bounds of the masked area within the selection:
        if np.all(selection_image[:, :, 3] == 0):
            self._bounding_box = None
        else:
            masked_rows = np.any(selection_image[:, :, 3] >= ALPHA_THRESHOLD, axis=1)
            masked_columns = np.any(selection_image[:, :, 3] >= ALPHA_THRESHOLD, axis=0)
            top = np.argmax(masked_rows) + selection.y()
            bottom = selection.y() + selection.height() - 1 - np.argmax(np.flip(masked_rows))
            left = selection.x() + np.argmax(masked_columns)
            right = selection.x() + selection.width() - 1 - np.argmax(np.flip(masked_columns))
            if left >= right:
                self._bounding_box = None
            else:
                self._bounding_box = QRect(left, top, right - left, bottom - top)

    def selection_is_empty(self) -> bool:
        """Returns whether the current selection mask is empty."""
        self._update_bounds()
        return self._bounding_box is None or self._bounding_box.isEmpty()

    @contextmanager
    def borrow_image(self) -> Generator[Optional[QImage], None, None]:
        """Provides direct access to the image for editing, then applies mask restrictions and draws outlines."""
        with super().borrow_image() as image:
            yield image
            # Got image back from borrower, do mask post-processing:
            selection = self._selection
            image_ptr = image.bits()
            image_ptr.setsize(image.byteCount())
            np_image = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)
            self._update_bounds(np_image)
            # Areas under ALPHA_THRESHOLD set to (0, 0, 0, 0), areas within the threshold set to #FF0000 with opacity
            # varying based on the selection bounds:
            masked = np_image[:, :, 3] >= ALPHA_THRESHOLD
            unmasked = ~masked
            np_image[unmasked, 0] = 0
            np_image[masked, 0] = 0  # blue
            np_image[masked, 1] = 0  # green
            np_image[masked, 2] = 255  # red
            np_image[masked, 3] = 255
            # TODO: figure out why setting alpha < 255 causes weird image effects
            # selection_image[masked, 3] = ALPHA_SELECTED
            # np_image[masked][3] = ALPHA_UNSELECTED
            # selection_masked = selection_image[:, :, 3] > 0
            # selection_image[selection_masked][3] = ALPHA_SELECTED

    def clear(self):
        """Replaces all image content with transparency."""
        with self.borrow_image() as image:
            image.fill(Qt.transparent)

    @property
    def pil_mask_image(self) -> Image.Image:
        """Gets the selection mask as a PIL image mask."""
        return qimage_to_pil_image(self.cropped_image_content(self._selection))

    def _generate_pixmap(self, image: QImage) -> QPixmap:
        """Apply the outline to the mask when generating the pixmap cache."""
        image = image.copy()
        # find edges:
        image_ptr = image.bits()
        image_ptr.setsize(image.byteCount())
        arr = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)

        # Convert edges to polygons and draw:
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        polygons = []
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            polygon = QPolygon()
            for point in contour:
                polygon.append(QPoint(point[0][0], point[0][1]))
            polygons.append(polygon)

        painter = QPainter(image)
        line_pen_1 = QPen(Qt.GlobalColor.black, 1)
        line_pen_2 = QPen(Qt.GlobalColor.white, 1)
        dash_pattern = [2, 2]
        line_pen_1.setDashPattern(dash_pattern)
        line_pen_2.setDashPattern(dash_pattern)
        line_pen_2.setDashOffset(2)

        for polygon in polygons:
            painter.setPen(line_pen_1)
            painter.drawPolygon(polygon)
            painter.setPen(line_pen_2)
            painter.drawPolygon(polygon)

        painter.end()
        return QPixmap.fromImage(image)

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

    def _validate_bounds(self, bounds_rect: QRect):
        assert_type(bounds_rect, QRect)
        layer_bounds = QRect(QPoint(0, 0), self.size)
        if not layer_bounds.contains(bounds_rect):
            raise ValueError(f'{bounds_rect} not within {layer_bounds}')
