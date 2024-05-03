"""
Runs IntraPaint with no real image editing functionality. Intended for testing only.
"""
from PIL import Image
from controller.base_controller import BaseInpaintController

class MockController(BaseInpaintController):
    """Mock controller for UI testing, performs no real inpainting"""
    def __init__(self, args):
        super().__init__(args)

    def _inpaint(self, selection, mask, load_image):
        print("Mock inpainting call:")
        print(f"\tselection: {selection}")
        print(f"\tmask: {mask}")
        config_options = self._config.list()
        for option_name in config_options:
            value = self._config.get(option_name)
            print(f"\t{option_name}: {value}")
        test_sample = Image.open(open('mask.png', 'rb')).convert('RGB')
        for y in range(0, self._config.get('batchCount')):
            for x in range(0, self._config.get('batchSize')):
                load_image(test_sample, y, x)

