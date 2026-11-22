"""
Provides simple popup windows for error messages, requesting confirmation, and loading images.
"""
import logging
import os
import traceback
import weakref
from typing import Optional, Iterable

from PIL import UnidentifiedImageError
from PySide6.QtCore import Qt, QDateTime, QLocale, QSize
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QMessageBox, QFileDialog, QWidget, QStyle, QApplication

from src.config.application_config import AppConfig
from src.ui.ink_style import set_signal
from src.ui.input_fields.check_box import CheckBox
from src.ui.modal.modal_parent import modal_parent
from src.util.rich_text import escape_rich_text, rich_text_format
from src.util.visual.display_size import get_screen_size
from src.util.visual.image_format_utils import IMAGE_WRITE_FORMATS, IMAGE_READ_FORMATS, OPENRASTER_FORMAT, \
    ImageFormatGroup, image_format_groups
from src.util.visual.image_utils import get_standard_qt_icon

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.modal_utils'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


TITLE_LOAD_IMAGE = _tr('Open Image')
TITLE_LOAD_LAYER = _tr('Open Images as Layers')
TITLE_SAVE_IMAGE = _tr('Save Image')
MESSAGE_LOAD_IMAGE_ERROR = _tr('Open failed')

IMAGE_FORMATS_DESCRIPTION = _tr('Images and IntraPaint projects')
LAYER_FORMATS_DESCRIPTION = _tr('Images')

CHECKBOX_MESSAGE_DO_NOT_WARN_AGAIN = _tr('Don\'t show this again')
CHECKBOX_MESSAGE_REMEMBER_CHOICE = _tr('Remember my choice')

REMEMBER_OPTION_NONE = 'always_ask'
REMEMBER_OPTION_CONFIRM = 'confirm'
REMEMBER_OPTION_CANCEL = 'cancel'

TITLE_RESTORE_RECOVERY = _tr('Restore unsaved work?')
MESSAGE_RESTORE_RECOVERY_FILE = _tr('IntraPaint closed without quitting normally while editing "{file_path}". A'
                                    ' recovery copy was saved at {saved_time}.')
MESSAGE_RESTORE_RECOVERY_UNSAVED = _tr('IntraPaint closed without quitting normally while editing an image that was'
                                       ' never saved. A recovery copy was saved at {saved_time}.')
MESSAGE_RESTORE_RECOVERY_CHOICES = _tr('Restore opens the copy. Discard deletes it. Later keeps it and asks again'
                                       ' the next time IntraPaint starts.')
BUTTON_RESTORE_RECOVERY = _tr('Restore')
BUTTON_DISCARD_RECOVERY = _tr('Discard')
BUTTON_LATER_RECOVERY = _tr('Later')

# `request_recovery_choice` results:
RECOVERY_RESTORE = 'restore'
RECOVERY_DISCARD = 'discard'
RECOVERY_LATER = 'later'
RECOVERY_THUMBNAIL_SIZE = QSize(128, 128)

TITLE_UNSAVED_CHANGES = _tr('Save changes to "{file_name}"?')
MESSAGE_UNSAVED_CHANGES = _tr('Changes you haven\'t saved will be lost.')
BUTTON_SAVE_CHANGES = _tr('Save')

# Choices returned by `request_unsaved_changes_choice`:
UNSAVED_SAVE = 'save'
UNSAVED_DISCARD = 'discard'
UNSAVED_CANCEL = 'cancel'


def _extension_patterns(groups: list[ImageFormatGroup]) -> str:
    return ' '.join(f'*.{ext}' for group in groups for ext in group.extensions)


def _filter_entries(groups: list[ImageFormatGroup]) -> list[str]:
    """Returns one `<label> (*.ext1 *.ext2)` file dialog filter per group."""
    return [f'{group.label} ({_extension_patterns([group])})' for group in groups]


def save_filters(formats: Optional[Iterable[str]] = None) -> list[str]:
    """Returns the Save As type filters, one per format.

    `formats` are upper-case extensions to offer, defaulting to every writable one.
    """
    return _filter_entries(image_format_groups(IMAGE_WRITE_FORMATS if formats is None else formats))


def load_filters(layers: bool = False) -> list[str]:
    """Returns the Open type filters: "All supported" first, then one per readable format.

    With `layers`, OpenRaster is left out, as it can't be added as one layer.
    """
    groups = image_format_groups(IMAGE_READ_FORMATS - {OPENRASTER_FORMAT} if layers else IMAGE_READ_FORMATS)
    label = LAYER_FORMATS_DESCRIPTION if layers else IMAGE_FORMATS_DESCRIPTION
    return [f'{label} ({_extension_patterns(groups)})', *_filter_entries(groups)]


