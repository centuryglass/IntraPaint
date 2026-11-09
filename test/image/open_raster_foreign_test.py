"""Tests that other programs' .ora data survives a load and save in IntraPaint.

`mypaint_test.ora` and `krita_test.ora` were saved by MyPaint 2.0.1 and Krita. MyPaint's file has namespaced
`<image>` and `<layer>` attributes, an SVG layer, files named by layer attributes (strokemaps and a background tile), a
settings file named by an `<image>` attribute, an empty group and its own composite op on every layer. Krita's has
`xres`/`yres`, stack `x`/`y` and a `krita:heat` composite op. Neither has foreign elements, so
`_write_foreign_elements_ora` builds a file that does.
"""
import os
import sys
import tempfile
import zipfile
from typing import Optional
from xml.etree.ElementTree import Element, fromstring

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QTransform
from PySide6.QtWidgets import QApplication

from src.image.composite_mode import CompositeMode
from src.image.image_metadata import ImageMetadata
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.open_raster import read_ora_image, save_ora_image, XML_FILE_NAME
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

FOREIGN_ORA_DIR = 'test/resources/test_images/foreign_ora'
MYPAINT_ORA = f'{FOREIGN_ORA_DIR}/mypaint_test.ora'
KRITA_ORA = f'{FOREIGN_ORA_DIR}/krita_test.ora'

MYPAINT_NS = 'http://mypaint.org/ns/openraster'
FOREIGN_NS = 'urn:example:foreign'

STACK_SIZE = QSize(8, 8)

# Archive members rebuilt on every save, which never match the original's bytes:
REBUILT_FILES = {'mimetype', 'stack.xml', 'mergedimage.png', 'Thumbnails/thumbnail.png'}


def _mypaint(name: str) -> str:
    return f'{{{MYPAINT_NS}}}{name}'


def _archive_files(ora_path: str) -> dict[str, bytes]:
    with zipfile.ZipFile(ora_path) as zip_file:
        return {name: zip_file.read(name) for name in zip_file.namelist()}


def _layer_elements(stack_xml: bytes) -> dict[str, Element]:
    """Returns every `<layer>` and non-root `<stack>` element, keyed by name."""
    root = fromstring(stack_xml)
    root_stack = root.find('stack')
    assert root_stack is not None
    return {str(element.get('name')): element for element in root_stack.iter()
            if element is not root_stack and element.tag in ('layer', 'stack')}


def _write_foreign_elements_ora(path: str) -> None:
    """Writes an .ora file with foreign elements in `<image>`, `<stack>` and `<layer>`, and an unreferenced file."""
    image = QImage(4, 4, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.red)
    png_path = os.path.join(os.path.dirname(path), 'layer.png')
    assert image.save(png_path, 'PNG')
    with open(png_path, 'rb') as png_file:
        png_data = png_file.read()
    stack_xml = (f'<image xmlns:fx="{FOREIGN_NS}" w="4" h="4" version="0.0.5">'
                 '<fx:document-info author="someone"/>'
                 '<stack name="root">'
                 '<fx:guide position="2"/>'
                 '<layer name="painted" src="data/painted.png" x="0" y="0"><fx:history steps="3"/></layer>'
                 '</stack>'
                 '</image>')
    with zipfile.ZipFile(path, 'w') as zip_file:
        zip_file.writestr('mimetype', 'image/openraster')
        zip_file.writestr('stack.xml', stack_xml)
        zip_file.writestr('data/painted.png', png_data)
        zip_file.writestr('animation/timeline.json', '{"frames": 1}', compress_type=zipfile.ZIP_DEFLATED)


