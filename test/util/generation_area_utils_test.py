"""Tests for the generation area frame, resolution rule, follow-selection and handle resizing helpers."""
from PySide6.QtCore import QSize, QRect, QPoint, QPointF

from src.util.generation_area_utils import resolution_for_area, RESOLUTION_RULE_MATCH_AREA, \
    RESOLUTION_RULE_MATCH_AREA_UPSCALED, RESOLUTION_RULE_MANUAL, full_image_frame, square_frame, parse_size, \
    updated_recent_sizes, recent_frames, previous_frame, MAX_RECENT_SIZES, MAX_PARSED_SIDE, follow_selection_target, \
    follow_selection_position, FOLLOW_SELECTION_MINIMAL, FOLLOW_SELECTION_CENTER, FOLLOW_SELECTION_OFF, \
    area_handle_positions, resize_area_from_handle, HANDLE_TOP_LEFT, HANDLE_TOP, HANDLE_TOP_RIGHT, HANDLE_RIGHT, \
    HANDLE_BOTTOM_RIGHT, HANDLE_BOTTOM, HANDLE_BOTTOM_LEFT, HANDLE_LEFT
from test.base_test_case import IntraPaintTestCase

MAX_GEN_SIZE = QSize(2048, 2048)
MAX_AREA_SIZE = QSize(10240, 10240)
IMAGE_SIZE = QSize(1024, 768)


class ResolutionForAreaTest(IntraPaintTestCase):
    """Tests resolution_for_area under each rule."""

    def test_manual_returns_none(self) -> None:
        """The manual rule never picks a resolution."""
        self.assertIsNone(resolution_for_area(QSize(300, 200), RESOLUTION_RULE_MANUAL, 512, MAX_GEN_SIZE))

    def test_match_area_returns_area_size(self) -> None:
        """Match area returns the area size, even when it's small or above the maximum."""
        for size in (QSize(300, 200), QSize(768, 768), QSize(4000, 3000)):
            self.assertEqual(resolution_for_area(size, RESOLUTION_RULE_MATCH_AREA, 512, MAX_GEN_SIZE), size)

    def test_upscaled_leaves_large_areas_alone(self) -> None:
        """Areas with a short side of at least min_side keep their size."""
        for size in (QSize(512, 512), QSize(1024, 768), QSize(4000, 3000)):
            self.assertEqual(resolution_for_area(size, RESOLUTION_RULE_MATCH_AREA_UPSCALED, 512, MAX_GEN_SIZE), size)

    def test_upscaled_uses_smallest_whole_factor(self) -> None:
        """Small areas scale by the smallest whole number that brings the short side to min_side."""
        self.assertEqual(resolution_for_area(QSize(256, 256), RESOLUTION_RULE_MATCH_AREA_UPSCALED, 512, MAX_GEN_SIZE),
                         QSize(512, 512))
        self.assertEqual(resolution_for_area(QSize(300, 200), RESOLUTION_RULE_MATCH_AREA_UPSCALED, 512, MAX_GEN_SIZE),
                         QSize(900, 600))
        self.assertEqual(resolution_for_area(QSize(511, 600), RESOLUTION_RULE_MATCH_AREA_UPSCALED, 512, MAX_GEN_SIZE),
                         QSize(1022, 1200))

    def test_upscaled_factor_capped_by_max_size(self) -> None:
        """The factor drops until the result fits the maximum size, but never below one."""
        # Factor 6 would reach 512 on the short side, but 6 * 400 > 2048; 5 * 400 = 2000 fits.
        self.assertEqual(resolution_for_area(QSize(400, 100), RESOLUTION_RULE_MATCH_AREA_UPSCALED, 512, MAX_GEN_SIZE),
                         QSize(2000, 500))
        self.assertEqual(resolution_for_area(QSize(3000, 100), RESOLUTION_RULE_MATCH_AREA_UPSCALED, 512, MAX_GEN_SIZE),
                         QSize(3000, 100))

    def test_unknown_rule_raises(self) -> None:
        """An unrecognized rule string is an error."""
        with self.assertRaises(ValueError):
            resolution_for_area(QSize(300, 200), 'not a rule', 512, MAX_GEN_SIZE)


