from PyQt5.QtCore import QThread, QSize, QObject, pyqtSignal
from PyQt5.QtWidgets import QInputDialog
from threading import Lock
from PIL import Image
import requests, io, sys, secrets, threading, json, re, os

from ui.window.stable_diffusion_main_window import StableDiffusionMainWindow
from ui.modal.modal_utils import showErrorDialog
from ui.modal.image_scale_modal import ImageScaleModal
from ui.modal.login_modal import LoginModal
from controller.base_controller import BaseInpaintController
from startup.utils import imageToBase64, loadImageFromBase64
from sd_api.a1111_webservice import A1111Webservice


class StableDiffusionController(BaseInpaintController):
    def __init__(self, args):
        self._server_url = args.server_url
        super().__init__(args)
        self._webservice = A1111Webservice(args.server_url)
        self._session = self._webservice._session

        # Login automatically if username/password are defined as env variables.
        # Obviously this isn't terribly secure, but A1111 auth security is already pretty minimal and I'm just using
        # this for testing.
        if 'SD_UNAME' in os.environ and 'SD_PASS' in os.environ:
            self._webservice._login(os.environ['SD_UNAME'], os.environ['SD_PASS'])
            self._webservice._setAuth((os.environ['SD_UNAME'], os.environ['SD_PASS']))

        # Since stable-diffusion supports alternate generation modes, configure sketch/mask to only be available
        # when using appropriate modes:
        def updateMaskState(editMode):
            self._maskCanvas.setEnabled(editMode == 'Inpaint')
        self._config.connect(self._maskCanvas, 'editMode', updateMaskState)
        def updateSketchState(editMode):
            self._sketchCanvas.setEnabled(editMode != 'Text to Image')
        self._config.connect(self._sketchCanvas, 'editMode', updateSketchState)

    def initSettings(self, settingsModal):
        if not isinstance(self._webservice, A1111Webservice):
            print('Disabling remote settings: only supported with the A1111 API')
            return False
        settings = self._webservice.getConfig()

        # Model settings:
        models = list(map(lambda m: m['title'], self._webservice.getModels()))
        settingsModal.addComboBoxSetting('sd_model_checkpoint',
                'Models',
                settings['sd_model_checkpoint'],
                models,
                'Stable-Diffusion Model:')
        settingsModal.addCheckBoxSetting('sd_checkpoints_keep_in_cpu',
                'Models',
                int(settings['sd_checkpoints_keep_in_cpu']),
                'Only keep one model on GPU/TPU')
        settingsModal.setTooltip('sd_checkpoints_keep_in_cpu',
                'If selected, checkpoints after the first are cached in RAM instead.')
        settingsModal.addSpinBoxSetting('sd_checkpoints_limit',
                'Models',
                int(settings['sd_checkpoints_limit']),
                1,
                10,
                'Max checkpoints loaded:')
        vaeOptions = list(map(lambda v: v['model_name'], self._webservice.getVAE()))
        vaeOptions.insert(0, "Automatic")
        vaeOptions.insert(0, "None")
        settingsModal.addComboBoxSetting('sd_vae',
                'Models',
                settings['sd_vae'],
                vaeOptions,
                'Stable-Diffusion VAE:')
        settingsModal.setTooltip('sd_vae',
                "Automatic: use VAE with same name as model\nNone: use embedded VAE\n" \
                + re.sub(r'<.*?>', '', settings['sd_vae_explanation']))
        settingsModal.addSpinBoxSetting('sd_vae_checkpoint_cache',
                'Models',
                int(settings['sd_vae_checkpoint_cache']),
                1,
                10,
                'VAE models cached:')
        settingsModal.addSpinBoxSetting('CLIP_stop_at_last_layers',
                'Models',
                int(settings['CLIP_stop_at_last_layers']),
                1,
                50,
                'CLIP skip:')

        # Upscaling:
        settingsModal.addSpinBoxSetting('ESRGAN_tile',
                'Upscalers',
                int(settings['ESRGAN_tile']),
                8, 9999, "ESRGAN tile size")
        settingsModal.addSpinBoxSetting('ESRGAN_tile_overlap',
                'Upscalers',
                int(settings['ESRGAN_tile_overlap']),
                8,
                9999,
                "ESRGAN tile overlap")
        return True

    def refreshSettings(self, settingsModal):
        settings = self._webservice.getConfig()
        settingsModal.updateSettings(settings)

    def updateSettings(self, changedSettings):
        for key in changedSettings:
            print(f"Setting {key} to {changedSettings[key]}")
        self._webservice.setConfig(changedSettings)

    def healthCheck(url=None, webservice=None):
        try:
            res = None
            if webservice is None:
                res = requests.get(url)
            else:
                res = webservice.loginCheck()
            if res.status_code == 200 or (res.status_code == 401 and res.json()['detail'] == 'Not authenticated'):
                return True
            raise Exception(f"{res.status_code} : {res.text}")
        except Exception as err:
            print(f"error checking login: {err}")
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
                    image = controller._editedImage.getSelectionContent()
                    config = controller._config
                    self.promptReady.emit(controller._webservice.interrogate(config, image))
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

    def windowInit(self):
        screen = self._app.primaryScreen()
        size = screen.availableGeometry()

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
        while not StableDiffusionController.healthCheck(webservice=self._webservice):
            promptForURL('Server connection failed, enter a new URL or click "OK" to retry')

        try:
            self._config.set('controlnetVersion', float(self._webservice.getControlnetVersion()))
        except Exception as err:
            print(f"Loading controlnet config failed: {err}")
            self._config.set('controlnetVersion', -1.0)

        optionLoadingParams = [
            ['styles', lambda: self._webservice.getStyles()],
            ['samplingMethod', lambda: self._webservice.getSamplers()],
            ['upscaleMethod', lambda: self._webservice.getUpscalers()]
        ]
        if self._config.get('controlnetVersion') > 0:
            print('TODO: add controlnet items to optionLoadingParams')

        # load various option lists:
        for configKey, loadingFn in optionLoadingParams:
            try:
                self._config.updateOptions(configKey, loadingFn())
            except Exception as err:
                print(f"error loading {configKey} from {self._server_url}: {err}")

        # initialize remote options modal:
        
        # Handle final window init now that data is loaded from the API:
        self._window = StableDiffusionMainWindow(self._config, self._editedImage, self._maskCanvas, self._sketchCanvas, self)
        self._window.setGeometry(0, 0, size.width(), size.height())
        self.fixStyles()
        self._window.show()


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
                    images, info = controller._webservice.upscale(controller._editedImage.getPilImage(),
                            newSize.width(),
                            newSize.height(),
                            controller._config)
                    if info is not None:
                        print(f"Upscaling result info: {info}")
                    self.imageReady.emit(images[-1])
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

        generateImages = None
        if editMode == 'Text to Image':
            generateImages = lambda: self._webservice.txt2img(self._config, selection.width, selection.height, image=selection)
        else:
            scripts = None
            generateImages = lambda: self._webservice.img2img(selection, self._config, mask=mask, scripts=scripts)


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
        init_data = self._webservice.progressCheck()
        if init_data['current_image'] is not None:
            raise Exception('Image generation in progress, try again later.')

        def asyncRequest():
            try:
                imageData, info = generateImages()
                for image in imageData:
                    images.append(image)
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
                status = self._webservice.progressCheck()
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
        idx = 0
        for image in images:
            saveImage(image, idx)
            idx += 1

    def _applyStatusUpdate(self, statusDict):
        if 'seed' in statusDict:
            self._config.set('lastSeed', str(statusDict['seed']))
        if 'progress' in statusDict:
            self._window.setLoadingMessage(statusDict['progress'])
