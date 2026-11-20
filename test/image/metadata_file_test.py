"""Tests that metadata-only writes replace a file's metadata and keep its pixels, for each write path."""
import io
import os
import sys
import tempfile
import zipfile

import numpy as np
from PIL import Image, ImageSequence, ExifTags, PngImagePlugin
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from src.image.image_metadata import ImageMetadata, PARAMETERS_KEY, COMMENT_KEY, XMP_INFO_KEY
from src.image.layers.image_stack import ImageStack
from src.image.metadata_file import read_file_metadata, write_file_metadata, metadata_write_method, \
    MetadataWriteMethod, save_metadata_copy, png_with_metadata, jpeg_with_metadata
from src.image.open_raster import save_ora_image, read_ora_image
from src.util.visual.image_format_utils import save_image_with_metadata
from test.base_test_case import IntraPaintTestCase
from test.image.image_metadata_test import photo_metadata

app = QApplication.instance() or QApplication(sys.argv)

PARAMETERS = 'a cat\nNegative prompt: blur\nSteps: 20, Sampler: Euler a, CFG scale: 7, Seed: 5, Size: 24x16'
EDITED = PARAMETERS.replace('a cat', 'a dög')
SIZE = (24, 16)


def _noise(mode: str, seed: int = 0) -> Image.Image:
    """Returns a noisy image, which a lossy re-encode would visibly change."""
    channels = {'RGB': 3, 'RGBA': 4, 'L': 1}[mode]
    pixels = np.random.default_rng(seed).integers(0, 256, (SIZE[1], SIZE[0], channels), dtype=np.uint8)
    return Image.fromarray(pixels.squeeze(), mode)


def _pixels(path: str) -> list[bytes]:
    """Returns every frame's decoded pixels, without any color conversion."""
    with Image.open(path) as image:
        return [frame.convert('RGBA').tobytes() for frame in ImageSequence.Iterator(image)]


def _png_text(text: dict[str, str]) -> PngImagePlugin.PngInfo:
    info = PngImagePlugin.PngInfo()
    for key, value in text.items():
        info.add_itxt(key, value)
    return info


def _jpeg_scan_data(data: bytes) -> bytes:
    """Returns a JPEG's image data, from its first start-of-scan marker on."""
    return data[data.index(b'\xff\xda'):]


