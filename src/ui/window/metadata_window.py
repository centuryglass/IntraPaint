"""View and edit the metadata an image carries: generation parameters, text chunks, EXIF tags and other embedded data.

`MetadataWindow` is non-modal and edits an `ImageMetadata` in place. Edits reach the file on the next save. A new
`ImageMetadata` (after a load or new image) is passed to `set_metadata`. The buttons that read from or write to the
editor's generation settings are built by `show_editor_buttons`, so a mode without an editor can hide them.
"""
import logging
import os
from typing import Any, Callable, Optional

from PIL.ExifTags import IFD
from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, \
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget, QAbstractItemView, QHeaderView

from src.image.image_metadata import A1111Parameters, ImageMetadata, ExifEntry
from src.image.metadata_cache_fields import PROMPT_FIELD, NEGATIVE_PROMPT_FIELD, apply_to_cache, update_from_cache, \
    cache_field_keys, read_field, write_field, differs_from_editor, editor_field_text
from src.ui.input_fields.plain_text_edit import PlainTextEdit
from src.ui.modal.dialog_footer import DialogFooter
from src.util.shared_constants import APP_ICON_PATH
from src.util.visual.image_format_utils import IMAGE_FORMATS_SUPPORTING_METADATA, RENAMED_FORMATS

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.window.metadata_window'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


WINDOW_TITLE = _tr('Image metadata')
GENERATION_TAB = _tr('Generation')
TEXT_TAB = _tr('Text chunks')
EXIF_TAB = _tr('EXIF')
OTHER_TAB = _tr('Other')
RAW_TEXT_LABEL = _tr('Raw text')
RAW_TEXT_TOOLTIP = _tr('Show and edit the saved parameters text directly.')
PROMPT_LABEL = _tr('Prompt')
NEGATIVE_PROMPT_LABEL = _tr('Negative prompt')
APPLY_LABEL = _tr('Apply to editor')
APPLY_SHORT_LABEL = _tr('Apply')
APPLY_TOOLTIP = _tr('Replace the editor setting with the saved value.')
UPDATE_LABEL = _tr('Update from editor')
UPDATE_SHORT_LABEL = _tr('Update')
UPDATE_TOOLTIP = _tr('Replace the saved value with the editor setting.')
APPLY_ALL_LABEL = _tr('Apply all')
APPLY_ALL_TOOLTIP = _tr('Replace every mapped editor setting with its saved value.')
UPDATE_ALL_LABEL = _tr('Update all')
UPDATE_ALL_TOOLTIP = _tr('Replace every mapped saved value with the editor setting. Other saved fields are kept.')
COPY_LABEL = _tr('Copy')
COPY_TOOLTIP = _tr('Copy the saved parameters text to the clipboard.')
FIELD_COLUMN = _tr('Field')
VALUE_COLUMN = _tr('Value')
EDITOR_COLUMN = _tr('Editor')
STATUS_COLUMN = _tr('Status')
DIFFERS_LABEL = _tr('Differs')
SAME_LABEL = _tr('Same')
ADD_FIELD_LABEL = _tr('Add field')
REMOVE_FIELD_LABEL = _tr('Remove field')
NEW_FIELD_NAME = _tr('New field')
ADD_ENTRY_LABEL = _tr('Add entry')
REMOVE_ENTRY_LABEL = _tr('Remove entry')
NEW_ENTRY_KEY = _tr('new_entry')
KEY_COLUMN = _tr('Key')
IFD_COLUMN = _tr('Group')
TAG_COLUMN = _tr('Tag')
REMOVE_TAG_LABEL = _tr('Remove tag')
REMOVE_LOCATION_LABEL = _tr('Remove location data')
REMOVE_LOCATION_TOOLTIP = _tr('Remove the GPS tags from the EXIF data.')
REMOVE_ALL_LABEL = _tr('Remove all metadata')
REMOVE_ALL_TOOLTIP = _tr('Remove every text entry, EXIF tag and embedded profile. The file changes on the next save.')
CLOSE_LABEL = _tr('Close')
NO_GENERATION_DATA = _tr('This image has no generation parameters.')
NO_OTHER_DATA = _tr('This image has no ComfyUI, NovelAI, InvokeAI or XMP data.')
ICC_PRESENT = _tr('The image has an embedded ICC color profile.')
NODES_VIEW = _tr('{source}: nodes')
XMP_VIEW = _tr('XMP')
REJECTED_MESSAGE = _tr('Not applied: {field} "{value}" ({reason})')
EXIF_MAIN_GROUP = _tr('Main')
EXIF_GROUPS = {IFD.Exif: _tr('Exif'), IFD.GPSInfo: _tr('GPS'), IFD.Interop: _tr('Interop')}
NOTE_NO_FILE = _tr('Formats that keep metadata: {formats}.')
NOTE_NONE = _tr('{file_format} files keep no metadata. Save as one of: {formats}.')
NOTE_ALL = _tr('{file_format} files keep every text entry and EXIF tag.')
NOTE_ORA = _tr('{file_format} files keep every text entry and EXIF tag.')
NOTE_COMMENT_ONLY = _tr('{file_format} files keep only the generation parameters, as a comment. EXIF tags are dropped.')
NOTE_COMMENT_EXIF = _tr('{file_format} files keep EXIF tags and the generation parameters as a comment. Other text'
                        ' entries are dropped.')
