"""View and edit the metadata an image carries: generation parameters, text entries, EXIF tags and other embedded data.

`MetadataWindow` is non-modal and edits a copy of the open image's `ImageMetadata`. "Apply changes" emits
`metadata_applied` with the edited copy, and the owner makes it the image's metadata, which a later save writes.
Closing without applying discards the edits. The buttons that read from or write to the editor's generation settings
change the editor at once, and are built by `show_editor_buttons`, so a mode without an editor can hide them.
"""
import logging
import os
from typing import Any, Callable, NamedTuple, Optional

from PIL.ExifTags import IFD
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QCloseEvent, QFont, QIcon
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, \
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget, QAbstractItemView, QHeaderView

from src.config.cache import Cache
from src.image.image_metadata import A1111Parameters, ImageMetadata, ExifEntry, PARAMETERS_KEY, COMMENT_KEY, \
    XMP_TEXT_KEY, XMP_INFO_KEY
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
ALL_TAB = _tr('All metadata')
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
EDITOR_COLUMN_TOOLTIP = _tr('The editor setting, shown where it differs from the saved value.')
EMPTY_EDITOR_VALUE = _tr('(empty)')
SOURCE_COLUMN = _tr('Source')
NAME_COLUMN = _tr('Name')
SELECTED_VALUE_LABEL = _tr('Value of "{name}"')
NO_SELECTION_LABEL = _tr('Select a row to see its full value.')
READ_ONLY_SUFFIX = _tr('(read-only)')
ADD_FIELD_LABEL = _tr('Add field')
ADD_FIELD_DISABLED_TOOLTIP = _tr('Generation parameters need a settings line first. Use "Update all" to create one.')
REMOVE_FIELD_LABEL = _tr('Remove field')
REMOVE_FIELD_DISABLED_TOOLTIP = _tr('Select a field to remove. A1111 reads a settings line with fewer than three fields'
                                    ' as part of the prompt, so the last three can\'t be removed.')
NEW_FIELD_NAME = _tr('New field')
ADD_ENTRY_LABEL = _tr('Add text entry')
REMOVE_LABEL = _tr('Remove')
REMOVE_DISABLED_TOOLTIP = _tr('Select a text entry or EXIF tag to remove.')
NEW_ENTRY_KEY = _tr('new_entry')
REMOVE_LOCATION_LABEL = _tr('Remove location data')
REMOVE_LOCATION_TOOLTIP = _tr('Remove the EXIF GPS tags, and the city, state, country and location fields of IPTC and'
                              ' XMP data. Captions, keywords and other text may still name a place.')
REMOVE_ALL_LABEL = _tr('Remove all metadata')
REMOVE_ALL_TOOLTIP = _tr('Remove every text entry, EXIF tag and embedded data block.')
APPLY_CHANGES_LABEL = _tr('Apply changes')
CLOSE_LABEL = _tr('Close')
DISCARD_LABEL = _tr('Discard changes')
UNAPPLIED_MESSAGE = _tr('Changes are not kept until you click "Apply changes". Saving the image writes applied'
                        ' changes.')
NO_GENERATION_DATA = _tr('This image has no generation parameters. Use "Update all" to add the editor\'s settings.')
NO_METADATA = _tr('This image has no metadata.')
NO_OTHER_DATA = _tr('This image has no ComfyUI, NovelAI or InvokeAI data.')
NODES_VIEW = _tr('{source}: nodes')
REJECTED_MESSAGE = _tr('Not applied: {field} "{value}" ({reason})')
SOURCE_TEXT = _tr('Text')
SOURCE_TEXT_TOOLTIP = _tr('A PNG or OpenRaster text entry, or a JPEG or GIF comment.')
SOURCE_EXIF = _tr('EXIF')
SOURCE_EXIF_GROUPS = {IFD.Exif: _tr('EXIF: Exif'), IFD.GPSInfo: _tr('EXIF: GPS'), IFD.Interop: _tr('EXIF: Interop')}
SOURCE_IPTC = _tr('IPTC')
SOURCE_XMP = _tr('XMP')
SOURCE_ICC = _tr('ICC')
XMP_ROW_NAME = _tr('XMP packet')
ICC_ROW_NAME = _tr('Color profile')
ICC_ROW_VALUE = _tr('Embedded. The image is converted to sRGB, and saved without a profile.')

