from PyQt5.QtCore import QObject, QSize
from PIL import Image
from threading import Lock

class Config(QObject):
    """
    A shared resource to set inpainting configuration and to provide default values.
    Current limitations, which may or may not be addressed eventually:
    - Expected values and defaults are hard-coded
    - Changes are not saved to disk
    - Data is not 100% guaranteed to be threadsafe, thread locking is used on get/set
      but there's no special handling to prevent deadlocks or protection for connected objects.
    """

    def __init__(self):
        self._values = {}
        self._types = {}
        self._connected = {}
        self._options = {}
        self._lock = Lock()

        # Editing options:
        self._setDefault('maxEditSize', QSize(256, 256))
        self._setDefault('minEditSize', QSize(8, 8))
        self._setDefault('initialMaskBrushSize', 40)
        self._setDefault('initialSketchBrushSize', 4)
        self._setDefault('scaleSelectionBeforeInpainting', True)
        self._setDefault('saveSketchInResult', False)

        # Inpainting guidance options:
        self._setDefault('prompt', '')
        self._setDefault('negativePrompt', '')
        self._setDefault('guidanceScale', 5.0)
        self._setDefault('maxGuidanceScale', 25.0)
        self._setDefault('guidanceScaleStep', 0.2)
        self._setDefault('cutn', 16)

        # Inpainting behavior options:
        self._setDefault('batchSize', 3)
        self._setDefault('batchCount', 3)
        self._setDefault('maxBatchSize', 9)
        self._setDefault('maxBatchCount', 9)
        self._setDefault('skipSteps', 0)
        self._setDefault('maxSkipSteps', 27)
        self._setDefault('upscaleMode', Image.LANCZOS)
        self._setDefault('downscaleMode', Image.HAMMING)
        # Set whether areas in the sketch layer outside of the mask should be included in inpainting results.
        self._setDefault('saveSketchChanges', False)
        # Inpainting can create subtle changes outside the mask area, which can gradually impact image quality
        # and create annoying lines in larger images. To fix this, enable this option to apply the mask to the
        # resulting sample, and re-combine it with the original image. In addition, blur the mask slightly to improve
        # image composite quality.
        self._setDefault('removeUnmaskedChanges', True)

        # Optional timelapse path where progress images should be saved:
        self._setDefault('timelapsePath', '')

        # Web client settings (delays in microseconds):
        self._setDefault('minRetryDelay', 300000) 
        self._setDefault('maxRetryDelay', 60000000)

        # Settings used only by stable-diffusion:
        self._setDefault('editMode', 'Inpaint', ['Inpaint', 'Text to Image', 'Image to Image'])
        self._setDefault('inpaintMasked', 'Inpaint masked', ['Inpaint masked', 'Inpaint not masked'])
        self._setDefault('maskedContent', 'original', ['fill', 'original', 'latent noise', 'latent nothing'])
        self._setDefault('stableResizeMode', 'Just resize', ['Just resize', 'Crop and resize', 'Resize and fill'])
        self._setDefault('samplingSteps', 20)
        self._setDefault('minSamplingSteps', 1)
        self._setDefault('maxSamplingSteps', 150)
        self._setDefault('samplingMethod', 'Euler a', ['Euler a', 'Euler', 'LMS', 'Heun', 'DPM2', 'DPM2 a',
                'LMS Karras', 'DPM2 Karras', 'DPM2 a Karras', 'DDIM', 'PLMS'])
        self._setDefault('maskBlur', 4)
        self._setDefault('maxMaskBlur', 64)
        self._setDefault('restoreFaces', False)
        self._setDefault('tiling', False)
        self._setDefault('cfgScale', 7.0)
        self._setDefault('minCfgScale', 0.0)
        self._setDefault('maxCfgScale', 30.0)
        self._setDefault('cfgScaleStep', 0.5)
        self._setDefault('denoisingStrength', 0.75)
        self._setDefault('minDenoisingStrength', 0.0)
        self._setDefault('maxDenoisingStrength', 1.0)
        self._setDefault('denoisingStrengthStep', 0.01)
        self._setDefault('seed', -1)

        # It's somewhat out of place here, but defining lastSeed and lastFile as config values makes it trivial to
        # wire them to widgets. TODO: maybe rename config to sharedData, or settings, perhaps? Add a separate config
        # module that actually reads (and writes?) saved settings in a text file.
        self._setDefault('lastSeed', "-1")
        self._setDefault('lastFilePath', '')

    def _setDefault(self, key, initialValue, options=None):
        self._values[key] = initialValue
        self._types[key] = type(initialValue)
        self._connected[key] = {}
        if options is not None:
            self._options[key] = options

    def get(self, key):
        if not key in self._values:
            raise Exception(f"Tried to get unknown config value '{key}'")
        self._lock.acquire()
        value = self._values[key]
        self._lock.release()
        return value

    def getOptionIndex(self, key):
        if not key in self._values:
            raise Exception(f"Tried to get unknown config value '{key}'")
        if not key in self._options:
            raise Exception(f"Config value '{key}' does not have an associated options list")
        self._lock.acquire()
        value = self._values[key]
        index = self._options[key].index(value)
        self._lock.release()
        return index

    def getOptions(self, key):
        if not key in self._values:
            raise Exception(f"Tried to set unknown config value '{key}'")
        return self._options[key]


    def set(self, key, value):
        if not key in self._values:
            raise Exception(f"Tried to set unknown config value '{key}'")
        if type(value) != self._types[key]:
            raise Exception(f"Expected '{key}' value '{value}' to have type '{self._types[key]}', found '{type(value)}'")
        if key in self._options and not value in self._options[key]:
            raise Exception(f"'{key}' value '{value}' is not a valid option")
            raise
        self._lock.acquire()
        valueChanged = (self._values[key] != value)
        self._values[key] = value
        self._lock.release()
        if valueChanged:
            for callback in self._connected[key].values():
                callback(value)
                if (self.get(key) != value):
                    break

    def connect(self, connectedObject, key, onChangeFn):
        if not key in self._values:
            raise Exception(f"Tried to connect to unknown config value '{key}'")
        self._connected[key][connectedObject] = onChangeFn

    def disconnect(self, connectedObject, key):
        if not key in self._values:
            raise Exception(f"Tried to disconnect from unknown config value '{key}'")
        self._connected[key].pop(connectedObject)

    def list(self):
        return self._values.keys()

    def applyArgs(self, args):
        if args.text:
            self.set('prompt', args.text)
        if args.negative:
            self.set('negativePrompt', args.negative)
        if ('num_batches' in args) and args.num_batches:
            self.set('batchCount', args.num_batches)
        if ('batch_size' in args) and args.batch_size:
            self.set('batchSize', args.batch_size)
        if ('timelapse_path' in args) and args.timelapse_path:
            self.set('timelapsePath', args.timelapse_path)
        if ('num_batches' in args) and args.num_batches:
            self.set('batchCount', args.num_batches)
        if ('batch_size' in args) and args.batch_size:
            self.set('batchSize', args.batch_size)
        if ('cutn' in args) and args.cutn:
            self.set('cutn', args.cutn)
