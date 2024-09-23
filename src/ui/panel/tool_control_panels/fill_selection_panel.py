"""Selection panel for the SelectionFillTool class."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.selection_layer import SelectionLayer
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.slider_spinbox import FloatSliderSpinbox
from src.ui.layout.divider import Divider
from src.ui.panel.tool_control_panels.selection_panel import SelectionPanel
from src.ui.widget.key_hint_label import KeyHintLabel

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.fill_selection_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


FILL_BY_SELECTION = _tr('Fill selection holes')
FILL_BY_SELECTION_TOOLTIP = _tr('Fill based on selection shape only.')


class FillSelectionPanel(SelectionPanel):
    """Selection panel for the SelectionFillTool class."""

    def __init__(self, selection_layer: SelectionLayer) -> None:
        super().__init__(selection_layer)
        cache = Cache()
        threshold_slider = cache.get_control_widget(Cache.FILL_THRESHOLD)
        assert isinstance(threshold_slider, FloatSliderSpinbox)
        threshold_slider.setText(cache.get_label(Cache.FILL_THRESHOLD))
        self.insert_into_layout(threshold_slider)

        checkbox_row = QHBoxLayout()
        checkbox_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        sample_merged_checkbox = cache.get_control_widget(Cache.SAMPLE_MERGED)
        checkbox_row.addWidget(sample_merged_checkbox)

        toggle_hint = KeyHintLabel(config_key=KeyConfig.TOOL_ACTION_HOTKEY, parent=self)
        checkbox_row.addWidget(toggle_hint)

        def _try_toggle() -> bool:
            if not self.isVisible():
                return False
            sample_merged_checkbox.toggle()
            return True
        binding_id = f'FillSelectionPanel_{id(self)}_try_toggle'
        HotkeyFilter.instance().register_config_keybinding(binding_id, _try_toggle, KeyConfig.TOOL_ACTION_HOTKEY)

        self._color_select_checkbox = cache.get_control_widget(Cache.COLOR_SELECT_MODE)
        checkbox_row.addWidget(self._color_select_checkbox)

        self._fill_by_selection_checkbox = CheckBox()
        self._fill_by_selection_checkbox.setText(FILL_BY_SELECTION)
        self._fill_by_selection_checkbox.setToolTip(FILL_BY_SELECTION_TOOLTIP)
        checkbox_row.addWidget(self._fill_by_selection_checkbox)

        self.insert_into_layout(checkbox_row)
        self.insert_into_layout(Divider(Qt.Orientation.Horizontal))

    @property
    def fill_by_selection(self) -> bool:
        """Returns whether the tool should ignore image content when filling selection gaps"""
        return self._fill_by_selection_checkbox.isChecked()
