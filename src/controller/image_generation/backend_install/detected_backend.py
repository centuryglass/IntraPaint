"""The result model of backend detection: installs found on disk, running servers, and findings about each.

Findings are evidence, not verdicts. A broken or stale install is still reported, with findings saying why, and
detection never ranks results or words them for users: the setup window maps each `FindingCode` to translated text.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

DEFAULT_COMFYUI_URL = 'http://localhost:8188'
DEFAULT_WEBUI_URL = 'http://localhost:7860'
DEFAULT_WEBUI_PORT = 7860


class BackendKind(Enum):
    """The API a backend serves."""
    COMFYUI = 'comfyui'
    WEBUI = 'webui'


class InstallOwner(Enum):
    """The app that installed and manages a backend, or `NONE` for one the user set up themselves.

    Whether IntraPaint may launch an owned install is undecided, so owned installs get no launch command.
    """
    NONE = 'none'
    STABILITY_MATRIX = 'stability_matrix'
    KRITA_AI_DIFFUSION = 'krita_ai_diffusion'
    COMFY_DESKTOP = 'comfy_desktop'
    INTRAPAINT = 'intrapaint'


class FindingSeverity(Enum):
    """How much a finding affects whether an install or server can be used."""
    BLOCKER = 'blocker'  # It can't work as it is.
    WARNING = 'warning'  # It may not work.
    INFO = 'info'


class FindingCode(Enum):
    """What a finding reports. `FINDING_SEVERITY` gives each code's severity."""
    ENTRY_POINT_MISSING = 'entry_point_missing'
    INTERPRETER_MISSING = 'interpreter_missing'
    BASE_PYTHON_MISSING = 'base_python_missing'
    TORCH_MISSING = 'torch_missing'
    INSTALL_INCOMPLETE = 'install_incomplete'
    API_DISABLED = 'api_disabled'
    NO_MODELS = 'no_models'
    PYTHON_VERSION_MISMATCH = 'python_version_mismatch'
    CPU_ONLY_TORCH = 'cpu_only_torch'
    INTERPRETER_UNKNOWN = 'interpreter_unknown'
    API_FLAG_UNKNOWN = 'api_flag_unknown'
    AUTH_REQUIRED = 'auth_required'


FINDING_SEVERITY: dict[FindingCode, FindingSeverity] = {
    FindingCode.ENTRY_POINT_MISSING: FindingSeverity.BLOCKER,
    FindingCode.INTERPRETER_MISSING: FindingSeverity.BLOCKER,
    FindingCode.BASE_PYTHON_MISSING: FindingSeverity.BLOCKER,
    FindingCode.TORCH_MISSING: FindingSeverity.BLOCKER,
    FindingCode.INSTALL_INCOMPLETE: FindingSeverity.BLOCKER,
    FindingCode.API_DISABLED: FindingSeverity.BLOCKER,
    FindingCode.NO_MODELS: FindingSeverity.WARNING,
    FindingCode.PYTHON_VERSION_MISMATCH: FindingSeverity.WARNING,
    FindingCode.CPU_ONLY_TORCH: FindingSeverity.WARNING,
    FindingCode.INTERPRETER_UNKNOWN: FindingSeverity.INFO,
    FindingCode.API_FLAG_UNKNOWN: FindingSeverity.INFO,
    FindingCode.AUTH_REQUIRED: FindingSeverity.INFO,
}


@dataclass
class Finding:
    """One piece of evidence about an install or server, with details such as paths and versions.

    Details are data for the UI to format, never user-facing text.
    """
    code: FindingCode
    details: dict[str, str] = field(default_factory=dict)

    @property
    def severity(self) -> FindingSeverity:
        """The code's severity, from `FINDING_SEVERITY`."""
        return FINDING_SEVERITY[self.code]


@dataclass
class DetectedServer:
    """A server that answered at a probed URL.

    `kind` is `None` when it answered as neither backend. `argv` is a ComfyUI server's command line, from
    `/system_stats`. `install_path` is the folder holding the `main.py` in `argv`, when that path is absolute.
    """
    url: str
    kind: Optional[BackendKind]
    version: Optional[str] = None
    argv: list[str] = field(default_factory=list)
    install_path: Optional[Path] = None
    findings: list[Finding] = field(default_factory=list)


@dataclass
class DetectedInstall:
    """A backend install found on disk, and what its files say about whether it works.

    `path` is the folder the user knows as the install: the portable build's root for ComfyUI portable, which holds
    `entry_point` in its `ComfyUI/` folder. `interpreter` comes from the install or its owner's environment only.
    `launch_command` is set only for unowned ComfyUI installs whose interpreter was found. `launch_args` are a WebUI
    install's recorded arguments, from `webui-user` or its owner's settings, or `None` if none were found.
    """
    kind: BackendKind
    owner: InstallOwner
    path: Path
    entry_point: Path
    webui_variant: Optional[str] = None  # 'forge' or 'a1111' for WebUI installs.
    interpreter: Optional[Path] = None
    launch_command: Optional[list[str]] = None
    launch_args: Optional[list[str]] = None
    version: Optional[str] = None
    git_commit: Optional[str] = None
    last_used: Optional[datetime] = None
    findings: list[Finding] = field(default_factory=list)
    server: Optional[DetectedServer] = None

    def has_finding(self, code: FindingCode) -> bool:
        """Whether any of the install's findings has `code`."""
        return any(finding.code == code for finding in self.findings)


@dataclass
class DetectionResult:
    """Every install found, and the running servers that weren't linked to one of them."""
    installs: list[DetectedInstall] = field(default_factory=list)
    servers: list[DetectedServer] = field(default_factory=list)
