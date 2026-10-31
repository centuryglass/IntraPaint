"""Tests `NonDestructiveLayer` through a stub subclass: the flatten gates on destructive operations, and the .ora layer
and document extension hooks in `src/image/ora_extensions.py`."""
import os
import tempfile
import zipfile
from typing import Any, Callable, Optional
from unittest.mock import patch, MagicMock

from PySide6.QtCore import QRect, QSize, QPoint
from PySide6.QtGui import QColor, QImage, QTransform

from src.image.filter.invert import InvertFilter
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.image_stack_utils import crop_layer_to_selection
from src.image.layers.layer import Layer
from src.image.layers.non_destructive_layer import NonDestructiveLayer
from src.image.open_raster import save_ora_image, read_ora_image, RESERVED_EXTENDED_TAGS
from src.image.ora_extensions import (OraWriteContext, OraReadContext, DocumentExtension, register_layer_loader,
                                      unregister_layer_loader, register_document_extension,
                                      unregister_document_extension)
from src.util.async_task import AsyncTask
from test.base_test_case import IntraPaintTestCase
from test.image.layers.image_stack_state import select_rect

CONFIRM = 'src.image.layers.non_destructive_layer.request_confirmation'
STACK_SIZE = QSize(32, 24)
STUB_COLOR = QColor(10, 200, 30)
STUB_TAG = 'stub-data'
STUB_FILE_TAG = 'stub-file'
DOCUMENT_EXTENSION = 'stub-document'


