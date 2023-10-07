from PyQt5.QtCore import QThread, QSize, QObject, pyqtSignal
from PyQt5.QtWidgets import QInputDialog
from threading import Lock
from PIL import Image
import requests, io, sys, secrets, threading, json, re

from ui.window.stable_diffusion_main_window import StableDiffusionMainWindow
from ui.modal.modal_utils import showErrorDialog
from ui.modal.image_scale_modal import ImageScaleModal
from ui.modal.login_modal import LoginModal
from controller.base_controller import BaseInpaintController
from startup.utils import imageToBase64, loadImageFromBase64

from sd_api.config import ConfigGet
from sd_api.embeddings import EmbeddingsGet
from sd_api.extras import ExtrasPost
from sd_api.hypernets import HypernetsGet
from sd_api.img2img import Img2ImgPost
from sd_api.interrogate import InterrogatePost
from sd_api.interrupt import InterruptPost
from sd_api.login_check import LoginCheckGet
from sd_api.memory import MemoryGet
from sd_api.models import ModelsGet
from sd_api.upscalers import UpscalersGet
from sd_api.options import OptionsGet, OptionsPost
from sd_api.progress import ProgressGet
from sd_api.refresh_ckpt import RefreshCheckpointsPost
from sd_api.samplers import SamplersGet
from sd_api.styles import StylesGet
from sd_api.txt2img import Txt2ImgPost
from sd_api.controlnet_upscale import ControlnetUpscalePost
from sd_api.controlnet_version import ControlnetVersionGet