class FrameHelperTest(IntraPaintTestCase):
    """Tests frame sizes, size parsing and the recent size list."""

    def test_dynamic_frames(self) -> None:
        """Full image and square frames follow the image size and the maximum area size."""
        self.assertEqual(full_image_frame(IMAGE_SIZE, MAX_AREA_SIZE), QSize(1024, 768))
        self.assertEqual(square_frame(IMAGE_SIZE, MAX_AREA_SIZE), QSize(768, 768))
        self.assertEqual(full_image_frame(IMAGE_SIZE, QSize(800, 800)), QSize(800, 768))
        self.assertEqual(square_frame(IMAGE_SIZE, QSize(600, 800)), QSize(600, 600))

    def test_parse_size(self) -> None:
        """Typed sizes accept a single number or WxH, and reject anything else."""
        self.assertEqual(parse_size('768'), QSize(768, 768))
        self.assertEqual(parse_size('640x480'), QSize(640, 480))
        self.assertEqual(parse_size(' 640 X 480 '), QSize(640, 480))
        self.assertEqual(parse_size('640*480'), QSize(640, 480))
        self.assertEqual(parse_size('99999999999999999x480'), QSize(MAX_PARSED_SIDE, 480))
        for invalid in ('', 'x', '0', '640x0', '-5', '640x480x2', 'abc', '1.5'):
            self.assertIsNone(parse_size(invalid), invalid)

    def test_updated_recent_sizes(self) -> None:
        """New sizes go to the front, repeats move to the front, and the list is trimmed."""
        recent = updated_recent_sizes([], QSize(768, 768))
        self.assertEqual(recent, ['768x768'])
        recent = updated_recent_sizes(recent, QSize(1024, 768))
        self.assertEqual(recent, ['1024x768', '768x768'])
        recent = updated_recent_sizes(recent, QSize(768, 768))
        self.assertEqual(recent, ['768x768', '1024x768'])
        for i in range(MAX_RECENT_SIZES + 2):
            recent = updated_recent_sizes(recent, QSize(100 + i, 100))
        self.assertEqual(len(recent), MAX_RECENT_SIZES)
        self.assertEqual(recent[0], f'{100 + MAX_RECENT_SIZES + 1}x100')

    def test_updated_recent_sizes_drops_invalid_entries(self) -> None:
        """Entries that don't parse are removed when the list is updated."""
        self.assertEqual(updated_recent_sizes(['bad', '512x512'], QSize(256, 256)), ['256x256', '512x512'])

    def test_recent_frames_filters(self) -> None:
        """Recent frames skip the full image and square sizes, sizes too big for the image, and stop at count."""
        recent = ['1024x768', '640x480', '768x768', '2048x2048', '512x512', '256x256', '300x200', '400x400']
        self.assertEqual(recent_frames(recent, IMAGE_SIZE, MAX_AREA_SIZE, 4),
                         [QSize(640, 480), QSize(512, 512), QSize(256, 256), QSize(300, 200)])

    def test_previous_frame(self) -> None:
        """The previous frame is the newest recent size that differs from the current one."""
        recent = ['768x768', '1024x768']
        self.assertEqual(previous_frame(recent, QSize(768, 768)), QSize(1024, 768))
        self.assertEqual(previous_frame(recent, QSize(512, 512)), QSize(768, 768))
        self.assertIsNone(previous_frame(['768x768'], QSize(768, 768)))
        self.assertIsNone(previous_frame([], QSize(768, 768)))


IMAGE_BOUNDS = QRect(QPoint(), IMAGE_SIZE)
FOLLOW_AREA = QRect(100, 100, 200, 200)


class FollowSelectionTargetTest(IntraPaintTestCase):
    """Tests follow_selection_target."""

    def test_no_selection_returns_none(self) -> None:
        """Without a selection there's nothing to follow, even with pins."""
        self.assertIsNone(follow_selection_target(None, [QPoint(5, 5)], 10))
        self.assertIsNone(follow_selection_target(QRect(), [QPoint(5, 5)], 10))

    def test_pins_and_padding_extend_selection(self) -> None:
        """Pins stretch the selection bounds to include their pixel, then padding grows every side."""
        target = follow_selection_target(QRect(50, 50, 10, 10), [QPoint(80, 55), QPoint(55, 40)], 5)
        self.assertEqual(target, QRect(QPoint(45, 35), QPoint(85, 64)))

    def test_target_is_not_clamped(self) -> None:
        """Padding can take the target past the image edge."""
        self.assertEqual(follow_selection_target(QRect(0, 0, 10, 10), [], 4), QRect(-4, -4, 18, 18))


