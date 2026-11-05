"""Input fields for the typed values in the settings window, each with the `value`/`setValue`/`valueChanged` interface
the window's other controls share.

- `ColorSettingField`: a swatch button for a color string, optionally with a "theme default" state for the empty string.
- `DirectorySettingField`: a path field with a Browse button.
- `KeybindingField`: a key binding in a text field, beside its keycaps. Recording keys by
  pressing them would replace the text field and keep this class's interface.
- `SizeSettingField`: a width and height pair.
- `NumberSettingField`, `SliderSettingField`, `OptionSegmentsField`: the kit's number, slider and segmented controls
  with the shared interface.
"""
from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QHBoxLayout, QPushButton, QSizePolicy, QWidget

from src.ui.input_fields.line_edit import LineEdit
from src.ui.input_fields.number_field import NumberField
from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from src.ui.input_fields.slider_field import SliderField
from src.ui.modal.color_dialog import ColorDialog
from src.ui.widget.keycap_badge import KeycapBadge
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

SWATCH_ICON_SIZE = 16
SIZE_FIELD_MAX_WIDTH = 140
KEY_TEXT_MAX_WIDTH = 160
KEY_TEXT_MIN_WIDTH = 80
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


class KeybindingField(QWidget):
    """A key binding setting: a text field that edits the binding, beside a keycap for each alternative binding."""

    valueChanged = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._edit = LineEdit(self)
        self._edit.setMaximumWidth(KEY_TEXT_MAX_WIDTH)
        self._edit.valueChanged.connect(self._text_changed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit.setMinimumWidth(KEY_TEXT_MIN_WIDTH)
        layout.addWidget(self._edit, stretch=1)
        self._badge = KeycapBadge(NO_KEY_TEXT, self)
        layout.addWidget(self._badge)
        layout.addStretch(1)
        self.setFocusProxy(self._edit)
        self._show_badge('')

    def value(self) -> str:
        """Returns the key sequence text."""
        return self._edit.value()

    def setValue(self, new_value: str) -> None:  # pylint: disable=invalid-name
        """Sets the key sequence text."""
        self._edit.setValue(new_value)

    def badge_labels(self) -> list[str]:
        """Returns the label of each keycap shown."""
        return self._badge.labels

    def _text_changed(self, text: str) -> None:
        self._show_badge(text)
        self.valueChanged.emit(text)

    def _show_badge(self, key_text: str) -> None:
        self._badge.set_text(key_text if key_text.strip(', ') != '' else NO_KEY_TEXT)
        self._badge.setEnabled(key_text.strip(', ') != '')


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
    """A `SegmentedControl` over string options, with the shared `setValue` interface. It falls back to a combo box
    when too narrow for its segments."""

    def __init__(self, options: dict[str, str], parent: Optional[QWidget] = None) -> None:
        super().__init__([Segment(value, label) for value, label in options.items()], DisplayMode.LABEL,
                         combo_fallback=True, parent=parent)

    def setValue(self, new_value: str) -> None:  # pylint: disable=invalid-name
        """Selects the option with this value."""
        self.set_value(new_value)
