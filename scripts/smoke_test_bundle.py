"""Launch test for a packaged IntraPaint build: fail unless the bundle starts and reaches the editing state.

CI's bundle job (.github/workflows/ci.yml) runs this on each PyInstaller bundle, because a bundle can fail where
a source run works: a module PyInstaller didn't collect, or startup code that only runs in a bundle. Three checks:
1. `--help` exits cleanly. IntraPaint.py imports most of the app before parsing arguments, so this covers imports.
2. A `--mode none` launch logs the change to the editing state within the timeout, without failing to load an optional
   tool. That covers AppController and the main window. The app never exits on its own, so it's killed afterwards.
3. On Linux, the idle app then uses at most `IDLE_CPU_LIMIT` of a core. That catches a relayout loop, an endless
   animation or a fast polling timer, which only show up as CPU use. `test/controller/idle_activity_test.py` checks for
   the causes it can reach without running the event loop. The check reads `/proc`, so it doesn't run on Windows.

Qt runs offscreen. On Linux, the bundle's config and logs go to a temporary directory through the XDG variables. On
Windows and macOS, platformdirs ignores those, so the launch uses the real user directories.

Usage: python scripts/smoke_test_bundle.py path/to/bundle/executable [--timeout SECONDS]
"""
import argparse
import os
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time

EDITING_STATE_LINE = 'State change: from init to editing'
# Logged by src/util/optional_import.py when an optional tool fails to import, e.g. the MyPaint brush tool when
# libmypaint doesn't load. Other optional imports (themes, spacenav, GLID-3-XL) are expected to fail in a bundle.
OPTIONAL_IMPORT_FAILURE = 'Failed to load optional import from src.tools.'
HELP_TIMEOUT_SECONDS = 120
# The app settles for IDLE_SETTLE_SECONDS after reaching the editing state, then its CPU use is measured over
# IDLE_SAMPLE_SECONDS. An idle app uses well under 1% of a core, and the loops this catches use far more.
IDLE_SETTLE_SECONDS = 3
IDLE_SAMPLE_SECONDS = 10
IDLE_CPU_LIMIT = 0.10


def _bundle_env(temp_dir: str) -> dict[str, str]:
    env = dict(os.environ)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    for xdg_var in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME'):
        env[xdg_var] = os.path.join(temp_dir, xdg_var.lower())
    return env


def _kill_tree(process: subprocess.Popen) -> None:
    """Kill the bundle and the child process a one-file bundle extracts and runs."""
    if process.poll() is not None:
        return
    if sys.platform == 'win32':
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], check=False, capture_output=True)
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()


def _check_help(executable: str, env: dict[str, str]) -> bool:
    print(f'Running {executable} --help')
    result = subprocess.run([executable, '--help'], env=env, capture_output=True, text=True, errors='replace',
                            timeout=HELP_TIMEOUT_SECONDS, check=False)
    print(result.stdout + result.stderr)
    if result.returncode != 0:
        print(f'FAIL: --help exited with code {result.returncode}')
        return False
    return True


def _group_cpu_seconds(group_id: int) -> float:
    """Returns the CPU time used so far by the live processes of a Linux process group.

    A one-file bundle runs the app in a child process, which shares the bundle's process group.
    """
    ticks = 0
    for entry in os.listdir('/proc'):
        if not entry.isdigit():
            continue
        try:
            with open(f'/proc/{entry}/stat', encoding='ascii') as stat_file:
                # Fields after the parenthesized command name, which may contain spaces, start at the state field:
                fields = stat_file.read().rsplit(')', 1)[1].split()
        except (OSError, IndexError):
            continue  # The process exited while being read.
        process_group, user_ticks, system_ticks = int(fields[2]), int(fields[11]), int(fields[12])
        if process_group == group_id:
            ticks += user_ticks + system_ticks
    return ticks / os.sysconf('SC_CLK_TCK')


def _check_idle_cpu(process: subprocess.Popen) -> bool:
    """Checks that the launched app, already in the editing state, stays under the idle CPU limit."""
    if not sys.platform.startswith('linux'):
        print('Skipping the idle CPU check: it reads /proc, which only Linux has.')
        return True
    time.sleep(IDLE_SETTLE_SECONDS)
    start_cpu, start_time = _group_cpu_seconds(process.pid), time.monotonic()
    time.sleep(IDLE_SAMPLE_SECONDS)
    if process.poll() is not None:
        print(f'FAIL: exited with code {process.returncode} while idle')
        return False
    cpu_fraction = (_group_cpu_seconds(process.pid) - start_cpu) / (time.monotonic() - start_time)
    print(f'Idle CPU use: {cpu_fraction:.1%} of a core (limit {IDLE_CPU_LIMIT:.0%})')
    if cpu_fraction > IDLE_CPU_LIMIT:
        print('FAIL: the idle app keeps the CPU busy. A relayout loop, a running animation or a fast timer is the usual '
              'cause. test/controller/idle_activity_test.py finds most of them.')
        return False
    return True


def _check_launch(executable: str, env: dict[str, str], timeout: float) -> bool:
    print(f'Launching {executable} --mode none --verbose')
    popen_args = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == 'win32' \
        else {'start_new_session': True}
    with subprocess.Popen([executable, '--mode', 'none', '--verbose'], env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, errors='replace',
                          **popen_args) as process:
        assert process.stdout is not None
        lines: queue.Queue[str | None] = queue.Queue()

        def _read_output() -> None:
            assert process.stdout is not None
            for output_line in process.stdout:
                lines.put(output_line)
            lines.put(None)

        threading.Thread(target=_read_output, daemon=True).start()
        deadline = time.monotonic() + timeout
        failure = f'FAIL: no "{EDITING_STATE_LINE}" within {timeout} seconds'
        try:
            while (remaining := deadline - time.monotonic()) > 0:
                try:
                    line = lines.get(timeout=remaining)
                except queue.Empty:
                    break
                if line is None:
                    failure = f'FAIL: exited with code {process.wait()} before reaching the editing state'
                    break
                print(line, end='')
                if OPTIONAL_IMPORT_FAILURE in line:
                    failure = 'FAIL: an optional tool failed to load'
                    break
                if EDITING_STATE_LINE in line:
                    print('Reached the editing state.')
                    return _check_idle_cpu(process)
        finally:
            _kill_tree(process)
        print(failure)
        return False


def main() -> int:
    """Run the checks on the bundle named on the command line, returning the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('executable', help='path to the bundled IntraPaint executable')
    parser.add_argument('--timeout', type=float, default=180, help='seconds to wait for the editing state')
    args = parser.parse_args()
    executable = os.path.abspath(args.executable)
    with tempfile.TemporaryDirectory() as temp_dir:
        env = _bundle_env(temp_dir)
        if not _check_help(executable, env) or not _check_launch(executable, env, args.timeout):
            return 1
    print('PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
