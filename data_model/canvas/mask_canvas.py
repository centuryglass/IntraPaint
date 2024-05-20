"""
Provides a Canvas implementation for marking sections of an image to be edited with AI inpainting.
"""
from typing import Optional
import numpy as np
import cv2
from PIL import Image
from PyQt5.QtCore import Qt, QRect, QPoint, QSize
from PyQt5.QtGui import QPixmap, QPainter, QImage, QPen
from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsScene
from ui.util.contrast_color import contrast_color
from data_model.canvas.pixmap_canvas import PixmapCanvas
from data_model.config import Config

class MaskCanvas(PixmapCanvas):
    """Provides a Canvas implementation for marking sections of an image to be edited with AI inpainting."""

    def __init__(self,
            config: Config,
            image: Optional[QImage | Image.Image | QPixmap | QSize | str]):
        """Initialize with config values and optional arbitrary initial image data.

        Parameters
        ----------
        config: data_model.Config
            Used for setting initial size if no initial image data is provided.
        image: QImage or PIL Image or QPixmap or QSize or str, optional
        """
        super().__init__(config, image)
        config.connect(self, Config.MASK_BRUSH_SIZE, self.set_brush_size)
        self.set_brush_size(config.get(Config.MASK_BRUSH_SIZE))
        self._outline = None
        self._drawing = False
        self._bounding_box = None
        config.connect(self, Config.INPAINT_FULL_RES, lambda v: self._handle_changes())
        config.connect(self, Config.INPAINT_FULL_RES_PADDING, lambda v: self._handle_changes())

        self._dither_mask = QPixmap(QSize(512, 512))
        dither_stamp = QPixmap(QSize(8, 8))
        painter = QPainter(dither_stamp)
        painter.fillRect(0, 0, 8, 8, Qt.white)
        painter.fillRect(0, 0, 4, 4, Qt.black)
        painter.fillRect(4, 4, 4, 4, Qt.black)
        painter = QPainter(self._dither_mask)
        painter.drawTiledPixmap(0, 0, 512, 512, dither_stamp)

        self._outline = QGraphicsPixmapItem()
        self._set_empty_outline()
        self.setOpacity(0.5)


    def add_to_scene(self, scene: QGraphicsScene, z_value: Optional[int] = None):
        """Adds the canvas to a QGraphicsScene.

        Parameters
        ----------
        scene : QGraphicsScene
            Scene that will display the canvas content.
        z_value : int
            Level within the scene where canvas content is drawn, higher levels appear above lower ones.
        """
        super().add_to_scene(scene, z_value)
        self._outline.setZValue(self.zValue())
        scene.addItem(self._outline)


    def get_inpainting_mask(self) -> Image.Image:
        """Returns the canvas content as a 1-bit PIL Image mask. """
        image = self.get_pil_image()
        image = image.convert('L').point( lambda p: 255 if p < 1 else 0 )
        return image


    def start_stroke(self):
        """Signals the start of a brush stroke, to be called once whenever user input starts or resumes."""
        super().start_stroke()
        self._set_empty_outline()


    def end_stroke(self):
        """Signals the end of a brush stroke, to be called once whenever user input stops or pauses."""
        super().end_stroke()
        self._draw_outline()


    def set_image(self, image_data: QImage | QPixmap | QSize | Image.Image | str):
        """Loads an image into the canvas, overwriting existing canvas content.

        Parameters
        ----------
        image_data : QImage or QPixmap or QSize or PIL Image or str
            An image, image size, or image path. If necessary, the canvas will be resized to match the image size.
            If image_data is a QSize, the canvas will be cleared.
        """
        super().set_image(image_data)
        self._draw_outline()
        self.update()


    def get_masked_area(self, ignore_config: bool = False) -> QRect:
        """Returns the smallest QRect containing all masked areas, plus padding.

        Used for showing the actual area visible to the image model when the Config.INPAINT_FULL_RES config option is
        set to true. The padding abount is set by the Config.INPAINT_FULL_RES_PADDING config option, measured in
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
        if ((not ignore_config) and (not self._config.get(Config.INPAINT_FULL_RES))) or self._bounding_box is None:
            return None
        padding = self._config.get(Config.INPAINT_FULL_RES_PADDING)
        top = self._bounding_box.top()
        bottom = self._bounding_box.bottom()
        left = self._bounding_box.left()
        right = self._bounding_box.right()
        if top >= bottom:
            return None # mask was empty

        # Add padding:
        top = max(0, top - padding)
        bottom = min(self.height() - 1, bottom + padding)
        left = max(0, left - padding)
        right = min(self.width() - 1, right + padding)
        height = bottom - top
        width = right - left

        # Expand to match image section's aspect ratio:
        image_ratio = self.size().width() / self.size().height()
        bounds_ratio = width / height

        if image_ratio > bounds_ratio:
            target_width = int(image_ratio * height)
            width_to_add = target_width - width
            assert width_to_add >= 0
            d_left = min(left, width_to_add // 2)
            width_to_add -= d_left
            d_right = min(self.width() - 1 - right, width_to_add)
            width_to_add -= d_right
            if width_to_add > 0:
                d_left = min(left, d_left + width_to_add)
            left -= d_left
            right += d_right
        else:
            target_height = width // image_ratio
            height_to_add = target_height - height
            assert height_to_add >= 0
            d_top = min(top, height_to_add // 2)
            height_to_add -= d_top
            d_bottom = min(self.height() - 1 - bottom, height_to_add)
            height_to_add -= d_bottom
            if height_to_add > 0:
                d_top = min(top, d_top + height_to_add)
            top -= d_top
            bottom += d_bottom
        mask_rect = QRect(QPoint(int(left), int(top)), QPoint(int(right), int(bottom)))
        return mask_rect


    def resize(self, size: QSize):
        """Updates the canvas size, scaling any image content to match.

        Parameters
        ----------
        size : QSize
            New canvas size in pixels.
        """
        super().resize(size)
        self._outline.setPixmap(self._outline.pixmap().scaled(size))


    def fill(self):
        """Updates the mask to cover the entire canvas bounds."""
        super().fill(Qt.red)
        self._draw_outline()
        self.update()


    def clear(self):
        """Clears the mask so that no area is marked for editing."""
        super().fill(Qt.transparent)
        self._set_empty_outline()
        self.update()


    def setVisible(self, visible: bool):
        """Shows or hides the canvas."""
        super().setVisible(visible)
        self._outline.setVisible(visible)


    def setOpacity(self, opacity: float):
        """Changes the opacity used when drawing the masked area."""
        super().setOpacity(opacity)
        self._outline.setOpacity(opacity)


    # Outline masked areas with dotted lines, and draw the bonding rectangle used when Config.INPAINT_FULL_RES is set:
    def _handle_changes(self):
        width = self._dither_mask.width()
        height = self._dither_mask.height()
        while width < self.width():
            width += self.width()
        while height < self.height():
            height += self.height()
        if width != self._dither_mask.width() or height != self._dither_mask.height():
            new_dither_mask = QPixmap(QSize(width, height))
            painter = QPainter(new_dither_mask)
            painter.drawTiledPixmap(0, 0, width, height, self._dither_mask)
            self._dither_mask = new_dither_mask
        self._draw_outline()
        super()._handle_changes()

    def _set_empty_outline(self):
        blank_pixmap = QPixmap(self.size())
        blank_pixmap.fill(Qt.transparent)
        self._outline.setPixmap(blank_pixmap)
        self._bounding_box = None

    def _draw_outline(self):
        if not hasattr(self, '_drawing') or self._drawing or self.scene() is None:
            return
        image = self.get_qimage()

        # find edges:
        buffer = image.bits().asstring(image.byteCount())
        arr = np.frombuffer(buffer, dtype=np.uint8).reshape((image.height(), image.width(), 4))
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        edges= cv2.Canny(gray, 50, 150)

        # find bounds:
        nonzero_rows = np.any(arr[:, :, 3] > 0, axis=1)
        nonzero_cols = np.any(arr[:, :, 3] > 0, axis=0)
        top = np.argmax(nonzero_rows)
        bottom = image.height() - 1 - np.argmax(np.flip(nonzero_rows))
        left = np.argmax(nonzero_cols)
        right = image.width() - 1 - np.argmax(np.flip(nonzero_cols))
        if left > right:
            self._bounding_box = None
        else:
            self._bounding_box = QRect(left, top, right - left, bottom - top)

        # expand edges to draw a thicker outline:
        thickness = max(2, image.width() // 200, image.height() // 200)
        thickness = min(thickness, 4)
        edges = 255 - cv2.dilate(edges, np.ones((thickness, thickness), np.uint8), iterations=1)
        edges_a = np.zeros((edges.shape[0], edges.shape[1], 4), dtype=np.uint8)
        edges_a[:, :, 3] = 255 - edges
        # edges_a.strides is definitely a tuple, not sure why pylint disagrees.
        # pylint: disable-next=unsubscriptable-object
        outline = QImage(edges_a.data, edges_a.shape[1], edges_a.shape[0], edges_a.strides[0], QImage.Format_RGBA8888)
        painter = QPainter(outline)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.drawPixmap(0, 0, self._dither_mask)

        if self._config.get(Config.INPAINT_FULL_RES):
            masked_area = self.get_masked_area()
            if masked_area is not None:
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                color = contrast_color(self.scene().views()[0])
                pen = QPen(color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(pen)
                painter.drawRect(masked_area)
        painter.end()
        self._outline.setPixmap(QPixmap.fromImage(outline))
