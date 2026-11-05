"""Tests crash recovery autosaves: what they write, when they skip work, and restoring them after a crash."""
import os
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch, MagicMock

from PySide6.QtCore import QSize, QRect, Qt
from PySide6.QtGui import QColor, QImage, QTransform
from PySide6.QtWidgets import QApplication, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.autosave_controller import AutosaveController, BUSY_RETRY_MS
from src.controller.image_io import ImageIO
from src.image.image_metadata import ImageMetadata
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.text_layer import TextLayer
from src.image.layers.transform_layer import TransformLayer
from src.image.open_raster import save_ora_image, read_ora_image
from src.image.recovery_files import (find_recoverable_sessions, read_manifest, LOCK_FILE_NAME, MANIFEST_FILE_NAME,
                                      MANIFEST_TMP_FILE_NAME, FILES_DIR_NAME, KEY_GENERATION, KEY_ARCHIVE_FILES)
from src.image.text_rect import TextRect
from src.ui.modal.modal_utils import RECOVERY_RESTORE, RECOVERY_DISCARD, RECOVERY_LATER
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

IMG_SIZE = QSize(64, 48)
GEN_AREA_SIZE = QSize(16, 16)
MIN_GEN_AREA = QSize(8, 8)
MAX_GEN_AREA = QSize(64, 64)
ORIGINAL_PATH = '/images/original.png'
METADATA = {'parameters': 'a prompt\nSteps: 20'}


def _solid_image(color: QColor, size: QSize = IMG_SIZE) -> QImage:
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return image


def _dead_pid() -> int:
    """Returns the ID of a process that has exited."""
    process = subprocess.Popen([sys.executable, '-c', 'pass'])  # pylint: disable=consider-using-with
    process.wait()
    return process.pid


