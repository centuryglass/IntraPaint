from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QInputDialog
import requests, io, sys

from ui.window.main_window import MainWindow
from controller.base_controller import BaseInpaintController
from startup.utils import imageToBase64, loadImageFromBase64


class WebClientController(BaseInpaintController):
    def __init__(self, args):
        super().__init__(args)
        self._server_url = args.server_url
        self._fast_ngrok_connection = args.fast_ngrok_connection

    def healthCheck(url):
        try:
            res = requests.get(url, timeout=30)
            return res.status_code == 200 and ('application/json' in res.headers['content-type']) \
                and 'success' in res.json() and res.json()['success'] == True
        except Exception as err:
            print(f"error connecting to {url}: {err}")
            return False

    def startApp(self):
        screen = self._app.primaryScreen()
        size = screen.availableGeometry()
        self._window = MainWindow(self._config, self._editedImage, self._maskCanvas, self._sketchCanvas, self)
        self._window.setGeometry(0, 0, size.width(), size.height())
        self._window.show()

        # Make sure a valid connection exists:
        def promptForURL(promptText):
            newUrl, urlEntered = QInputDialog.getText(self._window, 'Inpainting UI', promptText)
            if not urlEntered: # User clicked 'Cancel'
                sys.exit()
            if newUrl != '':
                self._server_url=newUrl

        # Get URL if one was not provided on the command line:
        while self._server_url == '':
            print('requesting url:')
            promptForURL('Enter server URL:')

        # Check connection:
        def healthCheckPasses():
            try:
                res = requests.get(self._server_url, timeout=30)
                return res.status_code == 200 and ('application/json' in res.headers['content-type']) \
                    and 'success' in res.json() and res.json()['success'] == True
            except Exception as err:
                print(f"error connecting to {self._server_url}: {err}")
                return False
        while not WebClientController.healthCheck(self._server_url):
            promptForURL('Server connection failed, enter a new URL or click "OK" to retry')
        self._app.exec_()
        sys.exit()


    def _inpaint(self, selection, mask, saveImage, statusSignal):
        batchSize = self._config.get('batchSize')
        batchCount = self._config.get('batchCount')
        body = {
            'batch_size': batchSize,
            'num_batches': batchCount,
            'edit': imageToBase64(selection),
            'mask': imageToBase64(mask),
            'prompt': self._config.get('prompt'),
            'negative': self._config.get('negativePrompt'),
            'guidanceScale': self._config.get('guidanceScale'),
            'skipSteps': self._config.get('skipSteps'),
            'width': selection.width,
            'height': selection.height
        }

        def errorCheck(serverResponse, contextStr):
            if serverResponse.status_code != 200:
                if serverResponse.content and ('application/json' in serverResponse.headers['content-type']) \
                        and serverResponse.json() and 'error' in serverResponse.json():
                    raise Exception(f"{serverResponse.status_code} response to {contextStr}: {serverResponse.json()['error']}")
                else:
                    print("RES")
                    print(serverResponse.content)
                    raise Exception(f"{serverResponse.status_code} response to {contextStr}: unknown error")
        res = requests.post(self._server_url, json=body, timeout=30)
        errorCheck(res, 'New inpainting request')

        # POST to server_url, check response
        # If invalid or error response, throw Exception
        samples = {}
        in_progress = True
        errorCount = 0
        maxErrors = 10
        # refresh times in microseconds:
        minRefresh = 300000
        maxRefresh = 60000000
        if('.ngrok.io' in self._server_url and not self._fast_ngrok_connection):
            # Free ngrok accounts only allow 20 connections per minute, lower the refresh rate to avoid failures:
            minRefresh = 3000000

        while in_progress:
            sleepTime = min(minRefresh * pow(2, errorCount), maxRefresh)
            #print(f"Checking for response in {sleepTime//1000} ms...")
            QThread.usleep(sleepTime)
            # GET server_url/sample, sending previous samples:
            res = None
            try:
                res = requests.get(f'{self._server_url}/sample', json={'samples': samples}, timeout=30)
                errorCheck(res, 'sample update request')
            except Exception as err:
                errorCount += 1
                print(f'Error {errorCount}: {err}')
                if errorCount > maxErrors:
                    print('Inpainting failed, reached max retries.')
                    break
                else:
                    continue
            errorCount = 0 # Reset error count on success.

            # On valid response, for each entry in res.json.sample:
            jsonBody = res.json()
            if 'samples' not in jsonBody:
                continue
            for sampleName in jsonBody['samples'].keys():
                try:
                    sampleImage = loadImageFromBase64(jsonBody['samples'][sampleName]['image'])
                    idx = int(sampleName) % batchSize
                    batch = int(sampleName) // batchSize
                    saveImage(sampleImage, idx, batch)
                    samples[sampleName] = jsonBody['samples'][sampleName]['timestamp']
                except Exception as err:
                    print(f'Warning: {err}')
                    errorCount += 1
                    continue
            in_progress = jsonBody['in_progress']
