"""Input fields for the typed values in the settings window.

Each has the `value`/`setValue`/`valueChanged` interface the window's other controls share.

- `ColorSettingField`: a swatch button for a color string, optionally with a "theme default" state for the empty string.
- `DirectorySettingField`: a path field with a Browse button.
- `KeybindingField`: a key binding recorded by pressing keys, one recorder per alternative, with problems shown inline.
- `ModifierSettingField`: a modifier key binding chosen from a list of modifier combinations.
- `SizeSettingField`: a width and height pair.
- `NumberSettingField`, `SliderSettingField`, `OptionSegmentsField`: the kit's number, slider and segmented controls
  with the shared interface.
"""
from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFocusEvent, QIcon, QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QComboBox, QFileDialog, QHBoxLayout, QKeySequenceEdit, QLabel, \
    QPushButton, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from src.ui.input_fields.line_edit import LineEdit
from src.ui.input_fields.number_field import NumberField
from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from src.ui.input_fields.slider_field import SliderField
from src.ui.modal.color_dialog import ColorDialog
from src.ui.widget.keycap_badge import KeycapBadge
from src.util.layout import add_layout
from src.util.visual.image_utils import get_color_icon

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.input_fields.setting_fields'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


THEME_DEFAULT_LABEL = _tr('Theme default')
THEME_DEFAULT_TOOLTIP = _tr('Use the theme\'s color')
CHOOSE_COLOR_TOOLTIP = _tr('Choose a color')
BROWSE_LABEL = _tr('Browse...')
BROWSE_TOOLTIP = _tr('Choose a directory')
WIDTH_LABEL = _tr('Width')
HEIGHT_LABEL = _tr('Height')
NO_KEY_TEXT = _tr('Unbound')
RECORD_KEY_TOOLTIP = _tr('Click, then press the key or key combination to bind')
RECORD_KEY_NAME = _tr('Key binding')
ADD_KEY_LABEL = '+'
ADD_KEY_TOOLTIP = _tr('Bind an additional key')
DUPLICATE_KEY_NOTICE = _tr('"{key}" is already bound to this action')
UNRECORDABLE_KEY_NOTICE = _tr("That key can't be bound. Accent (dead) keys and some special keys aren't supported.")

SWATCH_ICON_SIZE = 16
SIZE_FIELD_MAX_WIDTH = 140
KEY_TEXT_MAX_WIDTH = 160
KEY_TEXT_MIN_WIDTH = 80
PROBLEM_STYLE = 'color: #c0392b;'
MODIFIER_PROBLEM_STYLE = 'QComboBox { border: 1px solid #c0392b; }'
DIRECTORY_FIELD_MAX_WIDTH = 420


