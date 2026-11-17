"""Selection panel for the MagicWandTool class."""
from typing import Optional

from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.selection_layer import SelectionLayer
from src.tools.base_tool import BaseTool
from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from src.ui.input_fields.slider_field import SliderField
from src.ui.panel.tool_control_panels.fill_tool_panel import build_sample_merged_checkbox, build_threshold_field
from src.ui.panel.tool_control_panels.selection_panel import SelectionPanel
from src.ui.panel.tool_control_panels.stroke_block import tool_section
from src.util.visual.magic_wand_area import FillArea, stored_fill_area

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.magic_wand_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


FILL_AREA_SECTION_TITLE = _tr('Fill area')


class MagicWandPanel(SelectionPanel):
    """Selection panel for the MagicWandTool class: Mode, a Fill area section, then Selection.

    The Fill area control is bound to `Cache.SELECTION_FILL_AREA`. Color threshold and Sample merged are the controls
    the Fill tool shows, and have no effect in Holes mode, so the panel disables them there.
    """

    def __init__(self, selection_layer: SelectionLayer, selection_tool: BaseTool) -> None:
        super().__init__(selection_layer, selection_tool)
        cache = Cache()
        self._area_control = SegmentedControl(
            [Segment(area.value, area.label, tooltip=area.tooltip) for area in FillArea], DisplayMode.LABEL,
            parent=self)
        self._area_control.set_value(stored_fill_area().value)
        self._area_control.valueChanged.connect(lambda value: cache.set(Cache.SELECTION_FILL_AREA, value))
        self._threshold_field = build_threshold_field(self)
        self._sample_merged_checkbox = build_sample_merged_checkbox()

        def _area_changed(_=None) -> None:
            area = stored_fill_area()
            self._area_control.set_value(area.value)
            for widget in (self._threshold_field, self._sample_merged_checkbox):
                widget.setEnabled(area != FillArea.HOLES)
        cache.connect(self._area_control, Cache.SELECTION_FILL_AREA, _area_changed)
        _area_changed()
        self.insert_into_layout(tool_section(FILL_AREA_SECTION_TITLE, self._area_control, self._threshold_field,
                                             self._sample_merged_checkbox))

        def _try_toggle() -> bool:
            if not self.selection_tool_is_active:
                return False
            self._sample_merged_checkbox.toggle()
            return True
        self.register_hotkey('toggle_sample_merged', _try_toggle, KeyConfig.TOGGLE_SAMPLE_MERGED_HOTKEY)

    @property
    def fill_area(self) -> FillArea:
        """Returns the area the tool should select."""
        return stored_fill_area()

    @property
    def area_control(self) -> SegmentedControl:
        """The Fill area control."""
        return self._area_control

    @property
    def threshold_field(self) -> SliderField:
        """The Color threshold field."""
        return self._threshold_field