class AutosaveControllerTest(IntraPaintTestCase):
    """Tests AutosaveController and the recovery folder it writes."""

    def setUp(self) -> None:
        super().setUp()
        self._root_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.root = self._root_dir.name
        self.image_stack = ImageStack(IMG_SIZE, GEN_AREA_SIZE, MIN_GEN_AREA, MAX_GEN_AREA)
        self.image_stack.load_image(_solid_image(QColor(Qt.GlobalColor.white)))
        self.window = QWidget()
        self.image_io = ImageIO(self.window, self.image_stack, lambda: None)
        self.controller = AutosaveController(self.image_stack, self.image_io, self.window, self.root)

    def tearDown(self) -> None:
        self.controller.shutdown()
        self._root_dir.cleanup()
        super().tearDown()

    def _build_document(self) -> None:
        """Fills the document with a group, a transformed layer, a hidden layer and a text layer."""
        group = self.image_stack.create_layer_group('group')
        self.image_stack.create_layer('nested', _solid_image(QColor(255, 0, 0, 128)), layer_parent=group,
                                      layer_index=0)
        rotated = self.image_stack.create_layer('rotated', _solid_image(QColor(0, 0, 255), QSize(20, 10)))
        rotated.transform = QTransform().translate(10, 5).rotate(30)
        hidden = self.image_stack.create_layer('hidden', _solid_image(QColor(0, 255, 0)))
        hidden.visible = False
        hidden.opacity = 0.5
        text_rect = TextRect()
        text_rect.text = 'text'
        text_rect.size = QSize(30, 12)
        text_rect.text_color = QColor(Qt.GlobalColor.red)
        self.image_stack.create_text_layer(text_rect)
        self.image_stack.generation_area = QRect(8, 4, 16, 16)
        Cache().set(Cache.LAST_FILE_PATH, ORIGINAL_PATH)
        self.image_io.metadata = ImageMetadata(dict(METADATA))

    def _simulate_crash(self) -> str:
        """Copies this session's folder to one owned by an exited process, and returns the copy's path."""
        session_dir = self.controller.session_dir
        assert session_dir is not None
        crashed_dir = os.path.join(self.root, 'crashed')
        shutil.copytree(session_dir, crashed_dir)
        with open(os.path.join(crashed_dir, LOCK_FILE_NAME), 'w', encoding='utf-8') as lock_file:
            lock_file.write(str(_dead_pid()))
        return crashed_dir

    def _assert_layers_match(self, expected: Layer, actual: Layer) -> None:
        self.assertEqual(type(expected), type(actual))
        self.assertEqual(expected.name, actual.name)
        self.assertEqual(expected.visible, actual.visible, expected.name)
        self.assertEqual(expected.opacity, actual.opacity, expected.name)
        if isinstance(expected, LayerGroup):
            assert isinstance(actual, LayerGroup)
            self.assertEqual(expected.count, actual.count, expected.name)
            for expected_child, actual_child in zip(expected.child_layers, actual.child_layers):
                self._assert_layers_match(expected_child, actual_child)
        else:
            assert isinstance(expected, TransformLayer) and isinstance(actual, TransformLayer)
            self.assert_images_equal(actual.image, expected.image, expected.name)
            self.assertEqual(expected.transform, actual.transform, expected.name)
            if isinstance(expected, TextLayer):
                assert isinstance(actual, TextLayer)
                self.assertEqual(expected.text_rect.serialize(), actual.text_rect.serialize())

    def _layer_file(self, layer: Layer) -> str:
        """Returns the name of the recovery file that holds a layer's flattened image."""
        manifest = read_manifest(str(self.controller.session_dir))
        assert manifest is not None
        names = [name for name in manifest[KEY_ARCHIVE_FILES].values() if name.startswith(f'{layer.id}-flattened-')]
        self.assertEqual(1, len(names), f'files for layer {layer.name}: {names}')
        return names[0]

    def test_restored_document_matches_autosave(self) -> None:
        """A restored copy matches the autosaved document's layers, size, generation area, metadata and path."""
        self._build_document()
        self.assertTrue(self.controller.dirty)
        self.assertTrue(self.controller.autosave_now(synchronous=True))
        crashed_dir = self._simulate_crash()
        expected_copy = ImageStack(IMG_SIZE, GEN_AREA_SIZE, MIN_GEN_AREA, MAX_GEN_AREA)
        with tempfile.TemporaryDirectory() as temp_dir:
            ora_path = os.path.join(temp_dir, 'expected.ora')
            save_ora_image(self.image_stack, ora_path, None)
            read_ora_image(expected_copy, ora_path)
        expected_gen_area = self.image_stack.generation_area
        expected_active_name = self.image_stack.active_layer.name

        # Opening another document replaces the stack's layers, and deletes this session's own copy:
        self.image_stack.load_image(_solid_image(QColor(Qt.GlobalColor.black)))
        self.image_io.clear_metadata()
        Cache().set(Cache.LAST_FILE_PATH, '')
        prompt = MagicMock(return_value=RECOVERY_RESTORE)

        self.assertTrue(self.controller.offer_recovery(prompt))
        prompt.assert_called_once()
        self._assert_layers_match(expected_copy.layer_stack, self.image_stack.layer_stack)
        self.assertEqual(IMG_SIZE, self.image_stack.size)
        self.assertEqual(expected_gen_area, self.image_stack.generation_area)
        self.assertEqual(expected_active_name, self.image_stack.active_layer.name)
        self.assertEqual(ORIGINAL_PATH, Cache().get(Cache.LAST_FILE_PATH))
        self.assertEqual(METADATA, self.image_io.metadata.text)
        # The restored document is this session's first autosave, so the crashed copy is gone:
        self.assertFalse(os.path.exists(crashed_dir))
        self.assertIsNotNone(read_manifest(str(self.controller.session_dir)))

    def test_unchanged_layer_is_not_rewritten(self) -> None:
        """An autosave writes only the layers whose content changed since the last one."""
        changed = self.image_stack.create_layer('changed', _solid_image(QColor(Qt.GlobalColor.red)))
        unchanged = self.image_stack.create_layer('unchanged', _solid_image(QColor(Qt.GlobalColor.blue)))
        self.assertTrue(self.controller.autosave_now(synchronous=True))
        changed_file = self._layer_file(changed)
        unchanged_file = self._layer_file(unchanged)
        unchanged_path = os.path.join(str(self.controller.session_dir), FILES_DIR_NAME, unchanged_file)
        modified_time = os.stat(unchanged_path).st_mtime_ns

        changed.image = _solid_image(QColor(Qt.GlobalColor.green))
        with patch.object(unchanged, 'transformed_image', side_effect=AssertionError('copied unchanged layer')):
            self.assertTrue(self.controller.autosave_now(synchronous=True))
        self.assertNotEqual(changed_file, self._layer_file(changed))
        self.assertFalse(os.path.exists(os.path.join(str(self.controller.session_dir), FILES_DIR_NAME,
                                                     changed_file)), 'the replaced file was not removed')
        self.assertEqual(unchanged_file, self._layer_file(unchanged))
        self.assertEqual(modified_time, os.stat(unchanged_path).st_mtime_ns)

    def test_unchanged_document_is_not_written(self) -> None:
        """A change signal with nothing actually changed writes nothing, and an opened document needs no copy."""
        self.image_stack.content_changed.emit()
        self.assertTrue(self.controller.dirty)
        self.assertFalse(self.controller.autosave_now(synchronous=True))
        self.assertIsNone(self.controller.session_dir)

        self.image_stack.create_layer('new layer')
        self.assertTrue(self.controller.autosave_now(synchronous=True))
        self.image_stack.content_changed.emit()
        self.assertFalse(self.controller.autosave_now(synchronous=True))

    def test_half_written_autosave_falls_back_to_previous(self) -> None:
        """A crash before the new manifest replaces the old one leaves the previous complete copy to restore."""
        layer = self.image_stack.create_layer('layer', _solid_image(QColor(Qt.GlobalColor.red)))
        self.assertTrue(self.controller.autosave_now(synchronous=True))
        session_dir = str(self.controller.session_dir)
        first_manifest = read_manifest(session_dir)
        assert first_manifest is not None

        layer.image = _solid_image(QColor(Qt.GlobalColor.green))
        with patch('src.image.recovery_files.os.replace', side_effect=OSError):
            self.assertFalse(self.controller.autosave_now(synchronous=True))
        with open(os.path.join(session_dir, MANIFEST_TMP_FILE_NAME), 'w', encoding='utf-8') as tmp_file:
            tmp_file.write('{"version": 1, "gener')  # Cut off mid-write
        self.assertEqual(first_manifest, read_manifest(session_dir))
        crashed_dir = self._simulate_crash()

        self.image_stack.load_image(_solid_image(QColor(Qt.GlobalColor.black)))
        self.assertTrue(self.controller.offer_recovery(MagicMock(return_value=RECOVERY_RESTORE)))
        self.assertFalse(os.path.exists(crashed_dir))
        restored = self.image_stack.layer_stack.child_layers[0]
        self.assertEqual('layer', restored.name)
        self.assert_images_equal(restored.image, _solid_image(QColor(Qt.GlobalColor.red)))

    def test_failed_write_retries_after_next_change(self) -> None:
        """A failed autosave keeps the document marked as changed."""
        self.image_stack.create_layer('layer')
        with patch('src.image.recovery_files.os.replace', side_effect=OSError):
            self.assertFalse(self.controller.autosave_now(synchronous=True))
        self.assertTrue(self.controller.dirty)
        self.assertTrue(self.controller.autosave_now(synchronous=True))
        manifest = read_manifest(str(self.controller.session_dir))
        assert manifest is not None
        self.assertEqual(1, manifest[KEY_GENERATION])

    def test_live_process_folder_is_not_offered(self) -> None:
        """Folders owned by a running process, this one included, are never offered or deleted."""
        self.image_stack.create_layer('layer')
        self.assertTrue(self.controller.autosave_now(synchronous=True))
        session_dir = str(self.controller.session_dir)
        self.assertEqual([], find_recoverable_sessions(self.root))
        with open(os.path.join(session_dir, LOCK_FILE_NAME), 'w', encoding='utf-8') as lock_file:
            lock_file.write(str(os.getppid()))
        self.assertEqual([], find_recoverable_sessions(self.root))
        self.assertTrue(os.path.isdir(session_dir))

    def test_crashed_folder_choices(self) -> None:
        """Later keeps a crashed copy for the next launch, Discard deletes it, and an empty one is deleted unasked."""
        self.image_stack.create_layer('layer')
        self.assertTrue(self.controller.autosave_now(synchronous=True))
        crashed_dir = self._simulate_crash()
        empty_dir = os.path.join(self.root, 'empty')
        os.makedirs(empty_dir)
        with open(os.path.join(empty_dir, LOCK_FILE_NAME), 'w', encoding='utf-8') as lock_file:
            lock_file.write(str(_dead_pid()))

        prompt = MagicMock(return_value=RECOVERY_LATER)
        self.assertFalse(self.controller.offer_recovery(prompt))
        prompt.assert_called_once()
        self.assertTrue(os.path.isdir(crashed_dir))
        self.assertFalse(os.path.exists(empty_dir))

        self.assertFalse(self.controller.offer_recovery(MagicMock(return_value=RECOVERY_DISCARD)))
        self.assertFalse(os.path.exists(crashed_dir))

    def test_shutdown_removes_folder(self) -> None:
        """A normal quit deletes the session folder."""
        self.image_stack.create_layer('layer')
        self.assertTrue(self.controller.autosave_now())  # Written on a worker
        session_dir = str(self.controller.session_dir)
        self.controller.shutdown()
        self.assertFalse(os.path.exists(session_dir))
        self.image_stack.create_layer('after quit')
        self.assertFalse(self.controller.dirty)

    def test_new_document_removes_folder(self) -> None:
        """Replacing the document deletes the copy of the old one."""
        self.image_stack.create_layer('layer')
        self.assertTrue(self.controller.autosave_now(synchronous=True))
        session_dir = str(self.controller.session_dir)
        self.image_stack.load_image(_solid_image(QColor(Qt.GlobalColor.black)))
        self.assertFalse(os.path.exists(session_dir))
        self.assertIsNone(self.controller.session_dir)
        # The opened document matches its file, so it gets no copy:
        self.assertFalse(self.controller.autosave_now(synchronous=True))
        self.assertIsNone(self.controller.session_dir)

    def test_save_removes_manifest_unless_edited_after(self) -> None:
        """A save removes the manifest, unless the document changed after the save read it."""
        self.image_stack.create_layer('layer')
        self.assertTrue(self.controller.autosave_now(synchronous=True))
        session_dir = str(self.controller.session_dir)
        on_save_started = self.image_io.on_save_started
        assert on_save_started is not None

        saved = on_save_started()
        self.image_stack.create_layer('edited during save')
        saved()
        self.assertTrue(os.path.isfile(os.path.join(session_dir, MANIFEST_FILE_NAME)))
        self.assertTrue(self.controller.dirty)

        self.assertTrue(self.controller.autosave_now(synchronous=True))
        on_save_started()()
        self.assertFalse(os.path.isfile(os.path.join(session_dir, MANIFEST_FILE_NAME)))
        self.assertFalse(self.controller.dirty)
        self.assertEqual([], find_recoverable_sessions(self.root))

    def test_busy_autosave_waits(self) -> None:
        """An autosave that comes due during a stroke or a generation waits and tries again."""
        self.image_stack.create_layer('layer')
        with patch('src.controller.autosave_controller.LayerBrush.any_stroke_in_progress', return_value=True):
            self.assertFalse(self.controller.autosave_now())
        self.assertTrue(self.controller.dirty)
        idle_timer = self.controller._idle_timer  # pylint: disable=protected-access
        self.assertTrue(idle_timer.isActive())
        self.assertEqual(BUSY_RETRY_MS, idle_timer.interval())
        self.assertIsNone(self.controller.session_dir)

    def test_disabled_autosave_writes_nothing(self) -> None:
        """Turning autosave off deletes the copy and stops tracking changes."""
        self.image_stack.create_layer('layer')
        self.assertTrue(self.controller.autosave_now(synchronous=True))
        session_dir = str(self.controller.session_dir)
        AppConfig().set(AppConfig.AUTOSAVE_ENABLED, False)
        self.assertFalse(os.path.exists(session_dir))
        self.image_stack.create_layer('another')
        self.assertFalse(self.controller.dirty)
        self.assertFalse(self.controller.autosave_now(synchronous=True))

    def test_write_after_background_write_reuses_its_files(self) -> None:
        """A write that waits for a background write builds on that write's files."""
        changed = self.image_stack.create_layer('changed', _solid_image(QColor(Qt.GlobalColor.red)))
        unchanged = self.image_stack.create_layer('unchanged', _solid_image(QColor(Qt.GlobalColor.blue)))
        self.assertTrue(self.controller.autosave_now())  # Written on a worker
        changed.image = _solid_image(QColor(Qt.GlobalColor.green))
        with patch.object(unchanged, 'transformed_image', side_effect=AssertionError('copied unchanged layer')):
            self.assertTrue(self.controller.autosave_now(synchronous=True))
        manifest = read_manifest(str(self.controller.session_dir))
        assert manifest is not None
        self.assertEqual(1, manifest[KEY_GENERATION])
        self._layer_file(unchanged)
