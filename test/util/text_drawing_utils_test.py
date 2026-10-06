"""Test text measurement, fitting and path placement in text_drawing_utils.

Glyph metrics depend on the fonts installed, so these tests compare measurements with each other, never with fixed
pixel sizes.
"""
from PySide6.QtCore import QRect, QRectF, QSize, QMargins, Qt
from PySide6.QtGui import QFont, QKeySequence

from src.util.visual.text_drawing_utils import find_text_size, max_font_size, MAX_FONT_PT, create_text_path, \
    get_key_display_string, left_button_hint_text, ICON_LMB
from test.base_test_case import IntraPaintTestCase


def _font(point_size: int = 12) -> QFont:
    font = QFont()
    font.setPointSize(point_size)
    return font


def _fits(size: QSize, bounds: QSize) -> bool:
    return size.width() < bounds.width() and size.height() < bounds.height()


class TestTextDrawingUtils(IntraPaintTestCase):
    """Test text measurement, fitting and path placement in text_drawing_utils."""

    def test_multiline_size_stacks_lines(self) -> None:
        """Multi-line text is as wide as its widest line and as tall as all lines combined."""
        font = _font()
        short_line = find_text_size('ab', font)
        long_line = find_text_size('abcdef', font)
        both = find_text_size('ab\nabcdef', font)
        self.assertEqual(both, QSize(long_line.width(), short_line.height() + long_line.height()))

    def test_single_line_size_matches_multiline_mode(self) -> None:
        """Text without line breaks measures the same with or without multiline."""
        font = _font()
        self.assertEqual(find_text_size('abc', font), find_text_size('abc', font, multiline=False))

    def test_empty_lines_keep_their_height(self) -> None:
        """An empty line is measured as a space, so it still adds a line's height."""
        font = _font()
        self.assertEqual(find_text_size('ab\n\nab', font).height(),
                         find_text_size('ab\n \nab', font).height())
        self.assertGreater(find_text_size('ab\n\nab', font).height(), find_text_size('ab\nab', font).height())

    def test_vertical_size_is_transposed(self) -> None:
        """Vertical orientation swaps the measured width and height."""
        font = _font()
        self.assertEqual(find_text_size('ab\nabcdef', font, orientation=Qt.Orientation.Vertical),
                         find_text_size('ab\nabcdef', font).transposed())

    def test_size_grows_with_font(self) -> None:
        """A larger font measures larger in both dimensions."""
        small = find_text_size('Text', _font(10))
        large = find_text_size('Text', _font(20))
        self.assertGreater(large.width(), small.width())
        self.assertGreater(large.height(), small.height())

    def test_max_font_size_is_largest_fitting_size(self) -> None:
        """The returned point size fits strictly inside the bounds, and one point larger doesn't."""
        for text, bounds in (('Hi', QSize(100, 40)), ('Wide text', QSize(60, 200)),
                             ('Hi\nHi\nHi\nHi', QSize(100, 40))):
            point_size = max_font_size(text, _font(), bounds)
            self.assertGreater(point_size, 0, text)
            self.assertTrue(_fits(find_text_size(text, _font(point_size)), bounds), text)
            self.assertFalse(_fits(find_text_size(text, _font(point_size + 1)), bounds), text)

    def test_max_font_size_limits(self) -> None:
        """Empty text, or text that fits at every size, returns MAX_FONT_PT."""
        self.assertEqual(max_font_size('', _font(), QSize(1, 1)), MAX_FONT_PT)
        self.assertEqual(max_font_size('.', _font(), QSize(100000, 100000)), MAX_FONT_PT)

    def test_max_font_size_too_small_bounds(self) -> None:
        """Bounds too small for any size return 0."""
        self.assertEqual(max_font_size('Hi', _font(), QSize(2, 2)), 0)

    def test_blank_text_path_is_empty(self) -> None:
        """Empty and whitespace-only text produce an empty path."""
        for text in ('', '   ', '\n'):
            self.assertTrue(create_text_path(text, _font()).isEmpty(), repr(text))

    def test_text_path_alignment_in_bounds(self) -> None:
        """Paths are placed inside the bounds according to the alignment."""
        bounds = QRect(10, 20, 200, 100)
        bounds_center = QRectF(bounds).center()
        unplaced = create_text_path('Hi', _font()).boundingRect()

        centered = create_text_path('Hi', _font(), bounds).boundingRect()
        self.assertAlmostEqual(centered.center().x(), bounds_center.x(), delta=1)
        self.assertAlmostEqual(centered.center().y(), bounds_center.y(), delta=1)
        self.assertAlmostEqual(centered.width(), unplaced.width(), delta=0.01)

        top_left = create_text_path('Hi', _font(), bounds,
                                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop).boundingRect()
        self.assertAlmostEqual(top_left.left(), bounds.left(), delta=1)
        self.assertAlmostEqual(top_left.top(), bounds.top(), delta=1)

        bottom_right = create_text_path('Hi', _font(), bounds,
                                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom).boundingRect()
        self.assertAlmostEqual(bottom_right.right(), bounds.x() + bounds.width(), delta=1)
        self.assertAlmostEqual(bottom_right.bottom(), bounds.y() + bounds.height(), delta=1)

    def test_text_path_margins_without_bounds(self) -> None:
        """With margins and no bounds, the path is offset by the top-left margin."""
        unplaced = create_text_path('Hi', _font()).boundingRect()
        with_margins = create_text_path('Hi', _font(), margins=QMargins(5, 7, 5, 7)).boundingRect()
        self.assertAlmostEqual(with_margins.left() - unplaced.left(), 5, delta=1)
        self.assertAlmostEqual(with_margins.top() - unplaced.top(), 7, delta=1)

    def test_vertical_text_path_is_rotated(self) -> None:
        """Vertical text is rotated a quarter turn and stays centered in the bounds."""
        bounds = QRect(0, 0, 100, 50)
        horizontal = create_text_path('Hi', _font(), bounds).boundingRect()
        vertical = create_text_path('Hi', _font(), bounds, orientation=Qt.Orientation.Vertical).boundingRect()
        self.assertAlmostEqual(vertical.width(), horizontal.height(), delta=0.01)
        self.assertAlmostEqual(vertical.height(), horizontal.width(), delta=0.01)
        self.assertAlmostEqual(vertical.center().x(), QRectF(bounds).center().x(), delta=1)
        self.assertAlmostEqual(vertical.center().y(), QRectF(bounds).center().y(), delta=1)

    def test_key_display_string_symbols(self) -> None:
        """Modifier and navigation key names become symbols, from strings, key codes and key sequences."""
        self.assertEqual(get_key_display_string('Ctrl+Shift+PgDown', rich_text=False), '⌃⇧⇟')
        self.assertEqual(get_key_display_string('Alt+Meta+Enter', rich_text=False), '⎇⌘⏎')
        self.assertEqual(get_key_display_string(Qt.Key.Key_Delete, rich_text=False), '⌫')
        self.assertEqual(get_key_display_string(QKeySequence('Ctrl+Up'), rich_text=False), '⌃↑')
        self.assertEqual(get_key_display_string('A', rich_text=False), 'A')

    def test_mouse_hint_text(self) -> None:
        """Mouse hints are rich-text images of the matching icon."""
        self.assertEqual(left_button_hint_text(), f'<img src="{ICON_LMB}"/>')
