"""Finds the Stable Diffusion backends installed or running on this machine, by reading files and probing URLs.

`detect` gathers evidence only: it never launches, filters, ranks or explains anything. Every check reads files; no
interpreter or git command is run. Each scanner takes its root path and a platform name, so tests build Windows and
POSIX layouts on any machine.
"""
import json
import os
import re
import shlex
import stat
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, Sequence
from urllib.parse import urlsplit

from pydantic import ValidationError
from sd_backend_client import A1111Webservice, AuthError, Backend, ComfyUiWebservice, SDBackendError, \
    UnexpectedResponseError, connect_to_backend

from src.controller.image_generation.backend_install.detected_backend import DEFAULT_COMFYUI_URL, \
    DEFAULT_WEBUI_PORT, DEFAULT_WEBUI_URL, BackendKind, DetectedInstall, DetectedServer, DetectionResult, Finding, \
    FindingCode, InstallOwner

# Folders below each candidate root that are checked for installs. An install deeper than this isn't found.
MAX_SCAN_DEPTH = 3
# Levels of a models folder searched for model files: 1 is the folder itself, 2 adds its subfolders. Stability Matrix
# links its shared models one level down (`models/Stable-diffusion/sd`), so 3 leaves room for one more level there.
MODEL_SEARCH_DEPTH = 3
PROBE_TIMEOUT_SECONDS = 5.0

MODEL_EXTENSIONS = ('.safetensors', '.ckpt', '.gguf', '.sft')
SKIPPED_FOLDER_NAMES = frozenset(('node_modules', 'site-packages', 'venv', '.venv', '.git', 'AppData', '$Recycle.Bin',
                                  'System Volume Information'))
LOCAL_HOSTS = frozenset(('localhost', '127.0.0.1', '::1', '0.0.0.0'))

MIN_COMFYUI_PYTHON_VERSION = (3, 9)

PORTABLE_ENVIRONMENT = 'python_embeded'
PORTABLE_COMFYUI_FOLDER = 'ComfyUI'
PORTABLE_LAUNCH_FLAG = '--windows-standalone-build'
FORGE_MARKER_FOLDER = 'modules_forge'
WEBUI_VARIANT_FORGE = 'forge'
WEBUI_VARIANT_A1111 = 'a1111'

STABILITY_MATRIX_PORTABLE_MARKER = '.sm-portable'
KRITA_INCOMPLETE_VERSION = 'incomplete'
KRITA_MANAGED_MODES = ('managed', 'undefined', '')

COMFYUI_MODEL_FOLDERS = ('models/checkpoints', 'models/diffusion_models', 'models/unet')
# `extra_model_paths.yaml` keys whose folders hold models that satisfy the `NO_MODELS` check.
COMFYUI_EXTRA_MODEL_KEYS = ('checkpoints', 'diffusion_models', 'unet')
WEBUI_MODEL_FOLDER = 'models/Stable-diffusion'

# WebUI arguments whose values are credentials. `DetectedInstall.launch_args` holds `REDACTED_VALUE` in their place.
SECRET_ARGS = ('--gradio-auth', '--api-auth')
REDACTED_VALUE = '<redacted>'

COMFYUI_LAST_USED_PATHS = ('user', 'output', 'temp')
WEBUI_LAST_USED_PATHS = ('config.json', 'ui-config.json', 'params.txt', 'outputs')

_WINDOWS_DRIVE_FIXED = 3
_TESTED_PYTHON_PATTERN = re.compile(r'tested with (\d+)\.(\d+)')
_VERSION_PATTERN = re.compile(r'^__version__\s*=\s*[\'"]([^\'"]+)[\'"]', re.MULTILINE)
_DLL_VERSION_PATTERN = re.compile(r'^python3(\d+)\.(dll|_pth|zip)$', re.IGNORECASE)
_LIB_VERSION_PATTERN = re.compile(r'^python3\.(\d+)$')
_SH_ARGS_PATTERN = re.compile(r'^\s*(?:export\s+)?COMMANDLINE_ARGS=(.*)$')
_BAT_ARGS_PATTERN = re.compile(r'^\s*set\s+"?COMMANDLINE_ARGS=(.*?)"?\s*$', re.IGNORECASE)

ConnectFunction = Callable[[str], Backend]


def is_windows(platform: str) -> bool:
    """Whether a `sys.platform` value names Windows."""
    return platform == 'win32'


@dataclass
class SearchLocations:
    """Where `detect` looks for installs: candidate roots to walk, and other apps' data files.

    `krita_settings_files` is in priority order: the first one that exists is read.
    """
    candidate_roots: list[Path] = field(default_factory=list)
    stability_matrix_app_data: list[Path] = field(default_factory=list)
    krita_settings_files: list[Path] = field(default_factory=list)


