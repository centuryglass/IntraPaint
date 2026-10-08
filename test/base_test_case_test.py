"""Tests the shared test infrastructure in test/base_test_case.py."""
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QWidget

from src.config.application_config import AppConfig
from src.hotkey_filter import HotkeyFilter
from src.undo_stack import UndoStack
from test.base_test_case import (IntraPaintTestCase, PROJECT_ROOT, assert_image_matches_golden, assert_images_equal,
                                 assert_json_matches_snapshot, tested_image_path)

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


class JsonSnapshotTest(unittest.TestCase):
    """Tests assert_json_matches_snapshot."""

    def setUp(self) -> None:
        temp_dir = tempfile.mkdtemp(prefix='intrapaint-snapshot-test-')
        self.addCleanup(shutil.rmtree, temp_dir)
        self.snapshot_path = os.path.join(temp_dir, 'snapshot.json')
        self.tested_path = os.path.join(temp_dir, 'snapshot_tested.json')

    def _write_snapshot(self, data: object, path: str = '') -> None:
        with open(path or self.snapshot_path, 'w', encoding='utf-8') as snapshot_file:
            snapshot_file.write(json.dumps(data, indent=2, sort_keys=True) + '\n')

    def test_match_ignores_key_order(self) -> None:
        """Data matches a snapshot written in the committed format, whatever its key order."""
        self._write_snapshot({'a': 1, 'b': [1, 2]})
        assert_json_matches_snapshot({'b': [1, 2], 'a': 1}, self.snapshot_path)
        self.assertFalse(os.path.exists(self.tested_path))

    def test_mismatch_writes_tested_data(self) -> None:
        """A mismatch fails with a diff, and saves the tested data next to the snapshot."""
        self._write_snapshot({'steps': 20})
        with self.assertRaisesRegex(AssertionError, r'(?s)-  "steps": 20.*\+  "steps": 30'):
            assert_json_matches_snapshot({'steps': 30}, self.snapshot_path)
        with open(self.tested_path, encoding='utf-8') as tested_file:
            self.assertEqual(json.load(tested_file), {'steps': 30})

    def test_missing_snapshot_writes_tested_data(self) -> None:
        """A missing snapshot fails, saving the tested data so it can become the snapshot."""
        with self.assertRaisesRegex(AssertionError, 'is missing'):
            assert_json_matches_snapshot([1], self.snapshot_path)
        self.assertTrue(os.path.isfile(self.tested_path))

    def test_match_removes_stale_tested_data(self) -> None:
        """Passing removes tested data left by an earlier failure."""
        self._write_snapshot([1])
        self._write_snapshot([2], self.tested_path)
        assert_json_matches_snapshot([1], self.snapshot_path)
        self.assertFalse(os.path.exists(self.tested_path))


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

    def test_hotkeys_reset_before_and_after(self) -> None:
        """Hotkey bindings and modifier connections made outside a test, or inside one, don't outlive it."""
        hotkey_filter = HotkeyFilter.instance()
        widget = QWidget()
        observed: dict[str, int] = {}

        def _press_key_and_change_modifiers() -> None:
            key_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F12, Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(widget, key_event)
            hotkey_filter.modifiers_changed.emit(Qt.KeyboardModifier.ShiftModifier)

        outside_hotkey = MagicMock(return_value=True)
        outside_listener = MagicMock()
        inside_hotkey = MagicMock(return_value=True)
        inside_listener = MagicMock()

        class _Case(IntraPaintTestCase):
            def test_body(self) -> None:
                """Checks that earlier bindings are gone, then adds its own."""
                _press_key_and_change_modifiers()
                observed['outside_hotkey'] = outside_hotkey.call_count
                observed['outside_listener'] = outside_listener.call_count
                hotkey_filter.register_keybinding('test.inside', inside_hotkey, QKeySequence(Qt.Key.Key_F12))
                hotkey_filter.modifiers_changed.connect(inside_listener)
                hotkey_filter.set_default_focus(widget)

        hotkey_filter.register_keybinding('test.outside', outside_hotkey, QKeySequence(Qt.Key.Key_F12))
        hotkey_filter.modifiers_changed.connect(outside_listener)
        result = unittest.TestResult()
        _Case('test_body').run(result)
        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
        self.assertEqual(observed, {'outside_hotkey': 0, 'outside_listener': 0})
        _press_key_and_change_modifiers()
        inside_hotkey.assert_not_called()
        inside_listener.assert_not_called()
        self.assertIsNone(hotkey_filter.default_focus())


if __name__ == '__main__':
    unittest.main()
