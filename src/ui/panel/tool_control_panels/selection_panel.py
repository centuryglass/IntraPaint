"""Base control panel for selection editing tools."""
from typing import Optional

from PySide6.QtCore import Qt, QSize, SignalInstance, QPoint
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QWidget, QApplication, QVBoxLayout, QPushButton, QHBoxLayout, QLabel, QLayout

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.selection_layer import SelectionLayer
from src.tools.base_tool import BaseTool
from src.ui.layout.reflowing_button_group import ReflowingButtonGroup
from src.util.shared_constants import PROJECT_DIR, SMALL_ICON_SIZE, EDIT_MODE_INPAINT
from src.util.visual.text_drawing_utils import get_key_display_string

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.selection_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


FILL_BUTTON_LABEL = _tr('Select All')
CLEAR_BUTTON_LABEL = _tr('Clear')
FILL_BUTTON_LABEL_WITH_KEY = _tr('Select All ({select_all_shortcut})')
CLEAR_BUTTON_LABEL_WITH_KEY = _tr('Clear ({clear_shortcut})')
CLEAR_PINS_BUTTON_LABEL = _tr('Clear Context Pins')
CLEAR_PINS_BUTTON_LABEL_WITH_KEY = _tr('Clear Context Pins ({clear_pins_shortcut})')
CLEAR_PINS_BUTTON_TOOLTIP = _tr('Remove all context pins. Right-click with the selection brush to add or remove pins.')
ICON_PATH_CLEAR = f'{PROJECT_DIR}/resources/icons/tool_modes/clear_all.svg'
ICON_PATH_FILL = f'{PROJECT_DIR}/resources/icons/tool_modes/fill.svg'
ICON_PATH_CLEAR_PINS = f'{PROJECT_DIR}/resources/icons/tool_modes/clear_context_pins.svg'


