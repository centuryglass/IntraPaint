"""Tests StrokePreview's timed updates and its real-brush render, for painting, erasing and smudging."""
import os
from typing import Optional

from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QImage, QPalette

from src.config.cache import Cache
from src.ui.input_fields.fill_style_combo_box import BRUSH_PATTERN_DENSE_3, BRUSH_PATTERN_SOLID
from src.ui.panel.tool_control_panels.stroke_preview import DrawStrokePreview, EraseStrokePreview, SmudgeStrokePreview, StrokePreview
from src.ui.panel.tool_control_panels.preview_backdrop import backdrop_image
from src.undo_stack import UndoStack
from src.util.visual.keycap import keycap_colors
from test.base_test_case import IntraPaintTestCase, TEST_RESOURCE_DIR

PREVIEW_SIZE = QSize(200, 80)
GOLDEN_DIR = os.path.join(TEST_RESOURCE_DIR, 'brush_previews')


class StrokePreviewTest(IntraPaintTestCase):
    """Tests the Draw tool's preview."""

    def make_preview(self, timer: Optional[QTimer] = None) -> DrawStrokePreview:
        """Returns a visible preview of the Draw tool's settings."""
        preview = DrawStrokePreview(Cache.DRAW_TOOL_BRUSH_SIZE, Cache.DRAW_TOOL_OPACITY, Cache.DRAW_TOOL_HARDNESS,
                                Cache.LAST_BRUSH_COLOR, Cache.DRAW_TOOL_BRUSH_PATTERN, Cache.DRAW_TOOL_ANTIALIAS,
                                render_timer=timer)
        preview.setFixedSize(PREVIEW_SIZE)
        preview.show()
        preview.render_now()
        return preview

    def render(self, preview: StrokePreview) -> QImage:
        """Returns the preview as painted."""
        return preview.grab().toImage()

    def test_input_change_keeps_the_old_render_until_the_timer_fires(self) -> None:
        """A changed input leaves the last render on screen and schedules one render, which the timer's timeout runs."""
        timer = QTimer()
        preview = self.make_preview(timer)
        self.assertTrue(preview.is_current)
        Cache().set(Cache.DRAW_TOOL_BRUSH_SIZE, 13)
        Cache().set(Cache.DRAW_TOOL_OPACITY, 0.4)
        self.assertFalse(preview.is_current)
        self.assertTrue(timer.isActive())
        timer.timeout.emit()
        self.assertTrue(preview.is_current)

    def test_cached_image_is_reused_for_the_same_inputs(self) -> None:
        """Returning to earlier settings shows the cached render at once, without waiting for the timer."""
        timer = QTimer()
        preview = self.make_preview(timer)
        original = Cache().get(Cache.DRAW_TOOL_BRUSH_SIZE)
        Cache().set(Cache.DRAW_TOOL_BRUSH_SIZE, original + 5)
        timer.timeout.emit()
        self.assertTrue(preview.is_current)
        Cache().set(Cache.DRAW_TOOL_BRUSH_SIZE, original)
        self.assertTrue(preview.is_current)
        self.assertFalse(timer.isActive())

    def test_rendering_leaves_undo_history_alone(self) -> None:
        """The scratch layer's edits are not recorded."""
        preview = self.make_preview()
        before = UndoStack().undo_count()
        preview.render_now()
        self.assertEqual(UndoStack().undo_count(), before)

    def test_background_contrasts_with_the_brush_color(self) -> None:
        """The background is whichever of the panel background and keycap fill contrasts more with the brush color."""
        preview = self.make_preview()
        base = preview.palette().color(QPalette.ColorRole.Base)
        keycap_fill = keycap_colors(preview.palette())[0]
        for color in (base, keycap_fill):
            with self.subTest(color=color.name()):
                Cache().set(Cache.LAST_BRUSH_COLOR, color.name())
                other = keycap_fill if color == base else base
                self.assertEqual(preview._background(), other)  # pylint: disable=protected-access

    def test_golden_images(self) -> None:
        """The render matches golden images for hard, soft and patterned brushes."""
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
                preview.render_now()
                self.assert_image_matches_golden(self.render(preview), os.path.join(GOLDEN_DIR, f'stroke_{name}.png'))


