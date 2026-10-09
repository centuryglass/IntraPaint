"""Test which image formats IntraPaint can load and save."""
import io
import os
import tempfile
import unittest

from PIL import Image, UnidentifiedImageError
from PySide6.QtWidgets import QApplication

from src.util.visual.image_format_utils import IMAGE_READ_FORMATS, IMAGE_WRITE_FORMATS, load_image, save_image


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
        """EPS and PS aren't offered for loading or saving, since Pillow reads them with Ghostscript."""
        for file_format in ('EPS', 'PS'):
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
