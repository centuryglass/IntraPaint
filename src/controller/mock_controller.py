"""
Runs IntraPaint with no real image editing functionality. Intended for testing only.
"""
from typing import Optional, Callable
from PIL import Image
from PyQt5.QtCore import pyqtSignal
from src.controller.base_controller import BaseInpaintController
from src.config.application_config import AppConfig
from src.ui.modal.settings_modal import SettingsModal


class MockController(BaseInpaintController):
    """Mock controller for UI testing, performs no real inpainting"""

    def _inpaint(self,
                 selection: Optional[Image.Image],
                 mask: Optional[Image.Image],
                 save_image: Callable[[Image.Image, int], None],
                 status_signal: pyqtSignal) -> None:
        print('Mock inpainting call:')
        print(f'\tselection: {selection}')
        print(f'\tmask: {mask}')
        config_options = self._config.list()
        for option_name in config_options:
            value = self._config.get(option_name)
            print(f'\t{option_name}: {value}')
        with Image.open(open('mask.png', 'rb')).convert('RGB') as test_sample:
            for y in range(0, self._config.get(AppConfig.BATCH_COUNT)):
                for x in range(0, self._config.get(AppConfig.BATCH_SIZE)):
                    save_image(test_sample, x + y * self._config.get(AppConfig.BATCH_SIZE))

    def refresh_settings(self, unused_settings_modal: SettingsModal) -> None:
        """Settings not in scope for mock controller."""

    def update_settings(self, changed_settings: dict) -> None:
        """Settings not in scope for mock controller."""
