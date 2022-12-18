from PyQt5.QtCore import QThread, QSize, QObject, pyqtSignal
from PyQt5.QtWidgets import QInputDialog
from threading import Lock
from PIL import Image
import requests, io, sys, secrets, threading, json, re

from ui.window.stable_diffusion_main_window import StableDiffusionMainWindow
from ui.modal.modal_utils import showErrorDialog
from ui.modal.image_scale_modal import ImageScaleModal
from controller.base_controller import BaseInpaintController
from data_model.stable_diffusion_api import *
from startup.utils import imageToBase64, loadImageFromBase64

# TODO: remove once API properly supports interrogate
INTERROGATE_FN_INDEX = 73

class StableDiffusionController(BaseInpaintController):
    def __init__(self, args):
        super().__init__(args)
        self._server_url = args.server_url
        self._session_hash = secrets.token_hex(5)
        # Since stable-diffusion supports alternate generation modes, configure sketch/mask to only be available
        # when using appropriate modes:
        def updateMaskState(editMode):
            self._maskCanvas.setEnabled(editMode == 'Inpaint')
        self._config.connect(self._maskCanvas, 'editMode', updateMaskState)
        def updateSketchState(editMode):
            self._sketchCanvas.setEnabled(editMode != 'Text to Image')
        self._config.connect(self._sketchCanvas, 'editMode', updateSketchState)
        # Load styles on init:
        self._styles = {}
        try:
            res = requests.get(f"{self._server_url}{API_ENDPOINTS['STYLES']}", timeout=30)
            if res.status_code == 200:
                styleList = res.json()
                for style in styleList:
                    self._styles[style['name']] = { 'prompt': style['prompt'], 'negative_prompt': style['negative_prompt'] }
                print(f"Loaded {len(self._styles)} styles (Invoke with <STYLE_NAME>)")
        except Exception as err:
            print(f"error connecting to {url}: {err}")
            return False

    def healthCheck(url, session_hash=secrets.token_hex(5)):
        try:
            res = requests.get(f"{url}{API_ENDPOINTS['LOGIN_CHECK']}", timeout=30)
            return res.status_code == 200
        except Exception as err:
            print(f"error connecting to {url}: {err}")
            return False

    def interrogate(self):
        if not self._editedImage.hasImage():
            showErrorDialog(self._window, "Interrogate failed", "Create or load an image first.")
            return
        if self._thread is not None:
            showErrorDialog(self._window, "Interrogate failed", "Existing operation currently in progress")
            return

        controller = self
        class InterrogateWorker(QObject):
            finished = pyqtSignal()
            promptReady = pyqtSignal(str)
            errorSignal = pyqtSignal(Exception)

            def __init__(self):
                super().__init__()

            def run(self):
                try:
                    body = {
                        'data': [ imageToBase64(controller._editedImage.getSelectionContent(), includePrefix=True) ],
                        'fn_index': INTERROGATE_FN_INDEX,
                        'session_hash': controller._session_hash
                    }
                    url = f"{controller._server_url}/api/predict/"
                    res = requests.post(url, json=body)
                    if res.status_code != 200:
                        raise Exception(f"{res.status_code} : {res.text}")
                    self.promptReady.emit(res.json()['data'][0])
                except Exception as err:
                    print (f"err:{err}")
                    self.errorSignal.emit(err)
                self.finished.emit()
        
        worker = InterrogateWorker()
        def setPrompt(promptText):
            self._config.set('prompt', promptText)
        worker.promptReady.connect(setPrompt)
        def handleError(err):
            self._window.setIsLoading(False)
            showErrorDialog(self._window, "Interrogate failure", err)
        worker.errorSignal.connect(handleError)
        self._startThread(worker, loadingText="Running CLIP interrogate")

    def _adjustConfigDefaults(self):
        # update size limits for stable-diffusion's capabilities:
        self._config.set('maxEditSize', QSize(512, 512))
        # stable-diffusion backend will handle this for us:
        self._config.set('removeUnmaskedChanges', False)
        self._config.set('saveSketchInResult', True)

    def startApp(self):
        screen = self._app.primaryScreen()
        size = screen.availableGeometry()
        self._window = StableDiffusionMainWindow(self._config, self._editedImage, self._maskCanvas, self._sketchCanvas, self)
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
        while not StableDiffusionController.healthCheck(self._server_url, self._session_hash):
            promptForURL('Server connection failed, enter a new URL or click "OK" to retry')
        self._app.exec_()
        sys.exit()


    def _scale(self, newSize):
        width = self._editedImage.width()
        height = self._editedImage.height()
        # If downscaling, use base implementation:
        if (newSize.width() <= width and newSize.height() <= height):
            super()._scale(newSize)
            return;
        # If upscaling, use stable-diffusion-webui upscale api:
        controller = self
        class UpscaleWorker(QObject):
            finished = pyqtSignal()
            imageReady = pyqtSignal(Image.Image)
            statusSignal = pyqtSignal(dict)
            errorSignal = pyqtSignal(Exception)

            def __init__(self):
                super().__init__()

            def run(self):
                try:
                    body = getUpscaleBody(controller._editedImage.getPilImage(), newSize.width(), newSize.height())
                    url = f"{controller._server_url}{API_ENDPOINTS['EXTRAS']}"
                    res = requests.post(url, json=body)
                    if res.status_code != 200:
                        raise Exception(f"{res.status_code} : {res.text}")
                    self.imageReady.emit(loadImageFromBase64(res.json()['image']))
                except Exception as err:
                    self.errorSignal.emit(err)
                self.finished.emit()
        worker = UpscaleWorker()
        def handleError(err):
            showErrorDialog(self._window, "Upscale failure", err)
        worker.errorSignal.connect(handleError)
        def applyUpscaled(img):
            self._editedImage.setImage(img)
        worker.imageReady.connect(applyUpscaled)
        self._startThread(worker)

    def _inpaint(self, selection, mask, saveImage, statusSignal):
        editMode = self._config.get('editMode')
        if editMode != 'Inpaint':
            mask = None
        body = getTxt2ImgBody(self._config, selection.width, selection.height) if editMode == 'Text to Image' \
               else getImg2ImgBody(self._config, selection, mask)
        uri = self._server_url + API_ENDPOINTS['TXT2IMG' if (editMode == 'Text to Image') else 'IMG2IMG']

        # Check prompt/negative for styles:
        def styleSub(promptTypeKey):
            prompt = body[promptTypeKey]
            matches = re.findall(r"<.+>", prompt)
            for style in matches:
                style = style[1:-1] # Remove <>
                if style in self._styles:
                    print(f"Applying style {style}")
                    prompt = prompt.replace(style, self._styles[style][promptTypeKey])
                else:
                    print(f"Style '{style}' not found")
            body[promptTypeKey] = prompt
        styleSub('prompt')
        styleSub('negative_prompt')

        def errorCheck(serverResponse, contextStr):
            if serverResponse.status_code != 200:
                if serverResponse.content and ('application/json' in serverResponse.headers['content-type']) \
                        and serverResponse.json() and 'detail' in serverResponse.json():
                    raise Exception(f"{serverResponse.status_code} response to {contextStr}: {serverResponse.json()['detail']}")
                else:
                    raise Exception(f"{serverResponse.status_code} response to {contextStr}: unknown error, response={serverResponse}")

        # POST to server_url, check response
        # If invalid or error response, throw Exception
        samples = {}
        errorCount = 0
        maxErrors = 10
        # refresh times in microseconds:
        minRefresh = 300000
        maxRefresh = 60000000
        images = []
        errors = []

        # Check progress before starting:
        init_response = requests.get(self._server_url + API_ENDPOINTS['PROGRESS'])
        errorCheck(init_response, 'Checking initial image generation progress')
        init_data = init_response.json()
        if init_data['current_image'] is not None:
            raise Exception('Image generation in progress, try again later.')

        def asyncRequest():
            res = requests.post(uri, json=body)
            try:
                errorCheck(res, f"New {editMode} request")
                if len(errors) == 0:
                    resBody = res.json()
                    imageData = resBody['images']
                    for item in imageData:
                        images.append(item)
                        info = json.loads(resBody['info'])
                        statusSignal.emit(info)

            except Exception as err:
                print(f"request failed: {err}")
                errors.append(err)
        thread = threading.Thread(target=asyncRequest)
        thread.start()

        while thread.is_alive():
            sleepTime = min(minRefresh * pow(2, errorCount), maxRefresh)
            thread.join(timeout=sleepTime / 1000000)
            if not thread.is_alive() or len(errors) > 0:
                break
            res = None
            try:
                progress_res = requests.get(self._server_url + API_ENDPOINTS['PROGRESS'])
                errorCheck(progress_res, 'Checking image generation progress')
                status = progress_res.json()
                statusText = f"{int(status['progress'] * 100)}%"
                if 'eta_relative' in status and status['eta_relative'] != 0:
                    # TODO: eta_relative is not a ms value, perhaps use it with timestamps to estimate actual ETA?
                    eta_sec = int(status['eta_relative'] / 1000)
                    minutes = eta_sec // 60
                    seconds = eta_sec % 60
                    if minutes > 0:
                        statusText = f"{statusText} ETA: {minutes}:{seconds}"
                    else:
                        statusText = f"{statusText} ETA: {seconds}s"
                statusSignal.emit({'progress': statusText})
            except Exception as err:
                errorCount += 1
                print(f'Error {errorCount}: {err}')
                if errorCount > maxErrors:
                    print('Inpainting failed, reached max retries.')
                    break
                else:
                    continue
            errorCount = 0 # Reset error count on success.
        if len(errors) > 0:
            print('Inpainting failed with error, raising...')
            raise errors[0]
        # discard image grid if present:
        batchSize = self._config.get('batchSize')
        batchCount = self._config.get('batchCount')
        if len(images) > (batchSize * batchCount):
            images.pop(0)
        idxInBatch = 0
        batchIdx = 0
        for image in images:
            if isinstance(image, dict):
                if not image['is_file'] and image['data'] is not None:
                    image = image['data']
                else:
                    filePath = image['name']
                    url = f"{self._server_url}/file={filePath}"
                    res = requests.get(url)
                    res.raise_for_status()
                    buffer = io.BytesIO()
                    buffer.write(res.content)
                    buffer.seek(0)
                    imageObject = Image.open(buffer)
                    saveImage(imageObject, idxInBatch, batchIdx)
            if isinstance(image, str):
                imageObject = loadImageFromBase64(image)
                saveImage(imageObject, idxInBatch, batchIdx)
            idxInBatch += 1
            if idxInBatch >= batchSize:
                idxInBatch = 0
                batchIdx += 1

    def _applyStatusUpdate(self, statusDict):
        if 'seed' in statusDict:
            self._config.set('lastSeed', str(statusDict['seed']))
        if 'progress' in statusDict:
            self._window.setLoadingMessage(statusDict['progress'])