def _filter_extensions(name_filter: str) -> list[str]:
    """Returns the extensions, without dots, that a filter built by this module lists."""
    return [pattern[2:] for pattern in name_filter[name_filter.rindex('(') + 1:-1].split(' ')]


def _filter_for_file(candidates: list[str], file_path: str) -> Optional[str]:
    """Returns the first of the `candidates` filters that lists `file_path`'s extension, or None."""
    extension = os.path.splitext(file_path)[1].lstrip('.').lower()
    for name_filter in candidates:
        if extension in _filter_extensions(name_filter):
            return name_filter
    return None


LOAD_IMAGE_MODE = 'load'
SAVE_IMAGE_MODE = 'save'


def _new_message_box(parent: Optional[QWidget]) -> QMessageBox:
    """Creates a message box that Qt draws itself, so the application style and `set_signal` marks apply.

    Platform themes may otherwise show message boxes through a native dialog, which ignores both. A missing `parent`
    defaults to `modal_parent`. The caller deletes the box with `deleteLater` once it has read the result.
    """
    message_box = QMessageBox(modal_parent(parent))
    message_box.setOption(QMessageBox.Option.DontUseNativeDialog, True)
    return message_box


def _set_title_and_message(message_box: QMessageBox, title: str, message: str) -> None:
    """Shows plain-text `title` as a bold first line in the box, with rich-text `message` under it.

    `title` is escaped. `message` is rendered as rich text with each newline shown as a line break, so callers escape
    any value they put into it (`src.util.rich_text.rich_text_format`) and keep newlines out of their markup.
    """
    message_box.setWindowTitle(title)
    message_box.setTextFormat(Qt.TextFormat.RichText)
    message_box.setText(f'<b>{escape_rich_text(title)}</b>')
    message_box.setInformativeText(message.replace('\n', '<br>'))


def show_error_dialog(parent: Optional[QWidget], title: str, error: str | BaseException,
                      signal: bool = False) -> None:
    """Opens a message box to show an error to the user. With `signal` set, the OK button uses the signal color.

    A string `error` is rich text (see `_set_title_and_message`). An exception's text is escaped.
    """
    logger.error(f'Error: {error}')
    if isinstance(error, BaseException) and hasattr(error, '__traceback__'):
        traceback.print_exception(type(error), error, error.__traceback__)
    messagebox = _new_message_box(parent)
    message = escape_rich_text(error) if isinstance(error, BaseException) else error
    _set_title_and_message(messagebox, title, message)
    messagebox.setWindowIcon(get_standard_qt_icon(QStyle.StandardPixmap.SP_MessageBoxWarning, parent))
    messagebox.setIcon(QMessageBox.Icon.Critical)
    messagebox.setStandardButtons(QMessageBox.StandardButton.Ok)
    if signal:
        ok_button = messagebox.button(QMessageBox.StandardButton.Ok)
        assert ok_button is not None
        set_signal(ok_button)
    messagebox.exec()
    messagebox.deleteLater()


def request_recovery_choice(parent: Optional[QWidget], original_path: str, saved_at: float,
                            thumbnail: Optional[QImage]) -> str:
    """Asks what to do with a crashed session's recovery copy.

    Returns `RECOVERY_RESTORE`, `RECOVERY_DISCARD` or `RECOVERY_LATER`. Closing the box counts as Later.
    """
    saved_time = QLocale().toString(QDateTime.fromSecsSinceEpoch(int(saved_at)), QLocale.FormatType.ShortFormat)
    if original_path == '':
        message = rich_text_format(MESSAGE_RESTORE_RECOVERY_UNSAVED, saved_time=saved_time)
    else:
        message = rich_text_format(MESSAGE_RESTORE_RECOVERY_FILE, file_path=original_path, saved_time=saved_time)
    message_box = _new_message_box(parent)
    _set_title_and_message(message_box, TITLE_RESTORE_RECOVERY, f'{message}\n\n{MESSAGE_RESTORE_RECOVERY_CHOICES}')
    message_box.setWindowIcon(get_standard_qt_icon(QStyle.StandardPixmap.SP_MessageBoxQuestion, parent))
    if thumbnail is not None:
        message_box.setIconPixmap(QPixmap.fromImage(thumbnail.scaled(RECOVERY_THUMBNAIL_SIZE,
                                                                     Qt.AspectRatioMode.KeepAspectRatio,
                                                                     Qt.TransformationMode.SmoothTransformation)))
    else:
        message_box.setIcon(QMessageBox.Icon.Question)
    restore_button = message_box.addButton(BUTTON_RESTORE_RECOVERY, QMessageBox.ButtonRole.AcceptRole)
    discard_button = message_box.addButton(BUTTON_DISCARD_RECOVERY, QMessageBox.ButtonRole.DestructiveRole)
    later_button = message_box.addButton(BUTTON_LATER_RECOVERY, QMessageBox.ButtonRole.RejectRole)
    set_signal(discard_button)
    message_box.setDefaultButton(restore_button)
    message_box.setEscapeButton(later_button)
    message_box.exec()
    clicked = message_box.clickedButton()
    message_box.deleteLater()
    if clicked is restore_button:
        return RECOVERY_RESTORE
    if clicked is discard_button:
        return RECOVERY_DISCARD
    return RECOVERY_LATER


