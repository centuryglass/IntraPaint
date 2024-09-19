"""Control panel for the fill/paint bucket tool"""
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QFormLayout

from src.config.cache import Cache
from src.ui.input_fields.pattern_combo_box import PatternComboBox
from src.ui.widget.color_button import ColorButton


class FillToolPanel(QWidget):
    """Control panel for the fill/paint bucket tool"""

    def __init__(self):
        super().__init__()
        cache = Cache()
        self._layout = QFormLayout(self)
        color_button = ColorButton()
        self._layout.addRow(color_button)
        pattern_dropdown = PatternComboBox(Cache.FILL_TOOL_BRUSH_PATTERN)
        self._layout.addRow(cache.get_label(Cache.FILL_TOOL_BRUSH_PATTERN), pattern_dropdown)
        threshold_slider = cache.get_control_widget(Cache.FILL_THRESHOLD)
        self._layout.addRow(cache.get_label(Cache.FILL_THRESHOLD), threshold_slider)
        sample_merged_checkbox = cache.get_control_widget(Cache.SAMPLE_MERGED)
        self._layout.addRow(sample_merged_checkbox)
        selection_only_checkbox = cache.get_control_widget(Cache.PAINT_SELECTION_ONLY)
        self._layout.addRow(selection_only_checkbox)

        def _update_pattern_color(color_str: str) -> None:
            if QColor.isValidColor(color_str):
                color = QColor(color_str)
                pattern_dropdown.set_icon_colors(color)
        cache.connect(self, Cache.LAST_BRUSH_COLOR, _update_pattern_color)
