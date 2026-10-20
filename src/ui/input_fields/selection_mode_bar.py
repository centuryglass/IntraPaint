"""A segmented control bound to `Cache.SELECTION_MODE`, in the fixed order Replace, Add, Subtract, Intersect."""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.selection_mode import SelectionMode, SelectionModifiers, stored_selection_mode
from src.util.visual.text_drawing_utils import get_key_display_string

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.input_fields.selection_mode_bar'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


MODE_ORDER = (SelectionMode.REPLACE, SelectionMode.ADD, SelectionMode.SUBTRACT, SelectionMode.INTERSECT)
MODE_LABELS = {
    SelectionMode.REPLACE: _tr('Replace'),
    SelectionMode.ADD: _tr('Add'),
    SelectionMode.SUBTRACT: _tr('Subtract'),
    SelectionMode.INTERSECT: _tr('Intersect')
}
MODE_ICONS = {
    SelectionMode.REPLACE: f'{PROJECT_DIR}/resources/icons/tool_modes/replace.svg',
    SelectionMode.ADD: f'{PROJECT_DIR}/resources/icons/tool_modes/select.svg',
    SelectionMode.SUBTRACT: f'{PROJECT_DIR}/resources/icons/tool_modes/clear.svg',
    SelectionMode.INTERSECT: f'{PROJECT_DIR}/resources/icons/tool_modes/intersect.svg'
}
MODE_TOOLTIPS = {
    SelectionMode.REPLACE: _tr('Discard the selection, and select only new areas'),
    SelectionMode.ADD: _tr('Add new areas to the selection'),
    SelectionMode.SUBTRACT: _tr('Remove new areas from the selection'),
    SelectionMode.INTERSECT: _tr('Keep only the part of the selection inside new areas')
}
MODE_TOOLTIP_WITH_KEYS = _tr('{description} (hold {keys})')


def mode_modifier_keys(modifiers: SelectionModifiers, mode: SelectionMode) -> tuple[str, ...]:
    """Returns the `KeyConfig` modifier keys that select a mode for one gesture, under a tool's modifier rule."""
    add, subtract = KeyConfig.SELECTION_ADD_MODIFIER, KeyConfig.SELECTION_SUBTRACT_MODIFIER
    if modifiers == SelectionModifiers.ADD_AND_SUBTRACT:
        return {SelectionMode.ADD: (add,), SelectionMode.SUBTRACT: (subtract,),
                SelectionMode.REPLACE: (KeyConfig.SELECTION_REPLACE_MODIFIER,),
                SelectionMode.INTERSECT: (add, subtract)}[mode]
    if modifiers == SelectionModifiers.BRUSH and mode == SelectionMode.SUBTRACT:
        return (subtract,)
    return ()


def modifier_keys_text(config_keys: tuple[str, ...]) -> str:
    """Returns the display text for holding every listed modifier, such as "Shift+Alt"."""
    names = [get_key_display_string(KeyConfig().get(key), rich_text=False) for key in config_keys
             if KeyConfig().get(key) != '']
    return '+'.join(names)


def _modifier_config_keys() -> tuple[str, ...]:
    return KeyConfig.SELECTION_ADD_MODIFIER, KeyConfig.SELECTION_SUBTRACT_MODIFIER, KeyConfig.SELECTION_REPLACE_MODIFIER


class SelectionModeBar(SegmentedControl):
    """Four icon segments bound to `Cache.SELECTION_MODE`.

    While modifier keys are held, the segment the gesture would use under the tool's `modifiers` rule is highlighted
    without changing the stored mode. Each segment's tooltip names the modifiers that pick it.
    """

    def __init__(self, parent: Optional[QWidget] = None,
                 modifiers: SelectionModifiers = SelectionModifiers.ADD_AND_SUBTRACT) -> None:
        super().__init__([Segment(mode.value, MODE_LABELS[mode], MODE_ICONS[mode]) for mode in MODE_ORDER],
                         DisplayMode.ICON, parent=parent)
        self._modifiers = modifiers
        self._held_modifiers = Qt.KeyboardModifier.NoModifier
        self._update_tooltips()
        cache = Cache()
        self.set_value(stored_selection_mode().value)
        cache.connect(self, Cache.SELECTION_MODE, self._cache_value_slot)
        self.valueChanged.connect(lambda value: cache.set(Cache.SELECTION_MODE, value))
        if modifiers != SelectionModifiers.NONE:
            for config_key in _modifier_config_keys():
                KeyConfig().connect(self, config_key, self._update_tooltips)
            HotkeyFilter.instance().modifiers_changed.connect(self.set_held_modifiers)

    # noinspection PyPep8Naming
    def deleteLater(self) -> None:  # pylint: disable=invalid-name  # Qt override
        """Disconnect from config before scheduling deletion."""
        Cache().disconnect(self, Cache.SELECTION_MODE)
        if self._modifiers != SelectionModifiers.NONE:
            for config_key in _modifier_config_keys():
                KeyConfig().disconnect(self, config_key)
        super().deleteLater()

    @property
    def modifiers(self) -> SelectionModifiers:
        """Returns the modifier rule the bar previews."""
        return self._modifiers

    def set_held_modifiers(self, modifiers: Qt.KeyboardModifier) -> None:
        """Highlights the segment a gesture would use with the given modifiers held, if it isn't the stored mode."""
        self._held_modifiers = modifiers
        stored = stored_selection_mode()
        mode = self._modifiers.mode_for_gesture(stored, modifiers)
        self.set_hint_value(None if mode == stored else mode.value)

    def modifier_hint(self, mode: SelectionMode) -> str:
        """Returns the display text of the modifiers that pick a mode, or an empty string if none do."""
        return modifier_keys_text(mode_modifier_keys(self._modifiers, mode))

    def _update_tooltips(self, _=None) -> None:
        for mode in MODE_ORDER:
            self.set_segment_tooltip(mode.value, self._tooltip(mode))

    def _tooltip(self, mode: SelectionMode) -> str:
        keys = self.modifier_hint(mode)
        title = f'{MODE_LABELS[mode]}: {MODE_TOOLTIPS[mode]}'
        return title if keys == '' else MODE_TOOLTIP_WITH_KEYS.format(description=title, keys=keys)

    def _cache_value_slot(self, mode_value: str) -> None:
        self.set_value(stored_selection_mode().value if mode_value not in MODE_VALUES else mode_value)
        self.set_held_modifiers(self._held_modifiers)


MODE_VALUES = tuple(mode.value for mode in MODE_ORDER)
