"""Base control panel for selection editing tools: a Mode section, the tool's own sections, then a Selection section.

The Mode section holds the shared `Cache.SELECTION_MODE` bar and one line naming the modifiers that override it. The
panel registers `KeyConfig.TOOL_ACTION_HOTKEY` to cycle the mode while its tool is active. Subclasses add their
sections with `insert_into_layout`, which places them between Mode and Selection.

The panel is a `FitToolPanel`. Sections stack in a side panel. A strip packs them into columns
(`src.ui.layout.column_packing`), stacking sections in a column while they fit the strip's height. The Selection
buttons take a row, or a column when the row doesn't fit. The modifier hint is optional: a plan without room
for it moves it to `overflow_content`, which the Tools panel shows in its More popover. The selection's bounds (two
read-only lines under the Selection buttons) are optional too, and are left out before the hint is.
"""
from typing import Callable, Optional
from weakref import ref

from PySide6.QtCore import Qt, QSize, QPoint, QEvent, QRect
from PySide6.QtGui import QIcon, QPixmap, QPalette, QShowEvent
from PySide6.QtWidgets import QWidget, QApplication, QVBoxLayout, QPushButton, QLabel, QBoxLayout

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.selection_layer import SelectionLayer
from src.tools.base_tool import BaseTool
from src.ui.button_weight import ButtonWeight, set_button_weight
from src.ui.input_fields.selection_mode_bar import SelectionModeBar, MODE_ORDER, MODE_LABELS, modifier_keys_text
from src.ui.layout.panel_fit import REQUIRED, FitItem, FitPlanner, Orientation, Placement
from src.ui.panel.tool_control_panels.fit_tool_panel import FitToolPanel
from src.ui.panel.tool_control_panels.stroke_block import tool_section
from src.ui.widget.key_hint_label import KeyHintLabel
from src.ui.widget.panel_section import PanelSection
from src.util.shared_constants import PROJECT_DIR, SMALL_ICON_SIZE, EDIT_MODE_INPAINT
from src.util.visual.selection_mode import SelectionMode, SelectionModifiers, stored_selection_mode
from src.util.visual.key_hint_text import key_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.selection_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


MODE_SECTION_TITLE = _tr('Mode')
MODE_SECTION_TITLE_WITH_MODE = _tr('Mode: {mode}')
SELECTION_SECTION_TITLE = _tr('Selection')
SELECT_ALL_LABEL = _tr('Select all')
CLEAR_LABEL = _tr('Clear')
CLEAR_PINS_LABEL = _tr('Clear pins')
TOOLTIP_WITH_KEY = _tr('{description} ({shortcut})')
SELECT_ALL_TOOLTIP = _tr('Select the whole image')
CLEAR_TOOLTIP = _tr('Clear the selection')
CLEAR_PINS_TOOLTIP = _tr('Remove all context pins. Right-click in the image with any selection tool to add, move or '
                         'remove pins.')
MODIFIER_HINT_BOTH = _tr('Hold {add_keys} to add, {subtract_keys} to subtract.')
MODIFIER_HINT_SUBTRACT = _tr('Hold {subtract_keys} to subtract.')
BOUNDS_POSITION_LINE = _tr('Position: {x}, {y}')
BOUNDS_SIZE_LINE = _tr('Size: {width} x {height}')
BOUNDS_EMPTY_VALUE = _tr('-')
BOUNDS_SUMMARY = _tr('{width} x {height} at {x}, {y}')
BOUNDS_SUMMARY_EMPTY = _tr('Nothing selected')
ICON_PATH_CLEAR = f'{PROJECT_DIR}/resources/icons/tool_modes/clear_all.svg'
ICON_PATH_FILL = f'{PROJECT_DIR}/resources/icons/tool_modes/fill.svg'
ICON_PATH_CLEAR_PINS = f'{PROJECT_DIR}/resources/icons/tool_modes/clear_context_pins.svg'


def next_selection_mode(mode: SelectionMode) -> SelectionMode:
    """Returns the mode after `mode` in the mode bar's order, wrapping around."""
    return MODE_ORDER[(MODE_ORDER.index(mode) + 1) % len(MODE_ORDER)]


