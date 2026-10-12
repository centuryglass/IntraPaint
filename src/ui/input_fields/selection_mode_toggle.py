"""A 2x2 toggle that sets the shared selection mode, showing the modifier keys that override it."""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QApplication

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.ui.input_fields.option_toggle import OptionToggle
from src.ui.widget.key_hint_label import KeyHintLabel
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.selection_mode import SelectionMode, SelectionModifiers

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.input_fields.selection_mode_toggle'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


MODE_LABELS = {
    SelectionMode.ADD: _tr('Add'),
    SelectionMode.SUBTRACT: _tr('Subtract'),
    SelectionMode.REPLACE: _tr('Replace'),
    SelectionMode.INTERSECT: _tr('Intersect')
}
MODE_TOOLTIPS = {
    SelectionMode.ADD: _tr('Add new areas to the selection'),
    SelectionMode.SUBTRACT: _tr('Remove new areas from the selection'),
    SelectionMode.REPLACE: _tr('Discard the selection, and select only new areas'),
    SelectionMode.INTERSECT: _tr('Keep only the part of the selection inside new areas')
}
MODE_ICONS = {
    SelectionMode.ADD: f'{PROJECT_DIR}/resources/icons/tool_modes/select.svg',
    SelectionMode.SUBTRACT: f'{PROJECT_DIR}/resources/icons/tool_modes/clear.svg',
    SelectionMode.REPLACE: f'{PROJECT_DIR}/resources/icons/tool_modes/replace.svg',
    SelectionMode.INTERSECT: f'{PROJECT_DIR}/resources/icons/tool_modes/intersect.svg'
}
# Order of the buttons, row by row:
MODE_ORDER = (SelectionMode.ADD, SelectionMode.SUBTRACT, SelectionMode.REPLACE, SelectionMode.INTERSECT)


def _mode_modifier_keys(modifiers: SelectionModifiers, mode: SelectionMode) -> tuple[str, ...]:
    """Returns the `KeyConfig` modifier keys that select a mode for one gesture, under a tool's modifier rule."""
    add, subtract = KeyConfig.SELECTION_ADD_MODIFIER, KeyConfig.SELECTION_SUBTRACT_MODIFIER
    if modifiers == SelectionModifiers.ADD_AND_SUBTRACT:
        return {SelectionMode.ADD: (add,), SelectionMode.SUBTRACT: (subtract,),
                SelectionMode.REPLACE: (KeyConfig.SELECTION_REPLACE_MODIFIER,),
                SelectionMode.INTERSECT: (add, subtract)}[mode]
    if modifiers == SelectionModifiers.BRUSH and mode == SelectionMode.SUBTRACT:
        return (subtract,)
    return ()


def _modifier_config_keys() -> tuple[str, ...]:
    """Returns every `KeyConfig` key the toggle's keycaps can show."""
    return KeyConfig.SELECTION_ADD_MODIFIER, KeyConfig.SELECTION_SUBTRACT_MODIFIER, KeyConfig.SELECTION_REPLACE_MODIFIER


# Space between keycaps, and between the keycaps and the button edge:
KEYCAP_SPACING = 2


