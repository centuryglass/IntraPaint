"""Tests for the generation area frame and resolution rule helpers."""
from PySide6.QtCore import QSize

from src.util.generation_area_utils import resolution_for_area, RESOLUTION_RULE_MATCH_AREA, \
    RESOLUTION_RULE_MATCH_AREA_UPSCALED, RESOLUTION_RULE_MANUAL, full_image_frame, square_frame, parse_size, \
    updated_recent_sizes, recent_frames, previous_frame, MAX_RECENT_SIZES, MAX_PARSED_SIDE
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
