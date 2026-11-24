"""Tests `src.startup.main`, the application's entry point, in the modes that open no window."""
import contextlib
import io
import os
import tempfile
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src import startup
from test.base_test_case import IntraPaintTestCase, TEST_RESOURCE_DIR

app = QApplication.instance()


class StartupTest(IntraPaintTestCase):
    """Tests `main` with arguments that finish before the editor loads."""

    def setUp(self) -> None:
        super().setUp()
        self._log_dir = tempfile.TemporaryDirectory()
        patcher = patch.object(startup, 'LOG_DIR', self._log_dir.name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        for handler in list(startup.logging.getLogger().handlers):
            if isinstance(handler, startup.RotatingFileHandler) and handler.baseFilename.startswith(self._log_dir.name):
                startup.logging.getLogger().removeHandler(handler)
                handler.close()
        self._log_dir.cleanup()
        super().tearDown()

    def test_metadata_print_writes_metadata_without_a_window(self) -> None:
        """`--metadata IMAGE --print` prints the image's metadata and returns 0, with no window."""
        image_path = os.path.join(TEST_RESOURCE_DIR, 'test_images', 'circle-10px.png')
        with patch('src.ui.metadata_mode.print_metadata') as print_metadata:
            result = startup.main(['--metadata', image_path, '--print'])
        self.assertEqual(0, result)
        print_metadata.assert_called_once_with(image_path)

    def test_print_without_an_image_fails(self) -> None:
        """`--print` with no image returns exit code 2."""
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, startup.main(['--metadata', '--print']))

    def test_parser_defaults(self) -> None:
        """The parser's `--mode` defaults to auto and `--metadata` defaults to off."""
        args = startup.build_parser().parse_args([])
        self.assertEqual('auto', args.mode)
        self.assertIsNone(args.metadata)
