"""Python wrapper for libmypaint brush data."""
import os
import sys
from typing import Optional, Any
from ctypes import c_void_p, c_float, c_char_p, c_int
from multiprocessing import Process, Pipe
from PyQt5.QtGui import QColor
from PyQt5.QtCore import QByteArray, QFile, QIODevice
from src.image.mypaint.libmypaint import libmypaint, load_libmypaint, DEFAULT_LIBRARY_PATH


class MPBrush:
    """Python wrapper for libmypaint brush data."""

    def __init__(self) -> None:
        """Initialize a brush with default settings."""
        self._color = QColor(0, 0, 0)
        self._brush = libmypaint.mypaint_brush_new()
        libmypaint.mypaint_brush_from_defaults(self._brush)
        self._path: Optional[str] = None
        self.set_value(MPBrush.COLOR_H, 0.0)
        self.set_value(MPBrush.COLOR_S, 0.0)
        self.set_value(MPBrush.COLOR_V, 0.0)
        self.set_value(MPBrush.SNAP_TO_PIXEL, 0.)
        self.set_value(MPBrush.ANTI_ALIASING, 1.0)
        self.set_value(MPBrush.RADIUS_LOGARITHMIC, 0.3)
        self.set_value(MPBrush.DIRECTION_FILTER, 10.0)
        self.set_value(MPBrush.DABS_PER_ACTUAL_RADIUS, 4.0)

    def __del__(self) -> None:
        """Free C library memory on delete."""
        libmypaint.mypaint_brush_unref(self._brush)

    @property
    def path(self) -> str:
        """Returns the path to the last brush file loaded, if any."""
        return self._path

    @property
    def brush_ptr(self) -> c_void_p:
        """Returns the internal brush pointer."""
        return self._brush

    def load_file(self, file_path: str, preserve_size: bool = False) -> None:
        """Load a brush from a .myb file, optionally preserving brush size."""
        file = QFile(file_path)
        if not file.open(QIODevice.ReadOnly | QIODevice.Text):
            raise IOError(f'Failed to open {file_path}')
        byte_array = QByteArray(file.readAll())
        file.close()
        self.load(byte_array, preserve_size)
        self._path = file_path

    def load(self, content: QByteArray, preserve_size: False) -> None:
        """Load a brush from a byte array, optionally preserving brush size."""
        size = -1.0 if not preserve_size else self.get_value(MPBrush.RADIUS_LOGARITHMIC)

        libmypaint.mypaint_brush_from_defaults(self._brush)
        c_string = c_char_p(content.data())
        if not bool(libmypaint.mypaint_brush_from_string(self._brush, c_string)):
            print('Failed to read selected MyPaint brush')
        self.color = self._color
        if size >= 0:
            self.set_value(MPBrush.RADIUS_LOGARITHMIC, size)

    @property
    def color(self) -> QColor:
        """Returns the brush color."""
        return self._color

    @color.setter
    def color(self, new_color: QColor) -> None:
        """Updates the brush color."""
        if new_color == self._color:
            return
        self._color = new_color
        self.set_value(MPBrush.COLOR_H, max(self._color.hue(), 0) / 360.0)
        self.set_value(MPBrush.COLOR_S, self._color.saturation() / 255.0)
        self.set_value(MPBrush.COLOR_V, self._color.value() / 255.0)

    def get_value(self, setting: int) -> float:
        """Returns a brush setting value."""
        assert 0 <= setting <= len(self._setting_info), f'get_value: setting {setting} not in range' \
                                                        f'0-{len(self._setting_info)}'
        return float(libmypaint.mypaint_brush_get_base_value(self._brush, c_int(setting)))

    def set_value(self, setting: int, value: float) -> None:
        """Updates a brush setting value."""
        assert 0 <= setting <= len(self._setting_info), f'get_value: setting {setting} not in range' \
                                                        f'0-{len(self._setting_info)}'
        setting_info = self._setting_info[setting]
        if not setting_info.min_value <= value <= setting_info.max_value:
            print(f'Warning: value {value} not in expected range {setting_info.min_value}-{setting_info.max_value} '
                  f'for MyPaint brush setting "{setting_info.name}"')
        libmypaint.mypaint_brush_set_base_value(self._brush, c_int(setting), c_float(value))


class BrushSetting:
    """Holds information loaded for a libMyPaint brush setting."""

    def __init__(self, setting_id):
        self.id = setting_id
        setting = libmypaint.mypaint_brush_setting_info(setting_id)
        self.cname = setting[0].cname.decode('utf-8')
        self.name = libmypaint.mypaint_brush_setting_info_get_name(setting).decode('utf-8')
        self.tooltip = libmypaint.mypaint_brush_setting_info_get_tooltip(setting).decode('utf-8')
        self.min_value = setting[0].min
        self.max_value = setting[0].max
        self.default_value = getattr(setting[0], 'def')


def _load_brush_settings():
    """Dynamically load settings into the brush class when the module first loads."""

    # Setting count in libmypaint varies depending on version, and there's no way I know to get the count from the
    # library. We can iterate over possible values to determine all possible settings, but going past the end of the
    # list triggers an assertion failure and terminates the program. To get around this, read the settings from
    # a child process until that process crashes.
    def read_settings(connection: Any) -> None:
        """Send back valid settings IDs through a connection after validating each with libmypaint."""
        devnull = os.open(os.devnull, os.O_WRONLY)
        sys.stdout = open(devnull, 'w')
        sys.stderr = open(devnull, 'w')
        lib = load_libmypaint(DEFAULT_LIBRARY_PATH)
        for test_setting_id in range(999):  # 999 is an arbitrary finite limit.
            lib.mypaint_brush_setting_info(test_setting_id)
            connection.send(test_setting_id)

    # All the tricks for suppressing stdout/stderr in a loaded library involve weird hacks that are not really worth
    # messing with, but it's best to let anyone reading through the output know that the assertion error isn't a
    # problem.
    print('Checking available MyPaint brush settings, the following assertion failure is not an error:')
    parent_connection, child_connection = Pipe()
    process = Process(target=read_settings, args=(child_connection,))
    max_setting = 0
    process.start()
    process.join()
    while parent_connection.poll():
        max_setting = max(max_setting, parent_connection.recv())
    settings = []
    for setting_id in range(max_setting):
        setting = BrushSetting(setting_id)
        attr_name = setting.cname.upper()
        if not hasattr(MPBrush, attr_name):
            setattr(MPBrush, attr_name, setting_id)
        settings.append(setting)
    if not hasattr(MPBrush, '_setting_info'):
        setattr(MPBrush, '_setting_info', settings)


_load_brush_settings()
