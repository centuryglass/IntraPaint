"""Selection panel for the SelectionBrushTool class."""
from typing import Optional

from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.selection_layer import SelectionLayer
from src.tools.base_tool import BaseTool
from src.ui.input_fields.selection_mode_bar import modifier_keys_text
from src.ui.input_fields.slider_field import SliderField
from src.ui.layout.label_column_layout import normalize_row_label
from src.ui.panel.tool_control_panels.selection_panel import SelectionPanel
from src.ui.panel.tool_control_panels.stroke_block import KEYS_TOOLTIP, PIXEL_SUFFIX, tool_section
from src.util.visual.selection_mode import SelectionModifiers

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.brush_selection_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


# Also used by the draw tool's mode toggle:
TOOL_MODE_SELECT = _tr('Select')
TOOL_MODE_DESELECT = _tr('Deselect')
BRUSH_SECTION_TITLE = _tr('Brush')
MODE_HINT = _tr('Hold {subtract_keys} to subtract. {line_keys} draws a straight line.')
MODE_HINT_WITH_PINS = _tr('Hold {subtract_keys} to subtract. {line_keys} draws a straight line. Right-click adds a '
                          'context pin.')


class BrushSelectionPanel(SelectionPanel):
    """Selection panel for the SelectionBrushTool class: Mode, a Brush section with the Size field, then
    Selection."""

    def __init__(self, selection_layer: SelectionLayer, selection_tool: BaseTool) -> None:
        super().__init__(selection_layer, selection_tool, modifiers=SelectionModifiers.BRUSH)
        cache = Cache()
        key_config = KeyConfig()
        minimum, maximum, step = cache.get_range(Cache.SELECTION_BRUSH_SIZE)
        assert minimum is not None and maximum is not None and step is not None
        size_field = SliderField(normalize_row_label(cache.get_label(Cache.SELECTION_BRUSH_SIZE)),
                                 cache.get(Cache.SELECTION_BRUSH_SIZE), minimum, maximum, step=step,
                                 suffix=PIXEL_SUFFIX, parent=self)
        size_field.setToolTip(KEYS_TOOLTIP.format(description=cache.get_tooltip(Cache.SELECTION_BRUSH_SIZE),
                                                  decrease=key_config.get(KeyConfig.BRUSH_SIZE_DECREASE),
                                                  increase=key_config.get(KeyConfig.BRUSH_SIZE_INCREASE)))

        def _field_changed(value: int | float) -> None:
            if cache.get(Cache.SELECTION_BRUSH_SIZE) != value:
                cache.set(Cache.SELECTION_BRUSH_SIZE, int(value))

        size_field.valueChanged.connect(_field_changed)
        cache.connect(size_field, Cache.SELECTION_BRUSH_SIZE, lambda value, *_: size_field.set_value(value))
        self._size_field = size_field
        self.insert_into_layout(tool_section(BRUSH_SECTION_TITLE, size_field))

        def _update_hint(_=None) -> None:
            text = MODE_HINT_WITH_PINS if cache.get(Cache.INPAINT_OPTIONS_AVAILABLE) else MODE_HINT
            self.set_mode_hint(text.format(subtract_keys=modifier_keys_text((KeyConfig.SELECTION_SUBTRACT_MODIFIER,)),
                                           line_keys=modifier_keys_text((KeyConfig.LINE_MODIFIER,))))
        cache.connect(size_field, Cache.INPAINT_OPTIONS_AVAILABLE, _update_hint)
        for config_key in (KeyConfig.SELECTION_SUBTRACT_MODIFIER, KeyConfig.LINE_MODIFIER):
            key_config.connect(size_field, config_key, _update_hint)
        _update_hint()

    @property
    def size_field(self) -> SliderField:
        """The brush Size field."""
        return self._size_field
