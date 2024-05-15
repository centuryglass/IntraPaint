"""
Alternate mask to provide in modes that edit the entire selection.
"""
from data_model.canvas.mask_canvas import MaskCanvas

class FilledMaskCanvas(MaskCanvas):
    """
    Alternate mask to provide in modes that edit the entire selection.
    """
    def __init__(self, config):
        super().__init__(config, None)
        self.fill()
