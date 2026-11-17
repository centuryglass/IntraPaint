"""Tests for OptionFilmstrip: thumbnails that overflow the width scroll instead of shrinking."""
import sys

from PySide6.QtCore import QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QWheelEvent
from PySide6.QtWidgets import QApplication

from src.ui.widget.option_filmstrip import OptionFilmstrip, THUMB_SIZE
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class OptionFilmstripTest(IntraPaintTestCase):
    """Tests scrolling of an overflowing filmstrip."""

    def setUp(self) -> None:
        super().setUp()
        self.filmstrip = OptionFilmstrip()
        self.filmstrip.resize(300, THUMB_SIZE + 16)
        image = QImage(QSize(64, 64), QImage.Format.Format_ARGB32)
        image.fill(QColor(10, 20, 30))
        self.count = 40
        self.filmstrip.set_options([image] * self.count, [True] * self.count, 0)

    def test_thumbnails_keep_their_size_when_overflowing(self) -> None:
        """Every thumbnail keeps its full height, and the last one starts past the right edge."""
        rects = self.filmstrip._thumb_rects()
        self.assertTrue(all(rect.height() == THUMB_SIZE for rect in rects))
        self.assertGreater(rects[-1].left(), self.filmstrip.width())

    def test_focus_scrolls_into_view(self) -> None:
        """Focusing the last option scrolls it fully into view."""
        image = QImage(QSize(64, 64), QImage.Format.Format_ARGB32)
        self.filmstrip.set_options([image] * self.count, [True] * self.count, self.count - 1)
        last = self.filmstrip._thumb_rects()[-1]
        self.assertLessEqual(last.right(), self.filmstrip.width())

    def test_wheel_scrolls(self) -> None:
        """The wheel moves the row, and never past either end."""
        event = QWheelEvent(QPointF(10, 10), QPointF(10, 10), QPoint(), QPoint(0, -120),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        self.filmstrip.wheelEvent(event)
        self.assertGreater(self.filmstrip._scroll, 0)
        for _ in range(100):
            self.filmstrip.wheelEvent(event)
        self.assertEqual(self.filmstrip._scroll, self.filmstrip._max_scroll())
