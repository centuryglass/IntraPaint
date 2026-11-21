"""Prints the Stable Diffusion backends `detect` finds on this machine, for checking detection by hand.

Prints readable text, or JSON with `--json`. `--redact-home` replaces the home folder and user name, so the output can
be posted publicly. `--root` and `--url` add places to look; nothing else changes what is detected.

Usage:
    python scripts/detect_backends.py [--json] [--redact-home] [--root PATH ...] [--url URL ...]
"""
import argparse
import dataclasses
import getpass
import json
import os
import re
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# pylint: disable=wrong-import-position
from src.controller.image_generation.backend_install.backend_detector import detect
from src.controller.image_generation.backend_install.detected_backend import DetectedInstall, DetectedServer, \
    DetectionResult, Finding


def _plain(value: object) -> object:
    """Convert detection results to JSON-compatible values."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        data = {item.name: _plain(getattr(value, item.name)) for item in dataclasses.fields(value)}
        if isinstance(value, Finding):
            data['severity'] = value.severity.value
        return data
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (Path, datetime)):
        return str(value)
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def _finding_lines(findings: list[Finding], indent: str) -> list[str]:
    lines = []
    for finding in findings:
        details = ', '.join(f'{key}={value}' for key, value in finding.details.items())
        lines.append(f'{indent}{finding.severity.value.upper()} {finding.code.value}' + (f' ({details})' if details
                                                                                          else ''))
    return lines


def _server_lines(server: DetectedServer, indent: str) -> list[str]:
    kind = server.kind.value if server.kind else 'unknown'
    lines = [f'{indent}{server.url}: {kind}' + (f' {server.version}' if server.version else '')]
    if server.argv:
        lines.append(f'{indent}  argv: {" ".join(server.argv)}')
    return lines + _finding_lines(server.findings, indent + '  ')


def _install_lines(install: DetectedInstall) -> list[str]:
    variant = f' ({install.webui_variant})' if install.webui_variant else ''
    lines = [f'{install.kind.value}{variant} at {install.path}', f'  owner: {install.owner.value}',
             f'  entry point: {install.entry_point}']
    for label, value in (('interpreter', install.interpreter), ('version', install.version),
                         ('git commit', install.git_commit), ('last used', install.last_used)):
        if value is not None:
            lines.append(f'  {label}: {value}')
    if install.launch_args is not None:
        lines.append(f'  launch args: {" ".join(install.launch_args)}')
    if install.launch_command is not None:
        lines.append(f'  launch command: {" ".join(install.launch_command)}')
    lines.extend(_finding_lines(install.findings, '  '))
    if install.server is not None:
        lines.append('  server:')
        lines.extend(_server_lines(install.server, '    '))
    return lines


def format_text(result: DetectionResult) -> str:
    """Describe a detection result as readable text."""
    lines = []
    for install in result.installs:
        lines.extend(_install_lines(install))
        lines.append('')
    if not result.installs:
        lines.extend(('No installs found.', ''))
    lines.append('Servers not linked to an install:' if result.servers else 'No unlinked servers.')
    for server in result.servers:
        lines.extend(_server_lines(server, '  '))
    return '\n'.join(lines)


def redact(text: str) -> str:
    """Replace the home folder in `text`, and the user name wherever it is a whole path component."""
    home = str(Path.home())
    text = text.replace(home, '~').replace(home.replace('\\', '\\\\'), '~')
    user = getpass.getuser()
    if not user:
        return text
    return re.sub(rf'(?<=[\\/]){re.escape(user)}(?=[\\/"]|$)', '<user>', text, flags=re.MULTILINE)


def main() -> None:
    """Run detection and print the result."""
    parser = argparse.ArgumentParser(description=__doc__.split('\n', maxsplit=1)[0])
    parser.add_argument('--json', action='store_true', help='print JSON instead of text')
    parser.add_argument('--redact-home', action='store_true', help='replace the home folder and user name')
    parser.add_argument('--root', action='append', default=[], type=Path, help='an extra folder to search')
    parser.add_argument('--url', action='append', default=[], help='an extra server URL to probe')
    args = parser.parse_args()
    result = detect(extra_roots=args.root, extra_urls=args.url)
    output = json.dumps(_plain(result), indent=2) if args.json else format_text(result)
    print(redact(output) if args.redact_home else output)


if __name__ == '__main__':
    main()