class SelectionModeToggle(OptionToggle):
    """A 2x2 toggle bound to `Cache.SELECTION_MODE`.

    Each button shows the selection modifier keys that select its mode for one gesture under the tool's `modifiers`
    rule, and while those keys are held the overriding mode's button is highlighted in place of the stored mode's.
    """

    def __init__(self, parent: Optional[QWidget] = None,
                 modifiers: SelectionModifiers = SelectionModifiers.ADD_AND_SUBTRACT) -> None:
        super().__init__(parent, [MODE_LABELS[mode] for mode in MODE_ORDER], 2)
        self._modifiers = modifiers
        self._held_modifiers = Qt.KeyboardModifier.NoModifier
        self.set_icons(*(MODE_ICONS[mode] for mode in MODE_ORDER))
        self.set_tooltips(*(MODE_TOOLTIPS[mode] for mode in MODE_ORDER))
        # Each mode's keycaps, with the `KeyConfig` key each one shows:
        self._keycaps: dict[SelectionMode, list[tuple[str, KeyHintLabel]]] = {mode: [] for mode in MODE_ORDER}
        if modifiers != SelectionModifiers.NONE:
            for mode in MODE_ORDER:
                for config_key in _mode_modifier_keys(modifiers, mode):
                    self._keycaps[mode].append((config_key, KeyHintLabel(config_key=config_key, parent=self)))
            for config_key in _modifier_config_keys():
                KeyConfig().connect(self, config_key, self._update_keycap_margins)
            HotkeyFilter.instance().modifiers_changed.connect(self._modifiers_changed_slot)
            self._update_keycap_margins()

        cache = Cache()
        self._cache_value_slot(cache.get(Cache.SELECTION_MODE))
        cache.connect(self, Cache.SELECTION_MODE, self._cache_value_slot)
        self.valueChanged.connect(self._value_changed_slot)

    # noinspection PyPep8Naming
    def deleteLater(self) -> None:  # pylint: disable=invalid-name  # Qt override
        """Disconnect from config before scheduling deletion."""
        Cache().disconnect(self, Cache.SELECTION_MODE)
        if self._modifiers != SelectionModifiers.NONE:
            for config_key in _modifier_config_keys():
                KeyConfig().disconnect(self, config_key)
        super().deleteLater()

    def highlighted_option(self) -> Optional[str]:
        """Returns the label of the mode a gesture would use with the currently held modifiers."""
        if self._selected is None:
            return None
        mode = self._modifiers.mode_for_gesture(self._mode_for_label(self._selected), self._held_modifiers)
        return MODE_LABELS[mode]

    def set_held_modifiers(self, modifiers: Qt.KeyboardModifier) -> None:
        """Updates the highlighted button for a change in held keyboard modifiers."""
        if modifiers == self._held_modifiers:
            return
        self._held_modifiers = modifiers
        self.update_highlight()

    def _modifiers_changed_slot(self, modifiers: Qt.KeyboardModifier) -> None:
        self.set_held_modifiers(modifiers)

    @staticmethod
    def _mode_for_label(label: str) -> SelectionMode:
        for mode, mode_label in MODE_LABELS.items():
            if mode_label == label:
                return mode
        raise ValueError(f'Unexpected selection mode label {label}')

    def _cache_value_slot(self, mode_value: str) -> None:
        try:
            mode = SelectionMode(mode_value)
        except ValueError:
            mode = SelectionMode.ADD
        self.setValue(MODE_LABELS[mode])
        self._update_keycap_visibility()

    def _value_changed_slot(self, label: Optional[str]) -> None:
        if label is not None:
            Cache().set(Cache.SELECTION_MODE, self._mode_for_label(label).value)

    @staticmethod
    def _is_bound(config_key: str) -> bool:
        return KeyConfig().get(config_key) != ''

    def _update_keycap_margins(self, _=None) -> None:
        """Reserves room at each button's right edge for its bound keycaps, then updates keycap visibility."""
        for mode in MODE_ORDER:
            reserved_width = 0
            for config_key, keycap in self._keycaps[mode]:
                if self._is_bound(config_key):
                    reserved_width += keycap.sizeHint().width() + KEYCAP_SPACING
            self.option_label(MODE_LABELS[mode]).setContentsMargins(0, 0, reserved_width, 0)
        self.updateGeometry()
        self._layout_buttons()
        self._update_keycap_visibility()

    def _update_keycap_visibility(self) -> None:
        """Shows each bound keycap, except on the stored mode's button, where no modifier is needed.

        Space stays reserved for the stored mode's keycaps, so changing the mode never resizes the buttons.
        """
        stored_mode = None if self._selected is None else self._mode_for_label(self._selected)
        for mode in MODE_ORDER:
            for config_key, keycap in self._keycaps[mode]:
                keycap.setHidden(mode == stored_mode or not self._is_bound(config_key))

    def _layout_buttons(self) -> None:
        """Places the buttons, then lines up each button's keycaps against its right edge."""
        super()._layout_buttons()
        for index, mode in enumerate(MODE_ORDER):
            x, y, width, height = self.cell_geometry(index)
            right = x + width - KEYCAP_SPACING
            for config_key, keycap in reversed(self._keycaps[mode]):
                if not self._is_bound(config_key):
                    continue
                size = keycap.sizeHint()
                right -= size.width()
                keycap.setGeometry(right, y + (height - size.height()) // 2, size.width(), size.height())
                keycap.raise_()
                right -= KEYCAP_SPACING
