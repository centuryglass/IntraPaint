"""Shows the edited image in its own window."""
from PyQt6.QtGui import QIcon

from src.image.layers.image_stack import ImageStack
from src.tools.generation_area_tool import GenerationAreaTool
from src.controller.tool_controller import ToolController
from src.ui.panel.image_panel import ImagePanel
from src.util.shared_constants import APP_ICON_PATH


class ImageWindow(ImagePanel):
    """Shows the edited image in its own window."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__(image_stack)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self._image_stack = image_stack
        self._tool_controller = ToolController(image_stack, self.image_viewer)
        self._generation_area_tool = GenerationAreaTool(image_stack, self.image_viewer)
        self._tool_controller.active_tool = self._generation_area_tool
