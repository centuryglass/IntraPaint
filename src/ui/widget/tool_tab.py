"""Tab widget associated with the ToolBar panel.  Connects to the ToolController to keep an up-to-date set of toolbar
   widgets for selecting the active tool."""
from typing import Optional

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller.tool_controller import ToolController
from src.tools.base_tool import BaseTool
from src.ui.layout.draggable_tabs.tab import Tab
from src.ui.widget.tool_button import ToolButton
from src.util.shared_constants import PROJECT_DIR

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.tool_tab'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


TOOL_TAB_NAME = _tr('Tools')

ICON_PATH_TOOL_TAB = f'{PROJECT_DIR}/resources/icons/tabs/wrench.svg'


class ToolTab(Tab):
    """Tab widget associated with the ToolBar panel.  Connects to the ToolController to keep an up-to-date set of
     toolbar widgets for selecting the active tool."""

    def __init__(self, tool_panel: QWidget, tool_controller: ToolController, parent: Optional[QWidget] = None) -> None:
        super().__init__(TOOL_TAB_NAME, tool_panel, KeyConfig.SELECT_TOOL_TAB, parent=parent)
        self.setIcon(QIcon(ICON_PATH_TOOL_TAB))
        self._toolbar_tool_widgets: dict[BaseTool, QWidget] = {}
        self._recent_tools: list[BaseTool] = []
        self._recent_tool_count = AppConfig().get(AppConfig.TOOLBAR_TOOL_BUTTON_COUNT)
        self._tool_controller = tool_controller
        recent_tool_list = Cache().get(Cache.RECENT_TOOLS)
        for tool_name in recent_tool_list:
            if len(self._recent_tools) >= self._recent_tool_count:
                break
            tool = tool_controller.find_tool_by_label(tool_name)
            if tool is not None:
                self._recent_tools.append(tool)
        for tool in tool_controller.tools:
            if len(self._recent_tools) < self._recent_tool_count and tool not in self._recent_tools:
                self._recent_tools.append(tool)
            tool_button = ToolButton(tool)
            tool_button.setVisible(False)
            tool_button.setParent(self)
            tool_button.tool_selected.connect(tool_controller.set_active_tool)
            self._toolbar_tool_widgets[tool] = tool_button
        for tool in self._recent_tools:
            self.add_tab_bar_widget(self._toolbar_tool_widgets[tool])
        tool_controller.tool_added.connect(self._add_tool_slot)
        tool_controller.tool_removed.connect(self._remove_tool_slot)
        tool_controller.active_tool_changed.connect(self._update_active_tool_slot)

        def _update_toolbar_button_count(count: int) -> None:
            self._recent_tool_count = count
            self._update_active_buttons()
        AppConfig().connect(self, AppConfig.TOOLBAR_TOOL_BUTTON_COUNT, _update_toolbar_button_count)

    def _update_active_buttons(self) -> None:
        if len(self._recent_tools) > self._recent_tool_count:
            self._recent_tools = self._recent_tools[:self._recent_tool_count]
        elif len(self._recent_tools) < self._recent_tool_count:
            for tool in self._toolbar_tool_widgets:
                if len(self._recent_tools) >= self._recent_tool_count:
                    break
                if tool not in self._recent_tools:
                    self._recent_tools.append(tool)
        active_buttons = self.tab_bar_widgets
        added = []
        removed = []
        items_moved = False
        try:
            self.blockSignals(True)
            for i, tool in enumerate(self._recent_tools):
                tool_button = self._toolbar_tool_widgets[tool]
                try:
                    current_idx = active_buttons.index(tool_button)
                except ValueError:
                    current_idx = -1
                if current_idx > 0:
                    if current_idx != i:
                        items_moved = True
                        self.move_tab_bar_widget(tool_button, i)
                        active_buttons.remove(tool_button)
                        active_buttons.insert(i, tool_button)
                else:
                    self.add_tab_bar_widget(tool_button, i)
                    tool_button.setVisible(True)
                    active_buttons.insert(i, tool_button)
                    added.append(tool_button)
            for active_button in active_buttons:
                assert isinstance(active_button, ToolButton)
                if active_button.connected_tool not in self._recent_tools:
                    self.remove_tab_bar_widget(active_button)
                    removed.append(active_button)
        finally:
            self.blockSignals(False)
        if len(added) == 0 and len(removed) == 0 and items_moved:
            self.tab_bar_widget_order_changed.emit()
        for added_button in added:
            self.tab_bar_widget_added.emit(added_button)
        for removed_button in removed:
            self.tab_bar_widget_removed.emit(removed_button)
            removed_button.setParent(self)
            removed_button.setVisible(False)
        if len(added) > 0 or len(removed) > 0 or items_moved:
            tool_labels = [tool.label for tool in self._recent_tools]
            Cache().set(Cache.RECENT_TOOLS, tool_labels)

    def _add_tool_slot(self, added_tool: BaseTool) -> None:
        assert added_tool not in self._toolbar_tool_widgets
        tool_button = ToolButton(added_tool)
        tool_button.hide()
        tool_button.tool_selected.connect(self._tool_controller.set_active_tool)
        self._toolbar_tool_widgets[added_tool] = tool_button
        self.add_tab_bar_widget(tool_button)

    def _remove_tool_slot(self, removed_tool: BaseTool) -> None:
        assert removed_tool in self._toolbar_tool_widgets
        self.remove_tab_bar_widget(self._toolbar_tool_widgets[removed_tool])
        del self._toolbar_tool_widgets[removed_tool]
        if removed_tool in self._recent_tools:
            self._recent_tools.remove(removed_tool)

    def _update_active_tool_slot(self, active_tool: BaseTool) -> None:
        for tool, tool_button in self._toolbar_tool_widgets.items():
            tool_button.is_active = tool == active_tool
        if active_tool in self._recent_tools:
            self._recent_tools.remove(active_tool)
            self._recent_tools.insert(0, active_tool)
        else:
            self._recent_tools.insert(0, active_tool)
            self._recent_tools = self._recent_tools[:self._recent_tool_count]
        self._update_active_buttons()
