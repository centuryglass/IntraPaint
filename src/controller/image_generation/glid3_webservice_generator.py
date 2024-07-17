"""Generate images using GLID-3-XL running on a web server."""
from argparse import Namespace
from typing import Optional, Dict, Any

import requests
from PyQt6.QtCore import pyqtSignal, QThread, QSize
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication, QInputDialog, QWidget

from src.config.application_config import AppConfig
from src.controller.image_generation.image_generator import ImageGenerator
from src.controller.image_generation.sd_webui_generator import URL_REQUEST_MESSAGE, URL_REQUEST_RETRY_MESSAGE, \
    URL_REQUEST_TITLE
from src.image.layers.image_stack import ImageStack
from src.ui.modal.settings_modal import SettingsModal
from src.ui.panel.generators.glid_panel import GlidPanel
from src.ui.window.main_window import MainWindow
from src.util.image_utils import image_to_base64, qimage_from_base64
from src.util.shared_constants import EDIT_MODE_INPAINT

# The QCoreApplication.translate context for strings in this file
TR_ID = 'controller.image_generation.glid3_webservice_generator'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


DEFAULT_GLID_URL = 'http://localhost:5555'
GLID_CONFIG_CATEGORY = 'GLID-3-XL'
GLID_WEB_GENERATOR_NAME = _tr('GLID-3-XL image generation server')
GLID_WEB_GENERATOR_DESCRIPTION = _tr('<p>Generate images using a network connection to a server running a GLID-3-XL '
                                     'image generation model.</p></br>  <p>This mode is included mostly for historical'
                                     ' reasons, GLID-3-XL is primitive by modern standards, only supporting inpainting'
                                     ' and only generating images up to 256x256 pixels.  This mode was one of the two'
                                     'supported modes available when IntraPaint alpha was released in 2022.  '
                                     'Instructions for setting it up can be found '
                                     '<a href="https://github.com/centuryglass/IntraPaint?tab=readme-ov-file#setup">'
                                     'here</a></p>')


class Glid3WebserviceGenerator(ImageGenerator):
    """Interface for providing image generation capabilities."""

    def __init__(self, window: MainWindow, image_stack: ImageStack, args: Namespace) -> None:
        super().__init__(window, image_stack)
        self._server_url = args.server_url if args.server_url != '' else DEFAULT_GLID_URL
        self._fast_ngrok_connection = args.fast_ngrok_connection
        self._control_panel: Optional[GlidPanel] = None

    def get_display_name(self) -> str:
        """Returns a display name identifying the generator."""
        return GLID_WEB_GENERATOR_NAME

    def get_description(self) -> str:
        """Returns an extended description of this generator."""
        return GLID_WEB_GENERATOR_DESCRIPTION

    def is_available(self) -> bool:
        """Returns whether the generator is supported on the current system."""
        try:
            res = requests.get(self._server_url, timeout=30)
            return res.status_code == 200 and ('application/json' in res.headers['content-type']) \
                and 'success' in res.json() and res.json()['success'] is True
        except requests.exceptions.RequestException as err:
            print(f'Request error: {err}')
            return False

    def configure_or_connect(self) -> bool:
        """Handles any required steps necessary to configure the generator, install required components, and/or
           connect to required external services, returning whether the process completed correctly."""
        while self._server_url == '' or not self.is_available():
            prompt_text = URL_REQUEST_MESSAGE if self._server_url == '' else URL_REQUEST_RETRY_MESSAGE
            new_url, url_entered = QInputDialog.getText(None, URL_REQUEST_TITLE, prompt_text)
            if not url_entered:
                return False
        AppConfig().set(AppConfig.GENERATION_SIZE, QSize(256, 256))
        AppConfig().set(AppConfig.EDIT_MODE, EDIT_MODE_INPAINT)
        return True

    def disconnect_or_disable(self) -> None:
        """No-op, web client controller does not maintain a persistent connection."""

    def init_settings(self, settings_modal: SettingsModal) -> None:
        """Updates a settings modal to add settings relevant to this generator."""
        settings_modal.load_from_config(AppConfig(), [GLID_CONFIG_CATEGORY])

    def refresh_settings(self, settings_modal: SettingsModal) -> None:
        """Reloads current values for this generator's settings, and updates them in the settings modal."""
        config = AppConfig()
        settings = {}
        for key in config.get_category_keys(GLID_CONFIG_CATEGORY):
            settings[key] = config.get(key)
        settings_modal.update_settings(settings)

    def update_settings(self, changed_settings: dict[str, Any]) -> None:
        """Applies any changed settings from a SettingsModal that are relevant to the image generator and require
           special handling."""
        config = AppConfig()
        glid_keys = config.get_category_keys(GLID_CONFIG_CATEGORY)
        for key, value in changed_settings.items():
            if key in glid_keys:
                config.set(key, value)

    def unload_settings(self, settings_modal: SettingsModal) -> None:
        """Unloads this generator's settings from the settings modal."""
        settings_modal.remove_category(AppConfig(), GLID_CONFIG_CATEGORY)

    def get_control_panel(self) -> QWidget:
        """Returns a widget with inputs for controlling this generator."""
        if self._control_panel is None:
            self._control_panel = GlidPanel()
            self._control_panel.generate_signal.connect(self.start_and_manage_image_generation)
        return self._control_panel

    def generate(self,
                 status_signal: pyqtSignal,
                 source_image: Optional[QImage] = None,
                 mask_image: Optional[QImage] = None) -> None:
        """Generates new images. Image size, image count, prompts, etc. are loaded from AppConfig as needed.

        Parameters
        ----------
        status_signal : pyqtSignal[str]
            Signal to emit when status updates are available.
        source_image : QImage, optional
            Image used as a basis for the edited image.
        mask_image : QImage, optional
            Mask marking edited image region.
        """
        if source_image is None or mask_image is None:
            raise RuntimeError('GLID-3-XL only supports inpainting')
        if source_image.hasAlphaChannel():
            source_image = source_image.convertToFormat(QImage.Format.Format_RGB32)
        config = AppConfig()
        batch_size = config.get(AppConfig.BATCH_SIZE)
        batch_count = config.get(AppConfig.BATCH_COUNT)
        body = {
            'batch_size': batch_size,
            'num_batches': batch_count,
            'edit': image_to_base64(source_image),
            'mask': image_to_base64(mask_image),
            'prompt': config.get(AppConfig.PROMPT),
            'negative': config.get(AppConfig.NEGATIVE_PROMPT),
            'guidanceScale': config.get(AppConfig.GUIDANCE_SCALE),
            'skipSteps': config.get(AppConfig.SKIP_STEPS),
            'width': source_image.width(),
            'height': source_image.height()
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
                    sample_image = qimage_from_base64(json_body['samples'][sample_name]['image'])
                    self._cache_generated_image(sample_image, int(sample_name))
                    samples[sample_name] = json_body['samples'][sample_name]['timestamp']
                except IOError as err:
                    print(f'Warning: {err}')
                    error_count += 1
                    continue
            in_progress = json_body['in_progress']
