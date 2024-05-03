"""
A shared resource to set inpainting configuration and to provide default values.

Main features
-------------
    - Save and load values from a JSON file.
    - Allow access to those values through config.get()
    - Allow typesafe changes to those values through config.set()
    - Subscribe to specific value changes through config.connect()
"""

import sys
import json
import os.path
import importlib.util
from threading import Lock
from inspect import signature
from PIL import Image
from PyQt5.QtWidgets import QStyleFactory
from PyQt5.QtCore import QObject, QSize, QTimer

class Config(QObject):
    """
    A shared resource to set inpainting configuration and to provide default values.

    Common Exceptions Raised
    ------------------------
    KeyError
        When any function with the `key` parameter is called with an unknown key.
    TypeError
        When a function with the optional `inner_key` parameter is used with a non-empty `inner_key` and a `key`
        that doesn't contain a dict value.
    RuntimeError
        If a function that interacts with lists of accepted value options is called on a value that doesn't have
        a fixed list of acceptable options.  keys in the file will be ignored.
    """

    def __init__(self, json_path='config.json'):
        """
        Load existing config, or initialize from defaults.

        Parameters
        ----------
        json_path: str
            Path where config values will be saved and read. If the file does not exist, it will be created with
            default values. Any expected keys not found in the file will be added with default values. Any unexpected

        """
        self._values = {}
        self._types = {}
        self._connected = {}
        self._options = {}
        self._json_path = json_path
        self._lock = Lock()
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)

        # UI options:
        self._set_default('style', 'Fusion', QStyleFactory.keys())
        self._set_default('fontPointSize', 10)

        # Themes will vary based on system, so initial options need to be dynamically loaded:
        theme_options = ['None']
        def module_installed(name):
            if name in sys.modules:
                return True
            return bool((spec := importlib.util.find_spec(name)) is not None)
        if module_installed('qdarktheme'):
            theme_options += [ 'qdarktheme_dark', 'qdarktheme_light', 'qdarktheme_auto' ]
        if module_installed('qt_material'):
            from qt_material import list_themes
            theme_options += [ f"qt_material_{theme}" for theme in list_themes() ]
        self._set_default('theme', 'None', theme_options)

        # Editing options:
        self._set_default('maxEditSize', QSize(10240, 10240))
        self._set_default('minEditSize', QSize(8, 8))
        self._set_default('editSize', QSize(512, 512))
        self._set_default('maskBrushSize', 40)
        self._set_default('sketchBrushSize', 4)
        self._set_default('minBrushSize', 1)
        self._set_default('maxBrushSize', 300)
        self._set_default('saveSketchInResult', True)
        self._set_default('maxUndo', 10)

        # Inpainting guidance options:
        self._set_default('prompt', '')
        self._set_default('negativePrompt', '')
        self._set_default('guidanceScale', 5.0)
        self._set_default('maxGuidanceScale', 25.0)
        self._set_default('guidanceScaleStep', 0.2)
        self._set_default('cutn', 16)

        # Inpainting behavior options:
        self._set_default('batchSize', 3)
        self._set_default('batchCount', 3)
        self._set_default('maxBatchSize', 30)
        self._set_default('maxBatchCount', 99)
        self._set_default('skipSteps', 0)
        self._set_default('maxSkipSteps', 27)
        self._set_default('upscaleMode', Image.LANCZOS)
        self._set_default('downscaleMode', Image.LANCZOS)
        # Set whether areas in the sketch layer outside of the mask should be included in inpainting results.
        self._set_default('saveSketchChanges', True)
        # Inpainting can create subtle changes outside the mask area, which can gradually impact image quality
        # and create annoying lines in larger images. To fix this, enable this option to apply the mask to the
        # resulting sample, and re-combine it with the original image. In addition, blur the mask slightly to improve
        # image composite quality.
        # NOTE: Regardless of this setting's value, this will always be done if the selection is being scaled.
        self._set_default('removeUnmaskedChanges', True)
        # Sets whether to include the original selection as an option in SampleSelector to better evaluate whether
        # available options are actually an improvement:
        self._set_default('addOriginalToSamples', True)

        # Optional timelapse path where progress images should be saved:
        self._set_default('timelapsePath', '')

        # Web client settings (delays in microseconds):
        self._set_default('minRetryDelay', 300000)
        self._set_default('maxRetryDelay', 60000000)

        # Default mypaint brushes:
        self._set_default('brush_default', './resources/brushes/experimental/1pixel.myb')
        self._set_default('brush_pressure_size', './resources/brushes/experimental/pixel_hardink.myb')
        self._set_default('brush_pressure_opacity', './resources/brushes/deevad/watercolor_glazing.myb')
        self._set_default('brush_pressure_both', './resources/brushes/tanda/acrylic-04-with-water.myb')

        # Settings used only by stable-diffusion:
        self._set_default('editMode', 'Inpaint', ['Inpaint', 'Text to Image', 'Image to Image'])
        self._set_default('inpaintMasked', 'Inpaint masked', ['Inpaint masked', 'Inpaint not masked'])
        self._set_default('maskedContent', 'original', ['fill', 'original', 'latent noise', 'latent nothing'])
        self._set_default('stableResizeMode', 'Just resize', ['Just resize', 'Crop and resize', 'Resize and fill'])
        self._set_default("interrogateModel", "clip")
        self._set_default('samplingSteps', 30)
        self._set_default('minSamplingSteps', 1)
        self._set_default('maxSamplingSteps', 150)
        self._set_default('samplingMethod', 'Euler a', ['Euler a', 'Euler', 'LMS', 'Heun', 'DPM2', 'DPM2 a',
                'LMS Karras', 'DPM2 Karras', 'DPM2 a Karras', 'DDIM', 'PLMS'])
        self._set_default('upscaleMethod', 'None', ['None'])
        self._set_default('styles', 'none', ['none'])
        self._set_default('maskBlur', 4)
        self._set_default('maxMaskBlur', 64)
        self._set_default('restoreFaces', False)
        self._set_default('tiling', False)
        self._set_default('cfgScale', 9.0)
        self._set_default('minCfgScale', 0.0)
        self._set_default('maxCfgScale', 30.0)
        self._set_default('cfgScaleStep', 0.5)
        self._set_default('denoisingStrength', 0.40)
        self._set_default('minDenoisingStrength', 0.0)
        self._set_default('maxDenoisingStrength', 1.0)
        self._set_default('denoisingStrengthStep', 0.01)
        self._set_default('seed', -1)
        self._set_default('inpaintFullRes', False)
        self._set_default('inpaintFullResPadding', 32)
        self._set_default('inpaintFullResPaddingMax', 1024)

        # Controlnet plugin options:
        self._set_default('controlnetVersion', -1.0)
        self._set_default('controlnetUpscaling', False)
        self._set_default('controlnetDownsampleRate', 1.0)
        self._set_default('controlnetDownsampleMin', 1.0)
        self._set_default('controlnetDownsampleMax', 4.0)
        self._set_default('controlnetDownsampleSteps', 0.1)
        self._set_default('controlnetInpainting', False)
        self._set_default('controlnetArgs', {})

        # It's somewhat out of place here, but defining lastSeed and lastFile as config values makes it trivial to
        # wire them to widgets.
        self._set_default('lastSeed', "-1")
        self._set_default('lastFilePath', '')

        # Pen tablet functionality
        # Should pen pressure affect sketch/mask size?
        self._set_default('pressureSize', True)
        # Should pen pressure affect mask opacity?
        self._set_default('pressureOpacity', False)

        # List all keys stored temporarily in config that shouldn't be saved to JSON:
        self._set_default('unsavedKeys', [
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
        if os.path.isfile(self._json_path):
            self._read_from_json()
        else:
            self._write_to_json()


    def get(self, key, inner_key=None):
        """
        Returns a value from config.

        Parameters
        ----------
        key : str
            A key tracked by this config file.
        inner_key : str, optional
            If not None, assume the value at `key` is a dict and attempt to return the value within it at `inner_key`.
            If the value is a dict but does not contain `inner_key`, instead return None

        Returns
        -------
        int or float or str or bool or list or dict or QSize or None
            Type varies based on key. Each key is guaranteed to always return the same type, but inner_key values
            are not type-checked.
        """
        if not key in self._values:
            raise KeyError(f"Tried to get unknown config value '{key}'")
        with self._lock:
            if inner_key is not None:
                value = None if inner_key not in self._values[key] else self._values[key][inner_key]
            else:
                value = self._values[key]
        return value


    def set(self, key, value, save_change=True, add_missing_options=False, inner_key=None):
        """
        Updates a saved value.

        Parameters
        ----------
        key : str
            A key tracked by this config file.
        value : int or float or str or bool or list or dict or QSize or None
            The new value to assign to the key. Unless inner_key is not None, this must have the same type as the
            previous value.
        save_change: bool, default=True
            If true, save the change to the underlying JSON file. Otherwise, the change will be saved the next time
            any value is set with save_change=True
        add_missing_options: bool, default=False
            If the key is associated with a list of valid options and this is true, value will be added to the list
            of options if not already present. Otherwise, RuntimeError is raised if value is not within the list
        inner_key: str, optional
            If not None, assume the value at `key` is a dict and attempt to set the value within it at `inner_key`. If
            the value is a dict but does not contain `inner_key`, instead return None
       
        Raises
        ------
        TypeError
            If `value` does not have the same type as the current value saved under `key`
        RuntimeError
            If `key` has a list of associated valid options, `value` is not one of those options, and
            `add_missing_options` is false.
        """
        if not key in self._values:
            raise KeyError(f"Tried to set unknown config value '{key}'")
        if inner_key is not None and not isinstance(self._values[key], dict):
            raise TypeError(f"Tried to set '{key}.{inner_key}' to value '{value}', but " + \
                            f"{key} is type '{type(value)}'")
        if inner_key is None and type(value) != self._types[key]:
            raise TypeError(f"Expected '{key}' value '{value}' to have type '{self._types[key]}', found " + \
                            f"'{type(value)}'")
        if key in self._options and not value in self._options[key]:
            if add_missing_options:
                self.add_option(key, value)
            else:
                raise RuntimeError(f"'{key}' value '{value}' is not a valid option in {json.dumps(self._options[key])}")
        value_changed = False
        last_value = None
        new_value = value
        # Update existing value:
        with self._lock:
            last_value = self._values[key]
            if inner_key is None:
                value_changed = self._values[key] != value
                self._values[key] = value
            else:
                old_inner_value = None if inner_key not in self._values[key] else self._values[key][inner_key]
                last_value = old_inner_value
                value_changed = old_inner_value != value
                if value is None and value_changed:
                    del self._values[key][inner_key]
                elif value_changed:
                    self._values[key][inner_key] = value
                new_value = self._values[key]
        if not value_changed:
            return
        # Schedule save to JSON file:
        if save_change:
            with self._lock:
                if not self._save_timer.isActive():
                    def write_change():
                        self._write_to_json()
                        self._save_timer.timeout.disconnect(write_change)
                    self._save_timer.timeout.connect(write_change)
                    self._save_timer.start(100)
        # Pass change to connected callback functions
        for callback in self._connected[key].values():
            num_args = len(signature(callback).parameters)
            if num_args == 1:
                callback(new_value)
            elif num_args == 2:
                callback(new_value, last_value)
            if self.get(key, inner_key) != value:
                break


    def connect(self, connected_object, key, on_change_fn, inner_key = None):
        """
        Registers a callback function that should run when a particular key is changed.

        Parameters
        ----------
        connected_object: object
            An object to associate with this connection. Only one connection can be made for a connected_object.
        key: str
            A key tracked by this config file.
        on_change_fn: function(new_value) or function(new_value, previous_value)
            The function to run when the value changes.
        inner_key: str, optional
            If not None, assume the value at `key` is a dict and ensure on_change_fn only runs when `inner_key`
            changes within the value.
        """
        if not key in self._values:
            raise KeyError(f"Tried to connect to unknown config value '{key}'")
        num_args = len(signature(on_change_fn).parameters)
        if num_args < 1 or num_args > 2:
            raise RuntimeError(f"callback function connected to {key} value takes {num_args} " + \
                                "parameters, expected 1-2")
        if inner_key is None:
            self._connected[key][connected_object] = on_change_fn
        else:
            def wrapper_fn(value, last_value):
                new_inner_value = None if inner_key not in value else value[inner_key]
                if last_value != new_inner_value:
                    on_change_fn(new_inner_value)
            self._connected[key][connected_object] = wrapper_fn


    def disconnect(self, connected_object, key):
        """
        Removes a callback function previously registered through config.connect() for a particular object and key.
        """
        if not key in self._values:
            raise KeyError(f"Tried to disconnect from unknown config value '{key}'")
        self._connected[key].pop(connected_object)


    def list(self):
        """Returns all keys tracked by this Config object."""
        return self._values.keys()


    def get_option_index(self, key):
        """
        Returns the index of the selected option for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options
        """
        if not key in self._values:
            raise KeyError(f"Tried to get unknown config value '{key}'")
        if not key in self._options:
            raise RuntimeError(f"Config value '{key}' does not have an associated options list")
        with self._lock:
            value = self._values[key]
            index = self._options[key].index(value)
            return index


    def get_options(self, key):
        """
        Returns all valid options accepted for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options.
        """
        if not key in self._values:
            raise KeyError(f"Tried to set unknown config value '{key}'")
        if not key in self._options:
            raise RuntimeError(f"Config value '{key}' does not have an associated options list")
        return self._options[key]


    def update_options(self, key, options_list):
        """
        Replaces the list of accepted options for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options.
        """
        if not key in self._values:
            raise KeyError(f"Tried to get unknown config value '{key}'")
        if not key in self._options:
            raise RuntimeError(f"Config value '{key}' does not have an associated options list")
        if not isinstance(options_list, list) or len(options_list) == 0:
            raise RuntimeError(f"Provided invalid options for config value '{key}'")
        self._options[key] = options_list
        if not self._values[key] in options_list:
            self.set(key, options_list[0], False)


    def add_option(self, key, option):
        """
        Adds a new item to the list of accepted options for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options.
        """
        if not key in self._values:
            raise KeyError(f"Tried to get unknown config value '{key}'")
        if not key in self._options:
            raise RuntimeError(f"Config value '{key}' does not have an associated options list")
        self._options[key].append(option)

    def apply_args(self, args):
        """Loads expected parameters from command line arguments"""
        expected = {
            args.text: 'prompt',
            args.negative: 'negativePrompt',
            args.num_batches: 'batchCount',
            args.batch_size: 'batchSize',
            args.cutn: 'cutn'
        }
        for arg_value, key in expected.items():
            if arg_value:
                self.set(key, arg_value)

    def _set_default(self, key, initial_value, options=None):
        self._values[key] = initial_value
        self._types[key] = type(initial_value)
        self._connected[key] = {}
        if options is not None:
            self._options[key] = options


    def _write_to_json(self):
        converted_dict = {}
        keys_to_skip = self.get('unsavedKeys')
        with self._lock:
            for key, value in self._values.items():
                if key in keys_to_skip:
                    continue
                if isinstance(value, QSize):
                    value = f"{value.width()}x{value.height()}"
                elif isinstance(value, list):
                    value = ','.join(value)
                converted_dict[key] = value
            with open(self._json_path, 'w', encoding='utf-8') as file:
                json.dump(converted_dict, file, ensure_ascii=False, indent=4)


    def _read_from_json(self):
        try:
            with open(self._json_path, encoding="utf-8") as file:
                json_data = json.load(file)
                for key, value in json_data.items():
                    try:
                        if self._types[key] == QSize:
                            value = QSize(*(int(n) for n in value.split("x")))
                        elif self._types[key] == list:
                            value = value.split(",")
                        self.set(key, value, add_missing_options=True)
                    except (KeyError, RuntimeError) as err:
                        print(f"Failed to set {key}={value}: {err}")
        except json.JSONDecodeError as err:
            print(f"Reading JSON config failed: {err}")
