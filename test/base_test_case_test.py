"""Tests the shared test infrastructure in test/base_test_case.py."""
import os
import shutil
import tempfile
import unittest

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage

from src.config.application_config import AppConfig
from src.undo_stack import UndoStack
from test.base_test_case import (IntraPaintTestCase, PROJECT_ROOT, assert_image_matches_golden, assert_images_equal,
                                 tested_image_path)

IMAGE_SIZE = QSize(8, 4)


def _solid_image(color: QColor | Qt.GlobalColor,
                 image_format: QImage.Format = QImage.Format.Format_ARGB32_Premultiplied) -> QImage:
    image = QImage(IMAGE_SIZE, image_format)
    image.fill(color)
    return image


class GoldenImageTest(unittest.TestCase):
    """Tests assert_image_matches_golden."""

    def setUp(self) -> None:
        temp_dir = tempfile.mkdtemp(prefix='intrapaint-golden-test-')
        self.addCleanup(shutil.rmtree, temp_dir)
        self.golden_path = os.path.join(temp_dir, 'golden.png')
        self.tested_path = tested_image_path(self.golden_path)

    def test_tested_image_path(self) -> None:
        """The tested image goes next to the golden, named after it."""
        self.assertEqual(tested_image_path('a/b/golden.png'), 'a/b/golden_tested.png')

    def test_match_ignores_format(self) -> None:
        """Images with the same pixels match whatever their format."""
        _solid_image(Qt.GlobalColor.red, QImage.Format.Format_ARGB32).save(self.golden_path)
        assert_image_matches_golden(_solid_image(Qt.GlobalColor.red), self.golden_path)
        self.assertFalse(os.path.exists(self.tested_path))

    def test_mismatch_writes_tested_image(self) -> None:
        """A mismatch fails with a description of the difference, and saves the tested image."""
        _solid_image(Qt.GlobalColor.red).save(self.golden_path)
        actual = _solid_image(Qt.GlobalColor.red)
        actual.setPixelColor(1, 1, QColor(255, 0, 10))
        with self.assertRaisesRegex(AssertionError, r'1 of 32 pixels differ, by up to 10'):
            assert_image_matches_golden(actual, self.golden_path)
        self.assertEqual(QImage(self.tested_path).convertToFormat(actual.format()), actual)

    def test_size_mismatch(self) -> None:
        """A size mismatch is reported as one."""
        QImage(QSize(4, 4), QImage.Format.Format_ARGB32).save(self.golden_path)
        with self.assertRaisesRegex(AssertionError, r'size 8x4 != expected 4x4'):
            assert_image_matches_golden(_solid_image(Qt.GlobalColor.red), self.golden_path)

    def test_missing_golden_writes_tested_image(self) -> None:
        """A missing golden fails, saving the tested image so it can become the golden."""
        with self.assertRaisesRegex(AssertionError, 'missing or unreadable'):
            assert_image_matches_golden(_solid_image(Qt.GlobalColor.blue), self.golden_path)
        self.assertTrue(os.path.isfile(self.tested_path))

    def test_match_removes_stale_tested_image(self) -> None:
        """Passing removes a tested image left by an earlier failure."""
        _solid_image(Qt.GlobalColor.green).save(self.golden_path)
        _solid_image(Qt.GlobalColor.red).save(self.tested_path)
        assert_image_matches_golden(_solid_image(Qt.GlobalColor.green), self.golden_path)
        self.assertFalse(os.path.exists(self.tested_path))

    def test_message_includes_context(self) -> None:
        """Extra context passed as msg leads the failure message."""
        _solid_image(Qt.GlobalColor.red).save(self.golden_path)
        with self.assertRaisesRegex(AssertionError, r'^after undo: image does not match'):
            assert_image_matches_golden(_solid_image(Qt.GlobalColor.blue), self.golden_path, 'after undo')


class ImagesEqualTest(unittest.TestCase):
    """Tests assert_images_equal."""

    def test_match_ignores_format(self) -> None:
        """Images with the same pixels are equal whatever their format."""
        assert_images_equal(_solid_image(Qt.GlobalColor.red), _solid_image(Qt.GlobalColor.red,
                                                                           QImage.Format.Format_ARGB32))

    def test_mismatch_saves_both_images(self) -> None:
        """A mismatch fails, saving both images outside the working tree."""
        actual = _solid_image(Qt.GlobalColor.red)
        expected = _solid_image(Qt.GlobalColor.blue)
        with self.assertRaisesRegex(AssertionError, r'32 of 32 pixels differ') as context:
            assert_images_equal(actual, expected)
        message = str(context.exception)
        for name, image in (('actual.png', actual), ('expected.png', expected)):
            path = message[:message.index(name) + len(name)].split()[-1]
            self.assertFalse(path.startswith(PROJECT_ROOT))
            self.assertEqual(QImage(path).convertToFormat(image.format()), image)
        shutil.rmtree(os.path.dirname(path))


class IntraPaintTestCaseTest(unittest.TestCase):
    """Tests that IntraPaintTestCase resets shared state around each test."""

    def test_state_reset_before_and_after(self) -> None:
        """Config values and undo history changed outside a test, or inside one, don't outlive it."""
        default_max_undo = AppConfig().get(AppConfig.MAX_UNDO)
        observed: dict[str, object] = {}

        class _Case(IntraPaintTestCase):
            def test_body(self) -> None:
                """Records the state the test starts in, then changes it."""
                observed['max_undo'] = AppConfig().get(AppConfig.MAX_UNDO)
                observed['undo_count'] = UndoStack().undo_count()
                observed['cwd'] = os.getcwd()
                AppConfig().set(AppConfig.MAX_UNDO, default_max_undo + 2)
                UndoStack().commit_action(lambda: None, lambda: None, 'test.inside')

        AppConfig().set(AppConfig.MAX_UNDO, default_max_undo + 1)
        UndoStack().commit_action(lambda: None, lambda: None, 'test.outside')
        result = unittest.TestResult()
        _Case('test_body').run(result)
        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
        self.assertEqual(observed, {'max_undo': default_max_undo, 'undo_count': 0, 'cwd': PROJECT_ROOT})
        self.assertEqual(AppConfig().get(AppConfig.MAX_UNDO), default_max_undo)
        self.assertEqual(UndoStack().undo_count(), 0)


if __name__ == '__main__':
    unittest.main()
