"""Test which image formats IntraPaint can load and save."""
import io
import os
import tempfile
import unittest
from typing import Optional

from PIL import Image, UnidentifiedImageError
from PySide6.QtWidgets import QApplication

from src.util.visual.image_format_utils import IMAGE_READ_FORMATS, IMAGE_WRITE_FORMATS, \
    IMAGE_FORMATS_SUPPORTING_METADATA, load_image, save_image, count_image_frames, load_image_frames


app = QApplication.instance() or QApplication([])


def _write_eps_file(directory: str, file_name: str) -> str:
    """Writes a small EPS image under any file name, and returns its path. Pillow can still write EPS itself."""
    eps_data = io.BytesIO()
    Image.new('RGB', (8, 8)).save(eps_data, 'EPS')
    file_path = os.path.join(directory, file_name)
    with open(file_path, 'wb') as eps_file:
        eps_file.write(eps_data.getvalue())
    return file_path


class TestImageFormatUtils(unittest.TestCase):
    """Test which image formats IntraPaint can load and save."""

    def test_postscript_formats_unsupported(self) -> None:
        """EPS and PS aren't offered for loading or saving, since Pillow and kimageformats read them with Ghostscript."""
        for file_format in ('EPS', 'EPSF', 'EPSI', 'PS'):
            self.assertNotIn(file_format, IMAGE_READ_FORMATS)
            self.assertNotIn(file_format, IMAGE_WRITE_FORMATS)

    def test_load_postscript(self) -> None:
        """PostScript files are rejected before they reach Ghostscript."""
        with tempfile.TemporaryDirectory() as temp_dir:
            for file_name in ('image.eps', 'image.ps'):
                with self.assertRaises(UnidentifiedImageError, msg=file_name):
                    load_image(_write_eps_file(temp_dir, file_name))

    def test_load_disguised_postscript(self) -> None:
        """PostScript files named like a supported format are rejected too, since Pillow goes by file contents."""
        with tempfile.TemporaryDirectory() as temp_dir:
            for file_name in ('image.png', 'image.jpg'):
                with self.assertRaises(UnidentifiedImageError, msg=file_name):
                    load_image(_write_eps_file(temp_dir, file_name))

    def test_load_disguised_postscript_with_qt(self) -> None:
        """PostScript files named like a format Qt loads are never decoded, since Qt also goes by file contents.

        Qt raises if an installed plugin identifies the file as EPS, and returns a null image if none can read it.
        """
        self.assertNotIn('BMP', IMAGE_FORMATS_SUPPORTING_METADATA)
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = _write_eps_file(temp_dir, 'image.bmp')
            try:
                loaded_image, _, _ = load_image(file_path)
            except UnidentifiedImageError:
                return
            self.assertTrue(loaded_image.isNull())

    def test_save_postscript(self) -> None:
        """Saving as EPS or PS fails without writing a file."""
        image = Image.new('RGB', (8, 8))
        with tempfile.TemporaryDirectory() as temp_dir:
            for file_name in ('image.eps', 'image.ps'):
                file_path = os.path.join(temp_dir, file_name)
                with self.assertRaises(ValueError, msg=file_name):
                    save_image(image, file_path)
                self.assertFalse(os.path.exists(file_path), file_name)

    def test_undecodable_formats_unsupported(self) -> None:
        """Formats Pillow identifies but can't decode or encode aren't offered."""
        for file_format in ('BUFR', 'GRIB', 'H5', 'HDF', 'MPG', 'MPEG'):
            self.assertNotIn(file_format, IMAGE_READ_FORMATS)
            self.assertNotIn(file_format, IMAGE_WRITE_FORMATS)
        for file_format in ('WMF', 'EMF'):
            self.assertNotIn(file_format, IMAGE_WRITE_FORMATS)
            if not hasattr(Image.core, 'drawwmf'):
                self.assertNotIn(file_format, IMAGE_READ_FORMATS)

    def test_save_and_load_every_format(self) -> None:
        """Every offered save format saves, and loads again if it is also offered for loading."""
        image = Image.new('RGBA', (32, 32), (200, 50, 50, 255))
        with tempfile.TemporaryDirectory() as temp_dir:
            for file_format in sorted(IMAGE_WRITE_FORMATS - {'ORA'}):
                with self.subTest(file_format=file_format):
                    file_path = os.path.join(temp_dir, f'image.{file_format.lower()}')
                    save_image(image, file_path)
                    self.assertTrue(os.path.isfile(file_path))
                    if file_format in IMAGE_READ_FORMATS:
                        loaded_image, _, _ = load_image(file_path)
                        self.assertFalse(loaded_image.isNull())


class TestImageFrames(unittest.TestCase):
    """Test loading every frame of animations and multi-page images."""

    COLORS = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
    DURATIONS = [100, 200, 50]

    def _save_frames(self, directory: str, extension: str, pil_format: Optional[str] = None) -> str:
        frames = [Image.new('RGBA', (16, 16), color) for color in self.COLORS]
        file_path = os.path.join(directory, f'animation.{extension}')
        frames[0].save(file_path, pil_format, save_all=True, append_images=frames[1:], duration=self.DURATIONS,
                       loop=0)
        return file_path

    def test_load_animation_frames(self) -> None:
        """Every frame of an animation loads in order, with its duration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            for extension, pil_format in (('gif', None), ('webp', None), ('png', None), ('apng', 'PNG'),
                                          ('avif', None)):
                with self.subTest(extension=extension):
                    file_path = self._save_frames(temp_dir, extension, pil_format)
                    self.assertEqual(count_image_frames(file_path), len(self.COLORS))
                    frames = load_image_frames(file_path)
                    self.assertEqual([frame.duration_ms for frame in frames], self.DURATIONS)
                    for frame, color in zip(frames, self.COLORS):
                        pixel = frame.image.pixelColor(8, 8)
                        for actual, expected in zip(pixel.getRgb(), color):
                            self.assertAlmostEqual(actual, expected, delta=8)

    def test_load_tiff_pages(self) -> None:
        """Each page of a multi-page TIFF loads as a frame with no duration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = self._save_frames(temp_dir, 'tiff')
            frames = load_image_frames(file_path)
            self.assertEqual([frame.duration_ms for frame in frames], [None, None, None])

    def test_single_frame_formats(self) -> None:
        """Single images, multi-frame formats outside ANIMATION_READ_FORMATS and Qt-only files load one frame."""
        with tempfile.TemporaryDirectory() as temp_dir:
            png_path = os.path.join(temp_dir, 'still.png')
            Image.new('RGBA', (16, 16)).save(png_path)
            mpo_path = os.path.join(temp_dir, 'stereo.mpo')
            Image.new('RGB', (16, 16)).save(mpo_path, 'MPO', save_all=True, append_images=[Image.new('RGB', (16, 16))])
            with Image.open(mpo_path) as mpo_image:
                self.assertGreater(getattr(mpo_image, 'n_frames', 1), 1)
            svg_path = os.path.join(temp_dir, 'still.svg')
            with open(svg_path, 'w', encoding='utf-8') as svg_file:
                svg_file.write('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"/>')
            for file_path in (png_path, mpo_path):
                with self.subTest(file_path=file_path):
                    self.assertEqual(count_image_frames(file_path), 1)
                    self.assertEqual(len(load_image_frames(file_path)), 1)
            self.assertEqual(count_image_frames(svg_path), 1)