class FollowSelectionPositionTest(IntraPaintTestCase):
    """Tests follow_selection_position in each mode."""

    def test_off_keeps_position(self) -> None:
        """The off mode never moves the area."""
        position = follow_selection_position(FOLLOW_AREA, QRect(600, 500, 20, 20), FOLLOW_SELECTION_OFF, IMAGE_BOUNDS)
        self.assertEqual(position, FOLLOW_AREA.topLeft())

    def test_minimal_keeps_contained_target(self) -> None:
        """A target already inside the area doesn't move it."""
        position = follow_selection_position(FOLLOW_AREA, QRect(150, 150, 20, 20), FOLLOW_SELECTION_MINIMAL,
                                             IMAGE_BOUNDS)
        self.assertEqual(position, FOLLOW_AREA.topLeft())

    def test_minimal_moves_only_as_far_as_needed(self) -> None:
        """The area moves until the target touches its edge, on each axis separately."""
        position = follow_selection_position(FOLLOW_AREA, QRect(350, 50, 20, 20), FOLLOW_SELECTION_MINIMAL,
                                             IMAGE_BOUNDS)
        self.assertEqual(position, QPoint(170, 50))
        position = follow_selection_position(FOLLOW_AREA, QRect(60, 200, 20, 20), FOLLOW_SELECTION_MINIMAL,
                                             IMAGE_BOUNDS)
        self.assertEqual(position, QPoint(60, 100))

    def test_center_centers_on_target(self) -> None:
        """The center mode centers the area on the target, even when the target is already inside."""
        position = follow_selection_position(FOLLOW_AREA, QRect(150, 150, 20, 20), FOLLOW_SELECTION_CENTER,
                                             IMAGE_BOUNDS)
        self.assertEqual(position, QPoint(60, 60))

    def test_larger_target_centers_along_that_axis(self) -> None:
        """Along an axis where the target is at least as long as the area, both modes center on it."""
        target = QRect(300, 150, 400, 20)
        for mode in (FOLLOW_SELECTION_MINIMAL, FOLLOW_SELECTION_CENTER):
            position = follow_selection_position(FOLLOW_AREA, target, mode, IMAGE_BOUNDS)
            self.assertEqual(position.x(), 400, mode)
        self.assertEqual(follow_selection_position(FOLLOW_AREA, target, FOLLOW_SELECTION_MINIMAL, IMAGE_BOUNDS).y(),
                         100)

    def test_result_stays_in_image(self) -> None:
        """Targets at or past the image edges leave the area inside the image."""
        for mode in (FOLLOW_SELECTION_MINIMAL, FOLLOW_SELECTION_CENTER):
            self.assertEqual(follow_selection_position(FOLLOW_AREA, QRect(-10, -10, 30, 30), mode, IMAGE_BOUNDS),
                             QPoint(0, 0), mode)
            self.assertEqual(follow_selection_position(FOLLOW_AREA, QRect(1000, 750, 40, 40), mode, IMAGE_BOUNDS),
                             QPoint(824, 568), mode)

    def test_unknown_mode_raises(self) -> None:
        """An unrecognized mode is an error, not a silent no-op."""
        with self.assertRaises(ValueError):
            follow_selection_position(FOLLOW_AREA, QRect(0, 0, 10, 10), 'Sideways', IMAGE_BOUNDS)


RESIZE_AREA = QRect(200, 100, 400, 200)
RESIZE_IMAGE_BOUNDS = QRect(QPoint(), IMAGE_SIZE)
RESIZE_MIN_SIZE = QSize(8, 8)


def _resize(handle: str, point: QPoint, keep_aspect: bool = False, max_size: QSize = MAX_AREA_SIZE) -> QRect:
    return resize_area_from_handle(RESIZE_AREA, handle, point, keep_aspect, RESIZE_IMAGE_BOUNDS, RESIZE_MIN_SIZE,
                                   max_size)


