"""Tests that ResizeCanvasModal's size is not pinned by its own earlier size."""
from PySide6.QtCore import QSize

from src.image.layers.image_stack import ImageStack
from src.ui.modal.resize_canvas_modal import ResizeCanvasModal
from test.base_test_case import IntraPaintTestCase


class ResizeCanvasModalTest(IntraPaintTestCase):
    """Tests ResizeCanvasModal's size constraints."""

    def test_minimum_size_does_not_follow_current_size(self) -> None:
        """Enlarging the modal leaves its minimum size hint unchanged, so it can shrink again."""
        size = QSize(1024, 1024)
        modal = ResizeCanvasModal(ImageStack(size, size, size, size))
        modal.show()
        initial_minimum = modal.minimumSizeHint()
        modal.resize(1200, 1200)
        modal.resize(400, 400)
        self.assertEqual(modal.minimumSizeHint(), initial_minimum)
        self.assertEqual(modal.size(), QSize(400, 400).expandedTo(initial_minimum))
