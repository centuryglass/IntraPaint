"""Tests for GenerationAreaController and the frame functions beside it."""
import sys
from unittest.mock import patch

from PySide6.QtCore import QSize, QRect, QPoint, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.generation_area_controller import GenerationAreaController, apply_generation_area_frame, \
    record_generation_area_size
from src.image.layers.image_stack import ImageStack
from src.undo_stack import UndoStack
from src.util.generation_area_utils import RESOLUTION_RULE_MATCH_AREA, RESOLUTION_RULE_MATCH_AREA_UPSCALED, \
    RESOLUTION_RULE_MANUAL, FOLLOW_SELECTION_MINIMAL, FOLLOW_SELECTION_CENTER, FOLLOW_SELECTION_OFF
from src.util.shared_constants import EDIT_MODE_INPAINT, EDIT_MODE_TXT2IMG
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


FOLLOW_AREA = QRect(100, 100, 200, 200)


class FollowSelectionTest(IntraPaintTestCase):
    """Tests moving the generation area to follow selection edits."""

    def setUp(self) -> None:
        super().setUp()
        config = AppConfig()
        config.restore_default_options(AppConfig.GENERATION_AREA_FOLLOW_SELECTION)
        config.set(AppConfig.GENERATION_AREA_FOLLOW_SELECTION, FOLLOW_SELECTION_MINIMAL)
        cache = Cache()
        cache.restore_default_options(Cache.EDIT_MODE)
        cache.set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
        cache.set(Cache.INPAINT_FULL_RES, True)
        cache.set(Cache.INPAINT_FULL_RES_PADDING, 0)
        self.image_stack = ImageStack(IMAGE_SIZE, FOLLOW_AREA.size(), QSize(8, 8), QSize(10240, 10240))
        self.image_stack.generation_area = FOLLOW_AREA
        self.selection_layer = self.image_stack.selection_layer
        self.controller = GenerationAreaController(self.image_stack)
        self.controller.generation_area_visible = True
        self.controller.follow_selection()
        UndoStack().clear()

    def _select(self, bounds: QRect) -> None:
        with self.selection_layer.borrow_image() as mask_image:
            painter = QPainter(mask_image)
            painter.fillRect(bounds, Qt.GlobalColor.black)
            painter.end()

    def _settle(self) -> None:
        """Runs the pending follow the way its timer would, without waiting on the event loop.

        A follow move changes the area, which schedules one more check, and that check must leave the area alone.
        """
        self.assertTrue(self.controller.follow_pending)
        self.controller.follow_selection()
        if self.controller.follow_pending:
            area = self.image_stack.generation_area
            self.controller.follow_selection()
            self.assertEqual(self.image_stack.generation_area, area)
        self.assertFalse(self.controller.follow_pending)

    def test_selection_edit_moves_area_minimally(self) -> None:
        """Once a selection edit settles, the area moves just far enough to contain it."""
        self._select(QRect(400, 150, 20, 20))
        self.assertEqual(self.image_stack.generation_area, FOLLOW_AREA)
        self._settle()
        self.assertEqual(self.image_stack.generation_area, QRect(220, 100, 200, 200))

    def test_center_mode_and_padding(self) -> None:
        """The center mode centers on the selection plus padding, and padding counts in the minimal mode."""
        Cache().set(Cache.INPAINT_FULL_RES_PADDING, 10)
        self._select(QRect(400, 150, 20, 20))
        self._settle()
        self.assertEqual(self.image_stack.generation_area, QRect(230, 100, 200, 200))
        AppConfig().set(AppConfig.GENERATION_AREA_FOLLOW_SELECTION, FOLLOW_SELECTION_CENTER)
        self._select(QRect(500, 200, 10, 20))
        self._settle()
        self.assertEqual(self.image_stack.generation_area, QRect(355, 85, 200, 200))

    def test_padding_ignored_without_full_res(self) -> None:
        """Padding only extends the target while Inpaint Full Resolution is on."""
        cache = Cache()
        cache.set(Cache.INPAINT_FULL_RES_PADDING, 10)
        cache.set(Cache.INPAINT_FULL_RES, False)
        self._select(QRect(400, 150, 20, 20))
        self._settle()
        self.assertEqual(self.image_stack.generation_area, QRect(220, 100, 200, 200))

    def test_frame_keeps_selection_inside(self) -> None:
        """Applying a frame places the new area over the selection, using the follow-selection placement rule."""
        self._select(QRect(900, 700, 20, 20))
        self._settle()
        self.assertEqual(self.image_stack.generation_area, QRect(720, 520, 200, 200))
        apply_generation_area_frame(self.image_stack, QSize(128, 128))
        self.assertEqual(self.image_stack.generation_area, QRect(792, 592, 128, 128))
        self.assertTrue(self.image_stack.generation_area.contains(QRect(900, 700, 20, 20)))

    def test_frame_without_selection_or_follow_centers(self) -> None:
        """Without a selection, or with follow-selection off, applying a frame resizes around the area's center."""
        apply_generation_area_frame(self.image_stack, QSize(128, 128))
        self.assertEqual(self.image_stack.generation_area, QRect(136, 136, 128, 128))
        AppConfig().set(AppConfig.GENERATION_AREA_FOLLOW_SELECTION, FOLLOW_SELECTION_OFF)
        self._select(QRect(900, 700, 20, 20))
        apply_generation_area_frame(self.image_stack, QSize(256, 256))
        self.assertEqual(self.image_stack.generation_area, QRect(72, 72, 256, 256))

    def test_frame_keeps_selection_inside_with_padding(self) -> None:
        """Applied frames count the full resolution padding, like follow_selection does."""
        Cache().set(Cache.INPAINT_FULL_RES_PADDING, 10)
        self._select(QRect(900, 700, 20, 20))
        self._settle()
        apply_generation_area_frame(self.image_stack, QSize(128, 128))
        self.assertEqual(self.image_stack.generation_area, QRect(802, 602, 128, 128))

    def test_context_pin_moves_area(self) -> None:
        """Pin changes are followed like selection edits, but only alongside a selection."""
        self.selection_layer.add_context_pin(QPoint(500, 120))
        self._settle()
        self.assertEqual(self.image_stack.generation_area, FOLLOW_AREA)
        self.selection_layer.clear_context_pins()
        self._settle()
        self._select(QRect(150, 150, 20, 20))
        self._settle()
        self.assertEqual(self.image_stack.generation_area, FOLLOW_AREA)
        self.selection_layer.add_context_pin(QPoint(320, 120))
        self._settle()
        self.assertEqual(self.image_stack.generation_area, QRect(121, 100, 200, 200))

    def test_follow_move_is_its_own_undo_step(self) -> None:
        """Undo first reverts the follow move, then the selection edit."""
        self._select(QRect(400, 150, 20, 20))
        self._settle()
        UndoStack().undo()
        self.assertEqual(self.image_stack.generation_area, FOLLOW_AREA)
        self.assertEqual(self.selection_layer.get_selection_bounds(), QRect(400, 150, 20, 20))
        UndoStack().undo()
        self.assertIsNone(self.selection_layer.get_selection_bounds())

    def test_undo_and_redo_never_move_area(self) -> None:
        """Selection changes made by undo or redo don't move the area."""
        self._select(QRect(400, 150, 20, 20))
        self._settle()
        UndoStack().undo()
        self._settle()
        UndoStack().undo()
        self._settle()
        self.assertEqual(self.image_stack.generation_area, FOLLOW_AREA)
        UndoStack().redo()
        self._settle()
        self.assertEqual(self.image_stack.generation_area, FOLLOW_AREA)
        self.assertEqual(self.selection_layer.get_selection_bounds(), QRect(400, 150, 20, 20))

    def test_manual_move_is_kept(self) -> None:
        """Moving the area by hand, even after a padding change, doesn't make it follow again."""
        self._select(QRect(400, 150, 20, 20))
        self._settle()
        Cache().set(Cache.INPAINT_FULL_RES_PADDING, 50)
        self.image_stack.generation_area = QRect(600, 400, 200, 200)
        self._settle()
        self.assertEqual(self.image_stack.generation_area, QRect(600, 400, 200, 200))

    def test_inactive_conditions_skip_follow(self) -> None:
        """The area stays put when follow is off, outside inpainting mode or while the area is hidden.

        Edits made then aren't followed later either, when an unrelated area move restarts the follow check.
        """
        def _disable_off() -> None:
            AppConfig().set(AppConfig.GENERATION_AREA_FOLLOW_SELECTION, FOLLOW_SELECTION_OFF)

        def _disable_mode() -> None:
            Cache().set(Cache.EDIT_MODE, EDIT_MODE_TXT2IMG)

        def _disable_hidden() -> None:
            self.controller.generation_area_visible = False

        for selection_x, disable in ((400, _disable_off), (450, _disable_mode), (500, _disable_hidden)):
            disable()
            self._select(QRect(selection_x, 150, 20, 20))
            self._settle()
            self.assertEqual(self.image_stack.generation_area, FOLLOW_AREA, disable.__name__)
            AppConfig().set(AppConfig.GENERATION_AREA_FOLLOW_SELECTION, FOLLOW_SELECTION_MINIMAL)
            Cache().set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
            self.controller.generation_area_visible = True
            self.image_stack.generation_area = FOLLOW_AREA.translated(0, 10)
            self._settle()
            self.assertEqual(self.image_stack.generation_area, FOLLOW_AREA.translated(0, 10), disable.__name__)
            self.image_stack.generation_area = FOLLOW_AREA
            self._settle()

    def test_waits_while_mouse_button_held(self) -> None:
        """A follow that comes due mid-stroke waits for the mouse button's release."""
        self._select(QRect(400, 150, 20, 20))
        with patch('src.controller.generation_area_controller.QApplication.mouseButtons',
                   return_value=Qt.MouseButton.LeftButton):
            self.controller.follow_selection()
        self.assertEqual(self.image_stack.generation_area, FOLLOW_AREA)
        self._settle()
        self.assertEqual(self.image_stack.generation_area, QRect(220, 100, 200, 200))
