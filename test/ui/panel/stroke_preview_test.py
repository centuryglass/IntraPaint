"""Tests StrokePreview's approximation/accurate swap and its real-brush render."""
import os
from typing import Optional

from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QImage

from src.config.cache import Cache
from src.ui.input_fields.fill_style_combo_box import BRUSH_PATTERN_DENSE_3, BRUSH_PATTERN_SOLID
from src.ui.panel.tool_control_panels.stroke_block import StrokePreview
from src.undo_stack import UndoStack
from test.base_test_case import IntraPaintTestCase, TEST_RESOURCE_DIR

PREVIEW_SIZE = QSize(200, 80)
GOLDEN_DIR = os.path.join(TEST_RESOURCE_DIR, 'brush_previews')


class StrokePreviewTest(IntraPaintTestCase):
    """Tests the Draw tool's preview."""

    def make_preview(self, timer: Optional[QTimer] = None) -> StrokePreview:
        """Returns a visible preview of the Draw tool's settings."""
        preview = StrokePreview(Cache.DRAW_TOOL_BRUSH_SIZE, Cache.DRAW_TOOL_OPACITY, Cache.DRAW_TOOL_HARDNESS,
                                Cache.LAST_BRUSH_COLOR, Cache.DRAW_TOOL_BRUSH_PATTERN, Cache.DRAW_TOOL_ANTIALIAS,
                                debounce_timer=timer)
        preview.setFixedSize(PREVIEW_SIZE)
        preview.show()
        return preview

    def render(self, preview: StrokePreview) -> QImage:
        """Returns the preview as painted."""
        return preview.grab().toImage()

    def test_input_change_shows_approximation_until_debounce_fires(self) -> None:
        """A changed input drops to the approximation, and the timer's timeout swaps the accurate render in."""
        timer = QTimer()
        preview = self.make_preview(timer)
        timer.timeout.emit()
        self.assertTrue(preview.is_accurate)
        Cache().set(Cache.DRAW_TOOL_BRUSH_SIZE, 13)
        self.assertFalse(preview.is_accurate)
        self.assertTrue(timer.isActive())
        timer.timeout.emit()
        self.assertTrue(preview.is_accurate)

    def test_cached_image_is_reused_for_the_same_inputs(self) -> None:
        """Returning to earlier settings shows the cached render at once."""
        timer = QTimer()
        preview = self.make_preview(timer)
        original = Cache().get(Cache.DRAW_TOOL_BRUSH_SIZE)
        timer.timeout.emit()
        Cache().set(Cache.DRAW_TOOL_BRUSH_SIZE, original + 5)
        self.assertFalse(preview.is_accurate)
        Cache().set(Cache.DRAW_TOOL_BRUSH_SIZE, original)
        self.assertTrue(preview.is_accurate)

    def test_rendering_leaves_undo_history_alone(self) -> None:
        """The scratch layer's edits are not recorded."""
        preview = self.make_preview()
        before = UndoStack().undo_count()
        preview.render_accurate_now()
        self.assertEqual(UndoStack().undo_count(), before)

    def test_golden_images(self) -> None:
        """The accurate render matches golden images for hard, soft and patterned brushes."""
        cases = {
            'hard': (20, 1.0, BRUSH_PATTERN_SOLID),
            'soft': (30, 0.3, BRUSH_PATTERN_SOLID),
            'pattern': (30, 1.0, BRUSH_PATTERN_DENSE_3),
        }
        for name, (size, hardness, pattern) in cases.items():
            with self.subTest(name):
                Cache().set(Cache.DRAW_TOOL_BRUSH_SIZE, size)
                Cache().set(Cache.DRAW_TOOL_HARDNESS, hardness)
                Cache().set(Cache.DRAW_TOOL_OPACITY, 0.8)
                Cache().set(Cache.DRAW_TOOL_BRUSH_PATTERN, pattern)
                Cache().set(Cache.DRAW_TOOL_ANTIALIAS, True)
                preview = self.make_preview()
                preview.render_accurate_now()
                self.assert_image_matches_golden(self.render(preview), os.path.join(GOLDEN_DIR, f'stroke_{name}.png'))
