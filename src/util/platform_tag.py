"""Names the platform a native library build is for, as `<os>-<arch>` (e.g. `linux-x86_64`, `win-x86_64`).

`lib/<PLATFORM_TAG>/` holds the bundled libmypaint for each platform. The PyInstaller specs import this module
before any app code, so it imports nothing beyond the standard library.
"""
import platform
import sys

_OS_NAMES = {'win32': 'win', 'darwin': 'macos'}
_ARCH_NAMES = {'amd64': 'x86_64'}

_machine = platform.machine().lower()
PLATFORM_TAG = f'{_OS_NAMES.get(sys.platform, sys.platform)}-{_ARCH_NAMES.get(_machine, _machine)}'