def _with_shortcut(description: str, config_key: str) -> str:
    keys = key_hint_text(KeyConfig().get(config_key))
    if keys == '':
        return description
    return TOOLTIP_WITH_KEY.format(description=description, shortcut=keys)


# The planned items: the Selection buttons in a row or a column, the optional modifier hint, and the optional bounds:
_BUTTONS_ITEM = FitItem(REQUIRED, 2)
_HINT_ITEM = FitItem(1)
_BOUNDS_ITEM = FitItem(2)


class SelectionPanel(FitToolPanel):
    """Base control panel for selection editing tools.

    The line under the mode bar names the add and subtract modifiers, unless `set_mode_hint` replaces it. The Selection
    section ends with the selection's position and size, refreshed while the panel is visible. Without a
    host that calls `set_fit_space`, the panel plans for its own size when resized.
    """

    def __init__(self, selection_layer: SelectionLayer, selection_tool: BaseTool,
                 modifiers: SelectionModifiers = SelectionModifiers.ADD_AND_SUBTRACT) -> None:
        super().__init__()
        self._selection_layer = selection_layer
        # Weak, since the tool owns the panel:
        self._selection_tool = ref(selection_tool)
        self._layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # Mode, the tool's sections, then Selection:
        self._sections: list[PanelSection] = []
        cache = Cache()

        # Mode section:
        self._mode_bar = SelectionModeBar(self, modifiers)
        self._hint_label = QLabel(self)
        self._hint_label.setWordWrap(True)
        self._mode_hint: Optional[str] = None
        mode_body = QWidget()
        self._mode_layout = QVBoxLayout(mode_body)
        self._mode_layout.setContentsMargins(0, 0, 0, 0)
        self._mode_layout.addWidget(self._mode_bar)
        self._mode_layout.addWidget(self._hint_label)
        self._mode_section = PanelSection(MODE_SECTION_TITLE, mode_body)
        self._mode_section.add_header_widget(KeyHintLabel(config_key=KeyConfig.TOOL_ACTION_HOTKEY, parent=self))

        def _update_mode_title(_=None) -> None:
            self._mode_section.set_title(MODE_SECTION_TITLE_WITH_MODE.format(
                mode=MODE_LABELS[stored_selection_mode()]))
        cache.connect(self, Cache.SELECTION_MODE, _update_mode_title)
        _update_mode_title()
        for config_key in (KeyConfig.SELECTION_ADD_MODIFIER, KeyConfig.SELECTION_SUBTRACT_MODIFIER):
            KeyConfig().connect(self, config_key, self._update_hint)
        self._update_hint()

        def _cycle_mode() -> bool:
            if not self.selection_tool_is_active:
                return False
            cache.set(Cache.SELECTION_MODE, next_selection_mode(stored_selection_mode()).value)
            return True
        self.register_hotkey('cycle_mode', _cycle_mode, KeyConfig.TOOL_ACTION_HOTKEY)

        # Selection section:
        select_all_button = self._action_button(SELECT_ALL_LABEL, ICON_PATH_FILL,
                                                _with_shortcut(SELECT_ALL_TOOLTIP, KeyConfig.SELECT_ALL_SHORTCUT))
        select_all_button.clicked.connect(lambda: selection_layer.select_all())  # pylint: disable=unnecessary-lambda
        clear_button = self._action_button(CLEAR_LABEL, ICON_PATH_CLEAR,
                                           _with_shortcut(CLEAR_TOOLTIP, KeyConfig.SELECT_NONE_SHORTCUT))
        set_button_weight(clear_button, ButtonWeight.DANGER)
        clear_button.clicked.connect(lambda: selection_layer.clear())  # pylint: disable=unnecessary-lambda
        clear_pins_button = self._action_button(CLEAR_PINS_LABEL, ICON_PATH_CLEAR_PINS,
                                                _with_shortcut(CLEAR_PINS_TOOLTIP,
                                                               KeyConfig.CLEAR_CONTEXT_PINS_SHORTCUT))
        set_button_weight(clear_pins_button, ButtonWeight.DANGER)
        clear_pins_button.clicked.connect(lambda: selection_layer.clear_context_pins())  # pylint: disable=unnecessary-lambda
        self._clear_pins_button = clear_pins_button

        def _update_clear_pins_enabled(pins: list[QPoint]) -> None:
            clear_pins_button.setEnabled(len(pins) > 0)
        selection_layer.context_pins_changed.connect(_update_clear_pins_enabled)
        _update_clear_pins_enabled(selection_layer.context_pins)

        def _update_clear_pins_visibility(_=None) -> None:
            """Show the clear pins button only while inpainting is available and selected."""
            clear_pins_button.setVisible(cache.get(Cache.INPAINT_OPTIONS_AVAILABLE)
                                         and cache.get(Cache.EDIT_MODE) == EDIT_MODE_INPAINT)
        cache.connect(self, Cache.INPAINT_OPTIONS_AVAILABLE, _update_clear_pins_visibility)
        cache.connect(self, Cache.EDIT_MODE, _update_clear_pins_visibility)
        _update_clear_pins_visibility()

        self._actions_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._actions_layout.addWidget(select_all_button)
        self._actions_layout.addStretch(1)
        self._actions_layout.addWidget(clear_pins_button)
        self._actions_layout.addWidget(clear_button)

        self._bounds_position_label = self._bounds_label()
        self._bounds_size_label = self._bounds_label()
        self._bounds_view = QWidget()
        bounds_layout = QVBoxLayout(self._bounds_view)
        bounds_layout.setContentsMargins(0, 0, 0, 0)
        bounds_layout.addWidget(self._bounds_position_label)
        bounds_layout.addWidget(self._bounds_size_label)
        self._selection_section = tool_section(SELECTION_SECTION_TITLE, self._actions_layout, self._bounds_view)
        for section in (self._mode_section, self._selection_section):
            self._add_section(section, len(self._sections))
        self._layout.addStretch(1)
        self._update_bounds_width()
        self._refresh_bounds()
        selection_layer.content_changed.connect(self._handle_content_changed)
        selection_layer.size_changed.connect(self._update_bounds_width)
        self._planner = FitPlanner([_BUTTONS_ITEM, _HINT_ITEM, _BOUNDS_ITEM], self._apply_fit, self._measure_fit)

    @staticmethod
    def _bounds_label() -> QLabel:
        label = QLabel()
        label.setWordWrap(False)
        label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _update_bounds_width(self, *_) -> None:
        """Reserves the width of the widest bounds lines the layer allows, so changing values never resize them."""
        layer = self._selection_layer
        sample = '-' + '8' * len(str(max(layer.width, layer.height)))
        metrics = self._bounds_position_label.fontMetrics()
        width = max(metrics.horizontalAdvance(BOUNDS_POSITION_LINE.format(x=sample, y=sample)),
                    metrics.horizontalAdvance(BOUNDS_SIZE_LINE.format(width=sample, height=sample)))
        for label in (self._bounds_position_label, self._bounds_size_label):
            label.setMinimumWidth(width)

    def _handle_content_changed(self, *_) -> None:
        if self.isVisible():
            self._refresh_bounds()

    def _refresh_bounds(self) -> None:
        """Shows the selection's bounds in the Selection section's lines and its collapsed summary."""
        bounds: QRect = self._selection_layer.get_content_bounds()
        if bounds.isEmpty():
            dash = BOUNDS_EMPTY_VALUE
            self._bounds_position_label.setText(BOUNDS_POSITION_LINE.format(x=dash, y=dash))
            self._bounds_size_label.setText(BOUNDS_SIZE_LINE.format(width=dash, height=dash))
            self._selection_section.set_summary(BOUNDS_SUMMARY_EMPTY)
            return
        self._bounds_position_label.setText(BOUNDS_POSITION_LINE.format(x=bounds.x(), y=bounds.y()))
        self._bounds_size_label.setText(BOUNDS_SIZE_LINE.format(width=bounds.width(), height=bounds.height()))
        self._selection_section.set_summary(BOUNDS_SUMMARY.format(x=bounds.x(), y=bounds.y(), width=bounds.width(),
                                                                  height=bounds.height()))

    def showEvent(self, event: QShowEvent) -> None:  # pylint: disable=invalid-name
        """Brings the bounds up to date after the panel was hidden."""
        super().showEvent(event)
        self._refresh_bounds()

    def changeEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """Recomputes the reserved bounds width after a font change."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self._update_bounds_width()

    @staticmethod
    def _action_button(label: str, icon_path: str, tooltip: str) -> QPushButton:
        button = QPushButton(label)
        button.setIcon(QIcon(QPixmap(icon_path)))
        button.setIconSize(QSize(SMALL_ICON_SIZE, SMALL_ICON_SIZE))
        button.setToolTip(tooltip)
        return button

    def register_hotkey(self, name: str, action: Callable[[], bool], config_key: str) -> None:
        """Binds a config key to an action for as long as the panel exists. `name` must be unique in the panel; the
           action returns whether it consumed the key."""
        if KeyConfig().get(config_key) == '':
            return
        binding_id = f'{type(self).__name__}_{id(self)}_{name}'
        HotkeyFilter.instance().register_config_keybinding(binding_id, action, config_key)
        self.destroyed.connect(lambda *_: HotkeyFilter.instance().remove_keybinding(binding_id))

    def set_mode_hint(self, text: Optional[str]) -> None:
        """Replaces the line under the mode bar. None restores the default."""
        self._mode_hint = text
        self._update_hint()

    def _update_hint(self, _=None) -> None:
        if self._mode_hint is not None:
            self._hint_label.setText(self._mode_hint)
            self._hint_label.setVisible(self._mode_hint != '')
            return
        add_keys = modifier_keys_text((KeyConfig.SELECTION_ADD_MODIFIER,))
        subtract_keys = modifier_keys_text((KeyConfig.SELECTION_SUBTRACT_MODIFIER,))
        if add_keys != '' and subtract_keys != '':
            text = MODIFIER_HINT_BOTH.format(add_keys=add_keys, subtract_keys=subtract_keys)
        elif subtract_keys != '':
            text = MODIFIER_HINT_SUBTRACT.format(subtract_keys=subtract_keys)
        else:
            text = ''
        self._hint_label.setText(text)
        self._hint_label.setVisible(text != '')

    def minimumSizeHint(self) -> QSize:
        """Returns the layout's minimum width, and the height its contents need at that width."""
        hint = super().minimumSizeHint()
        if self._layout.hasHeightForWidth():
            hint.setHeight(max(hint.height(), self._layout.totalHeightForWidth(hint.width())))
        return hint

    def _apply_fit(self, orientation: Orientation, placement: Placement) -> None:
        self._orientation = orientation
        self._actions_layout.setDirection(QBoxLayout.Direction.LeftToRight if placement[0] == 0
                                          else QBoxLayout.Direction.TopToBottom)
        if placement[1] is None:
            self._overflow_layout.addWidget(self._hint_label)
        else:
            self._mode_layout.addWidget(self._hint_label)
        if placement[2] is None:
            self._overflow_layout.addWidget(self._bounds_view)
        else:
            self._selection_section.body.layout().addWidget(self._bounds_view)
        # Moving a widget to another parent hides it:
        self._bounds_view.show()
        self._arrange_box_sections(self._layout, self._sections, orientation)

    def _add_section(self, section: PanelSection, index: int) -> None:
        self._sections.insert(index, section)
        self._packer.watch(section)
        if not self._packer.packing:
            self._layout.insertWidget(index, section)

    def insert_into_layout(self, section: PanelSection) -> None:
        """Adds a tool's section after the Mode section and previously inserted sections, above the Selection
        section."""
        self._add_section(section, len(self._sections) - 1)
        self._refit()

    @property
    def mode_bar(self) -> SelectionModeBar:
        """Returns the selection mode bar."""
        return self._mode_bar

    @property
    def selection_layer(self) -> SelectionLayer:
        """Returns the controlled selection layer."""
        return self._selection_layer

    @property
    def selection_tool_is_active(self) -> bool:
        """Returns whether this panel's tool is the active tool."""
        selection_tool = self._selection_tool()
        return selection_tool is not None and selection_tool.is_active