NOTE_EXIF_ONLY = _tr('{file_format} files keep EXIF tags and the generation parameters as the EXIF image'
                     ' description. Other text entries are dropped.')

_PNG_FORMATS = ('PNG', 'APNG')
_ORA_FORMATS = ('ORA',)
_COMMENT_ONLY_FORMATS = ('GIF',)
_COMMENT_EXIF_FORMATS = ('JP2', 'JPX', 'J2C', 'JPC', 'JPM')
_MAX_CELL_CHARS = 200
DEFAULT_SIZE = QSize(760, 700)
_DIFFERS_ROLE = Qt.ItemDataRole.UserRole


def save_format_note(file_path: str) -> str:
    """Returns a sentence saying which metadata a save to `file_path` keeps, following `save_image_with_metadata`.

    An empty path gives the list of formats that keep metadata.
    """
    formats = ', '.join(sorted(IMAGE_FORMATS_SUPPORTING_METADATA))
    extension = os.path.splitext(file_path)[1].lstrip('.').upper()
    if extension == '':
        return NOTE_NO_FILE.format(formats=formats)
    file_format = RENAMED_FORMATS.get(extension, extension)
    if file_format not in IMAGE_FORMATS_SUPPORTING_METADATA:
        return NOTE_NONE.format(file_format=file_format, formats=formats)
    if file_format in _PNG_FORMATS:
        return NOTE_ALL.format(file_format=file_format)
    if file_format in _ORA_FORMATS:
        return NOTE_ORA.format(file_format=file_format)
    if file_format in _COMMENT_ONLY_FORMATS:
        return NOTE_COMMENT_ONLY.format(file_format=file_format)
    if file_format in _COMMENT_EXIF_FORMATS:
        return NOTE_COMMENT_EXIF.format(file_format=file_format)
    return NOTE_EXIF_ONLY.format(file_format=file_format)


def _cell_text(value: Any) -> str:
    text = value.decode('utf-8', errors='replace') if isinstance(value, bytes) else str(value)
    text = text.replace('\n', ' ')
    return text if len(text) <= _MAX_CELL_CHARS else text[:_MAX_CELL_CHARS] + '...'


def _read_only_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def _configure_table(table: QTableWidget) -> None:
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.verticalHeader().setVisible(False)
    header = table.horizontalHeader()
    assert header is not None
    header.setStretchLastSection(True)
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)


