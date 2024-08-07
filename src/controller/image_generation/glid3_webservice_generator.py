"""Generate images using GLID-3-XL running on a web server."""
from argparse import Namespace
from typing import Optional, Dict, Any

import requests
from PyQt6.QtCore import pyqtSignal, QThread, QSize, pyqtBoundSignal
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication, QInputDialog, QWidget

from src.config.application_config import AppConfig
from src.controller.image_generation.glid3_xl_generator import GLID_PREVIEW_IMAGE, GLID_GENERATOR_DESCRIPTION
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
GLID_WEB_GENERATOR_SETUP = _tr('<h2>GLID-3-XL server setup</h2>'
                               '<p>NOTE: Because GLID-3-XL is mainly a historical curiosity at this point, few steps '
                               'have been taken to simplify the setup process. As the software involved becomes '
                               'increasingly outdated, further steps may be necessary to get this generator to work.'
                               '</p><p>The original preferred way to use this mode relied on a Google Colab notebook, '
                               'found <a href="https://colab.research.google.com/github/centuryglass/IntraPaint/blob/co'
                               'lab-refactor/colabFiles/IntraPaint_colab_server.ipynb">here</a>. This approach is '
                               'discouraged by Google and no longer seems to work using the free tier of Google Colab.'
                               ' It may or may not work on the paid tier, or if additional steps are taken to replace '
                               'the ngrok service used to handle external connections. Steps for running the server'
                               ' on your own machine are as follows:'
                               '<ol>'
                               '<li>Make sure the server system has a NVIDIA GPU with at least 8GB of VRAM. Other GPUs'
                               'or slightly less memory may work, but are not tested.</li>'
                               '<li>Install required dependencies:</li>'
                               '<ol><li><a href="https://www.python.org/">Python3</a></li>'
                               '<li><a href="https://git-scm.com/">Git</a></li>'
                               '<li><a href="https://developer.nvidia.com/cuda-toolkit">CUDA</a> (if using a NVIDIA'
                               ' graphics card)</li>'
                               '<li><a href="https://www.anaconda.com/download/">Anaconda</a></li></ol>'
                               '<li>Depending on your system, you may need to take extra steps to add Python, Git, '
                               'and Anaconda to your system path, or perform other configuration steps. Refer to the '
                               'sites linked above for full documentation.</li>'
                               '<li>In a terminal window, run `<code>conda create -n intrapaint-server</code>`, then '
                               '`<code>conda activate intrapaint-server</code>` to prepare to install additional'
                               ' dependencies.</li>'
                               '<li>Next run `<code>git clone https://github.com/centuryglass/IntraPaint.git</code>` to'
                               ' download the full IntraPaint repository, then change directory to the new IntraPaint '
                               'folder that this creates.</li>'
                               '<li>Within the the terminal in the IntraPaint directory with the `intrapaint-server`'
                               'environment active, install the appropriate versions of torch and torchvision found '
                               '<a href="https://pytorch.org/get-started/locally/">here</a>.'
                               '<li>Run `<code>conda install pip</code>` to make sure the environment has its own copy'
                               ' of the python package manager.</li>'
                               '<li>Run `<code>pip install -r requirements-glid.txt</code>` to install additional'
                               ' dependencies.</li>'
                               '<li>Run the following Git commands to add two other required dependencies:<li><ol>'
                               '<li>`<code>git clone https://github.com/CompVis/taming-transformers.git</code>`</li>'
                               '<li>`<code>git clone https://github.com/CompVis/latent-diffusion.git</code>`</li>'
                               '<li>Download one or more GLID-3-XL inpainting models, and place them in the IntraPaint/'
                               'models/ directory. These are the main options available:<li><ol>'
                               '<li><a href="https://dall-3.com/models/glid-3-xl/">inpaint.pt</a>, the original GLID-3-'
                               'XL inpainting model</li>'
                               '<li><a href="https://huggingface.co/laion/ongo/resolve/main/ongo.pt>ongo.pt</a>, '
                               'trained by LAION on paintings from the Wikiart dataset</li>'
                               '<li><a href="https://huggingface.co/laion/erlich/resolve/main/model/ema_0.9999_120000'
                               '.pt">erlich.pt</a>, trained on the LAION large logo dataset</li>'
                               '</ol>'
                               '<li>Start the server by running <code>python IntraPaint_server.py</code>. If you are'
                               ' using a model other than the default inpaint.pt, instead run `<code>python '
                               'Intrapaint_server.py --model_path models/model.pt</code>`, replacing "model.pt" with'
                               ' the file name of whatever model you are using.</li>'
                               '<li>If the setup was successful, something like "* Running on '
                               'http://192.168.0.XXX:5555" will be printed in the console  after a short delay. You '
                               'can now activate this generator, entering that URL when prompted.')

