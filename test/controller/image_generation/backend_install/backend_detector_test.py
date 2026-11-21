"""Tests backend detection over fixture install layouts built in a temporary folder, with no network access."""
import json
import os
import tempfile
from pathlib import Path
from typing import Optional
from unittest import mock

from sd_backend_client import A1111Webservice, AuthError, Backend, BackendConnectionError, ComfyUiWebservice, \
    UnexpectedResponseError

from src.controller.image_generation.backend_install.backend_detector import SearchLocations, \
    default_search_locations, detect, parse_extra_model_paths
from src.controller.image_generation.backend_install.detected_backend import DEFAULT_COMFYUI_URL, \
    DEFAULT_WEBUI_URL, BackendKind, DetectedInstall, DetectionResult, FindingCode, FindingSeverity, InstallOwner
from test.base_test_case import IntraPaintTestCase

POSIX = 'linux'
WINDOWS = 'win32'
CUDA_TORCH = '2.3.1+cu121'


def _write(path: Path, text: str = '') -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def _make_environment(env_dir: Path, layout: str, python: str = '3.10', torch: Optional[str] = CUDA_TORCH,
                      base_python: Optional[Path] = None, pyvenv: bool = True) -> None:
    """Build a Python environment: `layout` is 'posix' or 'windows' for a venv, 'embedded' for an embedded build."""
    major, minor = python.split('.')
    if layout == 'posix':
        _write(env_dir / 'bin' / 'python3')
        site_packages = env_dir / 'lib' / f'python{python}' / 'site-packages'
    else:
        _write(env_dir / ('python.exe' if layout == 'embedded' else 'Scripts/python.exe'))
        site_packages = env_dir / 'Lib' / 'site-packages'
    site_packages.mkdir(parents=True)
    if layout == 'embedded':
        _write(env_dir / f'python{major}{minor}.dll')
    elif pyvenv:
        home = base_python if base_python is not None else env_dir.parent
        _write(env_dir / 'pyvenv.cfg', f'home = {home}\nversion = {python}.4\n')
    if torch is not None:
        (site_packages / f'torch-{torch}.dist-info').mkdir()


def _make_comfyui(folder: Path, models: bool = True, version: str = '0.3.10') -> Path:
    _write(folder / 'main.py')
    _write(folder / 'nodes.py')
    (folder / 'comfy').mkdir()
    _write(folder / 'comfyui_version.py', f'__version__ = "{version}"\n')
    if models:
        _write(folder / 'models' / 'checkpoints' / 'sd15' / 'model.safetensors')
    return folder


def _make_webui(folder: Path, forge: bool = False, models: bool = True, args: Optional[str] = '--api',
                tested_python: Optional[str] = '3.10.6') -> Path:
    _write(folder / 'launch.py')
    _write(folder / 'webui.py')
    (folder / 'modules').mkdir()
    if tested_python is not None:
        _write(folder / 'modules' / 'launch_utils.py',
               f'print(f"This program is tested with {tested_python} Python, but you have {{major}}.{{minor}}.")\n')
    if forge:
        (folder / 'modules_forge').mkdir()
    if models:
        _write(folder / 'models' / 'Stable-diffusion' / 'model.ckpt')
    if args is not None:
        _write(folder / 'webui-user.sh', f'#!/bin/bash\n#export COMMANDLINE_ARGS=""\nexport COMMANDLINE_ARGS="{args}"\n')
    return folder


def _make_portable(folder: Path) -> Path:
    _make_comfyui(folder / 'ComfyUI')
    _make_environment(folder / 'python_embeded', 'embedded', python='3.12')
    return folder


def _comfyui_backend(argv: list[str], version: str = '0.3.10') -> Backend:
    backend = mock.MagicMock(spec=ComfyUiWebservice)
    backend.get_system_stats.return_value.system.comfyui_version = version
    backend.get_system_stats.return_value.system.argv = argv
    return backend


def _no_servers(url: str) -> Backend:
    raise BackendConnectionError(f'nothing at {url}')


def _servers(answers: dict[str, object]):
    """Return a `connect` that answers each URL in `answers` with its backend, or raises its exception."""
    def connect(url: str) -> Backend:
        answer = answers.get(url)
        if answer is None:
            raise BackendConnectionError(f'nothing at {url}')
        if isinstance(answer, Exception):
            raise answer
        return answer  # type: ignore[return-value]
    return connect


