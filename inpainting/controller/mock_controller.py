from PIL import Image
from inpainting.controller.base_controller import BaseInpaintController

class MockController(BaseInpaintController):
    """Mock controller for UI testing, performs no real inpainting"""
    def __init__(self, args):
        super().__init__(args)

    def _inpaint(self, selection, mask, loadImage):
        print("Mock inpainting call:")
        print(f"\tselection: {selection}")
        print(f"\tmask: {mask}")
        configOptions = self._config.list()
        for optionName in configOptions:
            value = self._config.get(optionName)
            print(f"\t{optionName}: {value}")
        testSample = Image.open(open('mask.png', 'rb')).convert('RGB')
        for y in range(0, self._config.get('batchCount')):
            for x in range(0, self._config.get('batchSize')):
                loadImage(testSample, y, x)

