"""
Alternate mask to provide in modes that edit the entire selection.
"""
from data_model.image.mask_canvas import MaskCanvas
from data_model.config.application_config import AppConfig


class FilledMaskCanvas(MaskCanvas):
    """
    Alternate mask to provide in modes that edit the entire selection.
    """

    def __init__(self, config: AppConfig):
        super().__init__(config, None)
        self.fill()