class ColorSettingField(QWidget):
    """A color string setting: a swatch button that opens the color dialog.

    With `allow_theme_default`, the empty string means "use the theme's color". The button then shows the theme default
    state until a color is chosen, and a flat button returns to it.
    """

    valueChanged = Signal(str)

    def __init__(self, allow_theme_default: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._allow_theme_default = allow_theme_default
        self._value = ''
        self._button = QPushButton(self)
        self._button.setIconSize(QSize(SWATCH_ICON_SIZE, SWATCH_ICON_SIZE))
        self._button.setToolTip(CHOOSE_COLOR_TOOLTIP)
        self._button.clicked.connect(self._choose_color)
        self._theme_button: Optional[QPushButton] = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._button)
        if allow_theme_default:
            self._theme_button = QPushButton(THEME_DEFAULT_LABEL, self)
            self._theme_button.setToolTip(THEME_DEFAULT_TOOLTIP)
            self._theme_button.setFlat(True)
            self._theme_button.clicked.connect(lambda: self.setValue(''))
            layout.addWidget(self._theme_button)
        layout.addStretch(1)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._refresh()

    def value(self) -> str:
        """Returns the color as a `#AARRGGBB` string, or the empty string for the theme default."""
        return self._value

    def setValue(self, new_value: str) -> None:  # pylint: disable=invalid-name
        """Sets the color from a color string. An invalid string is ignored."""
        if new_value == '' and self._allow_theme_default:
            normalized = ''
        else:
            color = QColor(new_value)
            if not color.isValid():
                return
            normalized = color.name(QColor.NameFormat.HexArgb)
        if normalized != self._value:
            self._value = normalized
            self._refresh()
            self.valueChanged.emit(self._value)

    def is_theme_default(self) -> bool:
        """Returns whether the field is in its theme default state."""
        return self._allow_theme_default and self._value == ''

    def _choose_color(self) -> None:
        selection = ColorDialog.show_color_dialog(QColor(self._value) if self._value != '' else QColor('white'))
        if selection is not None:
            self.setValue(selection.name(QColor.NameFormat.HexArgb))

    def _refresh(self) -> None:
        if self.is_theme_default():
            self._button.setIcon(QIcon())
            self._button.setText(THEME_DEFAULT_LABEL)
        else:
            color = QColor(self._value) if self._value != '' else QColor(Qt.GlobalColor.transparent)
            self._button.setIcon(QIcon(get_color_icon(color)))
            self._button.setText(self._value.upper() if self._value != '' else '')
        if self._theme_button is not None:
            self._theme_button.setVisible(not self.is_theme_default())


class DirectorySettingField(QWidget):
    """A directory path setting: a text field and a Browse button."""

    valueChanged = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._edit = LineEdit(self)
        self._edit.setMaximumWidth(DIRECTORY_FIELD_MAX_WIDTH)
        self._edit.valueChanged.connect(self.valueChanged)
        self._browse_button = QPushButton(BROWSE_LABEL, self)
        self._browse_button.setToolTip(BROWSE_TOOLTIP)
        self._browse_button.clicked.connect(self._browse)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._edit, stretch=1)
        layout.addWidget(self._browse_button)
        layout.addStretch(1)
        self.setFocusProxy(self._edit)

    def value(self) -> str:
        """Returns the path text."""
        return self._edit.value()

    def setValue(self, new_value: str) -> None:  # pylint: disable=invalid-name
        """Sets the path text."""
        self._edit.setValue(new_value)

    def _browse(self) -> None:
        selection = QFileDialog.getExistingDirectory(self, BROWSE_TOOLTIP, self._edit.value())
        if selection != '':
            self._edit.setValue(selection)


# Keys that only start a combination or a composed character. A recorder ignores them and waits for the next key.
_KEY_RECORDER_IGNORED_KEYS = frozenset((Qt.Key.Key_AltGr, Qt.Key.Key_Mode_switch, Qt.Key.Key_Multi_key,
                                        Qt.Key.Key_Super_L, Qt.Key.Key_Super_R, Qt.Key.Key_Hyper_L,
                                        Qt.Key.Key_Hyper_R, Qt.Key.Key_Direction_L, Qt.Key.Key_Direction_R))
# Keys a recorder passes to QKeySequenceEdit unchecked, which waits for a non-modifier key:
_KEY_RECORDER_MODIFIER_KEYS = frozenset((Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta,
                                         Qt.Key.Key_unknown))


def _same_binding(first: str, second: str) -> bool:
    """Returns whether two binding texts name the same key combination, whatever their spelling."""
    return QKeySequence(first) == QKeySequence(second)


def is_recordable_key(key: Qt.Key | int) -> bool:
    """Returns whether a key's text reads back as the same key, so a binding saved as text can trigger it.

    Accent (dead) keys and a few special keys fail this. A binding to one would display as an unrelated character and
    never trigger.
    """
    text = QKeySequence(key).toString()
    if text == '':
        return False
    sequence = QKeySequence(text)
    return sequence.count() == 1 and sequence[0].key() == key