class SelectionPanel(QWidget):
    """Base control panel for selection editing tools."""

    def __init__(self, selection_layer: SelectionLayer, selection_tool: BaseTool) -> None:
        super().__init__()
        self._selection_layer = selection_layer
        self._selection_tool = selection_tool
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._insert_index = 0

        select_all_key = KeyConfig().get_keycodes(KeyConfig.SELECT_ALL_SHORTCUT)
        clear_key = KeyConfig().get_keycodes(KeyConfig.SELECT_NONE_SHORTCUT)
        clear_pins_key = KeyConfig().get_keycodes(KeyConfig.CLEAR_CONTEXT_PINS_SHORTCUT)
        select_all_shortcut = None if select_all_key == '' else get_key_display_string(select_all_key, rich_text=False)
        clear_shortcut = None if clear_key == '' else get_key_display_string(clear_key, rich_text=False)
        clear_pins_shortcut = None if clear_pins_key == '' \
            else get_key_display_string(clear_pins_key, rich_text=False)

        clear_selection_button = QPushButton()
        clear_selection_button.setText(CLEAR_BUTTON_LABEL if clear_shortcut is None
                                       else CLEAR_BUTTON_LABEL_WITH_KEY.format(clear_shortcut=clear_shortcut))
        clear_selection_button.setIcon(QIcon(QPixmap(ICON_PATH_CLEAR)))
        clear_selection_button.setIconSize(QSize(SMALL_ICON_SIZE, SMALL_ICON_SIZE))
        clear_selection_button.clicked.connect(lambda: selection_layer.clear())

        fill_selection_button = QPushButton()
        fill_selection_button.setText(FILL_BUTTON_LABEL if select_all_shortcut is None
                                      else FILL_BUTTON_LABEL_WITH_KEY.format(select_all_shortcut=select_all_shortcut))
        fill_selection_button.setIcon(QIcon(QPixmap(ICON_PATH_FILL)))
        fill_selection_button.setIconSize(QSize(SMALL_ICON_SIZE, SMALL_ICON_SIZE))
        fill_selection_button.clicked.connect(lambda: selection_layer.select_all())

        clear_pins_button = QPushButton()
        clear_pins_button.setText(CLEAR_PINS_BUTTON_LABEL if clear_pins_shortcut is None
                                  else CLEAR_PINS_BUTTON_LABEL_WITH_KEY.format(clear_pins_shortcut=clear_pins_shortcut))
        clear_pins_button.setToolTip(CLEAR_PINS_BUTTON_TOOLTIP)
        clear_pins_button.setIcon(QIcon(QPixmap(ICON_PATH_CLEAR_PINS)))
        clear_pins_button.setIconSize(QSize(SMALL_ICON_SIZE, SMALL_ICON_SIZE))

        def _clear_pins() -> None:
            selection_layer.clear_context_pins()
        clear_pins_button.clicked.connect(_clear_pins)
        self._clear_pins_button = clear_pins_button

        def _update_clear_pins_enabled(pins: list[QPoint]) -> None:
            clear_pins_button.setEnabled(len(pins) > 0)
        selection_layer.context_pins_changed.connect(_update_clear_pins_enabled)
        _update_clear_pins_enabled(selection_layer.context_pins)

        button_group = ReflowingButtonGroup()
        for button in (clear_selection_button, fill_selection_button, clear_pins_button):
            button_group.add_button(button)
        self._layout.addWidget(button_group)

        cache = Cache()
        padding_checkbox = cache.get_control_widget(Cache.INPAINT_FULL_RES)
        self._layout.addWidget(padding_checkbox)
        padding_line_layout = QHBoxLayout()
        padding_line_layout.setContentsMargins(0, 0, 0, 0)
        padding_line_layout.setSpacing(0)
        padding_line_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        padding_label = QLabel(cache.get_label(Cache.INPAINT_FULL_RES_PADDING))
        padding_line_layout.addWidget(padding_label)
        padding_spinbox = cache.get_control_widget(Cache.INPAINT_FULL_RES_PADDING)
        padding_line_layout.addWidget(padding_spinbox)

        def _set_inpaint_padding_visibility(should_show: bool) -> None:
            """Toggle padding controls based on the inpaint full res checkbox state:"""
            if should_show and cache.get(Cache.INPAINT_OPTIONS_AVAILABLE):
                padding_label.show()
                padding_spinbox.show()
            else:
                padding_label.hide()
                padding_spinbox.hide()
        assert isinstance(padding_checkbox.stateChanged, SignalInstance)
        padding_checkbox.stateChanged.connect(lambda state: _set_inpaint_padding_visibility(bool(state)))

        full_res_padding_tip = cache.get_tooltip(Cache.INPAINT_FULL_RES_PADDING)
        for padding_widget in (padding_label, padding_spinbox):
            padding_widget.setToolTip(full_res_padding_tip)
        self._layout.addLayout(padding_line_layout)
        _set_inpaint_padding_visibility(padding_checkbox.isChecked())

        def _set_inpainting_control_visibility(should_show: bool) -> None:
            """Toggle all inpainting controls based on available generator features:"""
            assert should_show == cache.get(Cache.INPAINT_OPTIONS_AVAILABLE)
            if should_show:
                padding_checkbox.show()
                if padding_checkbox.isChecked():
                    padding_label.show()
                    padding_spinbox.show()
                else:
                    padding_label.hide()
                    padding_spinbox.hide()
            else:
                padding_checkbox.hide()
                padding_label.hide()
                padding_spinbox.hide()
        cache.connect(self, Cache.INPAINT_OPTIONS_AVAILABLE, _set_inpainting_control_visibility)
        _set_inpainting_control_visibility(cache.get(Cache.INPAINT_OPTIONS_AVAILABLE))

        def _update_clear_pins_visibility(_=None) -> None:
            """Show the clear context pins button only while inpainting is available and selected."""
            clear_pins_button.setVisible(cache.get(Cache.INPAINT_OPTIONS_AVAILABLE)
                                         and cache.get(Cache.EDIT_MODE) == EDIT_MODE_INPAINT)
        cache.connect(self, Cache.INPAINT_OPTIONS_AVAILABLE, _update_clear_pins_visibility)
        cache.connect(self, Cache.EDIT_MODE, _update_clear_pins_visibility)
        _update_clear_pins_visibility()

    def minimumSizeHint(self) -> QSize:
        """Returns the layout's minimum width, and the height its contents need at that width.

        The button group stacks its buttons below the width of one row, so the panel is taller at its minimum width
        than its layout's minimum size says.
        """
        hint = super().minimumSizeHint()
        if self._layout.hasHeightForWidth():
            hint.setHeight(max(hint.height(), self._layout.totalHeightForWidth(hint.width())))
        return hint

    def insert_into_layout(self, layout_item: QWidget | QLayout, stretch=0) -> None:
        """Insert an item into the layout above all default items but below previously inserted content."""
        if isinstance(layout_item, QWidget):
            self._layout.insertWidget(self._insert_index, layout_item, stretch=stretch)
        else:
            assert isinstance(layout_item, QLayout)
            self._layout.insertLayout(self._insert_index, layout_item, stretch=stretch)
        self._insert_index += 1

    @property
    def selection_layer(self) -> SelectionLayer:
        """Returns the controlled selection layer."""
        return self._selection_layer

    @property
    def selection_tool_is_active(self) -> bool:
        """Returns whether this panel's tool is the active tool."""
        return self._selection_tool.is_active
