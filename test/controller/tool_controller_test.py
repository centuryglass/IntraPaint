"""Tests ToolController tool loading, including startup without the compiled image_fill module, and the padding scroll
   modifier."""
import importlib
import sys
from unittest.mock import patch

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.config_entry import RangeKey
from src.controller import tool_controller
from src.controller.tool_controller import ToolController, WHEEL_NOTCH_DELTA
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


class PaddingScrollTest(ToolTestCase):
    """Padding scroll modifier tests."""

    def setUp(self) -> None:
        super().setUp()
        self.activate_tool(DrawTool(self.image_stack, self.image_viewer))
        self.padding_step = (Cache().get(Cache.INPAINT_FULL_RES_PADDING, RangeKey.STEP)
                             * QApplication.wheelScrollLines())

    def _send_wheel(self, angle_delta: QPoint,
                    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.ShiftModifier) -> None:
        """Sends a synthetic wheel event over the center of the image viewer."""
        center = QPointF(self.image_viewer.width() / 2, self.image_viewer.height() / 2)
        event = QWheelEvent(center, self.image_viewer.mapToGlobal(center), QPoint(), angle_delta,
                            Qt.MouseButton.NoButton, modifiers, Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(self.image_viewer, event)

    def test_scroll_changes_padding_without_zooming(self) -> None:
        """A notch with the modifier held changes padding by the slider's wheel step, and the view doesn't zoom."""
        Cache().set(Cache.INPAINT_FULL_RES_PADDING, 32)
        self._send_wheel(QPoint(0, WHEEL_NOTCH_DELTA))
        self.assertEqual(Cache().get(Cache.INPAINT_FULL_RES_PADDING), 32 + self.padding_step)
        self._send_wheel(QPoint(0, -WHEEL_NOTCH_DELTA * 2))
        self.assertEqual(Cache().get(Cache.INPAINT_FULL_RES_PADDING), 32 - self.padding_step)
        self.assertEqual(self.image_viewer.scene_scale, 1.0)

    def test_horizontal_scroll_changes_padding(self) -> None:
        """Horizontal scroll counts, for platforms that turn Shift + vertical scroll horizontal."""
        Cache().set(Cache.INPAINT_FULL_RES_PADDING, 32)
        self._send_wheel(QPoint(WHEEL_NOTCH_DELTA, 0))
        self.assertEqual(Cache().get(Cache.INPAINT_FULL_RES_PADDING), 32 + self.padding_step)

    def test_partial_notches_accumulate(self) -> None:
        """High-resolution wheel deltas change padding once they add up to a full notch."""
        Cache().set(Cache.INPAINT_FULL_RES_PADDING, 32)
        self._send_wheel(QPoint(0, WHEEL_NOTCH_DELTA // 2))
        self.assertEqual(Cache().get(Cache.INPAINT_FULL_RES_PADDING), 32)
        self._send_wheel(QPoint(0, WHEEL_NOTCH_DELTA // 2))
        self.assertEqual(Cache().get(Cache.INPAINT_FULL_RES_PADDING), 32 + self.padding_step)

    def test_speed_modifier_multiplies_step(self) -> None:
        """Holding the speed modifier too multiplies the padding step."""
        Cache().set(Cache.INPAINT_FULL_RES_PADDING, 32)
        self._send_wheel(QPoint(0, WHEEL_NOTCH_DELTA),
                         Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier)
        multiplier = AppConfig().get(AppConfig.SPEED_MODIFIER_MULTIPLIER)
        self.assertEqual(Cache().get(Cache.INPAINT_FULL_RES_PADDING), 32 + self.padding_step * multiplier)

    def test_padding_clamps_to_range(self) -> None:
        """Padding stays within its configured range."""
        Cache().set(Cache.INPAINT_FULL_RES_PADDING, 1)
        self._send_wheel(QPoint(0, -WHEEL_NOTCH_DELTA))
        self.assertEqual(Cache().get(Cache.INPAINT_FULL_RES_PADDING),
                         Cache().get(Cache.INPAINT_FULL_RES_PADDING, RangeKey.MIN))

    def test_raising_padding_enables_full_res(self) -> None:
        """Scrolling padding above zero turns Inpaint Full Resolution on."""
        Cache().set(Cache.INPAINT_FULL_RES, False)
        Cache().set(Cache.INPAINT_FULL_RES_PADDING, 0)
        self._send_wheel(QPoint(0, WHEEL_NOTCH_DELTA))
        self.assertTrue(Cache().get(Cache.INPAINT_FULL_RES))

    def test_scroll_without_modifier_zooms(self) -> None:
        """Without the modifier, padding is unchanged and the view zooms as before."""
        Cache().set(Cache.INPAINT_FULL_RES_PADDING, 32)
        self._send_wheel(QPoint(0, WHEEL_NOTCH_DELTA), Qt.KeyboardModifier.NoModifier)
        self.assertEqual(Cache().get(Cache.INPAINT_FULL_RES_PADDING), 32)
        self.assertGreater(self.image_viewer.scene_scale, 1.0)
