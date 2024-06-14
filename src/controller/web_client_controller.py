"""
Provides image editing functionality through the GLID-3-XL API provided through IntraPaint_server.py or
colabFiles/IntraPaint_colab_server.ipynb.
"""
import sys
from typing import Optional, Callable, Any, Dict, List
import requests
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QInputDialog
from PIL import Image

from src.controller.local_controller import GLID_CONFIG_CATEGORY
from src.ui.window.main_window import MainWindow
from src.util.screen_size import get_screen_size
from src.ui.modal.settings_modal import SettingsModal
from src.controller.base_controller import BaseInpaintController
from src.util.image_utils import load_image_from_base64, image_to_base64
from src.config.application_config import AppConfig


class WebClientController(BaseInpaintController):
    """Provides image editing functionality through the GLID-3-XL API."""

    def __init__(self, args):
        super().__init__(args)
        self._server_url = args.server_url
        self._fast_ngrok_connection = args.fast_ngrok_connection
        self._window = None

    @staticmethod
    def health_check(url: str):
        """Static method to check if the GLID-3-XL API is available."""
        try:
            res = requests.get(url, timeout=30)
            return res.status_code == 200 and ('application/json' in res.headers['content-type']) \
                and 'success' in res.json() and res.json()['success'] is True
        except requests.exceptions.RequestException as err:
            print(f'Request error: {err}')
            return False

    def get_config_categories(self) -> List[str]:
        """Return the list of AppConfig categories this controller supports."""
        categories = super().get_config_categories()
        categories.append(GLID_CONFIG_CATEGORY)
        return categories

    def window_init(self) -> None:
        """Initialize and show the main application window."""
        self._window = MainWindow(self._layer_stack, self)
        size = get_screen_size(self._window)
        self._window.setGeometry(0, 0, size.width(), size.height())
        self._window.show()

        # Make sure a valid connection exists:
        def prompt_for_url(prompt_text: str) -> None:
            """Requests a server URL from the user."""
            new_url, url_entered = QInputDialog.getText(self._window, 'Inpainting UI', prompt_text)
            if not url_entered:  # User clicked 'Cancel'
                sys.exit()
            if new_url != '':
                self._server_url = new_url

        # Get URL if one was not provided on the command line:
        while self._server_url == '':
            print('requesting url:')
            prompt_for_url('Enter server URL:')

        # Check connection:
        while not WebClientController.health_check(self._server_url):
            prompt_for_url('Server connection failed, enter a new URL or click "OK" to retry')

    def _inpaint(self,
                 source_image_section: Optional[Image.Image],
                 mask: Optional[Image.Image],
                 save_image: Callable[[Image.Image, int], None],
                 status_signal: pyqtSignal) -> None:
        """Handle image editing operations using the GLID-3-XL API.
        Parameters
        ----------
        source_image_section : PIL Image, optional
            Image selection to edit
        mask : PIL Image, optional
            Mask marking edited image region.
        save_image : function (PIL Image, int)
            Function used to return each image response and its index.
        status_signal : pyqtSignal
            Signal to emit when status updates are available.
        """
        assert source_image_section is not None and mask is not None, "GLID-3-XL only supports inpainting"
        config = AppConfig.instance()
        batch_size = config.get(AppConfig.BATCH_SIZE)
        batch_count = config.get(AppConfig.BATCH_COUNT)
        body = {
            'batch_size': batch_size,
            'num_batches': batch_count,
            'edit': image_to_base64(source_image_section),
            'mask': image_to_base64(mask),
            'prompt': config.get(AppConfig.PROMPT),
            'negative': config.get(AppConfig.NEGATIVE_PROMPT),
            'guidanceScale': config.get(AppConfig.GUIDANCE_SCALE),
            'skipSteps': config.get(AppConfig.SKIP_STEPS),
            'width': source_image_section.width,
            'height': source_image_section.height
        }

        def error_check(server_response: requests.Response, context_str: str):
            """Make sure network errors throw exceptions with useful error messages."""
            if server_response.status_code != 200:
                if server_response.content and ('application/json' in server_response.headers['content-type']) \
                        and server_response.json() and 'error' in server_response.json():
                    raise RuntimeError(f'{server_response.status_code} response to {context_str}: '
                                       f'{server_response.json()["error"]}')
                print(f'RESPONSE: {server_response.content}')
                raise RuntimeError(f'{server_response.status_code} response to {context_str}: unknown error')

        res = requests.post(self._server_url, json=body, timeout=30)
        error_check(res, 'New inpainting request')

        # POST to server_url, check response
        # If invalid or error response, throw Exception
        samples: Dict[str, Any] = {}
        in_progress = True
        error_count = 0
        max_errors = 10
        # refresh times in microseconds:
        min_refresh = 300000
        max_refresh = 60000000
        if '.ngrok.io' in self._server_url and not self._fast_ngrok_connection:
            # Free ngrok accounts only allow 20 connections per minute, lower the refresh rate to avoid failures:
            min_refresh = 3000000

        while in_progress:
            sleep_time = min(min_refresh * pow(2, error_count), max_refresh)
            # print(f"Checking for response in {sleep_time//1000} ms...")
            QThread.usleep(sleep_time)
            # GET server_url/sample, sending previous samples:
            try:
                res = requests.get(f'{self._server_url}/sample', json={'samples': samples}, timeout=30)
                error_check(res, 'sample update request')
            except requests.exceptions.RequestException as err:
                error_count += 1
                print(f'Error {error_count}: {err}')
                if error_count > max_errors:
                    print('Inpainting failed, reached max retries.')
                    break
                continue
            error_count = 0  # Reset error count on success.

            # On valid response, for each entry in res.json.sample:
            json_body = res.json()
            if 'samples' not in json_body:
                continue
            for sample_name in json_body['samples'].keys():
                try:
                    sample_image = load_image_from_base64(json_body['samples'][sample_name]['image'])
                    save_image(sample_image, int(sample_name))
                    samples[sample_name] = json_body['samples'][sample_name]['timestamp']
                except IOError as err:
                    print(f'Warning: {err}')
                    error_count += 1
                    continue
            in_progress = json_body['in_progress']

    def refresh_settings(self, settings_modal: SettingsModal):
        """Settings not in scope for GLID-3-XL controller."""

    def update_settings(self, changed_settings: dict):
        """Settings not in scope for GLID-3-XL controller."""