def default_search_locations(home: Optional[Path] = None, platform: str = sys.platform,
                             env: Optional[Mapping[str, str]] = None) -> SearchLocations:
    """Return the standard places to look on this machine: home folders, drive roots and app data folders."""
    home = Path.home() if home is None else home
    env = os.environ if env is None else env
    roots = [home, home / 'Desktop', home / 'Documents', home / 'Downloads']
    if is_windows(platform):
        roots.extend(_fixed_drive_roots())
        app_data = Path(env.get('APPDATA', home / 'AppData' / 'Roaming'))
        generic_data = Path(env.get('LOCALAPPDATA', home / 'AppData' / 'Local'))
        sm_app_data = app_data / 'StabilityMatrix'
        krita_data = app_data / 'krita'
    elif platform == 'darwin':
        app_data = home / 'Library' / 'Application Support'
        generic_data = app_data
        sm_app_data = app_data / 'StabilityMatrix'
        krita_data = app_data / 'krita'
    else:
        config_home = Path(env.get('XDG_CONFIG_HOME') or home / '.config')
        generic_data = Path(env.get('XDG_DATA_HOME') or home / '.local' / 'share')
        sm_app_data = config_home / 'StabilityMatrix'
        krita_data = generic_data / 'krita'
        roots.append(Path('/opt'))  # Distribution packages, such as Stability Matrix's AUR package, install here.
    return SearchLocations(
        candidate_roots=roots,
        stability_matrix_app_data=[sm_app_data],
        krita_settings_files=[krita_data / 'ai_diffusion' / 'settings.json',
                              generic_data / 'krita-ai-diffusion' / 'settings.json'])


def _fixed_drive_roots() -> list[Path]:
    """Return the root of every fixed drive, or nothing when not running on Windows."""
    if sys.platform != 'win32':
        return []
    import ctypes  # pylint: disable=import-outside-toplevel
    kernel32 = ctypes.windll.kernel32
    drive_mask = kernel32.GetLogicalDrives()
    roots = []
    for index in range(26):
        if drive_mask & (1 << index):
            root = chr(ord('A') + index) + ':\\'
            if kernel32.GetDriveTypeW(root) == _WINDOWS_DRIVE_FIXED:
                roots.append(Path(root))
    return roots


def _default_connect(url: str) -> Backend:
    return connect_to_backend(url, request_timeout=PROBE_TIMEOUT_SECONDS)


def detect(locations: Optional[SearchLocations] = None,
           extra_roots: Sequence[Path] = (),
           extra_urls: Sequence[str] = (),
           managed_path: Optional[Path] = None,
           connect: ConnectFunction = _default_connect,
           platform: str = sys.platform) -> DetectionResult:
    """Find every backend install under `locations` and `extra_roots`, and every server answering at a probed URL.

    Blocks on disk reads and network probes, so run it off the main thread. `managed_path` is the install IntraPaint
    manages, if any. `connect` classifies a URL and raises as `connect_to_backend` does.
    """
    locations = default_search_locations(platform=platform) if locations is None else locations
    walked_installs, portable_libraries = scan_candidate_roots([*locations.candidate_roots, *extra_roots], platform)

    installs: list[DetectedInstall] = []
    if managed_path is not None:
        managed = inspect_managed_install(managed_path, platform)
        if managed is not None:
            installs.append(managed)
    libraries = [library for app_data in locations.stability_matrix_app_data
                 for library in stability_matrix_libraries(app_data)]
    for library in _unique_paths([*libraries, *portable_libraries]):
        installs.extend(scan_stability_matrix(library, platform))
    urls = [DEFAULT_COMFYUI_URL, DEFAULT_WEBUI_URL]
    krita_settings = next((path for path in locations.krita_settings_files if path.is_file()), None)
    if krita_settings is not None:
        krita_installs, krita_url = scan_krita(krita_settings, platform)
        installs.extend(krita_installs)
        if krita_url is not None:
            urls.append(krita_url)
    installs.extend(walked_installs)
    installs = _deduplicate(installs)

    urls.extend(f'http://localhost:{port}' for port in sorted({_install_port(install) for install in installs
                                                              if _install_port(install) is not None}))
    urls.extend(extra_urls)
    servers = [server for server in (probe_server(url, connect) for url in _unique_urls(urls)) if server is not None]
    return link_servers(installs, servers)


# Recognizing installs:


@dataclass
class _Recognized:
    kind: BackendKind
    path: Path
    entry_point: Path
    portable: bool = False