class MetadataFileTest(IntraPaintTestCase):
    """Writes edited metadata into a file of each format, and reads it back."""

    def setUp(self) -> None:
        super().setUp()
        self._temp_dir = tempfile.TemporaryDirectory()
        self.dir = self._temp_dir.name

    def tearDown(self) -> None:
        self._temp_dir.cleanup()
        super().tearDown()

    def _path(self, name: str) -> str:
        return os.path.join(self.dir, name)

    def _edit_and_check(self, path: str, expected_method: MetadataWriteMethod = MetadataWriteMethod.IN_PLACE,
                        allow_lossy: bool = False) -> ImageMetadata:
        """Replaces a file's parameters, checks its pixels are unchanged, and returns the reloaded metadata."""
        self.assertEqual(expected_method, metadata_write_method(path))
        pixels = _pixels(path)
        metadata = read_file_metadata(path)
        self.assertEqual(PARAMETERS, metadata.parameters)
        metadata.set_parameters(EDITED)
        write_file_metadata(path, metadata, allow_lossy)
        self.assertEqual(pixels, _pixels(path))
        reloaded = read_file_metadata(path)
        self.assertEqual(EDITED, reloaded.parameters)
        return reloaded

    def test_png(self) -> None:
        """PNG text entries and EXIF are replaced. Other text entries and the color profile are kept."""
        path = self._path('image.png')
        info = _png_text({PARAMETERS_KEY: PARAMETERS, 'other': 'kept'})
        _noise('RGBA').save(path, pnginfo=info, icc_profile=b'not a real profile')
        reloaded = self._edit_and_check(path)
        self.assertEqual('kept', reloaded.text['other'])
        self.assertEqual(b'not a real profile', reloaded.format_info['icc_profile'])

    def test_apng_keeps_frames(self) -> None:
        """An animated PNG keeps every frame and its durations."""
        path = self._path('animation.png')
        frames = [_noise('RGBA', seed) for seed in range(3)]
        info = _png_text({PARAMETERS_KEY: PARAMETERS})
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=[50, 60, 70], pnginfo=info)
        self._edit_and_check(path)
        with Image.open(path) as image:
            self.assertEqual(3, image.n_frames)

    def test_png_exif(self) -> None:
        """EXIF tags edited in a PNG are written as its eXIf chunk."""
        path = self._path('exif.png')
        exif = Image.Exif()
        exif[ExifTags.Base.Artist] = 'Someone'
        info = _png_text({PARAMETERS_KEY: PARAMETERS})
        _noise('RGB').save(path, pnginfo=info, exif=exif)
        metadata = read_file_metadata(path)
        metadata.set_exif_text(None, ExifTags.Base.Artist, 'Someone else')
        write_file_metadata(path, metadata)
        self.assertEqual('Someone else', read_file_metadata(path).exif[ExifTags.Base.Artist])

    def test_jpeg_keeps_image_data(self) -> None:
        """A JPEG's scan data is byte-identical after a metadata-only write, and every part of its metadata is kept."""
        path = self._path('photo.jpg')
        source = photo_metadata()
        source.set_parameters(PARAMETERS)
        save_image_with_metadata(_noise('RGB'), path, source)
        with open(path, 'rb') as file:
            original = file.read()
        reloaded = self._edit_and_check(path)
        with open(path, 'rb') as file:
            self.assertEqual(_jpeg_scan_data(original), _jpeg_scan_data(file.read()))
        self.assertEqual('a camera note', reloaded.text[COMMENT_KEY])
        self.assertEqual(source.xmp_packet, reloaded.xmp_packet)
        self.assertEqual(source.iptc_data, reloaded.iptc_data)
        self.assertEqual('N', reloaded.exif.get_ifd(ExifTags.IFD.GPSInfo)[ExifTags.GPS.GPSLatitudeRef])

    def test_jpeg_remove_all(self) -> None:
        """Removing all metadata leaves a JPEG with no EXIF, XMP, IPTC or comment segments, and keeps its JFIF one."""
        path = self._path('photo.jpg')
        source = photo_metadata()
        _noise('RGB').save(path, exif=source.exif, comment='note', xmp=source.format_info[XMP_INFO_KEY])
        metadata = read_file_metadata(path)
        metadata.remove_all()
        write_file_metadata(path, metadata)
        reloaded = read_file_metadata(path)
        self.assertFalse(reloaded.has_removable_data)
        with open(path, 'rb') as file:
            data = file.read()
        self.assertEqual(b'JFIF', data[6:10])

    def test_jpeg_segment_too_long(self) -> None:
        """A comment too long for a JPEG segment raises, so the write fails instead of dropping it."""
        path = self._path('photo.jpg')
        _noise('RGB').save(path)
        with open(path, 'rb') as file:
            data = file.read()
        with self.assertRaises(ValueError):
            jpeg_with_metadata(data, ImageMetadata({COMMENT_KEY: 'x' * 70000}))

    def test_webp(self) -> None:
        """Lossy, lossless and animated WebP files keep their image chunks, gaining a VP8X header where needed."""
        for name, save_args in (('lossy.webp', {'quality': 50}), ('lossless.webp', {'lossless': True}),
                                ('alpha.webp', {'lossless': True})):
            with self.subTest(name=name):
                path = self._path(name)
                _noise('RGBA' if name == 'alpha.webp' else 'RGB').save(path, **save_args)
                metadata = read_file_metadata(path)
                metadata.set_parameters(PARAMETERS)
                pixels = _pixels(path)
                write_file_metadata(path, metadata)
                self.assertEqual(pixels, _pixels(path))
                self._edit_and_check(path)
        path = self._path('animation.webp')
        frames = [_noise('RGB', seed) for seed in range(2)]
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=[40, 80])
        metadata = read_file_metadata(path)
        metadata.set_parameters(PARAMETERS)
        write_file_metadata(path, metadata)
        self._edit_and_check(path)
        with Image.open(path) as image:
            self.assertEqual(2, image.n_frames)

    def test_gif(self) -> None:
        """Still and animated GIFs keep every frame, with the parameters as their comment."""
        path = self._path('still.gif')
        _noise('RGB').convert('P').save(path, comment=PARAMETERS)
        self._edit_and_check(path)
        path = self._path('animation.gif')
        frames = [_noise('RGB', seed).convert('P') for seed in range(3)]
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=100, loop=0, comment=PARAMETERS)
        self._edit_and_check(path)
        with Image.open(path) as image:
            self.assertEqual(3, image.n_frames)
            self.assertEqual(0, image.info['loop'])

    def test_tiff_reencodes_every_page(self) -> None:
        """A TIFF is re-encoded losslessly, keeping every page."""
        path = self._path('pages.tiff')
        pages = [_noise('RGB', seed) for seed in range(2)]
        exif = Image.Exif()
        exif[ExifTags.Base.ImageDescription] = PARAMETERS
        pages[0].save(path, save_all=True, append_images=pages[1:], exif=exif, compression='tiff_lzw')
        self._edit_and_check(path, MetadataWriteMethod.REENCODE)
        with Image.open(path) as image:
            self.assertEqual(2, image.n_frames)
            self.assertEqual('tiff_lzw', image.info['compression'])

    def test_jpeg_compressed_tiff_needs_permission(self) -> None:
        """A JPEG-compressed TIFF is only re-encoded when a lossy write is allowed."""
        path = self._path('lossy.tiff')
        exif = Image.Exif()
        exif[ExifTags.Base.ImageDescription] = PARAMETERS
        _noise('RGB').save(path, exif=exif, compression='jpeg')
        self.assertEqual(MetadataWriteMethod.LOSSY_REENCODE, metadata_write_method(path))
        with self.assertRaises(ValueError):
            write_file_metadata(path, read_file_metadata(path))
        metadata = read_file_metadata(path)
        metadata.set_parameters(EDITED)
        write_file_metadata(path, metadata, allow_lossy=True)
        self.assertEqual(EDITED, read_file_metadata(path).parameters)

    def test_jpeg_2000(self) -> None:
        """A JPEG 2000 file is re-encoded losslessly."""
        path = self._path('image.jp2')
        _noise('RGB').save(path, comment=PARAMETERS)
        self._edit_and_check(path, MetadataWriteMethod.REENCODE)

    def test_unsupported_format(self) -> None:
        """Formats that hold no metadata are refused, and left unchanged."""
        path = self._path('image.bmp')
        _noise('RGB').save(path)
        self.assertEqual(MetadataWriteMethod.UNSUPPORTED, metadata_write_method(path))
        with open(path, 'rb') as file:
            original = file.read()
        with self.assertRaises(ValueError):
            write_file_metadata(path, ImageMetadata({PARAMETERS_KEY: PARAMETERS}))
        with open(path, 'rb') as file:
            self.assertEqual(original, file.read())
        self.assertEqual([], [name for name in os.listdir(self.dir) if name != 'image.bmp'])

    def test_mismatched_extension(self) -> None:
        """A file whose contents don't match its extension is refused, and left unchanged."""
        path = self._path('really_a_jpeg.png')
        _noise('RGB').save(path, 'JPEG')
        with self.assertRaises(ValueError):
            write_file_metadata(path, ImageMetadata({PARAMETERS_KEY: PARAMETERS}))
        with open(path, 'rb') as file:
            self.assertEqual(b'\xff\xd8', file.read(2))

    def test_ora_keeps_layers(self) -> None:
        """An .ora file's metadata is replaced without loading it, and every other archive member is unchanged."""
        path = self._path('layers.ora')
        image_stack = ImageStack(QSize(*SIZE), QSize(8, 8), QSize(8, 8), QSize(64, 64))
        layer_image = QImage(QSize(*SIZE), QImage.Format.Format_ARGB32_Premultiplied)
        layer_image.fill(QColor(10, 20, 30))
        image_stack.create_layer('one', layer_image)
        image_stack.create_layer('two', layer_image)
        source = photo_metadata()
        source.set_parameters(PARAMETERS)
        source.format_info['dpi'] = (300, 300)
        save_ora_image(image_stack, path, source)
        with zipfile.ZipFile(path) as archive:
            before = {info.filename: archive.read(info) for info in archive.infolist()}
            first_member = archive.infolist()[0]
        metadata = read_file_metadata(path)
        self.assertEqual(PARAMETERS, metadata.parameters)
        self.assertEqual(source.iptc_data, metadata.iptc_data)
        metadata.set_parameters(EDITED)
        metadata.remove_location()
        write_file_metadata(path, metadata)
        with zipfile.ZipFile(path) as archive:
            after = {info.filename: archive.read(info) for info in archive.infolist()}
            self.assertEqual('mimetype', archive.infolist()[0].filename)
            self.assertEqual(first_member.compress_type, archive.infolist()[0].compress_type)
        changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
        self.assertTrue(all(name in ('extended_data.xml', 'META-INF/metadata.xml') or name.startswith(
            'data/extensions/metadata/') for name in changed), changed)
        reloaded_stack = ImageStack(QSize(1, 1), QSize(8, 8), QSize(8, 8), QSize(64, 64))
        reloaded = read_ora_image(reloaded_stack, path)
        self.assertEqual(EDITED, reloaded.parameters)
        self.assertEqual((300, 300), reloaded.format_info['dpi'])
        self.assertEqual(2, reloaded_stack.layer_stack.count)
        self.assertFalse(reloaded.has_location_data)

    def test_save_copy_in_another_format(self) -> None:
        """Save as to another format re-encodes the pixels with the metadata, and leaves the source unchanged."""
        source_path = self._path('source.png')
        info = _png_text({PARAMETERS_KEY: PARAMETERS})
        _noise('RGB').save(source_path, pnginfo=info)
        with open(source_path, 'rb') as file:
            original = file.read()
        metadata = read_file_metadata(source_path)
        metadata.set_parameters(EDITED)
        for target_name in ('copy.webp', 'copy.png', 'copy.jpg'):
            with self.subTest(target=target_name):
                target_path = self._path(target_name)
                save_metadata_copy(source_path, target_path, metadata)
                self.assertEqual(EDITED, read_file_metadata(target_path).parameters)
        self.assertEqual(_pixels(source_path), _pixels(self._path('copy.png')))
        with open(source_path, 'rb') as file:
            self.assertEqual(original, file.read())
        with self.assertRaises(ValueError):
            save_metadata_copy(source_path, self._path('copy.ora'), metadata)

    def test_png_chunk_order(self) -> None:
        """New PNG chunks follow IHDR, and the rest keep their order."""
        buffer = io.BytesIO()
        _noise('RGB').save(buffer, 'PNG')
        data = png_with_metadata(buffer.getvalue(), ImageMetadata({PARAMETERS_KEY: PARAMETERS}))
        self.assertEqual(b'IHDR', data[12:16])
        ihdr_end = 8 + 12 + 13
        self.assertEqual(b'iTXt', data[ihdr_end + 4:ihdr_end + 8])

