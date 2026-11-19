"""Tests the standalone metadata mode's startup: its imports stay light, and `--print` writes the metadata."""
import io
import os
import subprocess
import sys
import tempfile

from PIL import Image, PngImagePlugin
from PySide6.QtWidgets import QApplication

from src.ui.metadata_mode import print_metadata, run_metadata_mode
from src.util.shared_constants import PROJECT_DIR
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

# Modules the metadata mode must not load: the editor, the image model, the generators and libmypaint.
_HEAVY_MODULES = ('src.controller', 'src.image.layers', 'src.image.mypaint', 'src.tools', 'src.ui.window.main_window')

_IMPORT_SCRIPT = f'''
import sys
from PySide6.QtWidgets import QApplication
app = QApplication([])
import src.ui.metadata_mode
loaded = [name for name in sys.modules if name.startswith({_HEAVY_MODULES!r})]
print('LOADED:' + ','.join(sorted(loaded)))
'''


class MetadataModeTest(IntraPaintTestCase):
    """Tests the metadata mode's import chain and its `--print` output."""

    def setUp(self) -> None:
        super().setUp()
        self._temp_dir = tempfile.TemporaryDirectory()
        self.image_path = os.path.join(self._temp_dir.name, 'image.png')
        info = PngImagePlugin.PngInfo()
        info.add_itxt('parameters', 'a cat\nSteps: 20')
        info.add_itxt('tab\tkey', 'back\\slash')
        Image.new('RGB', (4, 4)).save(self.image_path, pnginfo=info)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()
        super().tearDown()

    def test_imports_skip_the_editor(self) -> None:
        """Importing the metadata mode loads none of the editor, the generators or libmypaint."""
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        result = subprocess.run([sys.executable, '-c', _IMPORT_SCRIPT], capture_output=True, text=True, check=True,
                                cwd=PROJECT_DIR, env=env)
        loaded_line = [line for line in result.stdout.splitlines() if line.startswith('LOADED:')]
        self.assertEqual(['LOADED:'], loaded_line)

    def test_print_writes_one_line_per_row(self) -> None:
        """Each row prints as one tab-separated line, with line breaks, tabs and backslashes escaped."""
        output = io.StringIO()
        print_metadata(self.image_path, output)
        self.assertEqual(['Text\tparameters\ta cat\\nSteps: 20', 'Text\ttab\\tkey\tback\\\\slash'],
                         output.getvalue().splitlines())

    def test_print_without_metadata(self) -> None:
        path = os.path.join(self._temp_dir.name, 'plain.png')
        Image.new('RGB', (4, 4)).save(path)
        output = io.StringIO()
        print_metadata(path, output)
        self.assertEqual('plain.png has no metadata.', output.getvalue().strip())

    def test_print_exit_codes(self) -> None:
        """`--print` fails with no image or an unreadable one, without opening a window."""
        self.assertEqual(2, run_metadata_mode(app, '', True))
        self.assertEqual(1, run_metadata_mode(app, os.path.join(self._temp_dir.name, 'missing.png'), True))
        self.assertEqual(0, run_metadata_mode(app, self.image_path, True))