class _KeyRecorder(QKeySequenceEdit):
    """A QKeySequenceEdit that cancels on Esc and refuses keys that can't be saved as text.

    Esc leaves the recorder without changing its binding. A refused key leaves the binding as it was and emits
    `refused`.
    """

    refused = Signal()
    focus_lost = Signal(Qt.FocusReason)

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:  # pylint: disable=invalid-name
        """Cancels on Esc, ignores keys that start a combination, and refuses keys that can't be saved."""
        assert event is not None
        key = event.key()
        if key == Qt.Key.Key_Escape:
            event.accept()
            self.clearFocus()
            return
        if key in _KEY_RECORDER_IGNORED_KEYS:
            event.accept()
            return
        if key not in _KEY_RECORDER_MODIFIER_KEYS and not is_recordable_key(key):
            event.accept()
            self.refused.emit()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event: Optional[QFocusEvent]) -> None:  # pylint: disable=invalid-name
        """Reports the focus change after handling it."""
        assert event is not None
        super().focusOutEvent(event)
        self.focus_lost.emit(event.reason())


class _KeyRecorderRow(QWidget):
    """One alternative binding: a key recorder, whose clear button empties it."""

    changed = Signal(object)
    left_empty = Signal(object)
    refused = Signal()

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._text = text
        self._loading = False
        self.recorder = _KeyRecorder(self)
        self.recorder.setMaximumSequenceLength(1)
        self.recorder.setClearButtonEnabled(True)
        self.recorder.setMinimumWidth(KEY_TEXT_MIN_WIDTH)
        self.recorder.setMaximumWidth(KEY_TEXT_MAX_WIDTH)
        self.recorder.setToolTip(RECORD_KEY_TOOLTIP)
        self.recorder.setAccessibleName(RECORD_KEY_NAME)
        self.set_text(text)
        self.recorder.keySequenceChanged.connect(self._recorded)
        self.recorder.refused.connect(self.refused)
        self.recorder.focus_lost.connect(self._focus_lost)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.recorder)
        layout.addStretch(1)

    @property
    def text(self) -> str:
        """Returns the binding as text, or an empty string if none is recorded."""
        return self._text

    def set_text(self, text: str) -> None:
        """Shows a binding without emitting `changed`."""
        self._text = text
        self._loading = True
        try:
            self.recorder.setKeySequence(QKeySequence(text))
        finally:
            self._loading = False

    def _recorded(self, sequence: QKeySequence) -> None:
        if self._loading:
            return
        self._text = sequence.toString()
        self.changed.emit(self)

    def _focus_lost(self, reason: Qt.FocusReason) -> None:
        # Switching windows or opening a popup keeps the row, so the user can come back to it.
        if self._text == '' and reason not in (Qt.FocusReason.ActiveWindowFocusReason, Qt.FocusReason.PopupFocusReason):
            self.left_empty.emit(self)


