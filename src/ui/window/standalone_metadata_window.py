"""The metadata window of the standalone metadata mode (`IntraPaint.py --metadata`), which edits a file directly.

"Save" writes the edits into the file with `src/image/metadata_file.py`, keeping its pixels, then shows what the file
now holds. "Save as..." writes a copy and switches to it. Closing with unsaved edits asks first. There is no editor, so
the buttons that read from or write to its settings are hidden.
"""
import os
from typing import Optional

from PIL import UnidentifiedImageError
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from src.image.metadata_file import MetadataWriteMethod, metadata_write_method, read_file_metadata, \
    save_metadata_copy, file_format, METADATA_WRITE_FORMATS
from src.image.metadata_save_rules import format_name
from src.ui.modal.modal_utils import open_image_file, SAVE_IMAGE_MODE, request_unsaved_changes_choice, \
    UNSAVED_SAVE, UNSAVED_DISCARD, request_confirmation, show_error_dialog
from src.ui.window.metadata_window import MetadataWindow, SAVE_FAILED_TITLE, logger
from src.util.visual.image_format_utils import IMAGE_WRITE_FORMATS

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.window.standalone_metadata_window'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


WINDOW_TITLE = _tr('{file_name} - Image metadata')
SAVE_LABEL = _tr('Save')
SAVE_AS_LABEL = _tr('Save as...')
SAVE_AS_TOOLTIP = _tr('Save a copy with this metadata. A copy in another format is re-encoded from the image.')
UNSAVED_MESSAGE = _tr('Changes are not kept until you click "Save".')
ICC_KEPT_ROW_VALUE = _tr('Embedded. Saving keeps it, since the image\'s colors depend on it.')
CLOSE_WITHOUT_SAVING_LABEL = _tr('Close without saving')
SAVE_COPY_AS_PNG_LABEL = _tr('Save a copy as PNG')
UNSUPPORTED_TITLE = _tr('{file_format} files can\'t hold this metadata')
UNSUPPORTED_MESSAGE = _tr('IntraPaint can\'t write metadata into {file_format} files. Save a PNG copy of the image with'
                          ' the metadata instead?')
PNG_EXTENSION = '.png'

# The extensions Save as offers: the writable ones `write_file_metadata` can write metadata into.
_METADATA_SAVE_FORMATS = frozenset(ext for ext in IMAGE_WRITE_FORMATS if format_name(ext) in METADATA_WRITE_FORMATS)


class StandaloneMetadataWindow(MetadataWindow):
    """Views and edits the metadata of one image file, and saves the edits into it."""

    _confirm_label = SAVE_LABEL
    _unapplied_message = UNSAVED_MESSAGE
    _icc_row_value = ICC_KEPT_ROW_VALUE

    def __init__(self, file_path: str) -> None:
        """Reads the file's metadata and shows it. Raises OSError or ValueError if the file can't be read."""
        self._file_path = file_path
        self._in_close_event = False
        super().__init__(read_file_metadata(file_path), show_editor_buttons=False)
        self._save_as_button = self._footer.add_secondary_button(SAVE_AS_LABEL)
        self._save_as_button.setToolTip(SAVE_AS_TOOLTIP)
        self._save_as_button.clicked.connect(self.save_as)
        self._update_title()

    @property
    def file_path(self) -> str:
        """The file the window shows and saves to."""
        return self._file_path

    def _file_path_for_saves(self) -> str:
        return self._file_path

    def apply_changes(self) -> None:
        """Saves the edits into the file. The confirm button calls this."""
        self.save()

    def save(self) -> bool:
        """Writes the edits into the file, asking first if that loses quality, and returns whether it was written.

        A format that holds no metadata offers a PNG copy instead.
        """
        method = metadata_write_method(self._file_path)
        if method == MetadataWriteMethod.UNSUPPORTED:
            name = file_format(self._file_path)
            if request_confirmation(self, UNSUPPORTED_TITLE.format(file_format=name),
                                    UNSUPPORTED_MESSAGE.format(file_format=name), confirm_label=SAVE_COPY_AS_PNG_LABEL):
                return self.save_as(os.path.splitext(self._file_path)[0] + PNG_EXTENSION)
            return False
        if method == MetadataWriteMethod.LOSSY_REENCODE:
            choice = self._confirm_lossy_write(self._file_path, (SAVE_COPY_AS_PNG_LABEL,))
            if choice is None:
                return False
            if choice == 1:
                return self.save_as(os.path.splitext(self._file_path)[0] + PNG_EXTENSION)
            return self._write_and_reload(self._file_path, allow_lossy=True)
        return self._write_and_reload(self._file_path)

    def save_as(self, suggested_path: Optional[str] = None) -> bool:
        """Asks where to save a copy with the edited metadata, saves it, and switches the window to the copy.

        Returns whether the copy was saved.
        """
        target_path = open_image_file(self, SAVE_IMAGE_MODE, suggested_path or self._file_path, _METADATA_SAVE_FORMATS)
        if target_path is None:
            return False
        if os.path.splitext(target_path)[1] == '':
            target_path += os.path.splitext(self._file_path)[1]
        allow_lossy = False
        if file_format(target_path) == file_format(self._file_path) \
                and metadata_write_method(self._file_path) == MetadataWriteMethod.LOSSY_REENCODE:
            if self._confirm_lossy_write(target_path) != 0:
                return False
            allow_lossy = True
        return self._write_and_reload(target_path, allow_lossy)

    def _write_and_reload(self, target_path: str, allow_lossy: bool = False) -> bool:
        """Writes the edits to `target_path`, then shows the metadata that file now holds."""
        try:
            save_metadata_copy(self._file_path, target_path, self._metadata.copy(), allow_lossy)
            saved = read_file_metadata(target_path)
        except (OSError, ValueError, UnidentifiedImageError) as err:
            logger.error(f'Saving metadata to {target_path} failed: {err}')
            show_error_dialog(self, SAVE_FAILED_TITLE, err)
            return False
        self._file_path = target_path
        self._update_title()
        self.set_metadata(saved)
        return True

    def _update_title(self) -> None:
        self.setWindowTitle(WINDOW_TITLE.format(file_name=os.path.basename(self._file_path)))

    def reject(self) -> None:
        """Closes the window through `closeEvent`, so Escape asks about unsaved edits as the Close button does."""
        if self._in_close_event:
            super().reject()
        else:
            self.close()

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:  # pylint: disable=invalid-name
        """Asks whether to save unsaved edits, and stays open if the user cancels or the save fails."""
        if self.is_modified:
            choice = request_unsaved_changes_choice(self, os.path.basename(self._file_path),
                                                    CLOSE_WITHOUT_SAVING_LABEL)
            if (choice == UNSAVED_SAVE and not self.save()) or choice not in (UNSAVED_SAVE, UNSAVED_DISCARD):
                if event is not None:
                    event.ignore()
                return
        # QDialog.closeEvent calls `reject`, which must then hide the window instead of closing it again:
        self._in_close_event = True
        try:
            super().closeEvent(event)
        finally:
            self._in_close_event = False
