from PyQt5.QtCore import QObject, QSize
from PIL import Image
from threading import Lock
import sys, json, os.path, importlib.util
from io import StringIO
from PyQt5.QtWidgets import QStyleFactory

class Config(QObject):
    """
    A shared resource to set inpainting configuration and to provide default values.
    """

    def __init__(self):
        self._values = {}
        self._types = {}
        self._connected = {}
        self._options = {}
        self._jsonPath = 'config.json'
        self._lock = Lock()

        # UI options:
        self._setDefault('style', 'Fusion', QStyleFactory.keys())
        self._setDefault('fontPointSize', 10)
        themeOptions = ['None']
        if self._moduleInstalled('qdarktheme'):
            themeOptions += [ 'qdarktheme_dark', 'qdarktheme_light', 'qdarktheme_auto' ]
        if self._moduleInstalled('qt_material'):
            from qt_material import list_themes
            themeOptions += [ f"qt_material_{theme}" for theme in list_themes() ]
        self._setDefault('theme', 'None', themeOptions)

        # Editing options:
        self._setDefault('maxEditSize', QSize(10240, 10240))
        self._setDefault('minEditSize', QSize(8, 8))
        self._setDefault('editSize', QSize(512, 512))
        self._setDefault('initialMaskBrushSize', 40)
        self._setDefault('initialSketchBrushSize', 4)
        self._setDefault('saveSketchInResult', True)
        self._setDefault('maxUndo', 10)

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
        self._setDefault('maxBatchSize', 30)
        self._setDefault('maxBatchCount', 99)
        self._setDefault('skipSteps', 0)
        self._setDefault('maxSkipSteps', 27)
        self._setDefault('upscaleMode', Image.LANCZOS)
        self._setDefault('downscaleMode', Image.LANCZOS)
        # Set whether areas in the sketch layer outside of the mask should be included in inpainting results.
        self._setDefault('saveSketchChanges', False)
        # Inpainting can create subtle changes outside the mask area, which can gradually impact image quality
        # and create annoying lines in larger images. To fix this, enable this option to apply the mask to the
        # resulting sample, and re-combine it with the original image. In addition, blur the mask slightly to improve
        # image composite quality.
        # NOTE: Regardless of this setting's value, this will always be done if the selection is being scaled.
        self._setDefault('removeUnmaskedChanges', True)
        # Sets whether to include the original selection as an option in SampleSelector to better evaluate whether
        # available options are actually an improvement:
        self._setDefault('addOriginalToSamples', True)

        # Optional timelapse path where progress images should be saved:
        self._setDefault('timelapsePath', '')

        # Web client settings (delays in microseconds):
        self._setDefault('minRetryDelay', 300000) 
        self._setDefault('maxRetryDelay', 60000000)

        # Default mypaint brushes:
        self._setDefault('brush_default', './resources/brushes/experimental/1pixel.myb')
        self._setDefault('brush_pressure_size', './resources/brushes/experimental/pixel_hardink.myb')
        self._setDefault('brush_pressure_opacity', './resources/brushes/deevad/watercolor_glazing.myb')
        self._setDefault('brush_pressure_both', './resources/brushes/tanda/acrylic-04-with-water.myb')


        # Settings used only by stable-diffusion:
        self._setDefault('editMode', 'Inpaint', ['Inpaint', 'Text to Image', 'Image to Image'])
        self._setDefault('inpaintMasked', 'Inpaint masked', ['Inpaint masked', 'Inpaint not masked'])
        self._setDefault('maskedContent', 'original', ['fill', 'original', 'latent noise', 'latent nothing'])
        self._setDefault('stableResizeMode', 'Just resize', ['Just resize', 'Crop and resize', 'Resize and fill'])
        self._setDefault("interrogateModel", "clip")
        self._setDefault('samplingSteps', 30)
        self._setDefault('minSamplingSteps', 1)
        self._setDefault('maxSamplingSteps', 150)
        self._setDefault('samplingMethod', 'Euler a', ['Euler a', 'Euler', 'LMS', 'Heun', 'DPM2', 'DPM2 a',
                'LMS Karras', 'DPM2 Karras', 'DPM2 a Karras', 'DDIM', 'PLMS'])
        self._setDefault('upscaleMethod', 'None', ['None'])
        self._setDefault('styles', 'none', ['none'])
        self._setDefault('maskBlur', 4)
        self._setDefault('maxMaskBlur', 64)
        self._setDefault('restoreFaces', False)
        self._setDefault('tiling', False)
        self._setDefault('cfgScale', 9.0)
        self._setDefault('minCfgScale', 0.0)
        self._setDefault('maxCfgScale', 30.0)
        self._setDefault('cfgScaleStep', 0.5)
        self._setDefault('denoisingStrength', 0.40)
        self._setDefault('minDenoisingStrength', 0.0)
        self._setDefault('maxDenoisingStrength', 1.0)
        self._setDefault('denoisingStrengthStep', 0.01)
        self._setDefault('seed', -1)
        self._setDefault('inpaintFullRes', False)
        self._setDefault('inpaintFullResPadding', 32)
        self._setDefault('inpaintFullResPaddingMax', 1024)

        # Controlnet plugin options:
        self._setDefault('controlnetVersion', -1.0)
        self._setDefault('controlnetUpscaling', False)
        self._setDefault('controlnetDownsampleRate', 1.0)
        self._setDefault('controlnetDownsampleMin', 1.0)
        self._setDefault('controlnetDownsampleMax', 4.0)
        self._setDefault('controlnetDownsampleSteps', 0.1)
        self._setDefault('controlnetInpainting', False)
        self._setDefault('controlnetArgs', {})


        # It's somewhat out of place here, but defining lastSeed and lastFile as config values makes it trivial to
        # wire them to widgets.
        self._setDefault('lastSeed', "-1")
        self._setDefault('lastFilePath', '')

        # Pen tablet functionality
        # Should pen pressure affect sketch/mask size?
        self._setDefault('pressureSize', True)
        # Should pen pressure affect mask opacity?
        self._setDefault('pressureOpacity', False)

        # List all keys stored temporarily in config that shouldn't be saved to JSON:
        self._setDefault('unsavedKeys', [
                'prompt',
                'negativePrompt',
                'timelapsePath',
                'lastFilePath',
                'seed',
                'maxEditSize',
                'unsavedKeys',
                'styles',
                'controlnetVersion'
        ])

        if os.path.isfile(self._jsonPath):
            self._readFromJson()
        else:
            self._writeToJson()


    def _setDefault(self, key, initialValue, options=None):
        self._values[key] = initialValue
        self._types[key] = type(initialValue)
        self._connected[key] = {}
        if options is not None:
            self._options[key] = options

    def _writeToJson(self): 
        convertedDict = {}
        keysToSkip = self.get('unsavedKeys')
        self._lock.acquire()
        for key, value in self._values.items():
            if key in keysToSkip:
                continue
            if isinstance(value, QSize):
                value = f"{value.width()}x{value.height()}"
            elif isinstance(value, list):
                value = ','.join(value)
            convertedDict[key] = value
        with open(self._jsonPath, 'w', encoding='utf-8') as file:
            json.dump(convertedDict, file, ensure_ascii=False, indent=4)
        self._lock.release()

    def _readFromJson(self):
        try:
            with open(self._jsonPath) as file:
                json_data = json.load(file)
                for key, value in json_data.items():
                    try:
                        if self._types[key] == QSize:
                            value = QSize(*map(lambda n: int(n), value.split("x")))
                        elif self._types[key] == list:
                            value = value.split(",")
                        self.set(key, value, addMissingOptions=True)
                    except Exception as err:
                        print(f"Failed to set {key}={value}: {err}")
        except Exception as err:
            print(f"Reading JSON config failed: {err}")

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

    def updateOptions(self, key, optionsList):
        if not key in self._values:
            raise Exception(f"Tried to get unknown config value '{key}'")
        if not key in self._options:
            raise Exception(f"Config value '{key}' does not have an associated options list")
        if not isinstance(optionsList, list) or len(optionsList) == 0:
            raise Exception(f"Provided invalid options for config value '{key}'")
        self._options[key] = optionsList
        if not self._values[key] in optionsList:
            self.set(key, optionsList[0], False)

    def addOption(self, key, option):
        if not key in self._values:
            raise Exception(f"Tried to get unknown config value '{key}'")
        if not key in self._options:
            raise Exception(f"Config value '{key}' does not have an associated options list")
        self._options[key].append(option)

    def set(self, key, value, saveChange=True, addMissingOptions=False):
        if not key in self._values:
            raise Exception(f"Tried to set unknown config value '{key}'")
        if type(value) != self._types[key]:
            raise Exception(f"Expected '{key}' value '{value}' to have type '{self._types[key]}', found '{type(value)}'")
        if key in self._options and not value in self._options[key]:
            if addMissingOptions:
                self.addOption(key, value)
            else:
                raise Exception(f"'{key}' value '{value}' is not a valid option in {json.dumps(self._options[key])}")
        self._lock.acquire()
        valueChanged = (self._values[key] != value)
        self._values[key] = value
        self._lock.release()
        if valueChanged and saveChange:
            self._writeToJson()
            for callback in self._connected[key].values():
                try:
                    callback(value)
                except Exception as err:
                    print(f"Update triggered by {key} change failed: {err}")
                if (self.get(key) != value):
                    break

    def _moduleInstalled(self, name):
        if name in sys.modules:
            return true
        return bool((spec := importlib.util.find_spec(name)) is not None)

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