class KeybindingField(QWidget):
    """A key binding setting recorded by pressing keys, with one recorder per alternative binding.

    The value is the list of alternative bindings `KeyConfig` stores. Text that wasn't recorded here keeps its
    spelling until the user records over it. The field holds at most one empty recorder: an emptied recorder is
    removed when it loses focus unless it is the only one, and the add button focuses an existing empty recorder. A
    key already bound in another recorder is not recorded twice. `set_problems` shows the messages that
    `KeyConfig.binding_problems` reports.
    """

    valueChanged = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._rows: list[_KeyRecorderRow] = []
        self._problems: list[str] = []
        self._notice = ''
        self._badge = KeycapBadge(NO_KEY_TEXT, self)
        self._rows_layout = QVBoxLayout()
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._add_button = QToolButton(self)
        self._add_button.setText(ADD_KEY_LABEL)
        self._add_button.setAutoRaise(True)
        self._add_button.setToolTip(ADD_KEY_TOOLTIP)
        self._add_button.setAccessibleName(ADD_KEY_TOOLTIP)
        self._add_button.clicked.connect(lambda _checked=False: self.add_binding())
        self._problem_label = QLabel(self)
        self._problem_label.setWordWrap(True)
        self._problem_label.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        add_layout(layout, self._rows_layout)
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        add_layout(layout, footer)
        footer.addWidget(self._badge)
        footer.addWidget(self._add_button)
        footer.addStretch(1)
        layout.addWidget(self._problem_label)
        self._add_row('')
        self._show_badge()

    def value(self) -> list[str]:
        """Returns the bindings as key sequence text, without repeats."""
        bindings: list[str] = []
        for binding in (row.text.strip() for row in self._rows):
            if binding != '' and not any(_same_binding(binding, earlier) for earlier in bindings):
                bindings.append(binding)
        return bindings

    def setValue(self, new_value: list[str]) -> None:  # pylint: disable=invalid-name
        """Sets the bindings from a list of key sequence text."""
        if new_value == self.value():
            return
        for row in self._rows:
            row.hide()
            row.deleteLater()
        self._rows = []
        self._notice = ''
        for text in [binding.strip() for binding in new_value if binding.strip() != ''] or ['']:
            self._add_row(text)
        self._show_badge()
        self._show_problems()
        self.valueChanged.emit(self.value())

    def add_binding(self) -> None:
        """Focuses the empty recorder, adding one first if every recorder holds a binding."""
        empty_rows = [row for row in self._rows if row.text == '']
        row = empty_rows[0] if empty_rows else self._add_row('')
        row.recorder.setFocus(Qt.FocusReason.OtherFocusReason)

    def badge_labels(self) -> list[str]:
        """Returns the label of each keycap shown."""
        return self._badge.labels

    def recorders(self) -> list[QKeySequenceEdit]:
        """Returns the key recorders, one per alternative binding plus at most one empty one."""
        return [row.recorder for row in self._rows]

    def problem_text(self) -> str:
        """Returns the problem text shown under the recorders, or an empty string if there is none."""
        return self._problem_label.text() if not self._problem_label.isHidden() else ''

    def set_problems(self, problems: list[str]) -> None:
        """Shows a list of problem messages inline, or hides the problem text if the list is empty."""
        self._problems = list(problems)
        self._show_problems()

    def _show_problems(self) -> None:
        messages = ([self._notice] if self._notice else []) + self._problems
        self._problem_label.setText('\n'.join(messages))
        self._problem_label.setVisible(len(messages) > 0)
        self._problem_label.setStyleSheet(PROBLEM_STYLE if messages else '')

    def _set_notice(self, notice: str) -> None:
        if notice != self._notice:
            self._notice = notice
            self._show_problems()

    def _add_row(self, text: str) -> _KeyRecorderRow:
        row = _KeyRecorderRow(text, self)
        row.changed.connect(self._row_changed)
        row.left_empty.connect(self._remove_empty_row)
        row.refused.connect(self._key_refused)
        self._rows.append(row)
        self._rows_layout.addWidget(row)
        return row

    def _key_refused(self) -> None:
        self._set_notice(UNRECORDABLE_KEY_NOTICE)

    def _remove_empty_row(self, row: _KeyRecorderRow) -> None:
        if row not in self._rows or row.text != '' or len(self._rows) < 2:
            return
        self._rows.remove(row)
        row.hide()
        row.deleteLater()

    def _row_changed(self, row: _KeyRecorderRow) -> None:
        notice = ''
        if row.text != '' and any(_same_binding(row.text, other.text) for other in self._rows if other is not row):
            notice = DUPLICATE_KEY_NOTICE.format(key=row.text)
            row.set_text('')
        elif row.text == '' and self._notice != '':
            # Recording a key clears the recorder first, so keep the notice until the next key arrives.
            notice = self._notice
        self._set_notice(notice)
        self._show_badge()
        self.valueChanged.emit(self.value())

    def _show_badge(self) -> None:
        bindings = self.value()
        self._badge.set_text(bindings if len(bindings) > 0 else NO_KEY_TEXT)
        self._badge.setEnabled(len(bindings) > 0)