NOTE_NOT_SAVED = _tr('The image hasn\'t been saved yet. Formats that keep metadata: {formats}.')
NOTE_NOTHING_TO_SAVE = _tr('This image has no metadata to save.')
NOTE_NONE_KEPT = _tr('{file_format} files keep no metadata. To keep it, save as one of: {formats}.')
NOTE_ALL_KEPT = _tr('Saving as {file_format} keeps all of this metadata.')
NOTE_KEPT_AND_DROPPED = _tr('Saving as {file_format} keeps: {kept}. It drops: {dropped}.')
NOTE_NONE_OF_IT_KEPT = _tr('Saving as {file_format} drops all of this metadata: {dropped}.')
PART_PARAMETERS = _tr('generation parameters')
PART_COMMENT = _tr('comment')
PART_TEXT_ENTRIES = _tr('text entries ({keys})')
PART_EXIF = _tr('EXIF tags')
PART_XMP = _tr('XMP')
PART_IPTC = _tr('IPTC')

_PNG_FORMATS = ('PNG', 'APNG')
_ORA_FORMATS = ('ORA',)
_JPEG_FORMATS = ('JPEG',)
_COMMENT_ONLY_FORMATS = ('GIF',)
_COMMENT_EXIF_FORMATS = ('JP2', 'JPX', 'J2C', 'JPC', 'JPM')
_MAX_CELL_CHARS = 200
_MIN_A1111_FIELDS = 3  # Matches `_MIN_PARAMETER_LINE_FIELDS` in src/image/image_metadata.py.
DEFAULT_SIZE = QSize(720, 680)
EMPTY_SIZE = QSize(560, 360)
_EDITOR_COLUMN_MAX_WIDTH = 160
_PROMPT_LINES = 4  # Height of the prompt and field value boxes, in lines.

# Generation table columns:
_FIELD_COLUMN, _VALUE_COLUMN, _EDITOR_COLUMN, _BUTTON_COLUMN = range(4)
# All metadata table columns:
_SOURCE_COLUMN, _NAME_COLUMN, _ALL_VALUE_COLUMN = range(3)


def _format_name(file_path: str) -> str:
    extension = os.path.splitext(file_path)[1].lstrip('.').upper()
    return RENAMED_FORMATS.get(extension, extension)


def save_format_note(metadata: ImageMetadata, file_path: str) -> str:
    """Returns a sentence saying which of `metadata` a save to `file_path` keeps and drops.

    Follows the rules in `save_image_with_metadata` and `src/image/ora_metadata.py`. An empty path means the image
    hasn't been saved.
    """
    formats = ', '.join(sorted(IMAGE_FORMATS_SUPPORTING_METADATA))
    if file_path == '':
        return NOTE_NOT_SAVED.format(formats=formats)
    file_format = _format_name(file_path)
    parameters = metadata.parameters
    has_comment = metadata.text.get(COMMENT_KEY, '') != ''
    other_keys = [key for key in metadata.text if key not in (PARAMETERS_KEY, COMMENT_KEY, XMP_TEXT_KEY)]
    has_xmp = metadata.xmp_packet is not None
    present: dict[str, bool] = {
        PART_PARAMETERS: parameters is not None,
        PART_COMMENT: has_comment and metadata.text.get(COMMENT_KEY) != parameters,
        PART_TEXT_ENTRIES.format(keys=', '.join(other_keys)): len(other_keys) > 0,
        PART_EXIF: len(metadata.exif_entries()) > 0,
        PART_XMP: has_xmp,
        PART_IPTC: len(metadata.iptc_entries()) > 0,
    }
    present_parts = [part for part, is_present in present.items() if is_present]
    if len(present_parts) == 0:
        return NOTE_NOTHING_TO_SAVE
    if file_format not in IMAGE_FORMATS_SUPPORTING_METADATA:
        return NOTE_NONE_KEPT.format(file_format=file_format, formats=formats)
    text_parts = [part for part in present_parts if part not in (PART_EXIF, PART_XMP, PART_IPTC)]
    if file_format in _PNG_FORMATS:
        kept = text_parts + [PART_EXIF, PART_XMP]
    elif file_format in _ORA_FORMATS:
        kept = text_parts + [PART_EXIF, PART_XMP, PART_IPTC]
    elif file_format in _COMMENT_ONLY_FORMATS:
        kept = [PART_PARAMETERS if parameters is not None else PART_COMMENT]
    elif file_format in _COMMENT_EXIF_FORMATS:
        kept = [PART_PARAMETERS if parameters is not None else PART_COMMENT, PART_EXIF]
    elif file_format in _JPEG_FORMATS:
        kept = [PART_PARAMETERS, PART_COMMENT, PART_EXIF, PART_XMP, PART_IPTC]
    else:
        kept = [PART_PARAMETERS, PART_EXIF, PART_XMP]
    kept_parts = [part for part in present_parts if part in kept]
    dropped_parts = [part for part in present_parts if part not in kept]
    if len(dropped_parts) == 0:
        return NOTE_ALL_KEPT.format(file_format=file_format)
    if len(kept_parts) == 0:
        return NOTE_NONE_OF_IT_KEPT.format(file_format=file_format, dropped=', '.join(dropped_parts))
    return NOTE_KEPT_AND_DROPPED.format(file_format=file_format, kept=', '.join(kept_parts),
                                        dropped=', '.join(dropped_parts))