def _recognize(folder: Path) -> Optional[_Recognized]:
    """Return the install whose root is `folder`, or `None` if its files don't match a known backend layout."""
    try:
        if (folder / PORTABLE_ENVIRONMENT).is_dir() and (folder / PORTABLE_COMFYUI_FOLDER / 'main.py').is_file():
            return _Recognized(BackendKind.COMFYUI, folder, folder / PORTABLE_COMFYUI_FOLDER / 'main.py', True)
        if (folder / 'main.py').is_file() and (folder / 'nodes.py').is_file() and (folder / 'comfy').is_dir():
            if folder.name == PORTABLE_COMFYUI_FOLDER and (folder.parent / PORTABLE_ENVIRONMENT).is_dir():
                return _Recognized(BackendKind.COMFYUI, folder.parent, folder / 'main.py', True)
            return _Recognized(BackendKind.COMFYUI, folder, folder / 'main.py')
        if (folder / 'launch.py').is_file() and (folder / 'webui.py').is_file() and (folder / 'modules').is_dir():
            return _Recognized(BackendKind.WEBUI, folder, folder / 'launch.py')
    except OSError:
        return None
    return None


def _is_link(entry: os.DirEntry) -> bool:
    """Whether a directory entry is a symlink or a Windows junction, either of which can loop."""
    if entry.is_symlink():
        return True
    try:
        attributes = getattr(entry.stat(follow_symlinks=False), 'st_file_attributes', 0)
    except OSError:
        return True
    return bool(attributes & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0))


def scan_candidate_roots(roots: Iterable[Path], platform: str) -> tuple[list[DetectedInstall], list[Path]]:
    """Walk each root up to `MAX_SCAN_DEPTH` folders deep, returning the installs and portable Stability Matrix
    libraries found.

    Recognized installs, hidden folders, links and `SKIPPED_FOLDER_NAMES` aren't descended into, and unreadable folders
    are skipped.
    """
    installs: list[DetectedInstall] = []
    libraries: list[Path] = []
    visited: set[Path] = set()
    for root in roots:
        pending = [(root, 0)]
        while pending:
            folder, depth = pending.pop()
            try:
                resolved = folder.resolve()
            except OSError:
                continue
            if resolved in visited:
                continue
            visited.add(resolved)
            if (folder / 'Data' / STABILITY_MATRIX_PORTABLE_MARKER).is_file():
                libraries.append(folder / 'Data')
            recognized = _recognize(folder)
            if recognized is not None:
                installs.append(_inspect(recognized, InstallOwner.NONE, platform))
                continue
            if depth >= MAX_SCAN_DEPTH:
                continue
            try:
                with os.scandir(folder) as entries:
                    children = [Path(entry.path) for entry in entries
                                if entry.is_dir(follow_symlinks=False) and not _is_link(entry)
                                and not entry.name.startswith('.') and entry.name not in SKIPPED_FOLDER_NAMES]
            except OSError:
                continue
            pending.extend((child, depth + 1) for child in sorted(children, reverse=True))
    return installs, libraries


def inspect_managed_install(path: Path, platform: str) -> Optional[DetectedInstall]:
    """Return the install IntraPaint manages at `path`, as ComfyUI with `ENTRY_POINT_MISSING` if it isn't one.

    Returns `None` when `path` doesn't exist.
    """
    if not path.exists():
        return None
    recognized = _recognize(path)
    if recognized is None:
        return _missing_entry_point(BackendKind.COMFYUI, InstallOwner.INTRAPAINT, path)
    return _inspect(recognized, InstallOwner.INTRAPAINT, platform)


def _missing_entry_point(kind: BackendKind, owner: InstallOwner, path: Path) -> DetectedInstall:
    entry_point = path / ('main.py' if kind == BackendKind.COMFYUI else 'launch.py')
    return DetectedInstall(kind=kind, owner=owner, path=path, entry_point=entry_point,
                           findings=[Finding(FindingCode.ENTRY_POINT_MISSING, {'path': str(entry_point)})])


# Stability Matrix:


def stability_matrix_libraries(app_data: Path) -> list[Path]:
    """Return the library folder named by `library.json` in Stability Matrix's app data folder, if any."""
    data = _read_json(app_data / 'library.json')
    library = data.get('LibraryPath') if isinstance(data, dict) else None
    return [Path(library)] if isinstance(library, str) and library else []


