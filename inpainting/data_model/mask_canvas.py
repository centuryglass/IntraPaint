from inpainting.image_utils import qImageToImage
from inpainting.data_model.base_canvas import BaseCanvas

class MaskCanvas(BaseCanvas):
    def __init__(self, config, image):
        super().__init__(config, image)
        self.setBrushSize(self._config.get('initialMaskBrushSize'))

    def getInpaintingMask(self):
        image = self.getImage()
        image = image.convert('L').point( lambda p: 255 if p < 1 else 0 )
        return image