def _cell_text(value: Any) -> str:
    text = value.decode('utf-8', errors='replace') if isinstance(value, bytes) else str(value)
    text = text.replace('\n', ' ')
    return text if len(text) <= _MAX_CELL_CHARS else text[:_MAX_CELL_CHARS] + '...'


def _full_text(value: Any) -> str:
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else str(value)


def _read_only_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def _set_item_text(table: QTableWidget, row: int, column: int, text: str, editable: bool) -> QTableWidgetItem:
    """Sets a cell's text, reusing its item so a cell being edited isn't deleted under the editor."""
    item = table.item(row, column)
    if item is None:
        item = QTableWidgetItem(text) if editable else _read_only_item(text)
        table.setItem(row, column, item)
    elif item.text() != text:
        item.setText(text)
    return item


def _configure_table(table: QTableWidget) -> None:
    """Sets up a table whose long values are elided, so no column widens the window."""
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.setWordWrap(False)
    table.verticalHeader().setVisible(False)


class _MetadataRow(NamedTuple):
    """One row of the All metadata table: a text entry, an EXIF tag, or a read-only IPTC, XMP or ICC row."""
    source: str
    name: str
    value: str
    text_key: Optional[str] = None
    exif: Optional[ExifEntry] = None

    @property
    def editable(self) -> bool:
        """Whether the value can be edited."""
        return self.text_key is not None or (self.exif is not None and self.exif.editable)

    @property
    def removable(self) -> bool:
        """Whether Remove can delete the row."""
        return self.text_key is not None or self.exif is not None