class StableDiffusionController(BaseInpaintController):
    def __init__(self, args):
        self._server_url = args.server_url
        super().__init__(args)
        self._session_hash = secrets.token_hex(5)
        # Since stable-diffusion supports alternate generation modes, configure sketch/mask to only be available
        # when using appropriate modes:
        def updateMaskState(editMode):
            self._maskCanvas.setEnabled(editMode == 'Inpaint')
        self._config.connect(self._maskCanvas, 'editMode', updateMaskState)
        def updateSketchState(editMode):
            self._sketchCanvas.setEnabled(editMode != 'Text to Image')
        self._config.connect(self._sketchCanvas, 'editMode', updateSketchState)
        # Load various data on init:
        # Check for controlnet:
        controlnetCheckEndpoint = ControlnetVersionGet(self._server_url)
        try:
            res = controlnetCheckEndpoint.send(timeout=30)
            if res.status_code == 200:
                self._config.set('controlnetVersion', float(res.json()['version']))
            else:
                print(f"Failed to find controlnet, code={res.status_code}")
                self._config.set('controlnetVersion', -1.0)
        except Exception as err:
            print(f"Loading controlnet config failed: {err}")
            self._config.set('controlnetVersion', -1.0)

        optionLoadingParams = [
            [StylesGet, 'styles', lambda s: json.dumps(s)],
            [SamplersGet, 'samplingMethod', lambda s: s['name']],
            [UpscalersGet, 'upscaleMethod', lambda u: u['name']]
        ]
        if self._config.get('controlnetVersion') > 0:
            print('TODO: add controlnet items to optionLoadingParams')

        # load various option lists:
        for endpointClass, configKey, mapFn in optionLoadingParams:
            try:
                endpoint = endpointClass(self._server_url)
                res = endpoint.send(timeout=30)
                if res.status_code == 200:
                    resList = list(map(mapFn, res.json()))
                    self._config.updateOptions(configKey, resList)
                else:
                    print(f"Failed to load {configKey}, code={res.status_code}")
            except Exception as err:
                print(f"error loading {configKey} from {self._server_url}: {err}")

    def healthCheck(url, session_hash=secrets.token_hex(5)):
        try:
            loginCheckEndpoint = LoginCheckGet(url)
            res = loginCheckEndpoint.send(timeout=30)
            if res.status_code == 200 or (res.status_code == 401 and res.json()['detail'] == 'Not authenticated'):
                return True
            raise Exception(f"{res.status_code} : {res.text}")
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
                    interrogateEndpoint = InterrogatePost(controller._server_url)
                    res = interrogateEndpoint.send(controller._config, controller._editedImage.getSelectionContent())
                    if res.status_code != 200:
                        raise Exception(f"{res.status_code} : {res.text}")
                    self.promptReady.emit(res.json()['caption'])
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
        # On launch, check selected model to see if it is a 2.0 variant trained at 768x768:
        try:
            optionsEndpoint = OptionsGet(self._server_url)
            res = optionsEndpoint.send()
            if res.status_code != 200:
                raise Exception(f"Request failed with code {res.status_code}")
            resBody = res.json()
            modelKey = "sd_model_checkpoint"
            if not modelKey in resBody:
                raise Exception(f"Response did not contain {modelKey}")
            if "768" in resBody[modelKey]:
                print(f"model {resBody[modelKey]} name contains 768, setting edit size=768x768")
                self._config.set('maxEditSize', QSize(768, 768))
            else:
                print(f"model {resBody[modelKey]} name doesn't include 768, assuming edit size=512x512")
                self._config.set('maxEditSize', QSize(512, 512))
        except Exception as err:
            print(f"Checking model failed: {err}")
            self._config.set('maxEditSize', QSize(512, 512))
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

        # Check for required auth:
        loginCheckEndpoint = LoginCheckGet(self._server_url)
        auth_res = loginCheckEndpoint.send(timeout=30)
        if auth_res.status_code == 401 and auth_res.json()['detail'] == 'Not authenticated':
            loginModal = LoginModal(self._server_url)
            loginModal.showLoginModal()
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
                upscaleMethod = controller._config.get('upscaleMethod')
                upscaleEndpoint = None
                if controller._config.get('controlnetUpscaling'):
                    upscaleEndpoint = ControlnetUpscalePost(controller._server_url)
                    upscaleArgs = [controller._config, controller._editedImage.getPilImage(), newSize.width(), newSize.height()]
                else:
                    upscaleEndpoint = ExtrasPost(controller._server_url)
                    upscaleArgs = [controller._editedImage.getPilImage(), newSize.width(), newSize.height(), upscaleMethod]
                try:
                    res = upscaleEndpoint.send(*upscaleArgs)
                    if res.status_code != 200:
                        raise Exception(f"{res.status_code} : {res.text}")
                    res_json = res.json()
                    if 'image' in res_json:
                        self.imageReady.emit(loadImageFromBase64(res.json()['image']))
                    elif 'images' in res_json:
                        images = controller._getImageData(res_json['images'])
                        print(f"got scaled: {images}")
                        self.imageReady.emit(images[-1])
                    else:
                        raise Exception(f"Unexpected response format: {res_json}")
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
        imageEndpoint = Txt2ImgPost(self._server_url) if editMode == 'Text to Image' \
               else Img2ImgPost(self._server_url)
        postArgs = [self._config, selection.width, selection.height] if editMode == 'Text to Image' \
                   else [self._config, selection, mask]

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
        progressEndpoint = ProgressGet(self._server_url)
        init_response = progressEndpoint.send()
        errorCheck(init_response, 'Checking initial image generation progress')
        init_data = init_response.json()
        if init_data['current_image'] is not None:
            raise Exception('Image generation in progress, try again later.')

        def asyncRequest():
            res = imageEndpoint.send(*postArgs)
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
                progress_res = progressEndpoint.send()
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
        images = self._getImageData(images)
        for image in images:
            saveImage(image, idxInBatch, batchIdx)
            idxInBatch += 1
            if idxInBatch >= batchSize:
                idxInBatch = 0
                batchIdx += 1

    def _getImageData(self, images):
        imageData = []
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
                    imageData.append(Image.open(buffer))
            if isinstance(image, str):
                imageData.append(loadImageFromBase64(image))
        return imageData

    def _applyStatusUpdate(self, statusDict):
        if 'seed' in statusDict:
            self._config.set('lastSeed', str(statusDict['seed']))
        if 'progress' in statusDict:
            self._window.setLoadingMessage(statusDict['progress'])