class MetadataWindow(QDialog):
    """A non-modal window for viewing and editing one image's `ImageMetadata`."""

    metadata_edited = Signal()
    """Emitted after any edit to the metadata."""

    def __init__(self, metadata: ImageMetadata, get_file_path: Callable[[], str] = lambda: '',
                 show_editor_buttons: bool = True) -> None:
        """Creates the window.

        Parameters
        ----------
        metadata: ImageMetadata
            The metadata to show and edit in place.
        get_file_path: Callable[[], str]
            Returns the path the next save writes to, which decides the note about what the save keeps.
        show_editor_buttons: bool
            Whether to show the buttons that read from or write to the editor's generation settings.
        """
        super().__init__()
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle(WINDOW_TITLE)
        self.setModal(False)
        self.resize(DEFAULT_SIZE)
        self._metadata = metadata
        self._get_file_path = get_file_path
        self._show_editor_buttons = show_editor_buttons
        self._refreshing = False
        self._field_rows: list[str] = []
        self._exif_rows: list[ExifEntry] = []
        self._text_keys: list[str] = []
        self._other_views: list[str] = []

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, stretch=1)
        self._build_generation_tab()
        self._build_text_tab()
        self._build_exif_tab()
        self._build_other_tab()

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)
        self._note_label = QLabel()
        self._note_label.setWordWrap(True)
        layout.addWidget(self._note_label)
        footer = DialogFooter(CLOSE_LABEL, self, cancel_text=None)
        self._remove_all_button = footer.add_secondary_button(REMOVE_ALL_LABEL, destructive=True)
        self._remove_all_button.setToolTip(REMOVE_ALL_TOOLTIP)
        self._remove_all_button.clicked.connect(self._remove_all)
        footer.accepted.connect(self.close)
        layout.addWidget(footer)
        self.refresh()

    # Public interface:

    def set_metadata(self, metadata: ImageMetadata) -> None:
        """Shows a different image's metadata."""
        self._metadata = metadata
        self.refresh()

    def refresh(self) -> None:
        """Rebuilds every tab from the metadata and the editor's settings."""
        self._refreshing = True
        try:
            self._refresh_generation()
            self._refresh_text()
            self._refresh_exif()
            self._refresh_other()
            self._note_label.setText(save_format_note(self._get_file_path()))
        finally:
            self._refreshing = False

    def changeEvent(self, event: Optional[QEvent]) -> None:  # pylint: disable=invalid-name
        """Refreshes the editor comparison when the window is activated, since the editor may have changed."""
        super().changeEvent(event)
        if event is not None and event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self.refresh()

    # Shared helpers:

    def _edited(self) -> None:
        self.metadata_edited.emit()
        self.refresh()

    def _remove_all(self) -> None:
        self._metadata.remove_all()
        self._status_label.setText('')
        self._edited()

    def _parameters(self) -> A1111Parameters:
        """Returns the parsed generation parameters, or empty ones if the image has none."""
        params = self._metadata.a1111_parameters()
        return A1111Parameters() if params is None else params

    def _store_parameters(self, params: A1111Parameters) -> None:
        self._metadata.set_parameters(params.serialize())
        self._edited()

    # Generation tab:

    def _build_generation_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        top_row = QHBoxLayout()
        layout.addLayout(top_row)
        self._raw_toggle = QCheckBox(RAW_TEXT_LABEL)
        self._raw_toggle.setToolTip(RAW_TEXT_TOOLTIP)
        self._raw_toggle.toggled.connect(self._update_raw_mode)
        top_row.addWidget(self._raw_toggle)
        top_row.addStretch(1)
        self._apply_all_button = QPushButton(APPLY_ALL_LABEL)
        self._apply_all_button.setToolTip(APPLY_ALL_TOOLTIP)
        self._apply_all_button.clicked.connect(self._apply_all)
        self._update_all_button = QPushButton(UPDATE_ALL_LABEL)
        self._update_all_button.setToolTip(UPDATE_ALL_TOOLTIP)
        self._update_all_button.clicked.connect(self._update_all)
        copy_button = QPushButton(COPY_LABEL)
        copy_button.setToolTip(COPY_TOOLTIP)
        copy_button.clicked.connect(self._copy_parameters)
        for button in (self._apply_all_button, self._update_all_button, copy_button):
            top_row.addWidget(button)
        self._editor_buttons: list[QPushButton] = [self._apply_all_button, self._update_all_button]

        self._empty_label = QLabel(NO_GENERATION_DATA)
        layout.addWidget(self._empty_label)

        self._structured = QWidget()
        structured_layout = QVBoxLayout(self._structured)
        structured_layout.setContentsMargins(0, 0, 0, 0)
        self._prompt_box = self._build_prompt_row(structured_layout, PROMPT_FIELD, PROMPT_LABEL)
        self._negative_box = self._build_prompt_row(structured_layout, NEGATIVE_PROMPT_FIELD, NEGATIVE_PROMPT_LABEL)
        self._field_table = QTableWidget(0, 5)
        self._field_table.setHorizontalHeaderLabels([FIELD_COLUMN, VALUE_COLUMN, EDITOR_COLUMN, STATUS_COLUMN, ''])
        _configure_table(self._field_table)
        self._field_table.itemChanged.connect(self._field_item_changed)
        structured_layout.addWidget(self._field_table, stretch=1)
        field_buttons = QHBoxLayout()
        structured_layout.addLayout(field_buttons)
        add_button = QPushButton(ADD_FIELD_LABEL)
        add_button.clicked.connect(self._add_field)
        remove_button = QPushButton(REMOVE_FIELD_LABEL)
        remove_button.clicked.connect(self._remove_field)
        field_buttons.addWidget(add_button)
        field_buttons.addWidget(remove_button)
        field_buttons.addStretch(1)
        layout.addWidget(self._structured, stretch=1)

        self._raw_box = PlainTextEdit()
        self._raw_box.valueChanged.connect(self._raw_changed)
        layout.addWidget(self._raw_box, stretch=1)
        self._tabs.addTab(tab, GENERATION_TAB)
        self._update_raw_mode()

    def _build_prompt_row(self, layout: QVBoxLayout, field: str, label_text: str) -> PlainTextEdit:
        row = QHBoxLayout()
        layout.addWidget(QLabel(label_text))
        layout.addLayout(row)
        box = PlainTextEdit()
        box.setMaximumHeight(self.fontMetrics().lineSpacing() * 5)
        box.valueChanged.connect(lambda text, name=field: self._prompt_changed(name, text))
        row.addWidget(box, stretch=1)
        buttons = QVBoxLayout()
        row.addLayout(buttons)
        apply_button, update_button = self._field_buttons(field)
        buttons.addWidget(apply_button)
        buttons.addWidget(update_button)
        return box

    def _field_buttons(self, field: str, compact: bool = False) -> tuple[QPushButton, QPushButton]:
        apply_button = QPushButton(APPLY_SHORT_LABEL if compact else APPLY_LABEL)
        apply_button.setToolTip(APPLY_TOOLTIP)
        apply_button.clicked.connect(lambda: self._apply_fields((field,)))
        update_button = QPushButton(UPDATE_SHORT_LABEL if compact else UPDATE_LABEL)
        update_button.setToolTip(UPDATE_TOOLTIP)
        update_button.clicked.connect(lambda: self._update_fields((field,)))
        self._editor_buttons.extend((apply_button, update_button))
        apply_button.setVisible(self._show_editor_buttons)
        update_button.setVisible(self._show_editor_buttons)
        return apply_button, update_button

    def _update_raw_mode(self) -> None:
        raw = self._raw_toggle.isChecked()
        self._structured.setVisible(not raw and self._metadata.parameters is not None)
        self._raw_box.setVisible(raw)
        self._empty_label.setVisible(not raw and self._metadata.parameters is None)

    def _refresh_generation(self) -> None:
        params = self._metadata.a1111_parameters()
        has_data = params is not None
        shown = A1111Parameters() if params is None else params
        self._update_raw_mode()
        for button in self._editor_buttons:
            button.setVisible(self._show_editor_buttons)
        if not self._raw_box.hasFocus():
            self._raw_box.setValue(self._metadata.parameters or '')
        for box, field in ((self._prompt_box, PROMPT_FIELD), (self._negative_box, NEGATIVE_PROMPT_FIELD)):
            text = read_field(shown, field) or ''
            if box.value() != text and not box.hasFocus():
                box.setValue(text)
        self._refresh_field_table(shown)
        self._apply_all_button.setEnabled(has_data)

    def _refresh_field_table(self, params: A1111Parameters) -> None:
        mapped = cache_field_keys()
        self._field_rows = [key for key, _ in params.items()]
        table = self._field_table
        table.setRowCount(len(self._field_rows))
        for row, (key, value) in enumerate(params.items()):
            table.setItem(row, 0, _read_only_item(key))
            value_item = QTableWidgetItem(value)
            table.setItem(row, 1, value_item)
            if key in mapped and self._show_editor_buttons:
                table.setItem(row, 2, _read_only_item(editor_field_text(key)))
                differs = differs_from_editor(params, key)
                status = _read_only_item(DIFFERS_LABEL if differs else SAME_LABEL)
                status.setData(_DIFFERS_ROLE, differs)
                table.setItem(row, 3, status)
                apply_button, update_button = self._field_buttons(key, compact=True)
                holder = QWidget()
                holder_layout = QHBoxLayout(holder)
                holder_layout.setContentsMargins(0, 0, 0, 0)
                holder_layout.addWidget(apply_button)
                holder_layout.addWidget(update_button)
                table.setCellWidget(row, 4, holder)
            else:
                for column in (2, 3):
                    table.setItem(row, column, _read_only_item(''))
                table.removeCellWidget(row, 4)
        table.resizeColumnsToContents()

    def _prompt_changed(self, field: str, text: str) -> None:
        if self._refreshing:
            return
        params = self._parameters()
        if read_field(params, field) != text:
            write_field(params, field, text)
            self._store_parameters(params)

    def _raw_changed(self, text: str) -> None:
        if self._refreshing or text == (self._metadata.parameters or ''):
            return
        self._metadata.set_parameters(text)
        self._edited()

    def _field_item_changed(self, item: QTableWidgetItem) -> None:
        if self._refreshing or item.column() != 1 or item.row() >= len(self._field_rows):
            return
        params = self._parameters()
        key = self._field_rows[item.row()]
        if params.get(key) != item.text():
            params.set(key, item.text())
            self._store_parameters(params)

    def _add_field(self) -> None:
        params = self._parameters()
        name = NEW_FIELD_NAME
        suffix = 1
        while params.get(name) is not None:
            suffix += 1
            name = f'{NEW_FIELD_NAME} {suffix}'
        params.set(name, '')
        self._store_parameters(params)

    def _remove_field(self) -> None:
        row = self._field_table.currentRow()
        if 0 <= row < len(self._field_rows):
            params = self._parameters()
            params.remove(self._field_rows[row])
            self._store_parameters(params)

    def _apply_fields(self, fields: tuple[str, ...]) -> None:
        params = self._metadata.a1111_parameters()
        if params is None:
            return
        rejected = apply_to_cache(params, fields)
        self._status_label.setText('\n'.join(REJECTED_MESSAGE.format(field=item.field, value=item.value,
                                                                     reason=item.reason) for item in rejected))
        self.refresh()

    def _update_fields(self, fields: tuple[str, ...]) -> None:
        params = self._parameters()
        update_from_cache(params, fields)
        self._status_label.setText('')
        self._store_parameters(params)

    def _apply_all(self) -> None:
        self._apply_fields(tuple(cache_field_keys()))

    def _update_all(self) -> None:
        self._update_fields(tuple(cache_field_keys()))

    def _copy_parameters(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._metadata.parameters or '')

    # Text chunks tab:

    def _build_text_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self._text_table = QTableWidget(0, 2)
        self._text_table.setHorizontalHeaderLabels([KEY_COLUMN, VALUE_COLUMN])
        _configure_table(self._text_table)
        self._text_table.itemChanged.connect(self._text_key_changed)
        self._text_table.itemSelectionChanged.connect(self._show_selected_text)
        layout.addWidget(self._text_table, stretch=1)
        self._text_value_box = PlainTextEdit()
        self._text_value_box.valueChanged.connect(self._text_value_changed)
        layout.addWidget(self._text_value_box, stretch=1)
        row = QHBoxLayout()
        layout.addLayout(row)
        add_button = QPushButton(ADD_ENTRY_LABEL)
        add_button.clicked.connect(self._add_text_entry)
        remove_button = QPushButton(REMOVE_ENTRY_LABEL)
        remove_button.clicked.connect(self._remove_text_entry)
        row.addWidget(add_button)
        row.addWidget(remove_button)
        row.addStretch(1)
        self._tabs.addTab(tab, TEXT_TAB)

    def _refresh_text(self) -> None:
        table = self._text_table
        selected = self._selected_text_key()
        self._text_keys = list(self._metadata.text)
        table.setRowCount(len(self._text_keys))
        for row, key in enumerate(self._text_keys):
            table.setItem(row, 0, QTableWidgetItem(key))
            table.setItem(row, 1, _read_only_item(_cell_text(self._metadata.text[key])))
        if selected in self._text_keys:
            table.selectRow(self._text_keys.index(selected))
        self._show_selected_text()

    def _selected_text_key(self) -> Optional[str]:
        row = self._text_table.currentRow()
        if row < 0 or row >= len(self._text_keys) or len(self._text_table.selectedItems()) == 0:
            return None
        return self._text_keys[row]

    def _show_selected_text(self) -> None:
        key = self._selected_text_key()
        was_refreshing = self._refreshing
        self._refreshing = True
        try:
            self._text_value_box.setEnabled(key is not None)
            text = '' if key is None else self._metadata.text[key]
            if self._text_value_box.value() != text:
                self._text_value_box.setValue(text)
        finally:
            self._refreshing = was_refreshing

    def _text_key_changed(self, item: QTableWidgetItem) -> None:
        if self._refreshing or item.column() != 0 or item.row() >= len(self._text_keys):
            return
        old_key = self._text_keys[item.row()]
        new_key = item.text()
        if new_key == old_key:
            return
        if new_key == '' or new_key in self._metadata.text:
            self.refresh()
            return
        self._metadata.text = {(new_key if key == old_key else key): value
                               for key, value in self._metadata.text.items()}
        self._edited()

    def _text_value_changed(self, text: str) -> None:
        key = self._selected_text_key()
        if self._refreshing or key is None or self._metadata.text.get(key) == text:
            return
        self._metadata.text[key] = text
        self._edited()

    def _add_text_entry(self) -> None:
        key = NEW_ENTRY_KEY
        suffix = 1
        while key in self._metadata.text:
            suffix += 1
            key = f'{NEW_ENTRY_KEY}_{suffix}'
        self._metadata.text[key] = ''
        self._edited()
        self._text_table.selectRow(len(self._text_keys) - 1)

    def _remove_text_entry(self) -> None:
        key = self._selected_text_key()
        if key is not None:
            del self._metadata.text[key]
            self._edited()

    # EXIF tab:

    def _build_exif_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self._exif_table = QTableWidget(0, 4)
        self._exif_table.setHorizontalHeaderLabels([IFD_COLUMN, TAG_COLUMN, VALUE_COLUMN, ''])
        self._exif_table.setColumnHidden(3, True)
        _configure_table(self._exif_table)
        self._exif_table.itemChanged.connect(self._exif_value_changed)
        layout.addWidget(self._exif_table, stretch=1)
        row = QHBoxLayout()
        layout.addLayout(row)
        remove_button = QPushButton(REMOVE_TAG_LABEL)
        remove_button.clicked.connect(self._remove_exif_tag)
        self._remove_location_button = QPushButton(REMOVE_LOCATION_LABEL)
        self._remove_location_button.setToolTip(REMOVE_LOCATION_TOOLTIP)
        self._remove_location_button.clicked.connect(self._remove_location)
        row.addWidget(remove_button)
        row.addWidget(self._remove_location_button)
        row.addStretch(1)
        self._tabs.addTab(tab, EXIF_TAB)

    def _refresh_exif(self) -> None:
        self._exif_rows = self._metadata.exif_entries()
        table = self._exif_table
        table.setRowCount(len(self._exif_rows))
        for row, entry in enumerate(self._exif_rows):
            group = EXIF_MAIN_GROUP if entry.ifd is None else EXIF_GROUPS.get(entry.ifd, str(entry.ifd))
            table.setItem(row, 0, _read_only_item(group))
            table.setItem(row, 1, _read_only_item(entry.name))
            value = QTableWidgetItem(_cell_text(entry.value))
            if not entry.editable:
                value.setFlags(value.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 2, value)
        table.resizeColumnsToContents()
        self._remove_location_button.setEnabled(any(entry.ifd == IFD.GPSInfo for entry in self._exif_rows))

    def _exif_value_changed(self, item: QTableWidgetItem) -> None:
        if self._refreshing or item.column() != 2 or item.row() >= len(self._exif_rows):
            return
        entry = self._exif_rows[item.row()]
        if not entry.editable or item.text() == _cell_text(entry.value):
            return
        self._metadata.set_exif_text(entry.ifd, entry.tag, item.text())
        self._edited()

    def _remove_exif_tag(self) -> None:
        row = self._exif_table.currentRow()
        if 0 <= row < len(self._exif_rows):
            entry = self._exif_rows[row]
            self._metadata.remove_exif_tag(entry.ifd, entry.tag)
            self._edited()

    def _remove_location(self) -> None:
        self._metadata.remove_gps()
        self._edited()

    # Other tab:

    def _build_other_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self._other_empty_label = QLabel(NO_OTHER_DATA)
        layout.addWidget(self._other_empty_label)
        self._other_selector = QComboBox()
        self._other_selector.currentIndexChanged.connect(self._show_other_view)
        layout.addWidget(self._other_selector)
        self._other_view = PlainTextEdit()
        self._other_view.setReadOnly(True)
        layout.addWidget(self._other_view, stretch=1)
        self._icc_label = QLabel(ICC_PRESENT)
        layout.addWidget(self._icc_label)
        self._tabs.addTab(tab, OTHER_TAB)

    def _refresh_other(self) -> None:
        names: list[str] = []
        texts: list[str] = []
        for data in self._metadata.structured_data():
            names.append(f'{data.source}: {data.key}')
            texts.append(data.text)
        nodes = self._metadata.comfyui_nodes()
        if len(nodes) > 0:
            names.append(NODES_VIEW.format(source='ComfyUI'))
            texts.append('\n'.join(f'{node.node_id}  {node.class_type}  {_cell_text(node.inputs)}'
                                   for node in nodes))
        xmp = self._metadata.xmp
        if xmp is not None:
            names.append(XMP_VIEW)
            texts.append(xmp)
        selected = self._other_selector.currentText()
        self._other_selector.blockSignals(True)
        self._other_selector.clear()
        self._other_selector.addItems(names)
        if selected in names:
            self._other_selector.setCurrentIndex(names.index(selected))
        self._other_selector.blockSignals(False)
        self._other_views = texts
        self._other_empty_label.setVisible(len(names) == 0)
        self._other_selector.setVisible(len(names) > 0)
        self._other_view.setVisible(len(names) > 0)
        self._icc_label.setVisible(self._metadata.has_icc_profile)
        self._show_other_view()

    def _show_other_view(self) -> None:
        index = self._other_selector.currentIndex()
        self._other_view.setPlainText(self._other_views[index] if 0 <= index < len(self._other_views) else '')