def scan_stability_matrix(library: Path, platform: str) -> list[DetectedInstall]:
    """Return the ComfyUI and WebUI packages in a Stability Matrix library folder.

    Packages come from `settings.json`'s `InstalledPackages`, or from the folders in `Packages/` when it can't be
    read. A package's kind comes from its files; its `PackageName` is used only when the files are missing.
    """
    settings = _read_json(library / 'settings.json')
    entries = settings.get('InstalledPackages') if isinstance(settings, dict) else None
    installs = []
    if not isinstance(entries, list):
        try:
            folders = sorted(path for path in (library / 'Packages').iterdir() if path.is_dir())
        except OSError:
            return []
        for folder in folders:
            recognized = _recognize(folder)
            if recognized is not None:
                installs.append(_inspect(recognized, InstallOwner.STABILITY_MATRIX, platform))
        return installs
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('LibraryPath'), str):
            continue
        folder = library / entry['LibraryPath'].replace('\\', '/')
        recognized = _recognize(folder)
        if recognized is None:
            kind = _stability_matrix_package_kind(entry.get('PackageName'))
            if kind is not None:
                installs.append(_missing_entry_point(kind, InstallOwner.STABILITY_MATRIX, folder))
            continue
        launch_args = _stability_matrix_launch_args(entry.get('LaunchArgs'))
        installs.append(_inspect(recognized, InstallOwner.STABILITY_MATRIX, platform, launch_args))
    return installs


def _stability_matrix_package_kind(package_name: object) -> Optional[BackendKind]:
    if not isinstance(package_name, str):
        return None
    name = package_name.lower()
    if 'comfy' in name:
        return BackendKind.COMFYUI
    if 'forge' in name or 'stable-diffusion-webui' in name or 'automatic1111' in name:
        return BackendKind.WEBUI
    return None


def _stability_matrix_launch_args(launch_args: object) -> Optional[list[str]]:
    """Convert a package entry's `LaunchArgs` to command-line arguments, or `None` if the entry has none.

    Each option is an object with a `Name` and an `OptionValue`. A true value is a bare flag; a false or empty value
    leaves the option out. The extra arguments field has an empty `Name`, and its value is split like a command line.
    """
    if not isinstance(launch_args, list):
        return None
    args = []
    for option in launch_args:
        if not isinstance(option, dict) or not isinstance(option.get('Name'), str):
            continue
        name, value = option['Name'], option.get('OptionValue')
        if not name:
            if isinstance(value, str):
                try:
                    args.extend(shlex.split(value))
                except ValueError:
                    args.extend(value.split())
        elif value is True:
            args.append(name)
        elif value not in (None, False, ''):
            args.extend((name, str(value)))
    return args


# Krita AI Diffusion:


def scan_krita(settings_path: Path, platform: str) -> tuple[list[DetectedInstall], Optional[str]]:
    """Return the ComfyUI install Krita AI Diffusion manages, if its server folder exists, and its server URL.

    The server folder is `server_path`, or `server` beside `settings_path`, used only in managed mode.
    """
    settings = _read_json(settings_path)
    if not isinstance(settings, dict):
        return [], None
    url = settings.get('server_url')
    server_url = None
    if isinstance(url, str) and url:
        server_url = url if '://' in url else f'http://{url}'
    if str(settings.get('server_mode', '')).lower() not in KRITA_MANAGED_MODES:
        return [], server_url
    server_path_setting = settings.get('server_path')
    server_path = Path(server_path_setting) if isinstance(server_path_setting, str) and server_path_setting \
        else settings_path.parent / 'server'
    if not server_path.is_dir():
        return [], server_url
    comfyui_path = server_path / 'ComfyUI'
    recognized = _recognize(comfyui_path)
    if recognized is None:
        install = _missing_entry_point(BackendKind.COMFYUI, InstallOwner.KRITA_AI_DIFFUSION, comfyui_path)
    else:
        install = _inspect(recognized, InstallOwner.KRITA_AI_DIFFUSION, platform,
                           owner_environments=[server_path / 'venv', server_path / 'python'])
    version = _read_text(server_path / '.version')
    if version is not None and version.strip() == KRITA_INCOMPLETE_VERSION:
        install.findings.append(Finding(FindingCode.INSTALL_INCOMPLETE, {'path': str(server_path / '.version')}))
    return [install], server_url


# Inspecting an install:


def _inspect(recognized: _Recognized, owner: InstallOwner, platform: str,
             launch_args: Optional[list[str]] = None,
             owner_environments: Sequence[Path] = ()) -> DetectedInstall:
    """Build a `DetectedInstall` from a recognized folder, with findings from its environment, models and settings.

    `launch_args` are the owner's recorded WebUI arguments; `None` reads them from `webui-user`. `owner_environments`
    are checked for an interpreter after the install's own.
    """
    backend_dir = recognized.entry_point.parent
    install = DetectedInstall(kind=recognized.kind, owner=owner, path=recognized.path,
                              entry_point=recognized.entry_point, git_commit=read_git_commit(backend_dir))
    environments = [recognized.path / PORTABLE_ENVIRONMENT] if recognized.portable else []
    environments.extend((recognized.path / 'venv', recognized.path / '.venv', *owner_environments))
    tested_python = _webui_tested_python(backend_dir) if recognized.kind == BackendKind.WEBUI else None
    install.interpreter = _inspect_environment(install, environments, platform, tested_python)

    if recognized.kind == BackendKind.COMFYUI:
        install.version = _read_comfyui_version(backend_dir)
        install.last_used = _last_used(backend_dir, COMFYUI_LAST_USED_PATHS)
        model_folders = _comfyui_model_folders(backend_dir)
        if owner == InstallOwner.NONE and install.interpreter is not None:
            install.launch_command = [str(install.interpreter), str(install.entry_point)]
            if recognized.portable:
                install.launch_command.append(PORTABLE_LAUNCH_FLAG)
    else:
        install.webui_variant = WEBUI_VARIANT_FORGE if (backend_dir / FORGE_MARKER_FOLDER).is_dir() \
            else WEBUI_VARIANT_A1111
        install.last_used = _last_used(backend_dir, WEBUI_LAST_USED_PATHS)
        args = read_webui_user_args(backend_dir, platform) if launch_args is None else launch_args
        args = None if args is None else redact_secret_args(args)
        install.launch_args = args
        _webui_launch_arg_findings(install, args)
        model_folders = [backend_dir / WEBUI_MODEL_FOLDER]
        ckpt_dir = _arg_value(args or [], '--ckpt-dir')
        if ckpt_dir is not None:
            model_folders.append(backend_dir / ckpt_dir)
    if model_folders is not None and not any(_has_model_file(folder, MODEL_SEARCH_DEPTH) for folder in model_folders):
        install.findings.append(Finding(FindingCode.NO_MODELS,
                                        {'searched': os.pathsep.join(str(folder) for folder in model_folders)}))
    return install


def _inspect_environment(install: DetectedInstall, environments: Sequence[Path], platform: str,
                         tested_python: Optional[tuple[int, int]] = None) -> Optional[Path]:
    """Return the interpreter in the first environment folder that exists, adding findings about that environment.

    `tested_python` is the version a WebUI install says it is tested with. A WebUI environment on another version gets
    `PYTHON_VERSION_MISMATCH`; with no tested version, its Python version isn't checked.
    """
    environment = next((folder for folder in environments if folder.is_dir()), None)
    if environment is None:
        install.findings.append(Finding(FindingCode.INTERPRETER_UNKNOWN))
        return None
    candidates = ('Scripts/python.exe', 'python.exe') if is_windows(platform) else ('bin/python3', 'bin/python')
    interpreter = next((environment / name for name in candidates if (environment / name).is_file()), None)
    if interpreter is None:
        install.findings.append(Finding(FindingCode.INTERPRETER_MISSING, {'environment': str(environment)}))
        return None

    config = _read_pyvenv_cfg(environment / 'pyvenv.cfg')
    home = config.get('home')
    if home and not Path(home).exists():
        install.findings.append(Finding(FindingCode.BASE_PYTHON_MISSING, {'home': home}))
    version = _python_version(environment, config)
    if version is not None:
        if install.kind == BackendKind.WEBUI:
            mismatch = tested_python is not None and version != tested_python
            expected = '.'.join(str(part) for part in tested_python or ())
        else:
            mismatch = version < MIN_COMFYUI_PYTHON_VERSION
            expected = '>=' + '.'.join(str(part) for part in MIN_COMFYUI_PYTHON_VERSION)
        if mismatch:
            install.findings.append(Finding(FindingCode.PYTHON_VERSION_MISMATCH,
                                            {'version': f'{version[0]}.{version[1]}', 'expected': expected}))

    site_packages = _site_packages(environment, version)
    torch_version = None if site_packages is None else _torch_version(site_packages)
    if torch_version is None:
        install.findings.append(Finding(FindingCode.TORCH_MISSING,
                                        {'environment': str(site_packages or environment)}))
    elif '+cpu' in torch_version:
        install.findings.append(Finding(FindingCode.CPU_ONLY_TORCH, {'torch_version': torch_version}))
    return interpreter


def _read_pyvenv_cfg(path: Path) -> dict[str, str]:
    text = _read_text(path)
    values = {}
    for line in (text or '').splitlines():
        key, separator, value = line.partition('=')
        if separator:
            values[key.strip().lower()] = value.strip()
    return values


def _python_version(environment: Path, config: Mapping[str, str]) -> Optional[tuple[int, int]]:
    """Return an environment's Python version from `pyvenv.cfg`, the embedded build's files, or its `lib/` folder."""
    for key in ('version', 'version_info'):
        match = re.match(r'(\d+)\.(\d+)', config.get(key, ''))
        if match:
            return int(match.group(1)), int(match.group(2))
    for folder, pattern in ((environment, _DLL_VERSION_PATTERN), (environment / 'lib', _LIB_VERSION_PATTERN)):
        try:
            names = sorted(path.name for path in folder.iterdir())
        except OSError:
            continue
        for name in names:
            match = pattern.match(name)
            if match:
                return 3, int(match.group(1))
    return None