class OpenRasterForeignDataTest(IntraPaintTestCase):
    """Loads other programs' .ora files, saves them, and checks what the saved archive keeps."""

    def setUp(self) -> None:
        super().setUp()
        self._temp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.image_stack = ImageStack(STACK_SIZE, STACK_SIZE, STACK_SIZE, STACK_SIZE)
        self.reloaded_stack = ImageStack(STACK_SIZE, STACK_SIZE, STACK_SIZE, STACK_SIZE)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()
        super().tearDown()

    def _save(self, metadata: Optional[ImageMetadata] = None) -> str:
        saved_path = os.path.join(self._temp_dir.name, 'saved.ora')
        save_ora_image(self.image_stack, saved_path, ImageMetadata({'comment': 'metadata'}) if metadata is None
                       else metadata)
        return saved_path

    def _layer(self, name: str) -> Layer:
        matches = [layer for layer in self.image_stack.layers if layer.name == name]
        self.assertEqual(1, len(matches), f'layers named "{name}"')
        return matches[0]

    def _edit_pixels(self, name: str) -> None:
        layer = self._layer(name)
        assert isinstance(layer, ImageLayer)
        image = layer.image
        image.setPixelColor(0, 0, Qt.GlobalColor.magenta)
        layer.set_qimage(image)

    def test_mypaint_round_trip_keeps_foreign_data(self) -> None:
        """Every MyPaint attribute and file comes back unchanged, and the archive still renders the same."""
        read_ora_image(self.image_stack, MYPAINT_ORA)
        saved_path = self._save()
        original = _archive_files(MYPAINT_ORA)
        saved = _archive_files(saved_path)

        # Non-PNG and unreferenced files keep their bytes:
        for path in ('data/layer-01.svg', 'data/layer-02-strokemap.dat', 'data/layer-03-strokemap.dat',
                     'data/background-04-tile.png', 'data/mypaint-settings.json'):
            self.assertIn(path, saved)
            self.assertEqual(original[path], saved[path], path)
        # Layer PNGs keep their paths:
        for path in ('data/layer-02.png', 'data/layer-03.png', 'data/background-04.png'):
            self.assertIn(path, saved)

        saved_root = fromstring(saved[XML_FILE_NAME])
        original_root = fromstring(original[XML_FILE_NAME])
        for name in ('eotf', 'frame-active', 'json-settings', 'version'):
            self.assertEqual(original_root.get(_mypaint(name)), saved_root.get(_mypaint(name)), name)
        self.assertIn(b'xmlns:mypaint=', saved[XML_FILE_NAME], 'namespace prefix not kept')
        original_stack = original_root.find('stack')
        saved_stack = saved_root.find('stack')
        assert original_stack is not None and saved_stack is not None
        self.assertEqual('mypaint:spectral-wgm', saved_stack.get('composite-op'))

        original_layers = _layer_elements(original[XML_FILE_NAME])
        saved_layers = _layer_elements(saved[XML_FILE_NAME])
        self.assertEqual(set(original_layers), set(saved_layers))
        for name, original_element in original_layers.items():
            saved_element = saved_layers[name]
            for key in ('src', 'composite-op', _mypaint('strokemap'), _mypaint('background-tile')):
                self.assertEqual(original_element.get(key), saved_element.get(key), f'{key} of "{name}"')

        read_ora_image(self.reloaded_stack, saved_path)
        self.assert_images_equal(self.reloaded_stack.qimage(True), self.image_stack.qimage(True))

    def test_resaving_twice_keeps_foreign_data(self) -> None:
        """A file IntraPaint saved keeps the foreign data when loaded and saved again."""
        read_ora_image(self.image_stack, MYPAINT_ORA)
        first_save = _archive_files(self._save())
        read_ora_image(self.image_stack, os.path.join(self._temp_dir.name, 'saved.ora'))
        second_save = _archive_files(self._save())
        self.assertEqual(set(first_save), set(second_save))
        self.assertEqual(_layer_elements(first_save[XML_FILE_NAME]).keys(),
                         _layer_elements(second_save[XML_FILE_NAME]).keys())
        for name, element in _layer_elements(first_save[XML_FILE_NAME]).items():
            self.assertEqual(element.attrib, _layer_elements(second_save[XML_FILE_NAME])[name].attrib, name)

    def test_krita_round_trip_keeps_foreign_data(self) -> None:
        """Krita's resolution, stack offsets and unsupported composite op are kept. The resolution goes through the
        metadata, as DPI."""
        metadata = read_ora_image(self.image_stack, KRITA_ORA)
        self.assertEqual((300, 300), metadata.format_info['dpi'])
        saved = _archive_files(self._save(metadata))
        saved_root = fromstring(saved[XML_FILE_NAME])
        self.assertEqual('300', saved_root.get('xres'))
        self.assertEqual('300', saved_root.get('yres'))
        saved_layers = _layer_elements(saved[XML_FILE_NAME])
        self.assertEqual('krita:heat', saved_layers['Paint Layer 3'].get('composite-op'))
        self.assertEqual('data/layer2.png', saved_layers['Paint Layer 3'].get('src'))
        self.assertEqual('0', saved_layers['Group 6'].get('x'))
        self.assertEqual(CompositeMode.NORMAL, self._layer('Paint Layer 3').composition_mode)

    def test_edited_layer_drops_foreign_data(self) -> None:
        """An edited layer loses its foreign attributes and files but keeps its PNG path and composite op."""
        read_ora_image(self.image_stack, MYPAINT_ORA)
        self._edit_pixels('Layer 1')
        self._edit_pixels('background')
        saved = _archive_files(self._save())
        saved_layers = _layer_elements(saved[XML_FILE_NAME])

        edited = saved_layers['Layer 1']
        self.assertIsNone(edited.get(_mypaint('strokemap')))
        self.assertNotIn('data/layer-02-strokemap.dat', saved)
        self.assertEqual('data/layer-02.png', edited.get('src'))
        self.assertEqual('mypaint:spectral-wgm', edited.get('composite-op'))
        self.assertIsNone(saved_layers['background'].get(_mypaint('background-tile')))
        self.assertNotIn('data/background-04-tile.png', saved)

        unedited = saved_layers['Layer']
        self.assertEqual('data/layer-03-strokemap.dat', unedited.get(_mypaint('strokemap')))
        self.assertIn('data/layer-03-strokemap.dat', saved)

    def test_undone_edit_keeps_foreign_data(self) -> None:
        """A layer whose pixels and transform are back to their loaded state counts as unedited."""
        read_ora_image(self.image_stack, MYPAINT_ORA)
        layer = self._layer('Layer 1')
        assert isinstance(layer, ImageLayer)
        loaded_image = layer.image
        loaded_transform = layer.transform
        self._edit_pixels('Layer 1')
        layer.set_transform(QTransform.fromTranslate(5, 5))
        layer.set_qimage(loaded_image)
        layer.set_transform(loaded_transform)
        saved = _archive_files(self._save())
        self.assertEqual('data/layer-02-strokemap.dat',
                         _layer_elements(saved[XML_FILE_NAME])['Layer 1'].get(_mypaint('strokemap')))

    def test_moved_layer_drops_foreign_data(self) -> None:
        """Moving a layer counts as an edit."""
        read_ora_image(self.image_stack, MYPAINT_ORA)
        layer = self._layer('Layer')
        assert isinstance(layer, ImageLayer)
        layer.set_transform(QTransform.fromTranslate(3, 4))
        saved = _archive_files(self._save())
        self.assertIsNone(_layer_elements(saved[XML_FILE_NAME])['Layer'].get(_mypaint('strokemap')))

    def test_svg_layer_source_kept_until_edited(self) -> None:
        """A non-PNG layer source is written back as-is, and replaced by a new PNG once the layer is edited."""
        read_ora_image(self.image_stack, MYPAINT_ORA)
        layer = self._layer('Vectors')
        layer.set_locked(False)
        saved = _archive_files(self._save())
        self.assertEqual('data/layer-01.svg', _layer_elements(saved[XML_FILE_NAME])['Vectors'].get('src'))

        self._edit_pixels('Vectors')
        saved = _archive_files(self._save())
        src = str(_layer_elements(saved[XML_FILE_NAME])['Vectors'].get('src'))
        self.assertTrue(src.endswith('.png'), src)
        self.assertNotIn('data/layer-01.svg', saved)
        self.assertTrue(saved[src].startswith(b'\x89PNG'))

    def test_changed_composite_mode_replaces_foreign_op(self) -> None:
        """Choosing a supported composite mode replaces the unsupported one."""
        read_ora_image(self.image_stack, KRITA_ORA)
        self._layer('Paint Layer 3').set_composition_mode(CompositeMode.MULTIPLY)
        saved = _archive_files(self._save())
        self.assertEqual('svg:multiply', _layer_elements(saved[XML_FILE_NAME])['Paint Layer 3'].get('composite-op'))

    def test_removed_layer_drops_its_files(self) -> None:
        """Files named by a removed layer's attributes aren't saved."""
        read_ora_image(self.image_stack, MYPAINT_ORA)
        self.image_stack.remove_layer(self._layer('Layer'))
        saved = _archive_files(self._save())
        self.assertNotIn('data/layer-03-strokemap.dat', saved)
        self.assertNotIn('data/layer-03.png', saved)
        self.assertIn('data/layer-02-strokemap.dat', saved)

    def test_copied_layer_has_no_foreign_data(self) -> None:
        """A layer copy gets its own file and none of the original's foreign data."""
        read_ora_image(self.image_stack, MYPAINT_ORA)
        self.image_stack.copy_layer(self._layer('Layer'))
        self.assertIsNone(self._layer('Layer copy').ora_foreign_data)
        saved = _archive_files(self._save())
        saved_layers = _layer_elements(saved[XML_FILE_NAME])
        self.assertEqual('data/layer-03.png', saved_layers['Layer'].get('src'))
        self.assertNotEqual('data/layer-03.png', saved_layers['Layer copy'].get('src'))
        self.assertIsNone(saved_layers['Layer copy'].get(_mypaint('strokemap')))

    def test_foreign_elements_and_files_round_trip(self) -> None:
        """Foreign elements return to their positions, and unreferenced files keep their bytes and compression."""
        source_path = os.path.join(self._temp_dir.name, 'foreign.ora')
        _write_foreign_elements_ora(source_path)
        read_ora_image(self.image_stack, source_path)
        saved_path = self._save()
        root = fromstring(_archive_files(saved_path)[XML_FILE_NAME])
        self.assertEqual(f'{{{FOREIGN_NS}}}document-info', root[0].tag)
        self.assertEqual('someone', root[0].get('author'))
        stack = root.find('stack')
        assert stack is not None
        self.assertEqual(f'{{{FOREIGN_NS}}}guide', stack[0].tag)
        layer_element: Optional[Element] = stack.find('layer')
        assert layer_element is not None
        self.assertEqual('data/painted.png', layer_element.get('src'))
        self.assertEqual(f'{{{FOREIGN_NS}}}history', layer_element[0].tag)
        with zipfile.ZipFile(saved_path) as zip_file:
            info = zip_file.getinfo('animation/timeline.json')
            self.assertEqual(zipfile.ZIP_DEFLATED, info.compress_type)
            self.assertEqual(b'{"frames": 1}', zip_file.read(info))

    def test_new_image_clears_document_data(self) -> None:
        """Loading a non-.ora image drops the previous file's document-level foreign data."""
        read_ora_image(self.image_stack, MYPAINT_ORA)
        self.assertIsNotNone(self.image_stack.ora_foreign_data)
        self.image_stack.load_image(QImage(STACK_SIZE, QImage.Format.Format_ARGB32_Premultiplied))
        self.assertIsNone(self.image_stack.ora_foreign_data)
        saved = _archive_files(self._save())
        self.assertNotIn('data/mypaint-settings.json', saved)
        self.assertIsNone(fromstring(saved[XML_FILE_NAME]).get(_mypaint('eotf')))

    def test_native_file_has_no_foreign_data(self) -> None:
        """A file IntraPaint wrote from scratch loads with no foreign records, so nothing extra is saved."""
        self.image_stack.create_layer('plain', QImage(STACK_SIZE, QImage.Format.Format_ARGB32_Premultiplied))
        saved_path = self._save()
        read_ora_image(self.reloaded_stack, saved_path)
        data = self.reloaded_stack.ora_foreign_data
        assert data is not None
        self.assertEqual({}, data.files)
        self.assertEqual({}, data.image_attributes)
        self.assertTrue(all(layer.ora_foreign_data is None for layer in self.reloaded_stack.layers))
        self.assertTrue(REBUILT_FILES.isdisjoint(data.files))

    def test_unsafe_src_path_gets_new_name(self) -> None:
        """A foreign `src` that isn't already a normalized path inside the archive isn't kept.

        A path that leaves the archive can't load at all, so this uses one that normalizes to a different path."""
        source_path = os.path.join(self._temp_dir.name, 'unsafe.ora')
        image = QImage(4, 4, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.blue)
        png_path = os.path.join(self._temp_dir.name, 'layer.png')
        assert image.save(png_path, 'PNG')
        with open(png_path, 'rb') as png_file:
            png_data = png_file.read()
        with zipfile.ZipFile(source_path, 'w') as zip_file:
            zip_file.writestr('mimetype', 'image/openraster')
            zip_file.writestr('stack.xml', '<image w="4" h="4"><stack><layer name="up" src="data/./up.png"'
                                           ' x="0" y="0" composite-op="other:mode"/></stack></image>')
            zip_file.writestr('data/up.png', png_data)
        read_ora_image(self.image_stack, source_path)
        saved = _archive_files(self._save())
        src = str(_layer_elements(saved[XML_FILE_NAME])['up'].get('src'))
        self.assertTrue(src.startswith('data/') and '..' not in src, src)
        self.assertEqual('other:mode', _layer_elements(saved[XML_FILE_NAME])['up'].get('composite-op'))