class StubLayer(NonDestructiveLayer):
    """A non-destructive layer rendering one solid color, with a string payload saved to .ora."""

    def __init__(self, payload: str = 'payload', size: QSize = QSize(16, 12)) -> None:
        super().__init__('stub')
        self.payload = payload
        self.set_size(size)

    def get_qimage(self) -> QImage:
        image = QImage(self.size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(STUB_COLOR)
        return image

    def copy(self) -> 'StubLayer':
        layer = StubLayer(self.payload, self.size)
        layer.set_transform(self.transform)
        return layer

    def save_state(self) -> Any:
        return self.name, self.transform

    def restore_state(self, saved_state: Any) -> None:
        self.set_name(saved_state[0])
        self.set_transform(saved_state[1])

    def ora_extension_data(self, context: OraWriteContext) -> dict[str, str]:
        file_path = context.write_file(f'stub_{self.id}.txt', self.payload.encode())
        return {STUB_TAG: self.payload, STUB_FILE_TAG: file_path}


def _load_stub(attributes: dict[str, str], context: OraReadContext) -> Optional[Layer]:
    file_content = context.read_file(attributes[STUB_FILE_TAG])
    if file_content is None:
        return None
    layer = StubLayer(attributes[STUB_TAG] + ':' + file_content.decode())
    return layer


class NonDestructiveGateTest(IntraPaintTestCase):
    """Every destructive operation asks before converting a non-text NonDestructiveLayer, and converts it only
    when the user agrees."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(STACK_SIZE, STACK_SIZE, QSize(8, 8), QSize(1024, 1024))
        backdrop = QImage(STACK_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        backdrop.fill(QColor(200, 0, 0))
        self.backdrop = self.image_stack.create_layer('backdrop', backdrop, layer_index=0)
        self.stub = StubLayer()
        self.image_stack.layer_stack.insert_layer(self.stub, 0)
        self.image_stack.active_layer = self.stub

    def _assert_gated(self, operation: Callable[[], Any], expect_prompt: bool = True) -> None:
        """Declining leaves the stub in place; accepting replaces it with an image layer."""
        with patch(CONFIRM, return_value=False) as declined:
            operation()
        if expect_prompt:
            declined.assert_called_once()
        self.assertIn(self.stub, self.image_stack.non_destructive_layers)
        with patch(CONFIRM, return_value=True) as accepted:
            operation()
        if expect_prompt:
            accepted.assert_called_once()
        self.assertEqual([], self.image_stack.non_destructive_layers)

    def test_pixel_edits_raise(self) -> None:
        """set_qimage and cut_masked refuse edits."""
        with self.assertRaises(RuntimeError):
            self.stub.set_qimage(QImage(STACK_SIZE, QImage.Format.Format_ARGB32_Premultiplied))
        with self.assertRaises(RuntimeError):
            self.stub.cut_masked(QImage(STACK_SIZE, QImage.Format.Format_ARGB32_Premultiplied))

    def test_copy_as_image_layer(self) -> None:
        """The conversion renders the stub with its properties."""
        self.stub.set_opacity(0.5)
        self.stub.set_transform(QTransform.fromTranslate(3, 4))
        image_layer = self.stub.copy_as_image_layer()
        self.assertIsInstance(image_layer, ImageLayer)
        self.assertEqual(0.5, image_layer.opacity)
        self.assertEqual(self.stub.transform, image_layer.transform)
        self.assertEqual(STUB_COLOR, image_layer.image.pixelColor(0, 0))

    def test_resize_canvas(self) -> None:
        """Resizing the canvas so that it cuts the stub prompts."""
        self._assert_gated(lambda: self.image_stack.resize_canvas(QSize(8, 8), 0, 0, crop_layers=True))

    def test_merge_all_visible(self) -> None:
        """Merging all visible layers prompts."""
        self._assert_gated(self.image_stack.merge_all_visible)

    def test_merge_layer_down(self) -> None:
        """Merging the stub down prompts."""
        self._assert_gated(lambda: self.image_stack.merge_layer_down(self.stub))

    def test_layer_to_image_size(self) -> None:
        """Resizing a stub that extends past the image to the image size prompts."""
        self.stub.set_transform(QTransform.fromTranslate(20, 20))
        self._assert_gated(lambda: self.image_stack.layer_to_image_size(self.stub))

    def test_clear_selected(self) -> None:
        """Clearing a selection that covers the stub prompts."""
        select_rect(self.image_stack, QRect(0, 0, 8, 8))
        self._assert_gated(lambda: self.image_stack.clear_selected(self.stub))

    def test_crop_layer_to_selection(self) -> None:
        """Cropping the stub to a selection prompts."""
        select_rect(self.image_stack, QRect(2, 2, 8, 8))
        self._assert_gated(lambda: crop_layer_to_selection(self.image_stack, self.stub))

    def test_apply_filter(self) -> None:
        """Filtering the stub prompts."""
        image_filter = InvertFilter(self.image_stack)
        image_filter.active_layer_only = True

        def _apply() -> None:
            with patch.object(AsyncTask, 'start', AsyncTask.run):
                image_filter.apply_filter([])

        self._assert_gated(_apply)


class OraExtensionTest(IntraPaintTestCase):
    """Round trips through the .ora layer and document extension hooks."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(STACK_SIZE, STACK_SIZE, QSize(8, 8), QSize(1024, 1024))
        self.loaded_stack = ImageStack(STACK_SIZE, STACK_SIZE, QSize(8, 8), QSize(1024, 1024))
        self.image_stack.create_layer('backdrop', QImage(STACK_SIZE, QImage.Format.Format_ARGB32_Premultiplied),
                                      layer_index=0)

    def _round_trip(self) -> str:
        """Saves self.image_stack, loads it into self.loaded_stack, and returns the saved path's directory-free
        listing of archive entries joined by newlines."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ora_path = os.path.join(temp_dir, 'extension.ora')
            save_ora_image(self.image_stack, ora_path, 'metadata')
            read_ora_image(self.loaded_stack, ora_path)
            with zipfile.ZipFile(ora_path) as archive:
                return '\n'.join(archive.namelist())

    def _add_stub(self, payload: str) -> StubLayer:
        layer = StubLayer(payload)
        layer.set_transform(QTransform.fromTranslate(5, 6))
        self.image_stack.layer_stack.insert_layer(layer, 0)
        self.image_stack.active_layer = layer
        return layer

    def test_layer_extension_round_trip(self) -> None:
        """A registered loader rebuilds the layer from its attributes and archive file."""
        register_layer_loader(STUB_TAG, _load_stub)
        self.addCleanup(unregister_layer_loader, STUB_TAG)
        layer = self._add_stub('alpha')
        entries = self._round_trip()
        self.assertIn(f'data/stub_{layer.id}.txt', entries)
        loaded = self.loaded_stack.non_destructive_layers
        self.assertEqual(1, len(loaded))
        assert isinstance(loaded[0], StubLayer)
        self.assertEqual('alpha:alpha', loaded[0].payload)
        self.assertEqual(layer.transform, loaded[0].transform)

    def test_unclaimed_layer_loads_as_image(self) -> None:
        """Without a loader for its attributes, the layer loads as an image layer of its rendered PNG."""
        self._add_stub('alpha')
        self._round_trip()
        self.assertEqual([], self.loaded_stack.non_destructive_layers)
        self.assertEqual(2, len(self.loaded_stack.image_layers))  # The backdrop and the stub.
        self.assertEqual(STUB_COLOR, self.loaded_stack.image_layers[0].image.pixelColor(0, 0))

    def _assert_loader_falls_back(self, loader: Callable[..., Optional[Layer]]) -> None:
        register_layer_loader(STUB_TAG, loader)
        self.addCleanup(unregister_layer_loader, STUB_TAG)
        self._add_stub('alpha')
        self._round_trip()
        self.assertEqual([], self.loaded_stack.non_destructive_layers)
        self.assertEqual(2, len(self.loaded_stack.image_layers))  # The backdrop and the stub.

    def test_loader_declining_falls_back_to_image(self) -> None:
        """A loader that returns None leaves the layer as an image layer."""
        self._assert_loader_falls_back(lambda _attributes, _context: None)

    def test_loader_error_falls_back_to_image(self) -> None:
        """A loader that raises ValueError leaves the layer as an image layer, and the error is logged."""
        def _fail(_attributes: dict[str, str], _context: OraReadContext) -> Optional[Layer]:
            raise ValueError('bad data')

        with self.assertLogs('src.image.open_raster', 'ERROR'):
            self._assert_loader_falls_back(_fail)

    def test_reserved_attribute_rejected(self) -> None:
        """Layer extension data can't overwrite the attributes open_raster writes itself."""
        for tag in sorted(RESERVED_EXTENDED_TAGS):
            with self.subTest(tag=tag):
                layer = StubLayer()
                self.image_stack.layer_stack.insert_layer(layer, 0)
                with patch.object(StubLayer, 'ora_extension_data', return_value={tag: 'x'}):
                    with tempfile.TemporaryDirectory() as temp_dir, self.assertRaises(ValueError):
                        save_ora_image(self.image_stack, os.path.join(temp_dir, 'reserved.ora'), 'metadata')
                self.image_stack.layer_stack.remove_layer(layer)

    def test_document_extension_round_trip(self) -> None:
        """A document extension's payload and files come back on load."""
        saved: dict[str, Any] = {}

        def _save(_stack: ImageStack, context: OraWriteContext) -> Optional[str]:
            return context.write_file('nested/data.bin', b'\x00\x01') + '|payload'

        def _load(_stack: ImageStack, payload: str, context: OraReadContext) -> None:
            saved['payload'] = payload
            saved['file'] = context.read_file(payload.split('|')[0])

        register_document_extension(DocumentExtension(DOCUMENT_EXTENSION, _save, _load))
        self.addCleanup(unregister_document_extension, DOCUMENT_EXTENSION)
        entries = self._round_trip()
        expected_path = f'data/extensions/{DOCUMENT_EXTENSION}/nested/data.bin'
        self.assertIn(expected_path, entries)
        self.assertEqual(f'{expected_path}|payload', saved['payload'])
        self.assertEqual(b'\x00\x01', saved['file'])

    def test_document_extension_without_payload(self) -> None:
        """An extension that saves None writes nothing, and isn't loaded."""
        load = MagicMock()
        register_document_extension(DocumentExtension(DOCUMENT_EXTENSION, lambda _s, _c: None, load))
        self.addCleanup(unregister_document_extension, DOCUMENT_EXTENSION)
        self._round_trip()
        load.assert_not_called()

    def test_extension_paths_stay_in_directory(self) -> None:
        """Extension files can't be written or read outside their directory."""
        context = OraWriteContext()
        for path in ('../escape', '/absolute', 'a/../../escape', '..', '', 'C:\\temp'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                context.write_file(path, b'')
        with tempfile.TemporaryDirectory() as temp_dir:
            read_context = OraReadContext(temp_dir)
            self.assertIsNone(read_context.read_file('../escape'))
            self.assertIsNone(read_context.read_file('data/missing.txt'))

    def test_text_layer_round_trip_uses_hook(self) -> None:
        """Text layers save and load through the same hook, with the text-data attribute in extended_data.xml."""
        text_layer = self.image_stack.create_text_layer(None)
        self._round_trip()
        self.assertEqual(1, len(self.loaded_stack.text_layers))
        self.assertEqual(text_layer.text_rect.serialize(), self.loaded_stack.text_layers[0].text_rect.serialize())
        self.assertEqual(QPoint(), self.loaded_stack.text_layers[0].transform.map(QPoint()))