class ModifierSettingField(QComboBox):
    """A modifier key binding: a combo box of the modifier combinations, with an unbound choice.

    A saved value that isn't one of the choices is added to the list so that it round-trips.
    """

    valueChanged = Signal(str)

    CHOICES = ('', 'Ctrl', 'Alt', 'Shift', 'Ctrl+Alt', 'Ctrl+Shift', 'Alt+Shift', 'Ctrl+Alt+Shift')

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._base_tooltip: Optional[str] = None
        for choice in self.CHOICES:
            self.addItem(choice if choice != '' else NO_KEY_TEXT, choice)
        self.currentIndexChanged.connect(lambda _index: self.valueChanged.emit(self.value()))

    def value(self) -> str:
        """Returns the modifier text, empty if unbound."""
        return str(self.currentData())

    def setValue(self, new_value: str) -> None:  # pylint: disable=invalid-name
        """Selects a modifier combination, adding it to the choices if it isn't listed."""
        index = self.findData(new_value)
        if index < 0:
            self.addItem(new_value, new_value)
            index = self.count() - 1
        self.setCurrentIndex(index)

    def choices(self) -> list[str]:
        """Returns the modifier text of each choice offered."""
        return [str(self.itemData(i)) for i in range(self.count())]

    def set_problems(self, problems: list[str]) -> None:
        """Shows problem messages as the tooltip, with a warning border; restores the tooltip when there are none."""
        if self._base_tooltip is None:
            self._base_tooltip = self.toolTip()
        self.setStyleSheet(MODIFIER_PROBLEM_STYLE if problems else '')
        if problems:
            self.setToolTip('\n'.join(problems))
        else:
            self.setToolTip(self._base_tooltip)
            self._base_tooltip = None


class SizeSettingField(QWidget):
    """A `QSize` setting: width and height number fields side by side."""

    valueChanged = Signal(QSize)

    def __init__(self, minimum: Optional[QSize] = None, maximum: Optional[QSize] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._width = NumberField(WIDTH_LABEL, 1, minimum.width() if minimum is not None else 1,
                                  maximum.width() if maximum is not None else None, parent=self)
        self._height = NumberField(HEIGHT_LABEL, 1, minimum.height() if minimum is not None else 1,
                                   maximum.height() if maximum is not None else None, parent=self)
        for field in (self._width, self._height):
            field.setMaximumWidth(SIZE_FIELD_MAX_WIDTH)
            field.valueChanged.connect(self._field_changed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._width)
        layout.addWidget(self._height)
        layout.addStretch(1)

    def value(self) -> QSize:
        """Returns the size."""
        return QSize(int(self._width.value()), int(self._height.value()))

    def setValue(self, new_value: QSize) -> None:  # pylint: disable=invalid-name
        """Sets the size."""
        if new_value != self.value():
            self._width.set_value(new_value.width())
            self._height.set_value(new_value.height())

    def _field_changed(self, _value: object) -> None:
        self.valueChanged.emit(self.value())


class NumberSettingField(NumberField):
    """A `NumberField` with the shared `setValue` interface."""

    def setValue(self, new_value: int | float) -> None:  # pylint: disable=invalid-name
        """Sets the number."""
        self.set_value(new_value)


class SliderSettingField(SliderField):
    """A `SliderField` with the shared `setValue` interface."""

    def setValue(self, new_value: int | float) -> None:  # pylint: disable=invalid-name
        """Sets the number."""
        self.set_value(new_value)


class OptionSegmentsField(SegmentedControl):
    """A `SegmentedControl` over string options. It falls back to a combo box when too narrow for its segments."""

    def __init__(self, options: dict[str, str], parent: Optional[QWidget] = None) -> None:
        super().__init__([Segment(value, label) for value, label in options.items()], DisplayMode.LABEL,
                         combo_fallback=True, parent=parent)