def _site_packages(environment: Path, version: Optional[tuple[int, int]]) -> Optional[Path]:
    """Return the environment's `site-packages` folder.

    A POSIX environment can hold folders for several Python versions, left behind when it was upgraded. The one for
    `version` is used when it exists; otherwise the first one holding torch, else the first one.
    """
    windows_layout = environment / 'Lib' / 'site-packages'
    if windows_layout.is_dir():
        return windows_layout
    if version is not None:
        matching = environment / 'lib' / f'python{version[0]}.{version[1]}' / 'site-packages'
        if matching.is_dir():
            return matching
    candidates = [path for path in sorted(environment.glob('lib/python3*/site-packages')) if path.is_dir()]
    return next((path for path in candidates if _torch_version(path) is not None), next(iter(candidates), None))


def _webui_tested_python(webui_dir: Path) -> Optional[tuple[int, int]]:
    """Return the Python version a WebUI's own version warning says it is tested with, if it has one.

    A1111, Forge, reForge and Forge Neo each check the version differently, but all warn with the same sentence.
    """
    match = _TESTED_PYTHON_PATTERN.search(_read_text(webui_dir / 'modules' / 'launch_utils.py') or '')
    return (int(match.group(1)), int(match.group(2))) if match else None


def _torch_version(site_packages: Path) -> Optional[str]:
    """Return the version in torch's `dist-info` folder name, or `None` if torch isn't installed."""
    for path in site_packages.glob('torch-*.dist-info'):
        return path.name[len('torch-'):-len('.dist-info')]
    return None


def _has_model_file(folder: Path, depth: int, visited: Optional[set[Path]] = None) -> bool:
    """Whether `folder`, or a folder up to `depth - 1` levels below it, holds a model file.

    Links are followed, since model managers such as Stability Matrix link shared model folders into each install.
    Each real folder is read once, so a link loop ends.
    """
    visited = set() if visited is None else visited
    resolved = _resolve(folder)
    if resolved in visited:
        return False
    visited.add(resolved)
    try:
        with os.scandir(folder) as entries:
            subfolders = []
            for entry in entries:
                if entry.is_file() and entry.name.lower().endswith(MODEL_EXTENSIONS):
                    return True
                if entry.is_dir():
                    subfolders.append(Path(entry.path))
    except OSError:
        return False
    return depth > 1 and any(_has_model_file(subfolder, depth - 1, visited) for subfolder in subfolders)


def _comfyui_model_folders(backend_dir: Path) -> Optional[list[Path]]:
    """Return the folders that may hold ComfyUI's checkpoints, or `None` if `extra_model_paths.yaml` can't be read."""
    folders = [backend_dir / folder for folder in COMFYUI_MODEL_FOLDERS]
    yaml_path = backend_dir / 'extra_model_paths.yaml'
    if not yaml_path.exists():
        return folders
    text = _read_text(yaml_path)
    extra = None if text is None else parse_extra_model_paths(text, backend_dir)
    return None if extra is None else folders + extra


def parse_extra_model_paths(text: str, base_dir: Path) -> Optional[list[Path]]:
    """Return the model folders that ComfyUI's `extra_model_paths.yaml` names, or `None` if it isn't in the expected
    shape.

    Reads only the block-style mappings ComfyUI's example file uses: top-level sections holding `base_path` and folder
    keys, whose value is a path or a `|` block of paths. Only `COMFYUI_EXTRA_MODEL_KEYS` are returned. Relative paths
    resolve against `base_path`, which resolves against `base_dir`.
    """
    sections: list[dict[str, list[str]]] = []
    block_key: Optional[str] = None
    block_indent = 0
    for raw_line in text.splitlines():
        line = re.sub(r'(^|\s)#.*$', '', raw_line).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if block_key is not None and indent > block_indent:
            sections[-1][block_key].append(line.strip())
            continue
        block_key = None
        if '\t' in line[:indent] or line.lstrip()[0] in '{[-':
            return None
        key, separator, value = line.strip().partition(':')
        if not separator:
            return None
        if indent == 0:
            if value.strip():
                return None
            sections.append({})
            continue
        if not sections:
            return None
        value = value.strip().strip('\'"')
        if value in ('|', '|-', '>'):
            block_key, block_indent = key.strip(), indent
            sections[-1][block_key] = []
        else:
            sections[-1][key.strip()] = [value]
    folders = []
    for section in sections:
        base_values = section.get('base_path', [])
        base = base_dir / os.path.expanduser(base_values[0]) if base_values else base_dir
        for key in COMFYUI_EXTRA_MODEL_KEYS:
            folders.extend(base / os.path.expanduser(value) for value in section.get(key, []) if value)
    return folders