# TODO: Colab notebook support is currently broken. The server starts successfully, but flask-ngrok is no longer
#       working in Colab. Find a new method to provide a temporary external URL for a Colab Flask server.
GLID_COLAB_SETUP = _tr('<h2>Colab server setup</h2>'
                       '<p>This is the easier way to set up this mode. It does not require a powerful GPU, but'
                       ' it does require an internet connection and a Google account.</p>'
                       '<ol>'
                       '<li>You\'ll need a free ngrok account to handle the connection between IntraPaint and'
                       ' the Colab Notebook, sign up for that at <a>https://ngrok.com</a></li>'
                       '<li>Once you sign up for an ngrok account, log in to their site, find your ngrok '
                       'AuthToken on <a href="https://dashboard.ngrok.com/get-started/your-authtoken">this '
                       'page. Copy it, and save it somewhere safe (e.g. a password manager).</li>'
                       '<li>Open the <a href="https://colab.research.google.com/github/centuryglass/IntraPaint/blob/'
                       'colab-refactor/colabFiles/IntraPaint_colab_server.ipynb">'
                       'IntraPaint Server notebook</a> in Google Colab.</li>'
                       '<li>Click "connect" in the upper right, after making sure that the dropdown to the '
                       'right of the connect button is set to "GPU". If you don\'t pay for Google Colab there '
                       'is a chance that a GPU server won\'t be available, and you\'ll have to try again later.'
                       '</li>'
                       '<li>By default, the server uses Google Drive to save configuration info to simplify the'
                       'process of starting it again later.  If you don\'t want to do this, scroll down through'
                       ' the notebook, find where it says "use_google_drive=True", and change it to '
                       '"use_google_drive=False"</li>'
                       '<li>If you have an extra 10GB of space free in Google Drive, you can scroll down, find'
                       ' the line that says "save_missing_models_to_drive=False", and change False to True, and'
                       ' it will start up much more quickly in the future.</li>'
                       '<li>Under the "Runtime" menu, select "Run All".  You\'ll see a popup warning you that'
                       'the notebook is not from Google. Click "Run anyway".</li>'
                       '<li>If you chose to use Google Drive, another popup will appear asking you to grant'
                       'permission to access Google Drive. Click "Connect to Google Drive", and follow '
                       'on-screen instructions to allow it to read and write files.</li>'
                       '<li>Below the first section of code on the page, a dialog asking you to enter your '
                       'ngrok AuthToken will appear.  Paste in the auth token you saved earlier, and press '
                       'enter. If you are using Google Drive, you won\'t need to do this again the next time'
                       ' you start the server.</li>'
                       '<li>Scroll down, and the server URL you need should be printed at the end of all '
                       'log entries after a few minutes.</li>'
                       '</ol>')
NO_SERVER_ERROR = _tr('No GLID-3-XL server address was provided.')
CONNECTION_ERROR = _tr('Could not find a valid GLID-3-XL server at "{server_address}"')


class Glid3WebserviceGenerator(ImageGenerator):
    """Interface for providing image generation capabilities."""

    def __init__(self, window: MainWindow, image_stack: ImageStack, args: Namespace) -> None:
        super().__init__(window, image_stack)
        self._server_url = args.server_url if args.server_url != '' else DEFAULT_GLID_URL
        self._fast_ngrok_connection = args.fast_ngrok_connection
        self._control_panel: Optional[GlidPanel] = None
        self._preview = QImage(GLID_PREVIEW_IMAGE)

    def get_display_name(self) -> str:
        """Returns a display name identifying the generator."""
        return GLID_WEB_GENERATOR_NAME

    def get_description(self) -> str:
        """Returns an extended description of this generator."""
        return GLID_GENERATOR_DESCRIPTION

    def get_preview_image(self) -> QImage:
        """Returns a preview image for this generator."""
        return self._preview

    def get_setup_text(self) -> str:
        """Returns a rich text description of how to set up this generator."""
        return GLID_WEB_GENERATOR_SETUP

    def is_available(self) -> bool:
        """Returns whether the generator is supported on the current system."""
        try:
            res = requests.get(self._server_url, timeout=30)
            if res.status_code == 200 and ('application/json' in res.headers['content-type']) \
                    and 'success' in res.json() and res.json()['success'] is True:
                return True
        except requests.exceptions.RequestException:
            pass
        self.status_signal.emit(CONNECTION_ERROR.format(server_address=self._server_url))
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
                 status_signal: pyqtSignal | pyqtBoundSignal,
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
