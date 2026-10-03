"""Tests for GenerationAreaController and the frame functions beside it."""
import sys

from PySide6.QtCore import QSize, QRect
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.generation_area_controller import GenerationAreaController, apply_generation_area_frame, \
    record_generation_area_size
from src.image.layers.image_stack import ImageStack
from src.undo_stack import UndoStack
from src.util.generation_area_utils import RESOLUTION_RULE_MATCH_AREA, RESOLUTION_RULE_MATCH_AREA_UPSCALED, \
    RESOLUTION_RULE_MANUAL
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

IMAGE_SIZE = QSize(1024, 768)
INITIAL_AREA_SIZE = QSize(512, 512)


class GenerationAreaControllerTest(IntraPaintTestCase):
    """Tests the resolution rule wiring, recent sizes and the previous frame action."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(IMAGE_SIZE, INITIAL_AREA_SIZE, QSize(8, 8), QSize(10240, 10240))
        Cache().restore_default_options(Cache.GENERATION_RESOLUTION_RULE)
        Cache().set(Cache.GENERATION_RESOLUTION_RULE, RESOLUTION_RULE_MATCH_AREA_UPSCALED)
        AppConfig().set(AppConfig.GENERATION_RESOLUTION_MIN_SIDE, 512)
        Cache().set(Cache.GENERATION_SIZE, QSize(640, 640))
        self.controller = GenerationAreaController(self.image_stack)

    def _set_area_size(self, size: QSize) -> None:
        self.image_stack.generation_area = QRect(self.image_stack.generation_area.topLeft(), size)

    def test_rule_applied_on_init(self) -> None:
        """Creating the controller applies the rule to the current area."""
        self.assertEqual(Cache().get(Cache.GENERATION_SIZE), INITIAL_AREA_SIZE)
        self.assertEqual(Cache().get(Cache.GENERATION_RESOLUTION_RULE), RESOLUTION_RULE_MATCH_AREA_UPSCALED)

    def test_upscaled_rule_follows_area_size(self) -> None:
        """Area size changes set the resolution, upscaling small areas."""
        self._set_area_size(QSize(768, 768))
        self.assertEqual(Cache().get(Cache.GENERATION_SIZE), QSize(768, 768))
        self._set_area_size(QSize(300, 200))
        self.assertEqual(Cache().get(Cache.GENERATION_SIZE), QSize(900, 600))

    def test_match_rule_follows_area_size(self) -> None:
        """Switching to match area applies it at once, without upscaling."""
        self._set_area_size(QSize(300, 200))
        Cache().set(Cache.GENERATION_RESOLUTION_RULE, RESOLUTION_RULE_MATCH_AREA)
        self.assertEqual(Cache().get(Cache.GENERATION_SIZE), QSize(300, 200))

    def test_min_side_change_reapplies_rule(self) -> None:
        """Changing the minimum side setting updates the resolution."""
        self._set_area_size(QSize(300, 200))
        AppConfig().set(AppConfig.GENERATION_RESOLUTION_MIN_SIDE, 300)
        self.assertEqual(Cache().get(Cache.GENERATION_SIZE), QSize(600, 400))

    def test_position_change_keeps_resolution(self) -> None:
        """Moving the area without resizing it leaves a manual resolution alone."""
        Cache().set(Cache.GENERATION_SIZE, QSize(640, 640))
        self.image_stack.generation_area = QRect(100, 100, 512, 512)
        self.assertEqual(Cache().get(Cache.GENERATION_SIZE), QSize(640, 640))

    def test_hand_edit_switches_to_manual(self) -> None:
        """A resolution change the rule didn't make selects the manual rule, which then leaves it alone."""
        Cache().set(Cache.GENERATION_SIZE, QSize(640, 480))
        self.assertEqual(Cache().get(Cache.GENERATION_RESOLUTION_RULE), RESOLUTION_RULE_MANUAL)
        self._set_area_size(QSize(768, 768))
        self.assertEqual(Cache().get(Cache.GENERATION_SIZE), QSize(640, 480))

    def test_undo_restores_resolution(self) -> None:
        """Undoing an area size change restores the matching resolution."""
        self._set_area_size(QSize(768, 768))
        UndoStack().undo()
        self.assertEqual(self.image_stack.generation_area.size(), INITIAL_AREA_SIZE)
        self.assertEqual(Cache().get(Cache.GENERATION_SIZE), INITIAL_AREA_SIZE)

    def test_apply_frame_keeps_center_and_records(self) -> None:
        """Applying a frame resizes around the area's center, clamped to the image, and records the size."""
        self.image_stack.generation_area = QRect(256, 128, 512, 512)
        apply_generation_area_frame(self.image_stack, QSize(256, 256))
        self.assertEqual(self.image_stack.generation_area, QRect(384, 256, 256, 256))
        self.assertEqual(Cache().get(Cache.RECENT_GENERATION_AREA_SIZES)[0], '256x256')

        apply_generation_area_frame(self.image_stack, QSize(768, 768))
        self.assertEqual(self.image_stack.generation_area, QRect(128, 0, 768, 768))

        apply_generation_area_frame(self.image_stack, QSize(4000, 4000))
        self.assertEqual(self.image_stack.generation_area, QRect(0, 0, 1024, 768))
        self.assertEqual(Cache().get(Cache.RECENT_GENERATION_AREA_SIZES)[0], '1024x768')

    def test_previous_frame_flips_between_sizes(self) -> None:
        """Selecting the previous frame repeatedly switches between the last two sizes."""
        self.assertFalse(self.controller.select_previous_frame())
        apply_generation_area_frame(self.image_stack, QSize(1024, 768))
        apply_generation_area_frame(self.image_stack, QSize(768, 768))
        self.assertTrue(self.controller.select_previous_frame())
        self.assertEqual(self.image_stack.generation_area.size(), QSize(1024, 768))
        self.assertTrue(self.controller.select_previous_frame())
        self.assertEqual(self.image_stack.generation_area.size(), QSize(768, 768))

    def test_record_size_deduplicates(self) -> None:
        """Recording a size already in the list moves it to the front."""
        record_generation_area_size(QSize(512, 512))
        record_generation_area_size(QSize(768, 768))
        record_generation_area_size(QSize(512, 512))
        self.assertEqual(Cache().get(Cache.RECENT_GENERATION_AREA_SIZES), ['512x512', '768x768'])
