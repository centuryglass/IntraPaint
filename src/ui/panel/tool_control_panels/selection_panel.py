"""Base control panel for selection editing tools."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QWidget, QApplication, QVBoxLayout, QPushButton, QHBoxLayout, QLabel, QLayout

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.selection_layer import SelectionLayer
from src.util.shared_constants import PROJECT_DIR, ICON_SIZE
from src.util.visual.text_drawing_utils import get_key_display_string

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.selection_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


FILL_BUTTON_LABEL = _tr('Select All')
CLEAR_BUTTON_LABEL = _tr('Clear')
FILL_BUTTON_LABEL_WITH_KEY = _tr('Select All ({select_all_shortcut})')
CLEAR_BUTTON_LABEL_WITH_KEY = _tr('Clear ({clear_shortcut})')
ICON_PATH_CLEAR = f'{PROJECT_DIR}/resources/icons/tool_modes/clear_all.svg'
ICON_PATH_FILL = f'{PROJECT_DIR}/resources/icons/tool_modes/fill.svg'


class SelectionPanel(QWidget):
    """Base control panel for selection editing tools."""

    def __init__(self, selection_layer: SelectionLayer) -> None:
        super().__init__()
        self._selection_layer = selection_layer
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._insert_index = 0

        select_all_key = KeyConfig().get_keycodes(KeyConfig.SELECT_ALL_SHORTCUT)
        clear_key = KeyConfig().get_keycodes(KeyConfig.SELECT_NONE_SHORTCUT)
        select_all_shortcut = None if select_all_key == '' else get_key_display_string(select_all_key, rich_text=False)
        clear_shortcut = None if clear_key == '' else get_key_display_string(clear_key, rich_text=False)

        clear_selection_button = QPushButton()
        clear_selection_button.setText(CLEAR_BUTTON_LABEL if clear_shortcut is None
                                       else CLEAR_BUTTON_LABEL_WITH_KEY.format(clear_shortcut=clear_shortcut))
        clear_selection_button.setIcon(QIcon(QPixmap(ICON_PATH_CLEAR)))
        clear_selection_button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        clear_selection_button.clicked.connect(lambda: selection_layer.clear())

        fill_selection_button = QPushButton()
        fill_selection_button.setText(FILL_BUTTON_LABEL if select_all_shortcut is None
                                      else FILL_BUTTON_LABEL_WITH_KEY.format(select_all_shortcut=select_all_shortcut))
        fill_selection_button.setIcon(QIcon(QPixmap(ICON_PATH_FILL)))
        fill_selection_button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        fill_selection_button.clicked.connect(lambda: selection_layer.select_all())
        clear_fill_line_layout = QHBoxLayout()
        clear_fill_line_layout.addWidget(clear_selection_button)
        clear_fill_line_layout.addSpacing(10)
        clear_fill_line_layout.addWidget(fill_selection_button)
        self._layout.addLayout(clear_fill_line_layout)

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

        def _show_hide_padding(should_show: bool) -> None:
            if should_show:
                padding_label.show()
                padding_spinbox.show()
            else:
                padding_label.hide()
                padding_spinbox.hide()
        padding_checkbox.stateChanged.connect(lambda state: _show_hide_padding(bool(state)))
        full_res_padding_tip = cache.get_tooltip(Cache.INPAINT_FULL_RES_PADDING)
        for padding_widget in (padding_label, padding_spinbox):
            padding_widget.setToolTip(full_res_padding_tip)
        self._layout.addLayout(padding_line_layout)
        _show_hide_padding(padding_checkbox.isChecked())

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
