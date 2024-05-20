"""
Alternate mask to provide in modes that edit the entire selection.
"""
from data_model.canvas.mask_canvas import MaskCanvas
from data_model.config import Config

class FilledMaskCanvas(MaskCanvas):
    """
    Alternate mask to provide in modes that edit the entire selection.
    """
    def __init__(self, config: Config):
        super().__init__(config, None)
        self.fill()
