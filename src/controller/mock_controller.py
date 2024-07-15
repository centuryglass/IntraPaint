"""
Runs IntraPaint with no real image editing functionality. Intended for testing only.
"""
from typing import Optional

from PIL import Image
from PyQt6.QtCore import pyqtSignal

from src.config.application_config import AppConfig
from src.controller.base_controller import BaseInpaintController
from src.ui.modal.settings_modal import SettingsModal


class MockController(BaseInpaintController):
    """Mock controller for UI testing, performs no real inpainting"""

    def _inpaint(self,
                 source_image_section: Optional[Image.Image],
                 mask: Optional[Image.Image],
                 status_signal: pyqtSignal) -> None:
        print('Mock inpainting call:')
        print(f'\tselection: {source_image_section}')
        print(f'\tmask: {mask}')
        config = AppConfig()
        config_options = config.list()
        for option_name in config_options:
            value = config.get(option_name)
            print(f'\t{option_name}: {value}')
        with Image.open(open('mask.png', 'rb')).convert('RGB') as test_sample:
            for y in range(0, config.get(AppConfig.BATCH_COUNT)):
                for x in range(0, config.get(AppConfig.BATCH_SIZE)):
                    self._cache_generated_image(test_sample, x + y * config.get(AppConfig.BATCH_SIZE))

    def refresh_settings(self, unused_settings_modal: SettingsModal) -> None:
        """Settings not in scope for mock controller."""

    def update_settings(self, changed_settings: dict) -> None:
        """Settings not in scope for mock controller."""
