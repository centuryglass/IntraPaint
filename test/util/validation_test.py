"""Test the validation helpers and debug string formatters in validation."""
from PySide6.QtCore import QRect, QRectF, QSize, QSizeF, QMargins, QMarginsF, Qt
from PySide6.QtGui import QRegion

from src.util.validation import assert_types, assert_valid_index, alignment_str, rect_str, region_str, size_str, \
    margins_str, orientation_str
from test.base_test_case import IntraPaintTestCase


class TestValidation(IntraPaintTestCase):
    """Test the validation helpers and debug string formatters in validation."""

    def test_assert_types(self) -> None:
        """Every value must match the type or tuple of types, and an empty collection always passes."""
        assert_types([], str)
        assert_types([1, 2, 3], int)
        assert_types([1, 2.0], (int, float))
        with self.assertRaises(TypeError):
            assert_types([1, '2'], int)
        with self.assertRaises(TypeError):
            assert_types([1.0], int)

    def test_assert_valid_index(self) -> None:
        """Indices from 0 to len - 1 pass, and allow_end also accepts len."""
        values = [1, 2, 3]
        for index in range(3):
            assert_valid_index(index, values)
        assert_valid_index(3, values, allow_end=True)
        assert_valid_index(0, [], allow_end=True)
        for index, allow_end in ((3, False), (-1, False), (4, True), (-1, True)):
            with self.assertRaises(ValueError, msg=f'{index}, allow_end={allow_end}'):
                assert_valid_index(index, values, allow_end)
        with self.assertRaises(ValueError):
            assert_valid_index(0, [])

    def test_assert_valid_index_error_names_accepted_range(self) -> None:
        """The error message's upper bound includes the end position when allow_end is set."""
        with self.assertRaisesRegex(ValueError, r'index < 4\)'):
            assert_valid_index(5, [1, 2, 3], allow_end=True)
        with self.assertRaisesRegex(ValueError, r'index < 3\)'):
            assert_valid_index(5, [1, 2, 3])

    def test_assert_valid_index_rejects_non_int_and_non_list(self) -> None:
        """A non-int index or a non-list container fails its assertion."""
        with self.assertRaises(AssertionError):
            assert_valid_index(1.0, [1, 2])
        with self.assertRaises(AssertionError):
            assert_valid_index(0, (1, 2))

    def test_alignment_str(self) -> None:
        """Each set flag is listed by name, AlignCenter also lists both centering axes, and no flags is 'None'."""
        self.assertEqual(alignment_str(Qt.AlignmentFlag.AlignLeft), 'left')
        self.assertEqual(alignment_str(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight), 'top | right')
        self.assertEqual(alignment_str(Qt.AlignmentFlag.AlignHCenter), 'center-horizontal')
        self.assertEqual(alignment_str(Qt.AlignmentFlag.AlignCenter),
                         'center | center-vertical | center-horizontal')
        self.assertEqual(alignment_str(Qt.AlignmentFlag(0)), 'None')

    def test_geometry_strings(self) -> None:
        """Rects, sizes and margins format their fields, and None formats as 'None'."""
        self.assertEqual(rect_str(QRect(1, 2, 30, 40)), '30x40 at (1, 2)')
        self.assertEqual(rect_str(QRectF(0.5, 1.0, 2.5, 3.0)), '2.5x3.0 at (0.5, 1.0)')
        self.assertEqual(size_str(QSize(5, 6)), '5x6')
        self.assertEqual(size_str(QSizeF(5.5, 6.0)), '5.5x6.0')
        self.assertEqual(margins_str(QMargins(1, 2, 3, 4)), 'left: 1, right: 3, top: 2, bottom: 4')
        self.assertEqual(margins_str(QMarginsF(1.0, 2.0, 3.0, 4.0)), 'left: 1.0, right: 3.0, top: 2.0, bottom: 4.0')
        for formatter in (rect_str, size_str, margins_str, region_str, orientation_str):
            self.assertEqual(formatter(None), 'None', formatter.__name__)

    def test_geometry_strings_fall_back_to_str(self) -> None:
        """A value of the wrong type formats with str()."""
        for formatter in (rect_str, size_str, margins_str, region_str, orientation_str):
            self.assertEqual(formatter(42), '42', formatter.__name__)

    def test_region_str(self) -> None:
        """Regions list up to two rects, and only count three or more."""
        two_rects = QRegion(QRect(0, 0, 2, 2)).united(QRect(10, 0, 2, 2))
        self.assertEqual(region_str(two_rects), '12x2 at (0, 0): 2x2 at (0, 0), 2x2 at (10, 0)')
        three_rects = two_rects.united(QRect(20, 0, 2, 2))
        self.assertEqual(region_str(three_rects), '22x2 at (0, 0): 3 regions')

    def test_orientation_str(self) -> None:
        """Orientations format as lowercase words."""
        self.assertEqual(orientation_str(Qt.Orientation.Horizontal), 'horizontal')
        self.assertEqual(orientation_str(Qt.Orientation.Vertical), 'vertical')