class MetadataWindow(QDialog):
    """A non-modal window for viewing and editing a copy of one image's `ImageMetadata`."""

    metadata_applied = Signal(ImageMetadata)
    """Emitted with the edited metadata when the user applies their changes."""

    def __init__(self, metadata: ImageMetadata, get_file_path: Callable[[], str] = lambda: '',
                 show_editor_buttons: bool = True) -> None:
        """Creates the window.

        Parameters
        ----------
        metadata: ImageMetadata
            The image's metadata. The window edits a copy, and leaves this one unchanged.
        get_file_path: Callable[[], str]
            Returns the path the next save writes to, which decides the note about what the save keeps.
        show_editor_buttons: bool
            Whether to show the buttons that read from or write to the editor's generation settings.
        """
        super().__init__()
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle(WINDOW_TITLE)
        self.setModal(False)
        self._source = metadata
        self._metadata = metadata.copy()
        self._modified = False
        self._get_file_path = get_file_path
        self._show_editor_buttons = show_editor_buttons
        self._refreshing = False
        self._field_rows: list[str] = []
        self._row_buttons: dict[str, tuple[QPushButton, QPushButton]] = {}
        self._prompt_buttons: dict[str, tuple[QPushButton, QPushButton]] = {}
        self._metadata_rows: list[_MetadataRow] = []
        self._other_views: list[str] = []

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, stretch=1)
        self._build_generation_tab()
        self._build_all_tab()
        self._build_other_tab()

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)
        self._note_label = QLabel()
        self._note_label.setWordWrap(True)
        layout.addWidget(self._note_label)
        self._footer = DialogFooter(APPLY_CHANGES_LABEL, self, cancel_text=CLOSE_LABEL)
        self._remove_all_button = self._footer.add_secondary_button(REMOVE_ALL_LABEL, destructive=True)
        self._remove_all_button.setToolTip(REMOVE_ALL_TOOLTIP)
        self._remove_all_button.clicked.connect(self._remove_all)
        self._footer.accepted.connect(self.apply_changes)
        self._footer.rejected.connect(self.close)
        layout.addWidget(self._footer)
        assert self._footer.cancel_button is not None
        # The cancel button switches between two labels, so it is sized for the longer one:
        self._footer.cancel_button.setText(DISCARD_LABEL)
        self._footer.cancel_button.setMinimumWidth(self._footer.cancel_button.sizeHint().width())
        self._set_modified(False)

        cache = Cache()
        for cache_key in set(cache_field_keys().values()):
            cache.connect(self, cache_key, self._refresh_editor_state)
        self.refresh()
        has_content = self._metadata.has_removable_data or self._metadata.parameters is not None
        # Narrower, the field table's editor and button columns are cut off:
        self.setMinimumWidth(EMPTY_SIZE.width())
        self.resize(DEFAULT_SIZE if has_content else EMPTY_SIZE)

    # Public interface:

    @property
    def is_modified(self) -> bool:
        """Whether the window holds edits that haven't been applied."""
        return self._modified

    def set_metadata(self, metadata: ImageMetadata) -> None:
        """Shows a copy of another image's metadata, discarding unapplied edits."""
        self._source = metadata
        self._metadata = metadata.copy()
        self._set_modified(False)
        self._set_status('')
        self.refresh()

    def apply_changes(self) -> None:
        """Emits `metadata_applied` with a copy of the edited metadata."""
        if not self._modified:
            return
        self._set_modified(False)
        self._source = self._metadata.copy()
        self.metadata_applied.emit(self._source)

    def refresh(self) -> None:
        """Updates every tab from the metadata and the editor's settings."""
        self._refreshing = True
        try:
            self._refresh_generation()
            self._refresh_all()
            self._refresh_other()
            self._note_label.setText(save_format_note(self._metadata, self._get_file_path()))
            self._remove_all_button.setEnabled(self._metadata.has_removable_data)
        finally:
            self._refreshing = False

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:  # pylint: disable=invalid-name
        """Discards unapplied edits, so reopening the window shows the image's metadata."""
        if self._modified:
            self.set_metadata(self._source)
        super().closeEvent(event)

    def showEvent(self, event: Any) -> None:  # pylint: disable=invalid-name
        """Updates the note, since the save path may have changed while the window was hidden."""
        super().showEvent(event)
        self._note_label.setText(save_format_note(self._metadata, self._get_file_path()))

    # Shared helpers:

    def _set_status(self, text: str) -> None:
        self._status_label.setText(text)
        self._status_label.setVisible(text != '')

    def _set_modified(self, modified: bool) -> None:
        self._modified = modified
        self._footer.confirm_button.setEnabled(modified)
        assert self._footer.cancel_button is not None
        self._footer.cancel_button.setText(DISCARD_LABEL if modified else CLOSE_LABEL)
        if modified:
            self._set_status(UNAPPLIED_MESSAGE)
        elif self._status_label.text() == UNAPPLIED_MESSAGE:
            self._set_status('')

    def _edited(self) -> None:
        self._set_modified(True)
        self.refresh()

    def _remove_all(self) -> None:
        self._metadata.remove_all()
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
        self._copy_button = QPushButton(COPY_LABEL)
        self._copy_button.setToolTip(COPY_TOOLTIP)
        self._copy_button.clicked.connect(self._copy_parameters)
        for button in (self._apply_all_button, self._update_all_button, self._copy_button):
            top_row.addWidget(button)
        self._apply_all_button.setVisible(self._show_editor_buttons)
        self._update_all_button.setVisible(self._show_editor_buttons)

        self._empty_label = QLabel(NO_GENERATION_DATA if self._show_editor_buttons else NO_METADATA)
        self._empty_label.setWordWrap(True)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._empty_label)

        self._structured = QWidget()
        structured_layout = QVBoxLayout(self._structured)
        structured_layout.setContentsMargins(0, 0, 0, 0)
        self._prompt_box = self._build_prompt_row(structured_layout, PROMPT_FIELD, PROMPT_LABEL)
        self._negative_box = self._build_prompt_row(structured_layout, NEGATIVE_PROMPT_FIELD, NEGATIVE_PROMPT_LABEL)
        self._field_table = QTableWidget(0, 4)
        self._field_table.setHorizontalHeaderLabels([FIELD_COLUMN, VALUE_COLUMN, EDITOR_COLUMN, ''])
        editor_header = self._field_table.horizontalHeaderItem(_EDITOR_COLUMN)
        assert editor_header is not None
        editor_header.setToolTip(EDITOR_COLUMN_TOOLTIP)
        _configure_table(self._field_table)
        header = self._field_table.horizontalHeader()
        header.setSectionResizeMode(_FIELD_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(_VALUE_COLUMN, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_EDITOR_COLUMN, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(_BUTTON_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
        self._field_table.setColumnHidden(_EDITOR_COLUMN, not self._show_editor_buttons)
        self._field_table.setColumnHidden(_BUTTON_COLUMN, not self._show_editor_buttons)
        self._field_table.itemChanged.connect(self._field_item_changed)
        self._field_table.itemSelectionChanged.connect(self._show_selected_field)
        self._field_table.setMinimumHeight(self.fontMetrics().lineSpacing() * 8)
        structured_layout.addWidget(self._field_table, stretch=2)
        self._field_value_label = QLabel(NO_SELECTION_LABEL)
        structured_layout.addWidget(self._field_value_label)
        self._field_value_box = PlainTextEdit()
        self._field_value_box.setMaximumHeight(self.fontMetrics().lineSpacing() * _PROMPT_LINES)
        self._field_value_box.valueChanged.connect(self._field_value_changed)
        structured_layout.addWidget(self._field_value_box, stretch=1)
        field_buttons = QHBoxLayout()
        structured_layout.addLayout(field_buttons)
        self._add_field_button = QPushButton(ADD_FIELD_LABEL)
        self._add_field_button.clicked.connect(self._add_field)
        self._remove_field_button = QPushButton(REMOVE_FIELD_LABEL)
        self._remove_field_button.clicked.connect(self._remove_field)
        field_buttons.addWidget(self._add_field_button)
        field_buttons.addWidget(self._remove_field_button)
        field_buttons.addStretch(1)
        layout.addWidget(self._structured, stretch=1)

        self._raw_box = PlainTextEdit()
        self._raw_box.valueChanged.connect(self._raw_changed)
        layout.addWidget(self._raw_box, stretch=1)
        self._generation_spacer = QWidget()
        layout.addWidget(self._generation_spacer, stretch=1)
        self._tabs.addTab(tab, GENERATION_TAB)

    def _build_prompt_row(self, layout: QVBoxLayout, field: str, label_text: str) -> PlainTextEdit:
        row = QHBoxLayout()
        layout.addWidget(QLabel(label_text))
        layout.addLayout(row)
        box = PlainTextEdit()
        box.setMaximumHeight(self.fontMetrics().lineSpacing() * _PROMPT_LINES)
        box.valueChanged.connect(lambda text, name=field: self._prompt_changed(name, text))
        row.addWidget(box, stretch=1)
        buttons = QVBoxLayout()
        row.addLayout(buttons)
        apply_button, update_button = self._field_buttons(field)
        buttons.addWidget(apply_button)
        buttons.addWidget(update_button)
        buttons.addStretch(1)
        self._prompt_buttons[field] = (apply_button, update_button)
        return box

    def _field_buttons(self, field: str, compact: bool = False) -> tuple[QPushButton, QPushButton]:
        apply_button = QPushButton(APPLY_SHORT_LABEL if compact else APPLY_LABEL)
        apply_button.setToolTip(APPLY_TOOLTIP)
        apply_button.clicked.connect(lambda: self._apply_fields((field,)))
        update_button = QPushButton(UPDATE_SHORT_LABEL if compact else UPDATE_LABEL)
        update_button.setToolTip(UPDATE_TOOLTIP)
        update_button.clicked.connect(lambda: self._update_fields((field,)))
        apply_button.setVisible(self._show_editor_buttons)
        update_button.setVisible(self._show_editor_buttons)
        return apply_button, update_button

    def _update_raw_mode(self) -> None:
        raw = self._raw_toggle.isChecked()
        has_data = self._metadata.parameters is not None
        self._structured.setVisible(not raw and has_data)
        self._raw_box.setVisible(raw)
        self._empty_label.setVisible(not raw and not has_data)
        self._generation_spacer.setVisible(not raw and not has_data)

    def _refresh_generation(self) -> None:
        params = self._metadata.a1111_parameters()
        shown = A1111Parameters() if params is None else params
        self._update_raw_mode()
        if not self._raw_box.hasFocus():
            self._raw_box.setValue(self._metadata.parameters or '')
        for box, field in ((self._prompt_box, PROMPT_FIELD), (self._negative_box, NEGATIVE_PROMPT_FIELD)):
            text = read_field(shown, field) or ''
            if box.value() != text and not box.hasFocus():
                box.setValue(text)
        self._refresh_field_table(shown)
        self._apply_all_button.setEnabled(params is not None)
        self._copy_button.setEnabled(params is not None)
        self._refresh_editor_state()

    def _refresh_field_table(self, params: A1111Parameters) -> None:
        """Updates the field rows in place, rebuilding them only when the field names change."""
        table = self._field_table
        keys = params.keys()
        table.blockSignals(True)
        try:
            if keys != self._field_rows:
                self._rebuild_field_rows(keys)
            for row, (_, value) in enumerate(params.items()):
                _set_item_text(table, row, _VALUE_COLUMN, value, True).setToolTip(_cell_text(value))
        finally:
            table.blockSignals(False)
        if table.columnWidth(_EDITOR_COLUMN) > _EDITOR_COLUMN_MAX_WIDTH:
            table.setColumnWidth(_EDITOR_COLUMN, _EDITOR_COLUMN_MAX_WIDTH)
        has_fields = len(keys) > 0
        self._add_field_button.setEnabled(has_fields)
        self._add_field_button.setToolTip('' if has_fields else ADD_FIELD_DISABLED_TOOLTIP)
        self._show_selected_field()

    def _rebuild_field_rows(self, keys: list[str]) -> None:
        """Replaces every field row, and the row buttons with them. Qt deletes the replaced buttons later."""
        table = self._field_table
        selected = self._selected_field()
        mapped = cache_field_keys()
        self._field_rows = list(keys)
        self._row_buttons = {}
        table.clearContents()
        table.setRowCount(len(keys))
        for row, key in enumerate(keys):
            table.setItem(row, _FIELD_COLUMN, _read_only_item(key))
            table.setItem(row, _EDITOR_COLUMN, _read_only_item(''))
            if key in mapped and self._show_editor_buttons:
                apply_button, update_button = self._field_buttons(key, compact=True)
                holder = QWidget()
                holder_layout = QHBoxLayout(holder)
                holder_layout.setContentsMargins(0, 0, 0, 0)
                holder_layout.addWidget(apply_button)
                holder_layout.addWidget(update_button)
                table.setCellWidget(row, _BUTTON_COLUMN, holder)
                self._row_buttons[key] = (apply_button, update_button)
        if selected in keys:
            table.selectRow(keys.index(selected))

    def _refresh_editor_state(self) -> None:
        """Marks fields whose saved value differs from the editor, and enables the buttons that would change one."""
        if not self._show_editor_buttons:
            return
        params = self._metadata.a1111_parameters()
        shown = A1111Parameters() if params is None else params
        bold = QFont(self._field_table.font())
        bold.setBold(True)
        table = self._field_table
        table.blockSignals(True)
        try:
            for row, key in enumerate(self._field_rows):
                differs = key in self._row_buttons and differs_from_editor(shown, key)
                editor_text = (editor_field_text(key) or EMPTY_EDITOR_VALUE) if differs else ''
                item = _set_item_text(table, row, _EDITOR_COLUMN, editor_text, False)
                item.setFont(bold if differs else table.font())
                item.setToolTip(item.text())
                if key in self._row_buttons:
                    for button in self._row_buttons[key]:
                        button.setEnabled(differs)
        finally:
            table.blockSignals(False)
        for field, (apply_button, update_button) in self._prompt_buttons.items():
            saved = read_field(shown, field)
            differs = params is not None and differs_from_editor(shown, field)
            apply_button.setEnabled(differs)
            update_button.setEnabled(differs or (saved is None and editor_field_text(field) != ''))

    def _selected_field(self) -> Optional[str]:
        row = self._field_table.currentRow()
        if row < 0 or row >= len(self._field_rows) or len(self._field_table.selectedItems()) == 0:
            return None
        return self._field_rows[row]

    def _show_selected_field(self) -> None:
        key = self._selected_field()
        removable = key is not None and len(self._field_rows) > _MIN_A1111_FIELDS
        self._remove_field_button.setEnabled(removable)
        self._remove_field_button.setToolTip('' if removable else REMOVE_FIELD_DISABLED_TOOLTIP)
        self._field_value_box.setEnabled(key is not None)
        self._field_value_label.setText(NO_SELECTION_LABEL if key is None else SELECTED_VALUE_LABEL.format(name=key))
        text = '' if key is None else (self._parameters().get(key) or '')
        if self._field_value_box.value() != text and not self._field_value_box.hasFocus():
            was_refreshing = self._refreshing
            self._refreshing = True
            try:
                self._field_value_box.setValue(text)
            finally:
                self._refreshing = was_refreshing

    def _set_field(self, key: str, value: str) -> None:
        params = self._parameters()
        if params.get(key) != value:
            params.set(key, value)
            self._store_parameters(params)

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
        if self._refreshing or item.column() != _VALUE_COLUMN or item.row() >= len(self._field_rows):
            return
        self._set_field(self._field_rows[item.row()], item.text())

    def _field_value_changed(self, text: str) -> None:
        key = self._selected_field()
        if self._refreshing or key is None:
            return
        self._set_field(key, text)

    def _add_field(self) -> None:
        params = self._parameters()
        if not params.has_generation_fields:
            return
        name = NEW_FIELD_NAME
        suffix = 1
        while params.get(name) is not None:
            suffix += 1
            name = f'{NEW_FIELD_NAME} {suffix}'
        params.set(name, '')
        self._store_parameters(params)
        self._field_table.selectRow(self._field_rows.index(name))

    def _remove_field(self) -> None:
        key = self._selected_field()
        if key is None or len(self._field_rows) <= _MIN_A1111_FIELDS:
            return
        params = self._parameters()
        params.remove(key)
        self._store_parameters(params)

    def _apply_fields(self, fields: tuple[str, ...]) -> None:
        params = self._metadata.a1111_parameters()
        if params is None:
            return
        rejected = apply_to_cache(params, fields)
        self._set_status('\n'.join(REJECTED_MESSAGE.format(field=item.field, value=item.value,
                                                                     reason=item.reason) for item in rejected))
        self._refresh_editor_state()

    def _update_fields(self, fields: tuple[str, ...]) -> None:
        params = self._parameters()
        update_from_cache(params, fields)
        if params.serialize() != (self._metadata.parameters or ''):
            self._store_parameters(params)

    def _apply_all(self) -> None:
        self._apply_fields(tuple(cache_field_keys()))

    def _update_all(self) -> None:
        self._update_fields(tuple(cache_field_keys()))

    def _copy_parameters(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._metadata.parameters or '')

    # All metadata tab:

    def _build_all_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self._all_empty_label = QLabel(NO_METADATA)
        layout.addWidget(self._all_empty_label)
        self._all_table = QTableWidget(0, 3)
        self._all_table.setHorizontalHeaderLabels([SOURCE_COLUMN, NAME_COLUMN, VALUE_COLUMN])
        _configure_table(self._all_table)
        header = self._all_table.horizontalHeader()
        header.setSectionResizeMode(_SOURCE_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(_NAME_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(_ALL_VALUE_COLUMN, QHeaderView.ResizeMode.Stretch)
        self._all_table.itemChanged.connect(self._all_item_changed)
        self._all_table.itemSelectionChanged.connect(self._show_selected_row)
        layout.addWidget(self._all_table, stretch=2)
        self._row_value_label = QLabel(NO_SELECTION_LABEL)
        layout.addWidget(self._row_value_label)
        self._row_value_box = PlainTextEdit()
        self._row_value_box.valueChanged.connect(self._row_value_changed)
        layout.addWidget(self._row_value_box, stretch=1)
        row = QHBoxLayout()
        layout.addLayout(row)
        add_button = QPushButton(ADD_ENTRY_LABEL)
        add_button.setToolTip(SOURCE_TEXT_TOOLTIP)
        add_button.clicked.connect(self._add_text_entry)
        self._remove_row_button = QPushButton(REMOVE_LABEL)
        self._remove_row_button.clicked.connect(self._remove_row)
        self._remove_location_button = QPushButton(REMOVE_LOCATION_LABEL)
        self._remove_location_button.setToolTip(REMOVE_LOCATION_TOOLTIP)
        self._remove_location_button.clicked.connect(self._remove_location)
        row.addWidget(add_button)
        row.addWidget(self._remove_row_button)
        row.addWidget(self._remove_location_button)
        row.addStretch(1)
        self._tabs.addTab(tab, ALL_TAB)

    def _collect_rows(self) -> list[_MetadataRow]:
        rows = [_MetadataRow(SOURCE_TEXT, key, value, text_key=key) for key, value in self._metadata.text.items()]
        for entry in self._metadata.exif_entries():
            source = SOURCE_EXIF if entry.ifd is None else SOURCE_EXIF_GROUPS.get(entry.ifd, str(entry.ifd))
            rows.append(_MetadataRow(source, entry.name, _full_text(entry.value), exif=entry))
        for iptc in self._metadata.iptc_entries():
            rows.append(_MetadataRow(SOURCE_IPTC, iptc.name, iptc.value))
        xmp = self._metadata.format_info.get(XMP_INFO_KEY)
        if xmp is not None:
            rows.append(_MetadataRow(SOURCE_XMP, XMP_ROW_NAME, _full_text(xmp)))
        if self._metadata.has_icc_profile:
            rows.append(_MetadataRow(SOURCE_ICC, ICC_ROW_NAME, ICC_ROW_VALUE))
        return rows

    def _refresh_all(self) -> None:
        table = self._all_table
        selected = self._selected_row()
        rows = self._collect_rows()
        table.blockSignals(True)
        try:
            if [(row.source, row.name) for row in rows] != [(row.source, row.name) for row in self._metadata_rows]:
                table.clearContents()
                table.setRowCount(len(rows))
            self._metadata_rows = rows
            for index, row in enumerate(rows):
                source_item = _set_item_text(table, index, _SOURCE_COLUMN, row.source, False)
                if row.text_key is not None:
                    source_item.setToolTip(SOURCE_TEXT_TOOLTIP)
                _set_item_text(table, index, _NAME_COLUMN, row.name, row.text_key is not None)
                value_item = _set_item_text(table, index, _ALL_VALUE_COLUMN, _cell_text(row.value), row.editable)
                value_item.setToolTip(_cell_text(row.value))
            if selected is not None:
                for index, row in enumerate(rows):
                    if (row.source, row.name) == (selected.source, selected.name):
                        table.selectRow(index)
                        break
        finally:
            table.blockSignals(False)
        self._all_empty_label.setVisible(len(rows) == 0)
        self._remove_location_button.setEnabled(self._metadata.has_location_data)
        self._show_selected_row()

    def _selected_row(self) -> Optional[_MetadataRow]:
        index = self._all_table.currentRow()
        if index < 0 or index >= len(self._metadata_rows) or len(self._all_table.selectedItems()) == 0:
            return None
        return self._metadata_rows[index]

    def _show_selected_row(self) -> None:
        row = self._selected_row()
        self._remove_row_button.setEnabled(row is not None and row.removable)
        self._remove_row_button.setToolTip('' if row is not None and row.removable else REMOVE_DISABLED_TOOLTIP)
        if row is None:
            self._row_value_label.setText(NO_SELECTION_LABEL)
        else:
            label = SELECTED_VALUE_LABEL.format(name=row.name)
            self._row_value_label.setText(label if row.editable else f'{label} {READ_ONLY_SUFFIX}')
        self._row_value_box.setEnabled(row is not None)
        self._row_value_box.setReadOnly(row is None or not row.editable)
        text = '' if row is None else row.value
        if self._row_value_box.value() != text and not self._row_value_box.hasFocus():
            was_refreshing = self._refreshing
            self._refreshing = True
            try:
                self._row_value_box.setValue(text)
            finally:
                self._refreshing = was_refreshing

    def _set_row_value(self, row: _MetadataRow, value: str) -> None:
        if not row.editable or value == row.value:
            return
        if row.text_key is not None:
            self._metadata.text[row.text_key] = value
        elif row.exif is not None:
            self._metadata.set_exif_text(row.exif.ifd, row.exif.tag, value)
        self._edited()

    def _rename_text_entry(self, old_key: str, new_key: str) -> None:
        if new_key == old_key:
            return
        if new_key == '' or new_key in self._metadata.text:
            self.refresh()
            return
        self._metadata.text = {(new_key if key == old_key else key): value
                               for key, value in self._metadata.text.items()}
        self._edited()

    def _all_item_changed(self, item: QTableWidgetItem) -> None:
        if self._refreshing or item.row() >= len(self._metadata_rows):
            return
        row = self._metadata_rows[item.row()]
        if item.column() == _NAME_COLUMN and row.text_key is not None:
            self._rename_text_entry(row.text_key, item.text())
        elif item.column() == _ALL_VALUE_COLUMN and item.text() != _cell_text(row.value):
            self._set_row_value(row, item.text())

    def _row_value_changed(self, text: str) -> None:
        row = self._selected_row()
        if self._refreshing or row is None:
            return
        self._set_row_value(row, text)

    def _add_text_entry(self) -> None:
        key = NEW_ENTRY_KEY
        suffix = 1
        while key in self._metadata.text:
            suffix += 1
            key = f'{NEW_ENTRY_KEY}_{suffix}'
        self._metadata.text[key] = ''
        self._edited()
        index = [row.text_key for row in self._metadata_rows].index(key)
        self._all_table.selectRow(index)
        self._row_value_box.setFocus()

    def _remove_row(self) -> None:
        row = self._selected_row()
        if row is None or not row.removable:
            return
        if row.text_key is not None:
            del self._metadata.text[row.text_key]
        elif row.exif is not None:
            self._metadata.remove_exif_tag(row.exif.ifd, row.exif.tag)
        self._edited()

    def _remove_location(self) -> None:
        self._metadata.remove_location()
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
        self._other_spacer = QWidget()
        layout.addWidget(self._other_spacer, stretch=1)
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
        selected = self._other_selector.currentText()
        self._other_selector.blockSignals(True)
        self._other_selector.clear()
        self._other_selector.addItems(names)
        if selected in names:
            self._other_selector.setCurrentIndex(names.index(selected))
        self._other_selector.blockSignals(False)
        self._other_views = texts
        has_views = len(names) > 0
        self._other_empty_label.setVisible(not has_views)
        self._other_spacer.setVisible(not has_views)
        self._other_selector.setVisible(has_views)
        self._other_view.setVisible(has_views)
        self._show_other_view()

    def _show_other_view(self) -> None:
        index = self._other_selector.currentIndex()
        self._other_view.setPlainText(self._other_views[index] if 0 <= index < len(self._other_views) else '')
