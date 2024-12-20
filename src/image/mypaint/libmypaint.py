"""Low-level wrapper for the libmypaint library."""
import os
from ctypes import CFUNCTYPE, POINTER, Structure, c_int, c_void_p, c_float, c_double, c_char_p, c_uint16, CDLL, cdll
from ctypes.util import find_library
from typing import Optional, TypeAlias

from src.config.application_config import AppConfig
from src.util.shared_constants import PROJECT_DIR

# constants and basic typedefs:
c_float_p = POINTER(c_float)
c_uint16_p = POINTER(c_uint16)
RECTANGLE_BUF_SIZE = 100  # Paint operation rectangle buffer size.
NUM_BBOXES_DEFAULT = 32  # Tiled surface default bounding box count.
TILE_DIM = 64  # Tiled surface x/y resolution
LIBRARY_NAME = 'mypaint'  # For the ctypes.util.find_library function
if os.name == 'nt':
    DEFAULT_LIBRARY_PATH = f'{PROJECT_DIR}/lib/libmypaint.dll'
else:
    DEFAULT_LIBRARY_PATH = f'{PROJECT_DIR}/lib/libmypaint.so'


# Rectangles:


class MyPaintRectangle(Structure):
    """Basic rectangle data structure."""
    _fields_ = [
        ('x', c_int),
        ('y', c_int),
        ('width', c_int),
        ('height', c_int)
    ]


RectangleBuffer = MyPaintRectangle * RECTANGLE_BUF_SIZE


class MyPaintRectangles(Structure):
    """Internal rectangle data buffer, needs to be provided when drawing operations finish."""
    _fields_ = [
        ('num_rectangles', c_int),
        ('rectangles', POINTER(MyPaintRectangle))
    ]


# Surface:
surface_ptr: TypeAlias = c_void_p

MyPaintSurfaceDrawDabFunction = CFUNCTYPE(c_int, surface_ptr, c_float, c_float,  # (self, x, y
                                          c_float, c_float, c_float, c_float,  # radius, r, g, b
                                          c_float, c_float, c_float,  # opaque, hardness, softness
                                          c_float, c_float, c_float,  # alpha eraser, aspect ratio, angle
                                          c_float, c_float, c_float,  # lock alpha, colorize, posterize
                                          c_float, c_float)  # posterize_num, paint)

MyPaintSurfaceGetColorFunction = CFUNCTYPE(None, surface_ptr, c_float, c_float, c_float,  # (self, x, y, radius
                                           c_float_p, c_float_p, c_float_p, c_float_p, c_float)  # r, g, b, a, paint)

MyPaintSurfaceBeginAtomicFunction = CFUNCTYPE(None, surface_ptr)  # (self)

MyPaintSurfaceEndAtomicFunction = CFUNCTYPE(None, surface_ptr, POINTER(MyPaintRectangles))  # (self, rectangle buffer)

MyPaintSurfaceDestroyFunction = CFUNCTYPE(None, surface_ptr)  # (self)

MyPaintSurfaceSavePngFunction = CFUNCTYPE(None, surface_ptr, c_char_p, c_int, c_int,  # (self, path, x, y,
                                          c_int, c_int)  # width, height)


class MyPaintSurface(Structure):
    """Struct used by libMyPaint to represent a drawing surface."""
    _fields_ = [
        ('draw_dab', MyPaintSurfaceDrawDabFunction),
        ('get_color', MyPaintSurfaceGetColorFunction),
        ('begin_atomic', MyPaintSurfaceBeginAtomicFunction),
        ('end_atomic', MyPaintSurfaceEndAtomicFunction),
        ('destroy', MyPaintSurfaceDestroyFunction),
        ('save_png', MyPaintSurfaceSavePngFunction)
    ]


# noinspection SpellCheckingInspection
class MyPaintTileRequest(Structure):
    """Struct provided when libMyPaint requests tile data."""
    _fields_ = [
        ('tx', c_int),
        ('ty', c_int),
        ('readonly', c_int),
        ('buffer', c_uint16_p),
        ('context', c_void_p),
        ('thread_id', c_int),
        ('mipmap_level', c_int)
    ]


request_ptr = POINTER(MyPaintTileRequest)

MyPaintTileRequestStartFunction = CFUNCTYPE(None, surface_ptr, request_ptr)

MyPaintTileRequestEndFunction = CFUNCTYPE(None, surface_ptr, request_ptr)

MyPaintTiledSurfaceAreaChanged = CFUNCTYPE(None, surface_ptr, c_int, c_int, c_int, c_int)  # (self, x, y, w, h)


# Tiled surface:
class MyPaintTiledSurface(Structure):
    """Struct used by libMyPaint to represent a tiled drawing surface."""
    _fields_ = [
        ('parent', MyPaintSurface),
        ('tile_request_start', MyPaintTileRequestStartFunction),
        ('tile_request_end', MyPaintTileRequestEndFunction),
        ('operation_queue', c_void_p),
        ('num_bboxes', c_int),
        ('num_bboxes_dirtied', c_int),
        ('bboxes', c_void_p),
        ('default_boxes', MyPaintRectangle * NUM_BBOXES_DEFAULT),
        ('threadsave_tile_requests', c_int),
        ('tile_size', c_int)
    ]


