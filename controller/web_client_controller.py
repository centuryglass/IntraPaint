"""
Provides image editing functionality through the GLID3-XL API provided through Intrapaint_server.py or
colabFiles/IntraPaint_colab_server.ipynb.
"""
from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QInputDialog
import requests, io, sys

from ui.window.main_window import MainWindow
from controller.base_controller import BaseInpaintController
from startup.utils import image_to_base64, load_image_from_base64
from ui.util.screen_size import screen_size


class WebClientController(BaseInpaintController):
    def __init__(self, args):
        super().__init__(args)
        self._server_url = args.server_url
        self._fast_ngrok_connection = args.fast_ngrok_connection

    def health_check(url):
        try:
            res = requests.get(url, timeout=30)
            return res.status_code == 200 and ('application/json' in res.headers['content-type']) \
                and 'success' in res.json() and res.json()['success'] == True
        except Exception as err:
            print(f"error connecting to {url}: {err}")
            return False

    def window_init(self):
        self._window = MainWindow(self._config, self._edited_image, self._mask_canvas, self._sketch_canvas, self)
        size = screen_size(self._window)
        self._window.setGeometry(0, 0, size.width(), size.height())
        self._window.show()

        # Make sure a valid connection exists:
        def prompt_for_url(promptText):
            newUrl, urlEntered = QInputDialog.getText(self._window, 'Inpainting UI', promptText)
            if not urlEntered: # User clicked 'Cancel'
                sys.exit()
            if newUrl != '':
                self._server_url=newUrl

        # Get URL if one was not provided on the command line:
        while self._server_url == '':
            print('requesting url:')
            prompt_for_url('Enter server URL:')

        # Check connection:
        def health_check_passes():
            try:
                res = requests.get(self._server_url, timeout=30)
                return res.status_code == 200 and ('application/json' in res.headers['content-type']) \
                    and 'success' in res.json() and res.json()['success'] == True
            except Exception as err:
                print(f"error connecting to {self._server_url}: {err}")
                return False
        while not WebClientController.health_check(self._server_url):
            prompt_for_url('Server connection failed, enter a new URL or click "OK" to retry')


    def _inpaint(self, selection, mask, save_image, status_signal):
        batch_size = self._config.get('batchSize')
        batch_count = self._config.get('batchCount')
        body = {
            'batch_size': batch_size,
            'num_batches': batch_count,
            'edit': image_to_base64(selection),
            'mask': image_to_base64(mask),
            'prompt': self._config.get('prompt'),
            'negative': self._config.get('negativePrompt'),
            'guidanceScale': self._config.get('guidanceScale'),
            'skipSteps': self._config.get('skipSteps'),
            'width': selection.width,
            'height': selection.height
        }

        def error_check(server_response, contextStr):
            if server_response.status_code != 200:
                if server_response.content and ('application/json' in server_response.headers['content-type']) \
                        and server_response.json() and 'error' in server_response.json():
                    raise Exception(f"{server_response.status_code} response to {contextStr}: {server_response.json()['error']}")
                else:
                    print("RES")
                    print(server_response.content)
                    raise Exception(f"{server_response.status_code} response to {contextStr}: unknown error")
        res = requests.post(self._server_url, json=body, timeout=30)
        error_check(res, 'New inpainting request')

        # POST to server_url, check response
        # If invalid or error response, throw Exception
        samples = {}
        in_progress = True
        error_count = 0
        max_errors = 10
        # refresh times in microseconds:
        min_refresh = 300000
        max_refresh = 60000000
        if('.ngrok.io' in self._server_url and not self._fast_ngrok_connection):
            # Free ngrok accounts only allow 20 connections per minute, lower the refresh rate to avoid failures:
            min_refresh = 3000000

        while in_progress:
            sleep_time = min(min_refresh * pow(2, error_count), max_refresh)
            #print(f"Checking for response in {sleep_time//1000} ms...")
            QThread.usleep(sleep_time)
            # GET server_url/sample, sending previous samples:
            res = None
            try:
                res = requests.get(f'{self._server_url}/sample', json={'samples': samples}, timeout=30)
                error_check(res, 'sample update request')
            except Exception as err:
                error_count += 1
                print(f'Error {error_count}: {err}')
                if error_count > max_errors:
                    print('Inpainting failed, reached max retries.')
                    break
                else:
                    continue
            error_count = 0 # Reset error count on success.

            # On valid response, for each entry in res.json.sample:
            json_body = res.json()
            if 'samples' not in json_body:
                continue
            for sample_name in json_body['samples'].keys():
                try:
                    sample_image = load_image_from_base64(json_body['samples'][sample_name]['image'])
                    idx = int(sample_name) % batch_size
                    batch = int(sample_name) // batch_size
                    save_image(sample_image, idx, batch)
                    samples[sample_name] = json_body['samples'][sample_name]['timestamp']
                except Exception as err:
                    print(f'Warning: {err}')
                    error_count += 1
                    continue
            in_progress = json_body['in_progress']