class BackendDetectorTest(IntraPaintTestCase):
    """Tests backend detection over fixture install layouts built in a temporary folder, with no network access."""

    def setUp(self) -> None:
        super().setUp()
        temp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(temp_dir.cleanup)
        self.root = Path(temp_dir.name).resolve()

    def _detect(self, roots: Optional[list[Path]] = None, platform: str = POSIX, connect=_no_servers,
                sm_app_data: Optional[Path] = None, krita_settings: Optional[Path] = None,
                desktop_settings: Optional[Path] = None, **kwargs) -> DetectionResult:
        locations = SearchLocations(candidate_roots=[self.root] if roots is None else roots,
                                    stability_matrix_app_data=[] if sm_app_data is None else [sm_app_data],
                                    krita_settings_files=[] if krita_settings is None else [krita_settings],
                                    comfy_desktop_settings_files=[] if desktop_settings is None
                                    else [desktop_settings])
        return detect(locations, connect=connect, platform=platform, **kwargs)

    def _only_install(self, result: DetectionResult) -> DetectedInstall:
        self.assertEqual(len(result.installs), 1, result.installs)
        return result.installs[0]

    def _codes(self, install: DetectedInstall) -> set[FindingCode]:
        return {finding.code for finding in install.findings}

    # Stability Matrix:

    def _make_stability_matrix_library(self, library: Path, settings: bool = True) -> None:
        comfyui = _make_comfyui(library / 'Packages' / 'ComfyUI')
        _make_environment(comfyui / 'venv', 'posix', python='3.11')
        forge = _make_webui(library / 'Packages' / 'stable-diffusion-webui-forge', forge=True, args=None)
        _make_environment(forge / 'venv', 'posix')
        if settings:
            _write(library / 'settings.json', json.dumps({'InstalledPackages': [
                {'PackageName': 'ComfyUI', 'LibraryPath': 'Packages\\ComfyUI', 'LaunchArgs': []},
                {'PackageName': 'stable-diffusion-webui-forge', 'LibraryPath': 'Packages\\stable-diffusion-webui-forge',
                 'LaunchArgs': [{'Name': '--port', 'Type': 'String', 'OptionValue': '7861'},
                                {'Name': '--xformers', 'Type': 'Bool', 'OptionValue': False},
                                {'Name': '', 'Type': 'String',
                                 'OptionValue': "--api --api-auth user:secret --ckpt-dir '/my models'"}]}]}))

    def test_stability_matrix_library_json(self) -> None:
        """`library.json` in the app data folder points at a library elsewhere, whose packages are reported."""
        library = self.root / 'elsewhere' / 'SMLibrary'
        self._make_stability_matrix_library(library)
        app_data = self.root / 'appdata' / 'StabilityMatrix'
        _write(app_data / 'library.json', json.dumps({'LibraryPath': str(library)}))
        result = self._detect(roots=[], sm_app_data=app_data)
        self.assertEqual(len(result.installs), 2)
        comfyui, forge = result.installs
        self.assertEqual((comfyui.kind, comfyui.owner), (BackendKind.COMFYUI, InstallOwner.STABILITY_MATRIX))
        self.assertEqual(comfyui.interpreter, library / 'Packages' / 'ComfyUI' / 'venv' / 'bin' / 'python3')
        self.assertIsNone(comfyui.launch_command)
        self.assertEqual(comfyui.version, '0.3.10')
        self.assertEqual(comfyui.findings, [])
        self.assertEqual((forge.kind, forge.webui_variant), (BackendKind.WEBUI, 'forge'))
        self.assertEqual(forge.launch_args, ['--port', '7861', '--api', '--api-auth', '<redacted>', '--ckpt-dir',
                                             '/my models'])
        self.assertEqual(forge.findings, [])

    def test_stability_matrix_portable(self) -> None:
        """A portable Stability Matrix's `Data/` library is found through the candidate roots."""
        library = self.root / 'StabilityMatrix' / 'Data'
        _write(library / '.sm-portable')
        self._make_stability_matrix_library(library)
        result = self._detect()
        self.assertEqual([install.owner for install in result.installs], [InstallOwner.STABILITY_MATRIX] * 2)

    def test_stability_matrix_without_settings(self) -> None:
        """With no `settings.json`, the packages in `Packages/` are scanned, and WebUI arguments are unknown."""
        library = self.root / 'SMLibrary'
        self._make_stability_matrix_library(library, settings=False)
        app_data = self.root / 'StabilityMatrix'
        _write(app_data / 'library.json', json.dumps({'LibraryPath': str(library)}))
        result = self._detect(roots=[], sm_app_data=app_data)
        self.assertEqual([install.kind for install in result.installs], [BackendKind.COMFYUI, BackendKind.WEBUI])
        self.assertIn(FindingCode.API_FLAG_UNKNOWN, self._codes(result.installs[1]))

    def test_stability_matrix_entry_point_missing(self) -> None:
        """A package entry whose folder lacks `main.py` is reported, with its kind from `PackageName`."""
        library = self.root / 'SMLibrary'
        (library / 'Packages' / 'ComfyUI').mkdir(parents=True)
        _write(library / 'settings.json', json.dumps({'InstalledPackages': [
            {'PackageName': 'ComfyUI', 'LibraryPath': 'Packages/ComfyUI'},
            {'PackageName': 'InvokeAI', 'LibraryPath': 'Packages/InvokeAI'}]}))
        app_data = self.root / 'StabilityMatrix'
        _write(app_data / 'library.json', json.dumps({'LibraryPath': str(library)}))
        install = self._only_install(self._detect(roots=[], sm_app_data=app_data))
        self.assertEqual(install.kind, BackendKind.COMFYUI)
        self.assertEqual(self._codes(install), {FindingCode.ENTRY_POINT_MISSING})
        self.assertEqual(install.findings[0].severity, FindingSeverity.BLOCKER)

    # Krita AI Diffusion:

    def _make_krita(self, server_mode: Optional[str] = 'managed', version: str = '1.20.0',
                    legacy: bool = False) -> Path:
        data_dir = self.root / 'krita' / 'ai_diffusion'
        server = data_dir / 'server'
        _make_comfyui(server / 'ComfyUI')
        if legacy:
            _make_environment(server / 'python', 'posix', python='3.11', pyvenv=False)
        else:
            _make_environment(server / 'venv', 'posix', python='3.12')
        _write(server / '.version', version)
        settings = {'server_url': '127.0.0.1:8189'}
        if server_mode is not None:
            settings['server_mode'] = server_mode
        return _write(data_dir / 'settings.json', json.dumps(settings))

    def test_krita_managed(self) -> None:
        """Krita's managed server is reported as an owned install, and its URL is probed."""
        probed = []

        def connect(url: str) -> Backend:
            probed.append(url)
            raise BackendConnectionError(url)
        install = self._only_install(self._detect(roots=[], krita_settings=self._make_krita(), connect=connect))
        self.assertEqual((install.kind, install.owner), (BackendKind.COMFYUI, InstallOwner.KRITA_AI_DIFFUSION))
        self.assertEqual(install.interpreter, self.root / 'krita' / 'ai_diffusion' / 'server' / 'venv' / 'bin' /
                         'python3')
        self.assertEqual(install.findings, [])
        self.assertIsNone(install.launch_command)
        self.assertIn('http://127.0.0.1:8189', probed)

    def test_krita_incomplete(self) -> None:
        """A `.version` file reading `incomplete` is a blocker."""
        install = self._only_install(self._detect(roots=[], krita_settings=self._make_krita(version='incomplete')))
        self.assertEqual(self._codes(install), {FindingCode.INSTALL_INCOMPLETE})

    def test_krita_legacy_python(self) -> None:
        """The legacy `python/` environment is used when there is no `venv/`, and an unset mode counts as managed."""
        install = self._only_install(self._detect(roots=[], krita_settings=self._make_krita(server_mode=None,
                                                                                            legacy=True)))
        self.assertEqual(install.interpreter, self.root / 'krita' / 'ai_diffusion' / 'server' / 'python' / 'bin' /
                         'python3')
        self.assertEqual(install.findings, [])

    def test_krita_external_mode(self) -> None:
        """In external mode Krita's server folder isn't reported."""
        self.assertEqual(self._detect(roots=[], krita_settings=self._make_krita(server_mode='external')).installs, [])

    # ComfyUI Desktop:

    def test_comfy_desktop(self) -> None:
        """Desktop's instances are owned installs, with models from its shared `modelsDirs`."""
        install_dir = self.root / 'ComfyUI-Installs'
        comfyui = _make_comfyui(install_dir / 'ComfyUI' / 'ComfyUI', models=False)
        _make_environment(comfyui / '.venv', 'posix', python='3.12')
        _write(self.root / 'ComfyUI-Shared' / 'models' / 'diffusion_models' / 'flux.safetensors')
        settings = _write(self.root / 'config' / 'comfyui-desktop-2' / 'settings.json', json.dumps({
            'modelsDirs': [str(self.root / 'ComfyUI-Shared' / 'models')], 'installDir': str(install_dir)}))
        result = self._detect(desktop_settings=settings)
        install = self._only_install(result)
        self.assertEqual((install.owner, install.path), (InstallOwner.COMFY_DESKTOP, comfyui))
        self.assertIsNone(install.launch_command)
        self.assertEqual(install.findings, [])

    def test_comfy_desktop_without_models(self) -> None:
        """A Desktop instance with no models in its own folder or the shared ones gets `NO_MODELS`."""
        install_dir = self.root / 'installs'
        _make_environment(_make_comfyui(install_dir / 'one' / 'ComfyUI', models=False) / '.venv', 'posix')
        settings = _write(self.root / 'settings.json', json.dumps({'installDir': str(install_dir)}))
        install = self._only_install(self._detect(roots=[], desktop_settings=settings))
        self.assertEqual(self._codes(install), {FindingCode.NO_MODELS})

    # Plain installs:

    def test_portable_comfyui(self) -> None:
        """The portable build uses its embedded interpreter and the standalone build flag."""
        portable = _make_portable(self.root / 'ComfyUI_windows_portable')
        install = self._only_install(self._detect(platform=WINDOWS))
        self.assertEqual(install.path, portable)
        self.assertEqual(install.entry_point, portable / 'ComfyUI' / 'main.py')
        self.assertEqual(install.launch_command, [str(portable / 'python_embeded' / 'python.exe'),
                                                  str(portable / 'ComfyUI' / 'main.py'),
                                                  '--windows-standalone-build'])
        self.assertEqual(install.findings, [])

    def test_portable_found_through_its_comfyui_folder(self) -> None:
        """A root pointing inside a portable build still reports the portable build once."""
        portable = _make_portable(self.root / 'portable')
        result = self._detect(roots=[portable / 'ComfyUI', self.root], platform=WINDOWS)
        self.assertEqual(self._only_install(result).path, portable)

    def test_comfyui_git_checkout_posix_venv(self) -> None:
        """A ComfyUI checkout with a POSIX venv has a launch command, version and commit."""
        comfyui = _make_comfyui(self.root / 'ComfyUI')
        _make_environment(comfyui / 'venv', 'posix', python='3.11')
        _write(comfyui / '.git' / 'HEAD', 'ref: refs/heads/master\n')
        _write(comfyui / '.git' / 'packed-refs', '# pack-refs\nabc123 refs/heads/master\n')
        install = self._only_install(self._detect())
        self.assertEqual(install.launch_command, [str(comfyui / 'venv' / 'bin' / 'python3'), str(comfyui / 'main.py')])
        self.assertEqual(install.git_commit, 'abc123')
        self.assertEqual(install.findings, [])

    def test_webui_git_checkout_windows_venv(self) -> None:
        """A WebUI checkout with a Windows `.venv` is detection-only and reads `webui-user.bat`."""
        webui = _make_webui(self.root / 'stable-diffusion-webui', args=None)
        _make_environment(webui / '.venv', 'windows')
        _write(webui / 'webui-user.bat', '@echo off\nset COMMANDLINE_ARGS=--api --port 7862\ncall webui.bat\n')
        _write(webui / '.git' / 'HEAD', 'def456\n')
        install = self._only_install(self._detect(platform=WINDOWS))
        self.assertEqual((install.kind, install.webui_variant), (BackendKind.WEBUI, 'a1111'))
        self.assertEqual(install.interpreter, webui / '.venv' / 'Scripts' / 'python.exe')
        self.assertIsNone(install.launch_command)
        self.assertEqual(install.launch_args, ['--api', '--port', '7862'])
        self.assertEqual(install.git_commit, 'def456')
        self.assertEqual(install.findings, [])

    def test_managed_install(self) -> None:
        """The IntraPaint-managed path is reported with its owner, and a missing one isn't."""
        managed = _make_comfyui(self.root / 'managed' / 'ComfyUI')
        _make_environment(managed / 'venv', 'posix', python='3.12')
        install = self._only_install(self._detect(managed_path=managed))
        self.assertEqual(install.owner, InstallOwner.INTRAPAINT)
        self.assertIsNone(install.launch_command)
        self.assertEqual(self._detect(roots=[], managed_path=self.root / 'missing').installs, [])

    # Findings:

    def _comfyui_codes(self, **environment_args) -> set[FindingCode]:
        comfyui = _make_comfyui(self.root / 'ComfyUI')
        _make_environment(comfyui / 'venv', 'posix', **environment_args)
        return self._codes(self._only_install(self._detect()))

    def test_torch_missing(self) -> None:
        """An environment with no torch `dist-info` is a blocker."""
        self.assertEqual(self._comfyui_codes(torch=None), {FindingCode.TORCH_MISSING})

    def test_base_python_missing(self) -> None:
        """A venv whose `pyvenv.cfg` home is gone is a blocker."""
        self.assertEqual(self._comfyui_codes(base_python=self.root / 'uninstalled'), {FindingCode.BASE_PYTHON_MISSING})

    def test_cpu_only_torch(self) -> None:
        """A `+cpu` torch build is a warning."""
        self.assertEqual(self._comfyui_codes(torch='2.3.1+cpu'), {FindingCode.CPU_ONLY_TORCH})

    def test_comfyui_old_python(self) -> None:
        """ComfyUI below Python 3.9 is a warning."""
        self.assertEqual(self._comfyui_codes(python='3.8'), {FindingCode.PYTHON_VERSION_MISMATCH})

    def test_interpreter_missing(self) -> None:
        """An environment folder with no interpreter is a blocker."""
        comfyui = _make_comfyui(self.root / 'ComfyUI')
        (comfyui / 'venv' / 'lib').mkdir(parents=True)
        self.assertEqual(self._codes(self._only_install(self._detect())), {FindingCode.INTERPRETER_MISSING})

    def test_interpreter_unknown(self) -> None:
        """An install with no environment folder is reported with no launch command, and torch isn't checked."""
        _make_comfyui(self.root / 'ComfyUI')
        install = self._only_install(self._detect())
        self.assertEqual(self._codes(install), {FindingCode.INTERPRETER_UNKNOWN})
        self.assertIsNone(install.interpreter)
        self.assertIsNone(install.launch_command)

    def test_webui_python_version(self) -> None:
        """A WebUI environment on another Python than the one its version warning names is a warning."""
        webui = _make_webui(self.root / 'webui')
        _make_environment(webui / 'venv', 'posix', python='3.11')
        install = self._only_install(self._detect())
        self.assertEqual(self._codes(install), {FindingCode.PYTHON_VERSION_MISMATCH})
        self.assertEqual(install.findings[0].details, {'version': '3.11', 'expected': '3.10'})

    def test_webui_python_version_unknown(self) -> None:
        """A WebUI with no tested version in `launch_utils.py` gets no Python version finding."""
        webui = _make_webui(self.root / 'webui', tested_python=None)
        _make_environment(webui / 'venv', 'posix', python='3.12')
        self.assertEqual(self._codes(self._only_install(self._detect())), set())

    def test_webui_upgraded_environment(self) -> None:
        """A venv upgraded to a new Python is checked in that version's `site-packages`, not a stale one's.

        Forge Neo is tested with Python 3.13, and its venvs can keep an empty `lib/python3.10/`.
        """
        webui = _make_webui(self.root / 'forge_neo', forge=True, tested_python='3.13.15')
        _make_environment(webui / 'venv', 'posix', python='3.13')
        (webui / 'venv' / 'lib' / 'python3.10' / 'site-packages').mkdir(parents=True)
        self.assertEqual(self._codes(self._only_install(self._detect())), set())

    def test_webui_api_flag(self) -> None:
        """`webui-user.sh` without `--api` is a blocker; with it, nothing is reported."""
        webui = _make_webui(self.root / 'webui', args='--xformers --port 7861')
        _make_environment(webui / 'venv', 'posix')
        self.assertEqual(self._codes(self._only_install(self._detect())), {FindingCode.API_DISABLED})
        _write(webui / 'webui-user.sh',
               'export COMMANDLINE_ARGS="--xformers --api --gradio-auth=user:secret"  # comment\n')
        install = self._only_install(self._detect())
        self.assertEqual(self._codes(install), set())
        self.assertEqual(install.launch_args, ['--xformers', '--api', '--gradio-auth=<redacted>'])

    def test_webui_ckpt_dir(self) -> None:
        """Models in `--ckpt-dir` count, and with none anywhere `NO_MODELS` is a warning."""
        webui = _make_webui(self.root / 'webui', models=False, args="--api --ckpt-dir '../my models'")
        _make_environment(webui / 'venv', 'posix')
        install = self._only_install(self._detect(roots=[webui]))
        self.assertEqual(self._codes(install), {FindingCode.NO_MODELS})
        self.assertEqual(install.findings[0].severity, FindingSeverity.WARNING)
        _write(self.root / 'my models' / 'model.safetensors')
        self.assertEqual(self._codes(self._only_install(self._detect(roots=[webui]))), set())

    def test_no_models(self) -> None:
        """A ComfyUI install with no checkpoint is a warning; models deeper than the search depth don't count."""
        comfyui = _make_comfyui(self.root / 'ComfyUI', models=False)
        _make_environment(comfyui / 'venv', 'posix')
        _write(comfyui / 'models' / 'checkpoints' / 'a' / 'b' / 'c' / 'model.safetensors')
        self.assertEqual(self._codes(self._only_install(self._detect())), {FindingCode.NO_MODELS})

    def test_models_through_symlinked_folder(self) -> None:
        """A models folder that is itself a link is followed."""
        comfyui = _make_comfyui(self.root / 'ComfyUI', models=False)
        _make_environment(comfyui / 'venv', 'posix')
        _write(self.root / 'shared' / 'model.gguf')
        (comfyui / 'models').mkdir()
        os.symlink(self.root / 'shared', comfyui / 'models' / 'unet', target_is_directory=True)
        self.assertEqual(self._codes(self._only_install(self._detect(roots=[comfyui]))), set())

    def test_models_through_linked_subfolder(self) -> None:
        """Links inside a models folder are followed, as Stability Matrix links its shared models into each install."""
        webui = _make_webui(self.root / 'webui', models=False)
        _make_environment(webui / 'venv', 'posix')
        _write(self.root / 'shared' / 'StableDiffusion' / 'SDXL' / 'model.safetensors')
        (webui / 'models' / 'Stable-diffusion').mkdir(parents=True)
        os.symlink(self.root / 'shared' / 'StableDiffusion', webui / 'models' / 'Stable-diffusion' / 'sd',
                   target_is_directory=True)
        os.symlink(webui / 'models', webui / 'models' / 'Stable-diffusion' / 'loop', target_is_directory=True)
        self.assertEqual(self._codes(self._only_install(self._detect(roots=[webui]))), set())

    def test_models_through_extra_model_paths(self) -> None:
        """Checkpoints named only by `extra_model_paths.yaml` count."""
        comfyui = _make_comfyui(self.root / 'ComfyUI', models=False)
        _make_environment(comfyui / 'venv', 'posix')
        _write(self.root / 'a1111' / 'models' / 'Stable-diffusion' / 'model.safetensors')
        _write(comfyui / 'extra_model_paths.yaml', '# Shared with A1111\n'
                                                   'a111:\n'
                                                   f'    base_path: {self.root / "a1111"}\n'
                                                   '    checkpoints: |\n'
                                                   '        models/missing\n'
                                                   '        models/Stable-diffusion  # the real one\n'
                                                   '    vae: models/VAE\n')
        self.assertEqual(self._codes(self._only_install(self._detect(roots=[comfyui]))), set())

    def test_unparseable_extra_model_paths(self) -> None:
        """An `extra_model_paths.yaml` that can't be read skips `NO_MODELS` rather than reporting a false one."""
        comfyui = _make_comfyui(self.root / 'ComfyUI', models=False)
        _make_environment(comfyui / 'venv', 'posix')
        _write(comfyui / 'extra_model_paths.yaml', 'a111: {base_path: /models, checkpoints: checkpoints}\n')
        self.assertEqual(self._codes(self._only_install(self._detect(roots=[comfyui]))), set())

    def test_parse_extra_model_paths_relative_base(self) -> None:
        """A relative `base_path` resolves against the ComfyUI folder, and keys outside the model list are ignored."""
        paths = parse_extra_model_paths('comfyui:\n  base_path: ../shared\n  checkpoints: ckpt\n  loras: loras\n',
                                        self.root)
        self.assertEqual(paths, [self.root / '../shared' / 'ckpt'])

    # Scanning:

    def test_scan_depth(self) -> None:
        """An install 3 folders below a root is found; one 4 folders below isn't."""
        _make_comfyui(self.root / 'a' / 'b' / 'ComfyUI')
        _make_comfyui(self.root / 'a' / 'b' / 'c' / 'ComfyUI')
        install = self._only_install(self._detect())
        self.assertEqual(install.path, self.root / 'a' / 'b' / 'ComfyUI')

    def test_symlink_loop_not_followed(self) -> None:
        """Linked folders aren't descended into, so a loop ends and an install reached only through a link isn't found."""
        (self.root / 'a').mkdir()
        os.symlink(self.root, self.root / 'a' / 'loop', target_is_directory=True)
        _make_comfyui(self.root / 'outside' / 'ComfyUI')
        os.symlink(self.root / 'outside', self.root / 'a' / 'link', target_is_directory=True)
        self.assertEqual(self._detect(roots=[self.root / 'a']).installs, [])

    def test_skipped_folders(self) -> None:
        """Hidden folders and environment folders aren't scanned."""
        _make_comfyui(self.root / '.hidden' / 'ComfyUI')
        _make_comfyui(self.root / 'node_modules' / 'ComfyUI')
        self.assertEqual(self._detect().installs, [])

    def test_owned_install_reported_once(self) -> None:
        """An install reached through Stability Matrix and the candidate roots is reported once, with its owner."""
        library = self.root / 'SM'
        self._make_stability_matrix_library(library)
        app_data = self.root / 'appdata'
        _write(app_data / 'library.json', json.dumps({'LibraryPath': str(library)}))
        result = self._detect(roots=[library / 'Packages'], sm_app_data=app_data)
        self.assertEqual([install.owner for install in result.installs], [InstallOwner.STABILITY_MATRIX] * 2)

    def test_empty_roots(self) -> None:
        """Nothing found and nothing answering gives an empty result."""
        self.assertEqual(self._detect(), DetectionResult())

    def test_default_search_locations(self) -> None:
        """Each platform's app data folders follow its conventions."""
        home = Path('/home/user')
        linux = default_search_locations(home, 'linux', {})
        self.assertEqual(linux.candidate_roots, [home, home / 'Desktop', home / 'Documents', home / 'Downloads',
                                                 Path('/opt')])
        self.assertEqual(linux.stability_matrix_app_data, [home / '.config' / 'StabilityMatrix'])
        self.assertEqual(linux.krita_settings_files[0], home / '.local/share/krita/ai_diffusion/settings.json')
        self.assertEqual(linux.comfy_desktop_settings_files, [home / '.config/comfyui-desktop-2/settings.json'])
        windows = default_search_locations(home, 'win32', {'APPDATA': '/roaming', 'LOCALAPPDATA': '/local'})
        self.assertEqual(windows.stability_matrix_app_data, [Path('/roaming/StabilityMatrix')])
        self.assertEqual(windows.krita_settings_files, [Path('/roaming/krita/ai_diffusion/settings.json'),
                                                        Path('/local/krita-ai-diffusion/settings.json')])

    # Servers:

    def test_comfyui_server_linked_by_argv(self) -> None:
        """A ComfyUI server whose `argv` names a detected install's `main.py` is attached to it."""
        comfyui = _make_comfyui(self.root / 'ComfyUI')
        connect = _servers({DEFAULT_COMFYUI_URL: _comfyui_backend([str(comfyui / 'main.py'), '--listen'],
                                                                  version='0.3.12')})
        result = self._detect(connect=connect)
        install = self._only_install(result)
        self.assertIsNotNone(install.server)
        assert install.server is not None
        self.assertEqual((install.server.kind, install.server.version), (BackendKind.COMFYUI, '0.3.12'))
        self.assertEqual(install.server.install_path, comfyui)
        self.assertEqual(result.servers, [])

    def test_portable_server_linked_by_relative_argv(self) -> None:
        """A relative `argv` path links when exactly one install's entry point ends with it."""
        _make_portable(self.root / 'portable')
        result = self._detect(platform=WINDOWS, connect=_servers({DEFAULT_COMFYUI_URL: _comfyui_backend(
            ['ComfyUI/main.py', '--windows-standalone-build'])}))
        self.assertIsNotNone(self._only_install(result).server)

    def test_server_linked_by_version(self) -> None:
        """A relative `argv` matching several installs links to the one whose version is the server's."""
        _make_comfyui(self.root / 'old', version='0.3.26')
        _make_comfyui(self.root / 'current', version='0.39.0')
        result = self._detect(connect=_servers({DEFAULT_COMFYUI_URL: _comfyui_backend(['main.py'], version='0.39.0')}))
        self.assertEqual([install.server is not None for install in result.installs], [True, False])
        self.assertEqual(result.servers, [])

    def test_comfyui_server_unlinked(self) -> None:
        """A ComfyUI server running from somewhere else stays in `servers`."""
        _make_comfyui(self.root / 'ComfyUI')
        result = self._detect(connect=_servers({DEFAULT_COMFYUI_URL: _comfyui_backend(['/other/main.py'])}))
        self.assertIsNone(self._only_install(result).server)
        self.assertEqual([server.install_path for server in result.servers], [Path('/other')])

    def test_webui_server_linked_by_port(self) -> None:
        """A WebUI server links to the one install whose `--port` matches, or that uses the default port."""
        _make_webui(self.root / 'custom_port', args='--api --port 7861')
        _make_webui(self.root / 'default_port', args='--api')
        connect = _servers({DEFAULT_WEBUI_URL: mock.MagicMock(spec=A1111Webservice),
                            'http://localhost:7861': mock.MagicMock(spec=A1111Webservice)})
        result = self._detect(connect=connect)
        servers = {install.path.name: install.server.url if install.server else None for install in result.installs}
        self.assertEqual(servers, {'custom_port': 'http://localhost:7861', 'default_port': DEFAULT_WEBUI_URL})
        self.assertEqual(result.servers, [])

    def test_webui_server_unknown_args_ambiguous(self) -> None:
        """An install with unknown launch arguments could use any port, so a server it could be running isn't linked."""
        _make_webui(self.root / 'custom_port', args='--api --port 7861')
        _make_webui(self.root / 'unknown_args', args=None)
        result = self._detect(connect=_servers({'http://localhost:7861': mock.MagicMock(spec=A1111Webservice)}))
        self.assertEqual([install.server for install in result.installs], [None, None])
        self.assertEqual([server.url for server in result.servers], ['http://localhost:7861'])

    def test_webui_server_ambiguous(self) -> None:
        """A WebUI server matching two installs' ports isn't linked."""
        _make_webui(self.root / 'one')
        _make_webui(self.root / 'two')
        result = self._detect(connect=_servers({DEFAULT_WEBUI_URL: mock.MagicMock(spec=A1111Webservice)}))
        self.assertEqual([install.server for install in result.installs], [None, None])
        self.assertEqual([server.kind for server in result.servers], [BackendKind.WEBUI])

    def test_server_api_disabled(self) -> None:
        """A server answering as neither backend has `API_DISABLED`."""
        result = self._detect(connect=_servers({DEFAULT_WEBUI_URL: UnexpectedResponseError('no api')}))
        self.assertEqual(len(result.servers), 1)
        self.assertIsNone(result.servers[0].kind)
        self.assertEqual([finding.code for finding in result.servers[0].findings], [FindingCode.API_DISABLED])

    def test_server_auth_required(self) -> None:
        """A server requiring a login has `AUTH_REQUIRED`."""
        result = self._detect(connect=_servers({DEFAULT_WEBUI_URL: AuthError('login')}))
        self.assertEqual([finding.code for finding in result.servers[0].findings], [FindingCode.AUTH_REQUIRED])

    def test_extra_urls_deduplicated(self) -> None:
        """Local host names count as one host, so the same server is probed once."""
        probed = []

        def connect(url: str) -> Backend:
            probed.append(url)
            raise BackendConnectionError(url)
        self._detect(connect=connect, extra_urls=['http://127.0.0.1:8188/', 'http://localhost:9000'])
        self.assertEqual(probed, [DEFAULT_COMFYUI_URL, DEFAULT_WEBUI_URL, 'http://localhost:9000'])