def read_webui_user_args(webui_dir: Path, platform: str) -> Optional[list[str]]:
    """Return `COMMANDLINE_ARGS` from `webui-user.bat` or `webui-user.sh`, or `None` if neither sets it.

    The platform's own file is read first. The last uncommented assignment wins, as it does when the script runs.
    """
    files = [('webui-user.bat', _BAT_ARGS_PATTERN, False), ('webui-user.sh', _SH_ARGS_PATTERN, True)]
    if not is_windows(platform):
        files.reverse()
    for name, pattern, posix in files:
        text = _read_text(webui_dir / name)
        if text is None:
            continue
        values = [match.group(1) for match in map(pattern.match, text.splitlines()) if match]
        if not values:
            continue
        value = values[-1].strip()
        if posix:
            try:
                return [arg for part in shlex.split(value, comments=True) for arg in shlex.split(part)]
            except ValueError:
                return None
        return [arg.strip('"') for arg in value.split()]
    return None


def _webui_launch_arg_findings(install: DetectedInstall, args: Optional[list[str]]) -> None:
    if args is None:
        install.findings.append(Finding(FindingCode.API_FLAG_UNKNOWN))
    elif '--api' not in args:
        install.findings.append(Finding(FindingCode.API_DISABLED, {'arguments': ' '.join(args)}))


def _arg_value(args: Sequence[str], name: str) -> Optional[str]:
    """Return the value of `name` in `args`, given as `name value` or `name=value`."""
    for index, arg in enumerate(args):
        if arg == name and index + 1 < len(args):
            return args[index + 1]
        if arg.startswith(f'{name}='):
            return arg[len(name) + 1:]
    return None


def redact_secret_args(args: Sequence[str]) -> list[str]:
    """Return `args` with the value of each `SECRET_ARGS` option replaced by `REDACTED_VALUE`."""
    redacted = list(args)
    for index, arg in enumerate(redacted):
        name, separator, _ = arg.partition('=')
        if name not in SECRET_ARGS:
            continue
        if separator:
            redacted[index] = f'{name}={REDACTED_VALUE}'
        elif index + 1 < len(redacted):
            redacted[index + 1] = REDACTED_VALUE
    return redacted


def _install_port(install: DetectedInstall) -> Optional[int]:
    """Return the `--port` in a WebUI install's launch arguments, if any."""
    port = _arg_value(install.launch_args or [], '--port')
    return int(port) if port is not None and port.isdigit() else None


def _read_comfyui_version(backend_dir: Path) -> Optional[str]:
    match = _VERSION_PATTERN.search(_read_text(backend_dir / 'comfyui_version.py') or '')
    return match.group(1) if match else None


def read_git_commit(repo_dir: Path) -> Optional[str]:
    """Return the commit a checkout's `HEAD` points to, read from `.git` files, or `None` if it can't be read."""
    git_dir = repo_dir / '.git'
    if git_dir.is_file():
        gitdir_line = (_read_text(git_dir) or '').strip()
        if not gitdir_line.startswith('gitdir:'):
            return None
        git_dir = repo_dir / gitdir_line[len('gitdir:'):].strip()
    head = (_read_text(git_dir / 'HEAD') or '').strip()
    if not head.startswith('ref:'):
        return head or None
    ref = head[len('ref:'):].strip()
    ref_dirs = [git_dir]
    common_dir = (_read_text(git_dir / 'commondir') or '').strip()
    if common_dir:
        ref_dirs.append(git_dir / common_dir)
    for ref_dir in ref_dirs:
        commit = (_read_text(ref_dir / ref) or '').strip()
        if commit:
            return commit
        for line in (_read_text(ref_dir / 'packed-refs') or '').splitlines():
            sha, _, name = line.partition(' ')
            if name.strip() == ref:
                return sha
    return None


def _last_used(backend_dir: Path, names: Sequence[str]) -> Optional[datetime]:
    """Return the newest modification time among `names` in `backend_dir` and their direct children."""
    newest: Optional[float] = None
    for name in names:
        path = backend_dir / name
        paths = [path]
        if path.is_dir():
            try:
                paths.extend(path.iterdir())
            except OSError:
                pass
        for item in paths:
            try:
                modified = item.stat().st_mtime
            except OSError:
                continue
            newest = modified if newest is None else max(newest, modified)
    return None if newest is None else datetime.fromtimestamp(newest, tz=timezone.utc)


# Running servers:


def probe_server(url: str, connect: ConnectFunction) -> Optional[DetectedServer]:
    """Classify the server at `url`, or return `None` if nothing answers there."""
    try:
        backend = connect(url)
    except UnexpectedResponseError:
        return DetectedServer(url=url, kind=None, findings=[Finding(FindingCode.API_DISABLED, {'url': url})])
    except AuthError:
        return DetectedServer(url=url, kind=None, findings=[Finding(FindingCode.AUTH_REQUIRED, {'url': url})])
    except SDBackendError:
        return None
    try:
        if isinstance(backend, ComfyUiWebservice):
            server = DetectedServer(url=url, kind=BackendKind.COMFYUI)
            try:
                system = backend.get_system_stats().system
            except (SDBackendError, ValidationError, ValueError):
                return server
            server.version = system.comfyui_version
            server.argv = list(system.argv)
            main_py = _argv_main_py(server.argv)
            if main_py is not None and main_py.is_absolute():
                server.install_path = main_py.parent
            return server
        kind = BackendKind.WEBUI if isinstance(backend, A1111Webservice) else None
        return DetectedServer(url=url, kind=kind)
    finally:
        disconnect = getattr(backend, 'disconnect', None)
        if callable(disconnect):
            disconnect()


def link_servers(installs: list[DetectedInstall], servers: list[DetectedServer]) -> DetectionResult:
    """Attach each server to the install it runs from, where that is unambiguous, and return the result.

    A ComfyUI server links to the install holding the `main.py` in its `argv`. A relative path, such as `main.py`
    when ComfyUI was started from its own folder, matches every install whose entry point ends with it; if several
    match, it links to the one whose version is the server's, if exactly one is. A local WebUI server links when
    exactly one WebUI install uses its port.
    """
    result = DetectionResult(installs=installs)
    for server in servers:
        if server.kind == BackendKind.COMFYUI:
            candidates = _comfyui_candidates(installs, _argv_main_py(server.argv))
        elif server.kind == BackendKind.WEBUI:
            candidates = _webui_candidates(installs, server.url)
        else:
            candidates = []
        candidates = [install for install in candidates if install.server is None]
        if len(candidates) > 1 and server.kind == BackendKind.COMFYUI and server.version is not None:
            candidates = [install for install in candidates if install.version == server.version]
        if len(candidates) == 1:
            candidates[0].server = server
        else:
            result.servers.append(server)
    return result


def _argv_main_py(argv: Sequence[str]) -> Optional[Path]:
    return next((Path(arg) for arg in argv if arg.endswith('main.py')), None)


def _comfyui_candidates(installs: Sequence[DetectedInstall], main_py: Optional[Path]) -> list[DetectedInstall]:
    if main_py is None:
        return []
    comfyui_installs = [install for install in installs if install.kind == BackendKind.COMFYUI]
    if main_py.is_absolute():
        resolved = _resolve(main_py)
        return [install for install in comfyui_installs if resolved.is_relative_to(_resolve(install.path))]
    return [install for install in comfyui_installs if install.entry_point.parts[-len(main_py.parts):]
            == main_py.parts]


def _webui_candidates(installs: Sequence[DetectedInstall], url: str) -> list[DetectedInstall]:
    parts = urlsplit(url)
    if parts.hostname not in LOCAL_HOSTS:
        return []
    port = parts.port or (443 if parts.scheme == 'https' else 80)
    return [install for install in installs if install.kind == BackendKind.WEBUI
            and (_install_port(install) or DEFAULT_WEBUI_PORT) == port]


# Helpers:


def _deduplicate(installs: Iterable[DetectedInstall]) -> list[DetectedInstall]:
    """Drop installs whose path an earlier one already has. Owned installs come first, so they keep their owner."""
    unique: dict[Path, DetectedInstall] = {}
    for install in installs:
        unique.setdefault(_resolve(install.path), install)
    return list(unique.values())


def _unique_paths(paths: Iterable[Path]) -> list[Path]:
    unique: dict[Path, Path] = {}
    for path in paths:
        unique.setdefault(_resolve(path), path)
    return list(unique.values())


def _unique_urls(urls: Iterable[str]) -> list[str]:
    """Drop URLs that name the same server as an earlier one, treating every local host name as the same host."""
    unique: dict[tuple[str, str, Optional[int]], str] = {}
    for url in urls:
        url = url.rstrip('/')
        parts = urlsplit(url)
        host = 'localhost' if parts.hostname in LOCAL_HOSTS else (parts.hostname or '')
        try:
            port = parts.port
        except ValueError:
            continue
        unique.setdefault((parts.scheme, host, port), url)
    return list(unique.values())


def _resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None


def _read_json(path: Path) -> object:
    text = _read_text(path)
    if text is None:
        return None
    try:
        return json.loads(text.lstrip('﻿'))
    except ValueError:
        return None
