"""Selection panel for the ShapeSelectionTool class."""
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QCheckBox

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.selection_layer import SelectionLayer
from src.tools.base_tool import BaseTool
from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from src.ui.input_fields.selection_mode_bar import modifier_keys_text
from src.ui.panel.tool_control_panels.selection_panel import SelectionPanel
from src.ui.panel.tool_control_panels.stroke_block import tool_section
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.shape_mode import ShapeMode

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.shape_selection_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SHAPE_SECTION_TITLE = _tr('Shape')
FIXED_RATIO_LABEL = _tr('Fixed 1:1 ratio')
FIXED_RATIO_TOOLTIP = _tr('{description} Hold {keys} to fix the ratio for a single drag.')
ICON_PATH_RECT = f'{PROJECT_DIR}/resources/icons/tool_modes/rect_select.svg'
ICON_PATH_ELLIPSE = f'{PROJECT_DIR}/resources/icons/tool_modes/ellipse_select.svg'
SHAPE_MODES = (ShapeMode.RECTANGLE, ShapeMode.ELLIPSE)


class ShapeSelectionPanel(SelectionPanel):
    """Selection panel for the ShapeSelectionTool class: Mode, a Shape section, then Selection.

    The shape toggles when `KeyConfig.TOGGLE_SELECTION_SHAPE_HOTKEY` is pressed, or when the tool's own activation key
    is pressed while the tool is already active.
    """

    tool_mode_changed = Signal(str)

    def __init__(self, selection_layer: SelectionLayer, selection_tool: BaseTool) -> None:
        super().__init__(selection_layer, selection_tool)
        # Segment values are the `ShapeMode` names, so they never change with translation:
        self._shape_control = SegmentedControl(
            [Segment(mode.name, mode.display_text(), ICON_PATH_RECT if mode == ShapeMode.RECTANGLE
                     else ICON_PATH_ELLIPSE) for mode in SHAPE_MODES], DisplayMode.ICON_AND_LABEL, parent=self)
        self._shape_control.set_value(ShapeMode.RECTANGLE.name)
        self._shape_control.valueChanged.connect(
            lambda value: self.tool_mode_changed.emit(ShapeMode[value].display_text()))

        fixed_ratio = Cache().get_control_widget(Cache.SHAPE_SELECTION_FIXED_ASPECT)
        if isinstance(fixed_ratio, QCheckBox):
            fixed_ratio.setText(FIXED_RATIO_LABEL)
        self._fixed_ratio = fixed_ratio

        def _update_ratio_tooltip(_=None) -> None:
            fixed_ratio.setToolTip(FIXED_RATIO_TOOLTIP.format(
                description=Cache().get_tooltip(Cache.SHAPE_SELECTION_FIXED_ASPECT),
                keys=modifier_keys_text((KeyConfig.FIXED_ASPECT_MODIFIER,))))
        KeyConfig().connect(fixed_ratio, KeyConfig.FIXED_ASPECT_MODIFIER, _update_ratio_tooltip)
        _update_ratio_tooltip()
        self.insert_into_layout(tool_section(SHAPE_SECTION_TITLE, self._shape_control, fixed_ratio))

        def _try_toggle() -> bool:
            if not self.selection_tool_is_active:
                return False
            self.toggle_shape()
            return True
        for config_key in (KeyConfig.TOGGLE_SELECTION_SHAPE_HOTKEY, selection_tool.get_activation_config_key()):
            self.register_hotkey(f'toggle_{config_key}', _try_toggle, config_key)

    @property
    def shape_control(self) -> SegmentedControl:
        """The Shape control."""
        return self._shape_control

    def toggle_shape(self) -> None:
        """Switches between rectangle and ellipse."""
        current = ShapeMode[self._shape_control.value()]
        self._shape_control.set_value(ShapeMode.ELLIPSE.name if current == ShapeMode.RECTANGLE
                                      else ShapeMode.RECTANGLE.name)
