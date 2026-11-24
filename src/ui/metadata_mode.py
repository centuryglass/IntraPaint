"""Runs the standalone metadata mode, `IntraPaint.py --metadata [image]`, which opens only the metadata window.

`src/startup.py` calls `run_metadata_mode` before it imports `AppController`. Nothing this module imports may load the
editor, the generators or libmypaint, which `test/ui/metadata_mode_test.py` checks.
"""
import os
import sys
from typing import Optional, TextIO

from PIL import UnidentifiedImageError
from PySide6.QtWidgets import QApplication, QWidget

from src.config.application_config import AppConfig
from src.image.metadata_file import read_file_metadata
from src.ui.modal.modal_utils import open_image_file, show_error_dialog
from src.ui.theme import apply_appearance_config
from src.ui.window.metadata_window import metadata_rows
from src.ui.window.standalone_metadata_window import StandaloneMetadataWindow, ICC_KEPT_ROW_VALUE

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.metadata_mode'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


OPEN_FAILED_TITLE = _tr('Opening the image failed')
PRINT_NEEDS_IMAGE = _tr('--print needs an image: IntraPaint.py --metadata <image> --print')
NO_METADATA = _tr('{file_name} has no metadata.')


def print_metadata(file_path: str, output: TextIO = sys.stdout) -> None:
    """Writes a file's metadata to `output`: one tab-separated source, name and value line per All metadata row.

    Backslashes, tabs and line breaks in names and values are escaped as in a Python string literal, so each row stays
    on one line.
    """
    rows = metadata_rows(read_file_metadata(file_path), ICC_KEPT_ROW_VALUE)
    if len(rows) == 0:
        print(NO_METADATA.format(file_name=os.path.basename(file_path)), file=output)
    for row in rows:
        print('\t'.join(_escaped(text) for text in (row.source, row.name, row.value)), file=output)


def _escaped(text: str) -> str:
    return text.replace('\\', '\\\\').replace('\t', '\\t').replace('\r', '\\r').replace('\n', '\\n')


def run_metadata_mode(app: QApplication, image_path: str, print_only: bool) -> int:
    """Runs the metadata mode, and returns the process exit code.

    With `print_only`, prints the metadata of `image_path` and returns without showing a window. Otherwise it applies
    the configured theme, opens the metadata window on `image_path` (asking for a file if it is empty), and runs the
    event loop until the window closes.
    """
    if print_only:
        if image_path == '':
            print(PRINT_NEEDS_IMAGE, file=sys.stderr)
            return 2
        try:
            print_metadata(image_path)
        except (OSError, ValueError, UnidentifiedImageError) as err:
            print(f'{OPEN_FAILED_TITLE}: {err}', file=sys.stderr)
            return 1
        return 0
    apply_appearance_config(AppConfig())
    if image_path == '':
        dialog_parent = QWidget()
        selected_path = open_image_file(dialog_parent)
        dialog_parent.deleteLater()
        if selected_path is None:
            return 0
        image_path = selected_path
    try:
        window = StandaloneMetadataWindow(image_path)
    except (OSError, ValueError, UnidentifiedImageError) as err:
        show_error_dialog(None, OPEN_FAILED_TITLE, err)
        return 1
    window.show()
    return app.exec()
