"""Tests loading animation frames as layers."""
import sys
from typing import cast

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication

from src.image.animation import frame_layer_name, load_frames_as_image, add_frame_layers
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.undo_stack import UndoStack
from src.util.visual.image_format_utils import ImageFrame
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

IMG_SIZE = QSize(64, 64)
GEN_AREA_SIZE = QSize(64, 64)
MIN_GEN_AREA = QSize(8, 8)
MAX_GEN_AREA = QSize(999, 999)


def _frame(color: QColor, duration_ms: int | None, size: QSize = IMG_SIZE) -> ImageFrame:
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return ImageFrame(image, duration_ms)


FRAMES = [_frame(QColor(255, 0, 0), 100), _frame(QColor(0, 255, 0), 200), _frame(QColor(0, 0, 255), None)]


class AnimationTest(IntraPaintTestCase):
    """Tests mapping animation frames to layers."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(IMG_SIZE, GEN_AREA_SIZE, MIN_GEN_AREA, MAX_GEN_AREA)

    def _frame_layers_bottom_up(self) -> list[ImageLayer]:
        layers = sorted(self.image_stack.top_level_layers, key=lambda layer: layer.z_value)
        return [cast(ImageLayer, layer) for layer in layers]

    def test_frame_layer_name(self) -> None:
        """Frame names are numbered from 1, with a duration tag only when the frame has a duration."""
        self.assertEqual(frame_layer_name(1, 120), 'Frame 1 (120ms)')
        self.assertEqual(frame_layer_name(3, None), 'Frame 3')
        self.assertEqual(frame_layer_name(2, 0, 'anim.gif: '), 'anim.gif: Frame 2 (0ms)')

    def test_load_frames_as_image(self) -> None:
        """Each frame becomes a top-level layer, first frame at the bottom, and only the first frame is visible."""
        self.image_stack.load_image(QImage(QSize(10, 10), QImage.Format.Format_ARGB32_Premultiplied))
        load_frames_as_image(self.image_stack, FRAMES)
        layers = self._frame_layers_bottom_up()
        self.assertEqual([layer.name for layer in layers], ['Frame 1 (100ms)', 'Frame 2 (200ms)', 'Frame 3'])
        self.assertEqual([layer.visible for layer in layers], [True, False, False])
        for layer, frame in zip(layers, FRAMES):
            self.assertEqual(layer.image.pixelColor(0, 0), frame.image.pixelColor(0, 0))
        self.assertEqual(self.image_stack.active_layer, layers[0])
        self.assertEqual(self.image_stack.size, IMG_SIZE)

    def test_load_frames_canvas_fits_largest_frame(self) -> None:
        """The canvas is sized to fit every frame, for multi-page files with pages of different sizes."""
        frames = [_frame(QColor(255, 0, 0), None, QSize(30, 50)), _frame(QColor(0, 255, 0), None, QSize(40, 20))]
        load_frames_as_image(self.image_stack, frames)
        self.assertEqual(self.image_stack.size, QSize(40, 50))

    def test_load_frames_undo(self) -> None:
        """Undoing a frame load restores the previous image."""
        self.image_stack.load_image(QImage(QSize(10, 10), QImage.Format.Format_ARGB32_Premultiplied))
        load_frames_as_image(self.image_stack, FRAMES)
        UndoStack().undo()
        self.assertEqual(len(self.image_stack.top_level_layers), 1)
        self.assertEqual(self.image_stack.size, QSize(10, 10))

    def test_add_frame_layers(self) -> None:
        """Frames are added above the existing layer in frame order, with only the first frame visible."""
        self.image_stack.load_image(QImage(IMG_SIZE, QImage.Format.Format_ARGB32_Premultiplied))
        base_layer = self.image_stack.top_level_layers[0]
        add_frame_layers(self.image_stack, FRAMES, 'anim.gif: ')
        layers = self._frame_layers_bottom_up()
        self.assertEqual(layers[0], base_layer)
        self.assertEqual([layer.name for layer in layers[1:]],
                         ['anim.gif: Frame 1 (100ms)', 'anim.gif: Frame 2 (200ms)', 'anim.gif: Frame 3'])
        self.assertEqual([layer.visible for layer in layers], [True, True, False, False])
