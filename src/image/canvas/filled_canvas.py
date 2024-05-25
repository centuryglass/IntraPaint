"""
Alternate mask to provide in modes that edit the entire selection.
"""
from src.image.canvas.mask_canvas import MaskCanvas
from src.config.application_config import AppConfig


class FilledMaskCanvas(MaskCanvas):
    """
    Alternate mask to provide in modes that edit the entire selection.
    """

    def __init__(self, config: AppConfig):
        super().__init__(config, None)
        self.fill()
