"""Tests ToolController tool loading, including startup without the compiled image_fill module."""
import importlib
import sys
from unittest.mock import patch

from src.controller import tool_controller
from src.controller.tool_controller import ToolController
from src.tools.draw_tool import DrawTool
from src.tools.eraser_tool import EraserTool
from src.tools.fill_tool import FillTool
from src.tools.selection_fill_tool import SelectionFillTool
from src.tools.shape_selection_tool import ShapeSelectionTool
from test.tools.tool_test_case import ToolTestCase

IMAGE_FILL_MODULE = 'src.util.visual.image_fill'
FILL_TOOL_MODULES = ('src.tools.fill_tool', 'src.tools.selection_fill_tool')


class ToolControllerTest(ToolTestCase):
    """ToolController tool loading tests."""

    def _load_all_tools(self) -> ToolController:
        """Builds a ToolController that loads the full tool set, without the libmypaint warning dialog."""
        with patch.object(tool_controller, 'show_warning_dialog'):
            return ToolController(self.image_stack, self.image_viewer, load_all_tools=True, use_hotkeys=False)

    def test_loads_fill_tools(self) -> None:
        """With image_fill available, both fill tools are loaded."""
        controller = self._load_all_tools()
        self.assertIsNotNone(controller.find_tool_by_class(FillTool))
        self.assertIsNotNone(controller.find_tool_by_class(SelectionFillTool))

    def test_starts_without_image_fill(self) -> None:
        """Without image_fill, ToolController starts with every tool except the two fill tools."""
        # Reloading rebinds the module-level fill tool imports. Reload again after the module state is restored.
        self.addCleanup(importlib.reload, tool_controller)
        with patch.dict(sys.modules):
            for module_name in FILL_TOOL_MODULES:
                del sys.modules[module_name]
            # A None entry makes the import statement raise ImportError, like an unbuilt image_fill module does.
            sys.modules[IMAGE_FILL_MODULE] = None  # type: ignore[assignment]
            importlib.reload(tool_controller)
            self.assertIsNone(tool_controller.FillTool)
            self.assertIsNone(tool_controller.SelectionFillTool)
            with self.assertLogs(tool_controller.__name__, level='WARNING') as construction_logs:
                controller = self._load_all_tools()
        self.assertTrue(any(tool_controller.FILL_TOOLS_UNAVAILABLE_LOG in message
                            for message in construction_logs.output), construction_logs.output)
        self.assertIsNone(controller.find_tool_by_class(FillTool))
        self.assertIsNone(controller.find_tool_by_class(SelectionFillTool))
        for tool_class in (DrawTool, EraserTool, ShapeSelectionTool):
            self.assertIsNotNone(controller.find_tool_by_class(tool_class))
        self.assertIsInstance(controller.active_tool, DrawTool)