def request_unsaved_changes_choice(parent: Optional[QWidget], file_name: str, discard_label: str) -> str:
    """Asks whether to save unsaved changes before an action that would discard them.

    Returns `UNSAVED_SAVE`, `UNSAVED_DISCARD` or `UNSAVED_CANCEL`. The discard button shows `discard_label`, which
    names the action ("Quit without saving"). Closing the box counts as Cancel.
    """
    message_box = _new_message_box(parent)
    _set_title_and_message(message_box, TITLE_UNSAVED_CHANGES.format(file_name=file_name), MESSAGE_UNSAVED_CHANGES)
    message_box.setWindowIcon(get_standard_qt_icon(QStyle.StandardPixmap.SP_MessageBoxQuestion, parent))
    message_box.setIcon(QMessageBox.Icon.Question)
    save_button = message_box.addButton(BUTTON_SAVE_CHANGES, QMessageBox.ButtonRole.AcceptRole)
    discard_button = message_box.addButton(discard_label, QMessageBox.ButtonRole.DestructiveRole)
    cancel_button = message_box.addButton(QMessageBox.StandardButton.Cancel)
    set_signal(discard_button)
    message_box.setDefaultButton(save_button)
    message_box.setEscapeButton(cancel_button)
    message_box.exec()
    clicked = message_box.clickedButton()
    message_box.deleteLater()
    if clicked is save_button:
        return UNSAVED_SAVE
    if clicked is discard_button:
        return UNSAVED_DISCARD
    return UNSAVED_CANCEL


def request_choice(parent: Optional[QWidget], title: str, message: str, choices: list[str]) -> Optional[int]:
    """Asks the user to pick one of several actions, or cancel.

    Returns the index in `choices` of the clicked button, or None for Cancel. `message` is rich text (see
    `_set_title_and_message`). The first choice is the default button, and closing the box counts as Cancel.
    """
    message_box = _new_message_box(parent)
    _set_title_and_message(message_box, title, message)
    message_box.setWindowIcon(get_standard_qt_icon(QStyle.StandardPixmap.SP_MessageBoxQuestion, parent))
    message_box.setIcon(QMessageBox.Icon.Question)
    buttons = [message_box.addButton(choice, QMessageBox.ButtonRole.AcceptRole) for choice in choices]
    cancel_button = message_box.addButton(QMessageBox.StandardButton.Cancel)
    if len(buttons) > 0:
        message_box.setDefaultButton(buttons[0])
    message_box.setEscapeButton(cancel_button)
    message_box.exec()
    clicked = message_box.clickedButton()
    message_box.deleteLater()
    return buttons.index(clicked) if clicked in buttons else None


def show_warning_dialog(parent: Optional[QWidget], title: str, message: str,
                        reminder_config_key: Optional[str]) -> None:
    """Show a warning dialog, optionally with a 'don't show again' checkbox.

    `message` is rich text (see `_set_title_and_message`).
    """
    if reminder_config_key is not None and not AppConfig().get(reminder_config_key):
        return  # Warning already disabled
    messagebox = _new_message_box(parent)
    _set_title_and_message(messagebox, title, message)
    messagebox.setWindowIcon(get_standard_qt_icon(QStyle.StandardPixmap.SP_MessageBoxWarning, parent))
    messagebox.setIcon(QMessageBox.Icon.Warning)
    if reminder_config_key is not None:
        checkbox = CheckBox()
        checkbox.setText(CHECKBOX_MESSAGE_DO_NOT_WARN_AGAIN)
        checkbox.valueChanged.connect(lambda is_checked: AppConfig().set(reminder_config_key, not is_checked))
        messagebox.setCheckBox(checkbox)
    messagebox.setStandardButtons(QMessageBox.StandardButton.Ok)
    messagebox.exec()
    messagebox.deleteLater()