class EraserPreviewTest(IntraPaintTestCase):
    """Tests the Eraser tool's preview."""

    def make_preview(self) -> EraseStrokePreview:
        """Returns a visible preview of the Eraser's settings."""
        preview = EraseStrokePreview(Cache.ERASER_TOOL_SIZE, Cache.ERASER_TOOL_OPACITY, Cache.ERASER_TOOL_HARDNESS,
                                     Cache.ERASER_TOOL_ANTIALIAS)
        preview.setFixedSize(PREVIEW_SIZE)
        preview.show()
        preview.render_now()
        return preview

    def test_stroke_shows_the_checkerboard_through_the_backdrop(self) -> None:
        """Pixels under the stroke differ from the backdrop-filled pixels beside it."""
        Cache().set(Cache.ERASER_TOOL_SIZE, 20)
        Cache().set(Cache.ERASER_TOOL_HARDNESS, 1.0)
        Cache().set(Cache.ERASER_TOOL_OPACITY, 1.0)
        image = self.make_preview().grab().toImage()
        backdrop = image.pixelColor(1, 1)
        stroke_start = image.pixelColor(PREVIEW_SIZE.width() // 2, PREVIEW_SIZE.height() // 2)
        self.assertNotEqual(backdrop, stroke_start)
        colors = {image.pixelColor(x, PREVIEW_SIZE.height() // 2).name() for x in range(20, 180)}
        self.assertGreater(len(colors), 1)

    def test_golden_images(self) -> None:
        """The render matches golden images for hard, soft and faint erasers."""
        cases = {
            'hard': (20, 1.0, 1.0),
            'soft': (30, 0.3, 1.0),
            'faint': (30, 1.0, 0.4),
        }
        for name, (size, hardness, opacity) in cases.items():
            with self.subTest(name):
                Cache().set(Cache.ERASER_TOOL_SIZE, size)
                Cache().set(Cache.ERASER_TOOL_HARDNESS, hardness)
                Cache().set(Cache.ERASER_TOOL_OPACITY, opacity)
                Cache().set(Cache.ERASER_TOOL_ANTIALIAS, True)
                preview = self.make_preview()
                self.assert_image_matches_golden(preview.grab().toImage(),
                                                 os.path.join(GOLDEN_DIR, f'erase_{name}.png'))


class SmudgePreviewTest(IntraPaintTestCase):
    """Tests the Smudge tool's preview."""

    def make_preview(self) -> SmudgeStrokePreview:
        """Returns a visible preview of the Smudge tool's settings."""
        preview = SmudgeStrokePreview(Cache.SMUDGE_TOOL_BRUSH_SIZE, Cache.SMUDGE_TOOL_OPACITY,
                                      Cache.SMUDGE_TOOL_HARDNESS, Cache.SMUDGE_TOOL_ANTIALIAS)
        preview.setFixedSize(PREVIEW_SIZE)
        preview.show()
        preview.render_now()
        return preview

    def test_stroke_changes_the_backdrop(self) -> None:
        """The rendered stroke differs from the unsmudged backdrop."""
        Cache().set(Cache.SMUDGE_TOOL_BRUSH_SIZE, 20)
        Cache().set(Cache.SMUDGE_TOOL_HARDNESS, 1.0)
        Cache().set(Cache.SMUDGE_TOOL_OPACITY, 1.0)
        image = self.make_preview().grab().toImage()
        self.assertNotEqual(image, backdrop_image(PREVIEW_SIZE))

    def test_golden_images(self) -> None:
        """The render matches golden images for hard, soft and faint smudges."""
        cases = {
            'hard': (20, 1.0, 1.0),
            'soft': (30, 0.3, 1.0),
            'faint': (30, 1.0, 0.4),
        }
        for name, (size, hardness, opacity) in cases.items():
            with self.subTest(name):
                Cache().set(Cache.SMUDGE_TOOL_BRUSH_SIZE, size)
                Cache().set(Cache.SMUDGE_TOOL_HARDNESS, hardness)
                Cache().set(Cache.SMUDGE_TOOL_OPACITY, opacity)
                Cache().set(Cache.SMUDGE_TOOL_ANTIALIAS, True)
                preview = self.make_preview()
                self.assert_image_matches_golden(preview.grab().toImage(),
                                                 os.path.join(GOLDEN_DIR, f'smudge_{name}.png'))