class AreaHandlePositionsTest(IntraPaintTestCase):
    """Tests area_handle_positions."""

    def test_handles_sit_on_the_outline(self) -> None:
        """Corners sit on the area's outer corners, and edge handles on the middle of each side."""
        positions = area_handle_positions(RESIZE_AREA)
        self.assertEqual(positions[HANDLE_TOP_LEFT], QPointF(200, 100))
        self.assertEqual(positions[HANDLE_TOP], QPointF(400, 100))
        self.assertEqual(positions[HANDLE_TOP_RIGHT], QPointF(600, 100))
        self.assertEqual(positions[HANDLE_RIGHT], QPointF(600, 200))
        self.assertEqual(positions[HANDLE_BOTTOM_RIGHT], QPointF(600, 300))
        self.assertEqual(positions[HANDLE_BOTTOM], QPointF(400, 300))
        self.assertEqual(positions[HANDLE_BOTTOM_LEFT], QPointF(200, 300))
        self.assertEqual(positions[HANDLE_LEFT], QPointF(200, 200))


class ResizeAreaFromHandleTest(IntraPaintTestCase):
    """Tests resize_area_from_handle."""

    def test_edge_handles_move_one_side(self) -> None:
        """Each edge handle moves only its own side, ignoring the other axis and keep_aspect."""
        self.assertEqual(_resize(HANDLE_RIGHT, QPoint(700, 999), True), QRect(200, 100, 500, 200))
        self.assertEqual(_resize(HANDLE_LEFT, QPoint(250, 0)), QRect(250, 100, 350, 200))
        self.assertEqual(_resize(HANDLE_TOP, QPoint(0, 50)), QRect(200, 50, 400, 250))
        self.assertEqual(_resize(HANDLE_BOTTOM, QPoint(0, 250)), QRect(200, 100, 400, 150))

    def test_free_corner_follows_point(self) -> None:
        """Without keep_aspect, a corner handle moves both of its sides to the point."""
        self.assertEqual(_resize(HANDLE_BOTTOM_RIGHT, QPoint(700, 500)), QRect(200, 100, 500, 400))
        self.assertEqual(_resize(HANDLE_TOP_LEFT, QPoint(100, 50)), QRect(100, 50, 500, 250))

    def test_corner_keeps_aspect(self) -> None:
        """With keep_aspect, a corner handle keeps the starting aspect ratio and the opposite corner fixed."""
        self.assertEqual(_resize(HANDLE_BOTTOM_RIGHT, QPoint(1000, 500), True), QRect(200, 100, 800, 400))
        self.assertEqual(_resize(HANDLE_TOP_LEFT, QPoint(400, 200), True), QRect(400, 200, 200, 100))
        self.assertEqual(_resize(HANDLE_BOTTOM_LEFT, QPoint(0, 400), True), QRect(0, 100, 600, 300))
        self.assertEqual(_resize(HANDLE_TOP_RIGHT, QPoint(800, 0), True), QRect(200, 0, 600, 300))

    def test_stays_in_image(self) -> None:
        """Moved sides stop at the image edges, and an aspect-locked corner stops where either side would leave."""
        self.assertEqual(_resize(HANDLE_BOTTOM_RIGHT, QPoint(5000, 5000)), QRect(200, 100, 824, 668))
        self.assertEqual(_resize(HANDLE_TOP_LEFT, QPoint(-500, -500)), QRect(0, 0, 600, 300))
        self.assertEqual(_resize(HANDLE_BOTTOM_RIGHT, QPoint(5000, 5000), True), QRect(200, 100, 824, 412))

    def test_size_limits(self) -> None:
        """The size stays between the minimum and maximum, and dragging past the fixed side stops at the minimum."""
        self.assertEqual(_resize(HANDLE_RIGHT, QPoint(0, 0)), QRect(200, 100, 8, 200))
        self.assertEqual(_resize(HANDLE_TOP, QPoint(0, 900)), QRect(200, 292, 400, 8))
        self.assertEqual(_resize(HANDLE_BOTTOM_RIGHT, QPoint(900, 700), max_size=QSize(500, 300)),
                         QRect(200, 100, 500, 300))
        self.assertEqual(_resize(HANDLE_BOTTOM_RIGHT, QPoint(900, 700), True, QSize(500, 500)),
                         QRect(200, 100, 500, 250))
        self.assertEqual(_resize(HANDLE_BOTTOM_RIGHT, QPoint(0, 0), True), QRect(200, 100, 16, 8))

    def test_unknown_handle_raises(self) -> None:
        """An unrecognized handle id is an error."""
        with self.assertRaises(ValueError):
            _resize('middle', QPoint(0, 0))