def request_confirmation(parent: Optional[QWidget], title: str, message: str,
                         reminder_config_key: Optional[str] = None,
                         confirm_option=QMessageBox.StandardButton.Ok,
                         cancel_option=QMessageBox.StandardButton.Cancel, discards_work: bool = False,
                         confirm_label: Optional[str] = None) -> bool:
    """Requests confirmation from the user, returns whether that confirmation was granted.

    `message` is rich text (see `_set_title_and_message`). With `discards_work` set, the confirm button uses the signal
    color. With `confirm_label` set, the confirm button names the action ("Quit without saving") instead of using the
    standard button's text.
    """
    if reminder_config_key is not None:
        reminder_setting = AppConfig().get(reminder_config_key)
        if reminder_setting not in (REMEMBER_OPTION_NONE, REMEMBER_OPTION_CONFIRM, REMEMBER_OPTION_CANCEL):
            AppConfig().set(reminder_config_key, REMEMBER_OPTION_NONE)
        if reminder_setting == REMEMBER_OPTION_CONFIRM:
            return True
        if reminder_setting == REMEMBER_OPTION_CANCEL:
            return False
    confirm_box = _new_message_box(parent)
    _set_title_and_message(confirm_box, title, message)
    confirm_box.setStandardButtons(confirm_option | cancel_option)
    confirm_box.setWindowIcon(get_standard_qt_icon(QStyle.StandardPixmap.SP_MessageBoxQuestion, parent))
    confirm_box.setIcon(QMessageBox.Icon.Question)
    confirm_button = confirm_box.button(confirm_option)
    assert confirm_button is not None
    if confirm_label is not None:
        confirm_button.setText(confirm_label)
    if discards_work:
        set_signal(confirm_button)
    checkbox: Optional[CheckBox] = None
    if reminder_config_key is not None:
        checkbox = CheckBox()
        checkbox.setText(CHECKBOX_MESSAGE_REMEMBER_CHOICE)
        confirm_box.setCheckBox(checkbox)
    response = confirm_box.exec()
    confirmed_action = bool(response == confirm_option)
    remember = checkbox is not None and checkbox.isChecked()
    confirm_box.deleteLater()
    if remember:
        assert reminder_config_key is not None
        AppConfig().set(reminder_config_key, REMEMBER_OPTION_CONFIRM if confirmed_action else REMEMBER_OPTION_CANCEL)
    return confirmed_action


def open_image_file(parent: QWidget, mode: str = LOAD_IMAGE_MODE, selected_file: str = '',
                    save_formats: Optional[Iterable[str]] = None) -> Optional[str]:
    """Opens an image file for editing, saving, etc.

    - `selected_file` starts the dialog on that file. A save dialog also starts on a file that doesn't exist yet.
    - The dialog starts on the type entry listing `selected_file`'s extension, or else the first entry: ORA when
      saving, "All supported" when opening.
    - A save dialog appends the selected entry's first extension to a name typed without one.
    - `save_formats` limits a save dialog to those upper-case extensions, defaulting to every writable one.
    """
    loading = mode == LOAD_IMAGE_MODE
    filters = load_filters() if loading else save_filters(save_formats)
    file_dialog = QFileDialog(parent)
    file_dialog.setNameFilters(filters)
    file_dialog.setWindowTitle(TITLE_LOAD_IMAGE if loading else TITLE_SAVE_IMAGE)
    if os.path.isfile(selected_file) or (mode == SAVE_IMAGE_MODE and selected_file != ''):
        file_dialog.selectFile(selected_file)
    # The load list's first entry covers every extension, so only the per-format entries are matched:
    matching_filter = _filter_for_file(filters[1:] if loading else filters, selected_file)
    if matching_filter is not None:
        file_dialog.selectNameFilter(matching_filter)
    if loading:
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
    else:
        assert mode == SAVE_IMAGE_MODE
        file_dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setDefaultSuffix(_filter_extensions(matching_filter or filters[0])[0])
        dialog_ref = weakref.ref(file_dialog)  # A direct reference would make a cycle through the connection.

        def _update_suffix(name_filter: str) -> None:
            dialog = dialog_ref()
            if dialog is not None:
                dialog.setDefaultSuffix(_filter_extensions(name_filter)[0])
        file_dialog.filterSelected.connect(_update_suffix)
    max_size = get_screen_size(parent.window())
    file_dialog.setMaximumSize(max_size)
    try:
        if file_dialog.exec():
            return file_dialog.selectedFiles()[0]
        return None
    except (ValueError, UnidentifiedImageError) as err:
        show_error_dialog(parent, MESSAGE_LOAD_IMAGE_ERROR, err)
    return None


def open_image_layers(parent: QWidget) -> tuple[list[str], str] | tuple[None, None]:
    """Opens multiple image files to import as layers."""
    return QFileDialog.getOpenFileNames(parent, TITLE_LOAD_LAYER, filter=';;'.join(load_filters(layers=True)))
