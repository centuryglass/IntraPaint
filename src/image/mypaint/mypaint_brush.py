"""Python wrapper for libmypaint brush data."""
import logging
from ctypes import c_void_p, c_float, c_char_p, c_int
from typing import Optional

from PySide6.QtCore import Qt, QByteArray, QFile, QIODevice
from PySide6.QtGui import QColor

from src.image.mypaint.libmypaint import libmypaint

logger = logging.getLogger(__name__)


class MyPaintBrush:
    """Python wrapper for libmypaint brush data."""

    def __init__(self) -> None:
        """Initialize a brush with default settings."""
        self._color = QColor(0, 0, 0)
        self._brush = libmypaint.mypaint_brush_new()
        libmypaint.mypaint_brush_from_defaults(self._brush)
        self._path: Optional[str] = None
        self.set_value(MyPaintBrush.COLOR_H, 0.0)
        self.set_value(MyPaintBrush.COLOR_S, 0.0)
        self.set_value(MyPaintBrush.COLOR_V, 0.0)
        self.set_value(MyPaintBrush.SNAP_TO_PIXEL, 0.)
        self.set_value(MyPaintBrush.ANTI_ALIASING, 1.0)
        self.set_value(MyPaintBrush.RADIUS_LOGARITHMIC, 0.3)
        self.set_value(MyPaintBrush.DIRECTION_FILTER, 10.0)
        self.set_value(MyPaintBrush.DABS_PER_ACTUAL_RADIUS, 4.0)

    def __del__(self) -> None:
        """Free C library memory on delete."""
        libmypaint.mypaint_brush_unref(self._brush)

    @property
    def path(self) -> Optional[str]:
        """Returns the path to the last brush file loaded, if any."""
        return self._path

    @property
    def brush_ptr(self) -> c_void_p:
        """Returns the internal brush pointer."""
        return self._brush

    def load_file(self, file_path: str, preserve_size: bool = True) -> None:
        """Load a brush from a .myb file, optionally preserving brush size."""
        logger.info(f'loading brush file {file_path}')
        file = QFile(file_path)
        # noinspection PyTypeChecker
        if not file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
            raise IOError(f'Failed to open {file_path}')
        byte_array = QByteArray(file.readAll())
        file.close()
        self.load(byte_array, preserve_size)
        self._path = file_path

    def load(self, content: QByteArray, preserve_size: bool = True) -> None:
        """Load a brush from a byte array, optionally preserving brush size."""
        size = -1.0 if not preserve_size else self.get_value(MyPaintBrush.RADIUS_LOGARITHMIC)

        libmypaint.mypaint_brush_from_defaults(self._brush)
        c_string = c_char_p(content.data())
        if not bool(libmypaint.mypaint_brush_from_string(self._brush, c_string)):
            logger.error('Failed to read selected MyPaint brush')
        self.color = self._color
        if size >= 0:
            logger.info(f'restore saved logarithmic radius {size} after brush load.')
            self.set_value(MyPaintBrush.RADIUS_LOGARITHMIC, size)

    @property
    def color(self) -> QColor:
        """Returns the brush color."""
        return self._color

    @color.setter
    def color(self, new_color: QColor | Qt.GlobalColor) -> None:
        """Updates the brush color."""
        if isinstance(new_color, Qt.GlobalColor):
            new_color = QColor(new_color)
        self._color = new_color
        self.set_value(MyPaintBrush.COLOR_H, max(self._color.hue(), 0) / 360.0)
        self.set_value(MyPaintBrush.COLOR_S, self._color.saturation() / 255.0)
        self.set_value(MyPaintBrush.COLOR_V, self._color.value() / 255.0)

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
            logger.warning(f'Warning: value {value} not in expected range {setting_info.min_value}'
                           f'-{setting_info.max_value} for MyPaint brush setting "{setting_info.name}"')
        libmypaint.mypaint_brush_set_base_value(self._brush, c_int(setting), c_float(value))

    # DYNAMIC PROPERTIES:
    # Generate with `python /home/anthony/Workspace/ML/IntraPaint/scripts/dynamic_import_typing.py src/image/mypaint/mypaint_layer_brush.py`

    ANTI_ALIASING: int
    CHANGE_COLOR_H: int
    CHANGE_COLOR_HSL_S: int
    CHANGE_COLOR_HSV_S: int
    CHANGE_COLOR_L: int
    CHANGE_COLOR_V: int
    COLORIZE: int
    COLOR_H: int
    COLOR_S: int
    COLOR_V: int
    CUSTOM_INPUT: int
    CUSTOM_INPUT_SLOWNESS: int
    DABS_PER_ACTUAL_RADIUS: int
    DABS_PER_BASIC_RADIUS: int
    DABS_PER_SECOND: int
    DIRECTION_FILTER: int
    ELLIPTICAL_DAB_ANGLE: int
    ELLIPTICAL_DAB_RATIO: int
    ERASER: int
    GRIDMAP_SCALE: int
    GRIDMAP_SCALE_X: int
    GRIDMAP_SCALE_Y: int
    HARDNESS: int
    LOCK_ALPHA: int
    OFFSET_ANGLE: int
    OFFSET_ANGLE_2: int
    OFFSET_ANGLE_2_ASC: int
    OFFSET_ANGLE_2_VIEW: int
    OFFSET_ANGLE_ADJ: int
    OFFSET_ANGLE_ASC: int
    OFFSET_ANGLE_VIEW: int
    OFFSET_BY_RANDOM: int
    OFFSET_BY_SPEED: int
    OFFSET_BY_SPEED_SLOWNESS: int
    OFFSET_MULTIPLIER: int
    OFFSET_X: int
    OFFSET_Y: int
    OPAQUE: int
    OPAQUE_LINEARIZE: int
    OPAQUE_MULTIPLY: int
    PAINT_MODE: int
    POSTERIZE: int
    POSTERIZE_NUM: int
    PRESSURE_GAIN_LOG: int
    RADIUS_BY_RANDOM: int
    RADIUS_LOGARITHMIC: int
    RESTORE_COLOR: int
    SLOW_TRACKING: int
    SLOW_TRACKING_PER_DAB: int
    SMUDGE: int
    SMUDGE_BUCKET: int
    SMUDGE_LENGTH: int
    SMUDGE_LENGTH_LOG: int
    SMUDGE_RADIUS_LOG: int
    SMUDGE_TRANSPARENCY: int
    SNAP_TO_PIXEL: int
    SPEED1_GAMMA: int
    SPEED1_SLOWNESS: int
    SPEED2_GAMMA: int
    SPEED2_SLOWNESS: int
    STROKE_DURATION_LOGARITHMIC: int
    # noinspection SpellCheckingInspection
    STROKE_HOLDTIME: int
    STROKE_THRESHOLD: int
    TRACKING_NOISE: int
    _setting_info: list['BrushSetting']


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


def _get_setting_count() -> int:
    """Returns the number of brush settings in the loaded libmypaint, reading only the setting names it knows.

    libmypaint aborts on an out-of-range setting id, so the count comes from the highest id that
    mypaint_brush_setting_from_cname finds for a name declared on MyPaintBrush. A newer library's extra settings are
    left out.
    """
    setting_names = [name.lower() for name in MyPaintBrush.__annotations__ if name.isupper()]
    return 1 + max(libmypaint.mypaint_brush_setting_from_cname(name.encode('utf-8')) for name in setting_names)


def _load_brush_settings():
    """Dynamically load settings into the brush class when the module first loads."""
    settings = []
    for setting_id in range(_get_setting_count()):
        setting = BrushSetting(setting_id)
        attr_name = setting.cname.upper()
        if not hasattr(MyPaintBrush, attr_name):
            setattr(MyPaintBrush, attr_name, setting_id)
        settings.append(setting)
    if not hasattr(MyPaintBrush, '_setting_info'):
        setattr(MyPaintBrush, '_setting_info', settings)


_load_brush_settings()
