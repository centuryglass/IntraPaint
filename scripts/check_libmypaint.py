"""Checks that a lib/<platform tag>/ directory holds a loadable libmypaint with the pinned version's brush settings.

Usage: python scripts/check_libmypaint.py <library dir>

Loads the directory the way `_load_from_dir` in `src/image/mypaint/libmypaint.py` does: every other file first, as
the library's dependencies, then the one file whose name contains "mypaint". Exits non-zero unless that library knows
EXPECTED_SETTING_COUNT brush settings. Standard library only, so it runs before IntraPaint's requirements install.
"""
import ctypes
import os
import sys

# MYPAINT_BRUSH_SETTINGS_COUNT in libmypaint 1.6.1, the version scripts/build_libmypaint.sh and
# .github/workflows/native-libs.yml pin. LAST_SETTING is the setting with the highest id.
EXPECTED_SETTING_COUNT = 64
LAST_SETTING = 'paint_mode'


def main() -> int:
    """Loads the library in sys.argv[1] and prints its setting count, returning 1 if it isn't the expected one."""
    library_dir = os.path.abspath(sys.argv[1])
    if os.name == 'nt':
        os.add_dll_directory(library_dir)
    names = sorted(name for name in os.listdir(library_dir) if os.path.splitext(name)[1] in ('.so', '.dll', '.dylib'))
    mypaint_names = [name for name in names if 'mypaint' in name.lower()]
    if len(mypaint_names) != 1:
        print(f'Expected one libmypaint in {library_dir}, found {mypaint_names}', file=sys.stderr)
        return 1
    for name in names:
        if name not in mypaint_names:
            ctypes.CDLL(os.path.join(library_dir, name))
    lib = ctypes.CDLL(os.path.join(library_dir, mypaint_names[0]))
    lib.mypaint_brush_setting_from_cname.argtypes = [ctypes.c_char_p]
    lib.mypaint_brush_setting_from_cname.restype = ctypes.c_int
    # Unknown names return -1.
    setting_count = 1 + lib.mypaint_brush_setting_from_cname(LAST_SETTING.encode())
    print(f'{mypaint_names[0]}: {setting_count} brush settings')
    if setting_count != EXPECTED_SETTING_COUNT:
        print(f'Expected {EXPECTED_SETTING_COUNT} brush settings', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
