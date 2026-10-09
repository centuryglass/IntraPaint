# -*- mode: python ; coding: utf-8 -*-
import sys

sys.path.insert(0, SPECPATH)
from src.util.platform_tag import PLATFORM_TAG

# Only this platform's libmypaint. As binaries, PyInstaller also collects the libraries they link against.
LIBMYPAINT_DIR = f'lib/{PLATFORM_TAG}'

a = Analysis(
    ['IntraPaint.py'],
    pathex=[],
    binaries=[(f'{LIBMYPAINT_DIR}/*', LIBMYPAINT_DIR)],
    datas=[('resources', 'resources')],
    hiddenimports=['src.tools.mypaint_brush_tool', 'src.tools.fill_tool', 'src.tools.selection_fill_tool',
                   'sd_backend_client'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['Cython', 'setuptools', 'pyximport', 'PySide6.QtNetwork', 'PySide6.QtDBus', 'libKf6BreezeIcons.so.6',
              'cv2.ab13.so'],
    noarchive=False,
    optimize=1,
)
# Keeps libmypaint's json-c, which not every distro has at the version it needs.
a.exclude_system_libraries(list_of_exceptions=['libjson-c*'])
pyz = PYZ(a.pure)

splash = Splash(
    'resources/IntraPaint_banner.jpg',
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,
    text_size=12,
    minify_script=True,
    always_on_top=True,
)


exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    splash,
    splash.binaries,
    [],
    name='IntraPaint',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['resources/icons/app_icon.png'],
)