# noinspection PyTypeChecker
TilePixelBuffer = c_uint16 * 4 * TILE_DIM * TILE_DIM


# Brush settings:
class MyPaintBrushSettingInfo(Structure):
    """Struct used by libMyPaint to define a brush setting."""
    _fields_ = [
        ('cname', c_char_p),
        ('name', c_char_p),
        ('constant', c_int),
        ('min', c_float),
        ('def', c_float),
        ('max', c_float),
        ('tooltip', c_char_p)
    ]


def load_libmypaint(default_library_path: Optional[str]) -> CDLL:
    """Returns a libmypaint library instance with function types defined."""
    library_path: Optional[str] = ''
    try:
        library_path = find_library(LIBRARY_NAME)
        if library_path is None:
            library_path = default_library_path
        try:
            if os.name == 'nt':
                cdll.LoadLibrary(f'{PROJECT_DIR}/lib/libiconv-2.dll')
                cdll.LoadLibrary(f'{PROJECT_DIR}/lib/libintl-8.dll')
                cdll.LoadLibrary(f'{PROJECT_DIR}/lib/libjson-c-2.dll')
                lib = cdll.LoadLibrary(f'{PROJECT_DIR}/lib/libmypaint-1-4-0.dll')
            else:
                lib = CDLL(library_path)
        except OSError as err:
            alt_library_dir = AppConfig().get(AppConfig.LIBMYPAINT_LIBRARY_DIR)
            if not os.path.isdir(alt_library_dir):
                raise RuntimeError(f'libmypaint alternate library directory {alt_library_dir} does not exist') from err
            mypaint_lib_path = ''
            for lib_file in os.listdir(alt_library_dir):
                file_path = os.path.join(alt_library_dir, lib_file)
                if not os.path.isfile(file_path):
                    continue
                if 'mypaint' in lib_file.lower():
                    mypaint_lib_path = file_path
                else:
                    cdll.LoadLibrary(file_path)
            if mypaint_lib_path == '':
                raise RuntimeError(f'No mypaint library found: exactly one file in {alt_library_dir} should have a '
                                   'name that includes "mypaint" (e.g. libmypaint.dll, libmypaint.so, etc.)') from err
            lib = cdll.LoadLibrary(mypaint_lib_path)
    except (OSError, RuntimeError) as err:
        raise ImportError(f'Failed to find {LIBRARY_NAME} library: last path tried: {library_path}') from err
    assert lib is not None
    # Brush functions:
    lib.mypaint_brush_new.restype = c_void_p
    lib.mypaint_brush_new.argtypes = []
    lib.mypaint_brush_from_defaults.restype = None
    lib.mypaint_brush_from_defaults.argtypes = [c_void_p]
    lib.mypaint_brush_from_string.restype = int
    lib.mypaint_brush_from_string.argtypes = [c_void_p, c_char_p]
    lib.mypaint_brush_reset.restype = None
    lib.mypaint_brush_reset.argtypes = [c_void_p]  # (brush)
    lib.mypaint_brush_new_stroke.restype = None
    lib.mypaint_brush_new_stroke.argtypes = [c_void_p]  # (brush)
    lib.mypaint_brush_stroke_to.restype = c_int
    lib.mypaint_brush_stroke_to.argtypes = [c_void_p, surface_ptr,  # brush, surface,
                                            c_float, c_float,  # x, y
                                            c_float, c_float, c_float,  # pressure, x_tilt, y_tilt
                                            c_double, c_float, c_float,  # dtime, view_zoom, view_rotation
                                            c_float, c_int]  # barrel_rotation, is_linear
    lib.mypaint_brush_get_base_value.restype = c_float
    lib.mypaint_brush_get_base_value.argtypes = [c_void_p, c_int]  # (brush, setting ID)
    lib.mypaint_brush_set_base_value.restype = None
    lib.mypaint_brush_set_base_value.argtypes = [c_void_p, c_int, c_float]  # (brush, setting ID, value)

    # Brush settings:
    lib.mypaint_brush_setting_info.restype = POINTER(MyPaintBrushSettingInfo)
    lib.mypaint_brush_setting_info.argtypes = [c_int]
    lib.mypaint_brush_setting_info_get_name.restype = c_char_p
    lib.mypaint_brush_setting_info_get_name.argtypes = [POINTER(MyPaintBrushSettingInfo)]
    lib.mypaint_brush_setting_info_get_tooltip.restype = c_char_p
    lib.mypaint_brush_setting_info_get_tooltip.argtypes = [POINTER(MyPaintBrushSettingInfo)]
    lib.mypaint_brush_setting_from_cname.restype = c_int
    lib.mypaint_brush_setting_from_cname.argtypes = [c_char_p]

    # Surface functions:
    lib.mypaint_surface_begin_atomic.restype = None
    lib.mypaint_surface_begin_atomic.argtypes = [surface_ptr]
    lib.mypaint_surface_end_atomic.restype = None
    lib.mypaint_surface_end_atomic.argtypes = [surface_ptr, POINTER(MyPaintRectangles)]
    return lib


libmypaint = load_libmypaint(DEFAULT_LIBRARY_PATH)
