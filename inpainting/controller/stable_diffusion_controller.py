from PyQt5.QtCore import QThread, QSize
from PyQt5.QtWidgets import QInputDialog
from inpainting.ui.stable_diffusion_main_window import StableDiffusionMainWindow
from inpainting.controller.base_controller import BaseInpaintController
from startup.utils import imageToBase64, loadImageFromBase64
import requests, io, sys, secrets, threading, json, re
from threading import Lock
from PIL import Image


BASE_64_PREFIX = 'data:image/png;base64,'

HEALTH_FN_INDEX = 170
TXT2IMG_FN_INDEX = 14
IMG2IMG_FN_INDEX = 33
PROGRESS_FN_INDEX = 3
PROGRESS_INIT_FN_INDEX = 4

# Not yet supported, add in future versions:
MODEL_QUERY_FN_INDEX = 0
MODEL_SWAP_FN_INDEX = 271
TOKEN_COUNT_FN_INDEX = 19
INTERROGATE_FN_INDEX = 36



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

    def _getRequestData(self, selection, mask):
        editMode = self._config.get('editMode')
        batchSize = self._config.get('batchSize')
        batchCount = self._config.get('batchCount')
        if editMode == "Inpaint" or editMode == "Image to Image":
            inpainting = (editMode == "Inpaint")
            return [
                1 if inpainting else 0, # 0=img2img, 1=inpaint, 2=batch img2img
                self._config.get('prompt'),
                self._config.get('negativePrompt'),
                "None", # prompt_style
                "None", # prompt_style2
                None if inpainting else (BASE_64_PREFIX + imageToBase64(selection)),   # init_image
                {
                    'image': BASE_64_PREFIX + imageToBase64(selection),
                    'mask': BASE_64_PREFIX + imageToBase64(mask)
                } if inpainting else None,
                None, # init_img_inpaint
                None, # init_mask_inpaint
                'Draw mask', # Mask mode
                self._config.get('samplingSteps'),
                self._config.get('samplingMethod'),
                self._config.get('maskBlur'),
                self._config.get('maskedContent'),
                self._config.get('restoreFaces'),
                self._config.get('tiling'),
                batchCount,
                batchSize,
                self._config.get('cfgScale'),
                self._config.get('denoisingStrength'),
                self._config.get('seed'),
                -1, # variation seed
                0, # variation strength
                0, # resize seed from height
                0, # resize seed from width
                False, # seed: enable extras
                selection.height,
                selection.width,
                self._config.get('stableResizeMode'),
                False, # Inpaint at full resolution (not relevant with IntraPaint)
                32, # Inpaint at full resolution padding (also not relevant)
                self._config.get('inpaintMasked'),
                "", # img2img_batch_input_dir
                "", # img2img_batch_output_dir,

                # Clip aesthetic:
                #"0.0001", # Aesthetic learning weight
                #0.9, # Aesthetic weight
                #10, # Aesthetic steps
                #"None", # Aesthetic image embedding
                #False, # Slerp interpolation checkbox
                #"", # Aesthetic text
                #0.1, # Slerp angle
                #False, # Aesthetic "is negative text" checkbox

                # Everything after this is for optional scripts we don't support, but the API still expects.
                # Actual values shouldn't matter (hopefully) as long as the types are valid
                "None", # selected script
                None, # markdown
                False,# override sampling method
                False,# Override prompt checkbox
                None, # Original prompt
                None, # Original negative prompt
                False,# override sampling steps
                1,    # Decode steps
                False,# Override denoising strength
                1, # Decode CFG scale
                1, # randomness slider
                1, # sigma slider
                1, # Loops slider
                1, # Denoising slider
                None, # HTML
                None, # 'Pixels to expand' slider
                None, # 'Mask blur' slider
                ['left', 'right', 'up', 'down'], # 'Outpainting direction' choices
                None, # Fall-off exponent
                None, # Color variation
                None, # Pixels to expand (again)
                None, # Mask blur (again)
                "fill", # 'Masked content' selection
                ['left', 'right', 'up', 'down'], # 'Outpainting direction' choices
                None, # 'Put variable parts at start of prompt'
                None, # 'show textbox' option
                None, # JSON object list (batch files list?)
                None, # Bulk prompt list
                None, # "represents null of the Html component" (???)
                None, # Tile overlap
                "None", # Upscaler
                "Seed", # X type
                None, # X values
                "Steps", # Y type
                None, # Y values
                None, # Draw legend
                False, # Include separate images
                None, # Keep -1 for seeds
            ]
        else: #txt2img
            return [
                self._config.get('prompt'),
                self._config.get('negativePrompt'),
                "None", # prompt_style
                "None", # prompt_style2
                self._config.get('samplingSteps'),
                self._config.get('samplingMethod'),
                self._config.get('restoreFaces'),
                self._config.get('tiling'),
                batchCount,
                batchSize,
                self._config.get('cfgScale'),
                self._config.get('seed'),
                -1, # variation seed
                0, # variation strength
                0, # resize seed from height
                0, # resize seed from width
                False, # seed: enable extras
                selection.height,
                selection.width,
                False, # highres fix checkbox
                self._config.get('denoisingStrength'),
                512, # Firstpass width
                512, # Firstpass height

                # Clip aesthetic:
                #"0.0001", # Aesthetic learning weight
                #0.9, # Aesthetic weight
                #10, # Aesthetic steps
                #"None", # Aesthetic image embedding
                #False, # Slerp interpolation checkbox
                #"", # Aesthetic text
                #0.1, # Slerp angle
                #False, # Aesthetic "is negative text" checkbox

                # Everything after this is for optional scripts we don't support, but the API still expects.
                # Actual values shouldn't matter as long as the types are valid
                "None",  # selected script
                False,   # 'Put variable parts at start of prompt'
                False,   # 'show textbox' option
                None,    # Prompt files
                "",      # Prompt textbox
                "Seed",  # X type
                "",      # X values
                "Steps", # Y type
                "",      # Y values
                True,    # Draw legend checkbox
                True,    # Keep -1 for seeds
                None,
                "",
                ""
            ]

    def healthCheck(url, session_hash=secrets.token_hex(5)):
        try:
            body = {
                'data': [],
                'fn_index': HEALTH_FN_INDEX,
                'session_hash': session_hash
            }
            res = requests.post(f"{url}/api/predict/", json=body, timeout=30)
            return res.status_code == 200 and ('application/json' in res.headers['content-type']) \
                    and 'data' in res.json()
        except Exception as err:
            print(f"error connecting to {url}: {err}")
            return False


    def _adjustConfigDefaults(self):
        # update size limits for stable-diffusion's capabilities:
        self._config.set('maxEditSize', QSize(512, 512))
        # stable-diffusion backend will handle this for us:
        self._config.set('removeUnmaskedChanges', False)

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


    def _inpaint(self, selection, mask, saveImage, statusSignal):
        editMode = self._config.get('editMode')
        inpaintArgs = self._getRequestData(selection, mask)
        body = {
            'data': inpaintArgs,
            'fn_index': TXT2IMG_FN_INDEX if editMode == 'Text to Image' else IMG2IMG_FN_INDEX,
            'session_hash': self._session_hash
        }
        #uri = f"{self._server_url}/api/" + ('txt2img' if (editMode == 'Text to Image') else 'img2img')
        uri = f"{self._server_url}/api/predict/"

        def errorCheck(serverResponse, contextStr):
            if serverResponse.status_code != 200:
                if serverResponse.content and ('application/json' in serverResponse.headers['content-type']) \
                        and serverResponse.json() and 'detail' in serverResponse.json():
                    raise Exception(f"{serverResponse.status_code} response to {contextStr}: {serverResponse.json()['detail']}")
                else:
                    raise Exception(f"{serverResponse.status_code} response to {contextStr}: unknown error with code {serverResponse.status_code}")

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

        # Send to progress 
        initBody = {
            'data': [],
            'fn_index': PROGRESS_INIT_FN_INDEX,
            'session_hash': self._session_hash
        }
        init_response = requests.post(uri, json=initBody)
        init_data = init_response.json()
        if init_data['is_generating'] is True:
            raise Exception('Image generation in progress, try again later.')


        def asyncRequest():
            res = requests.post(uri, json=body)
            try:
                errorCheck(res, f"New {editMode} request")
                if len(errors) == 0:
                    resBody = res.json()
                    imageData = resBody['data'][0]
                    for item in imageData:
                        images.append(item)
                    params  = json.loads(resBody['data'][1])
                    statusSignal.emit(params)
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
            # GET server_url/sample, sending previous samples:
            res = None
            try:
                progressCheckBody = {
                    'data': [],
                    'fn_index': PROGRESS_FN_INDEX,
                    'session_hash': self._session_hash
                }
                res = requests.post(f'{self._server_url}/api/predict/', json=progressCheckBody, timeout=30)
                errorCheck(res, 'Progress request')
                progressText = res.json()['data'][0]
                match = re.search("\d+% ETA: \d+[smh]", progressText)
                if match is not None:
                    statusSignal.emit({'progress': match.group()})
                elif progressText != '':
                    print(f"Failed to decode progress from '{progressText}'")
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
        print('Inpainting finished without errors.')
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
                if image.startswith(BASE_64_PREFIX):
                    image = image[len(BASE_64_PREFIX):]
                imageObject = loadImageFromBase64(imageStr)
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
