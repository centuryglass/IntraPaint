"""Starts, health-checks, streams logs from and stops a ComfyUI install that IntraPaint launches itself.

The server runs in a `QProcess` owned by the main thread, so output and exit signals arrive there and need no worker.
Only the readiness poll, a blocking HTTP call, runs in an `AsyncTask`. `stop` acts only on the process this instance
started: a ComfyUI the user started themselves is never touched.
"""
import codecs
import logging
import re
import threading
import time
from enum import Enum
from functools import partial
from typing import Callable, Optional, Sequence

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal, SignalInstance, Slot
from pydantic import ValidationError
from sd_backend_client import ComfyUiWebservice, SDBackendError

from src.config.cache import Cache
from src.util.async_task import AsyncTask
from src.util.main_thread import assert_main_thread

logger = logging.getLogger(__name__)

LISTEN_HOST = '127.0.0.1'
DEFAULT_READY_TIMEOUT_SECONDS = 300.0
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_STOP_GRACE_MS = 10000
HEALTH_CHECK_REQUEST_TIMEOUT_SECONDS = 5.0

# ComfyUI arguments that `ManagedComfyUI` sets itself. `--listen`'s value is optional.
_PORT_ARG = '--port'
_LISTEN_ARG = '--listen'

_LINE_BREAK_PATTERN = re.compile(r'\r\n|\n|\r')
# Terminal escape sequences, such as the color codes ComfyUI's log uses: CSI, OSC, and other two-character escapes.
_TERMINAL_ESCAPE_PATTERN = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]')

# Takes a server URL and returns the `argv` the ComfyUI there reports, or `None` if nothing valid answers. Blocks.
HealthCheck = Callable[[str], Optional[list[str]]]
ProcessFactory = Callable[[QObject], QProcess]


class ManagedState(Enum):
    """The lifecycle state of a `ManagedComfyUI`'s process."""
    STOPPED = 'stopped'
    STARTING = 'starting'  # Running, but not yet confirmed ready by `ManagedComfyUI.wait_until_ready`.
    READY = 'ready'
    CRASHED = 'crashed'  # Exited, or failed to start, without `ManagedComfyUI.stop` being called.


class WaitResult(Enum):
    """How a `ManagedComfyUI.wait_until_ready` call ended."""
    READY = 'ready'
    FAILED = 'failed'  # The process exited or failed to start, or wasn't running.
    TIMED_OUT = 'timed_out'  # The process is still running, in the `STARTING` state.


def comfyui_argv(url: str) -> Optional[list[str]]:
    """Return the `argv` the ComfyUI server at `url` reports, or `None` if no ComfyUI answers there. Blocks."""
    webservice: Optional[ComfyUiWebservice] = None
    try:
        webservice = ComfyUiWebservice(url, request_timeout=HEALTH_CHECK_REQUEST_TIMEOUT_SECONDS)
        return list(webservice.get_system_stats().system.argv)
    except (SDBackendError, ValidationError, ValueError, OSError):
        return None
    finally:
        disconnect = getattr(webservice, 'disconnect', None)
        if callable(disconnect):
            disconnect()


def server_arguments(launch_command: Sequence[str], port: int) -> list[str]:
    """Return the arguments after the interpreter that start `launch_command` serving locally on `port`.

    Any `--port` or `--listen` already in the command is replaced.
    """
    args: list[str] = []
    remaining = list(launch_command[1:])
    while remaining:
        arg = remaining.pop(0)
        if arg == _PORT_ARG:
            if remaining:
                remaining.pop(0)
        elif arg == _LISTEN_ARG:
            if remaining and not remaining[0].startswith('-'):
                remaining.pop(0)
        elif not arg.startswith(f'{_PORT_ARG}=') and not arg.startswith(f'{_LISTEN_ARG}='):
            args.append(arg)
    return [*args, _LISTEN_ARG, LISTEN_HOST, _PORT_ARG, str(port)]


def _poll_until_ready(health_check: HealthCheck, url: str, expected_argv: list[str], deadline: float,
                      poll_interval: float, clock: Callable[[], float], cancelled: threading.Event,
                      result_signal: SignalInstance) -> None:
    """Poll `url` until the server there reports `expected_argv`, the deadline passes, or `cancelled` is set.

    Emits `WaitResult.READY` or `WaitResult.TIMED_OUT`, or nothing once cancelled. A server reporting other arguments
    is another ComfyUI already using the port, and doesn't count as ready.
    """
    while not cancelled.is_set():
        if health_check(url) == expected_argv:
            result_signal.emit(WaitResult.READY)
            return
        if clock() >= deadline:
            result_signal.emit(WaitResult.TIMED_OUT)
            return
        cancelled.wait(poll_interval)


class _ReadyPollTask(AsyncTask):
    result_signal = Signal(object)

    def signals(self) -> list[SignalInstance]:
        return [self.result_signal]


class ManagedComfyUI(QObject):
    """One ComfyUI install on disk, run as a child process serving on `LISTEN_HOST`.

    `start` launches the process in the `STARTING` state, and `wait_until_ready` confirms it is serving and moves it
    to `READY`. The process exiting without `stop` moves it to `CRASHED`. All methods must be called on the main
    thread. Destroying a running instance kills its process, so the owner calls `stop` before quitting.

    The process launcher, health check and clock are parameters so tests can drive every transition without a server.
    """

    log_signal = Signal(str)  # One line of output, with terminal escape sequences removed.
    state_signal = Signal(ManagedState)
    wait_result_signal = Signal(WaitResult)

    def __init__(self, install_path: str, launch_command: Sequence[str], port: int,
                 parent: Optional[QObject] = None, process_factory: ProcessFactory = QProcess,
                 health_check: HealthCheck = comfyui_argv, clock: Callable[[], float] = time.monotonic,
                 stop_grace_ms: int = DEFAULT_STOP_GRACE_MS) -> None:
        """Set up the install to manage, without starting it.

        Parameters
        ----------
        install_path: str
            The install's folder, which is the process's working directory.
        launch_command: Sequence[str]
            Interpreter, entry point and arguments, such as `DetectedInstall.launch_command`. Any `--port` or
            `--listen` in it is replaced.
        port: int
            The local port the server listens on.
        """
        super().__init__(parent)
        if len(launch_command) < 2:
            raise ValueError(f'Expected an interpreter and an entry point, got {list(launch_command)}')
        self._install_path = install_path
        self._program = launch_command[0]
        self._arguments = server_arguments(launch_command, port)
        self._port = port
        self._process_factory = process_factory
        self._health_check = health_check
        self._clock = clock
        self._process: Optional[QProcess] = None
        self._state = ManagedState.STOPPED
        self._stopping = False
        self._decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self._partial_line = ''
        self._poll_task: Optional[_ReadyPollTask] = None
        self._poll_cancelled: Optional[threading.Event] = None
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.setInterval(stop_grace_ms)
        self._kill_timer.timeout.connect(self._kill)

    @staticmethod
    def from_cache(parent: Optional[QObject] = None) -> Optional['ManagedComfyUI']:
        """Return the install the `Cache` names, or `None` if no launch command is saved."""
        cache = Cache()
        launch_command = cache.get(Cache.MANAGED_COMFYUI_LAUNCH_COMMAND)
        if len(launch_command) < 2:
            return None
        return ManagedComfyUI(cache.get(Cache.MANAGED_COMFYUI_PATH), launch_command,
                              cache.get(Cache.MANAGED_COMFYUI_PORT), parent)

    @property
    def state(self) -> ManagedState:
        """The process's current lifecycle state."""
        return self._state

    @property
    def url(self) -> str:
        """The URL the server answers at once ready."""
        return f'http://{LISTEN_HOST}:{self._port}'

    @property
    def is_running(self) -> bool:
        """Whether this instance's process is running, in the `STARTING` or `READY` state."""
        return self._state in (ManagedState.STARTING, ManagedState.READY)

    def start(self) -> bool:
        """Launch the process in the `STARTING` state, returning whether it launched.

        Does nothing and returns False while it is already running.
        """
        assert_main_thread('ManagedComfyUI.start')
        if self.is_running:
            return False
        self._discard_process()
        self._stopping = False
        self._decoder.reset()
        self._partial_line = ''
        process = self._process_factory(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.setWorkingDirectory(self._install_path)
        environment = QProcessEnvironment.systemEnvironment()
        # Unbuffered UTF-8 output, so log lines arrive as they are written and decode the same on every platform:
        environment.insert('PYTHONUNBUFFERED', '1')
        environment.insert('PYTHONIOENCODING', 'utf-8')
        process.setProcessEnvironment(environment)
        process.readyReadStandardOutput.connect(self._read_output)
        process.finished.connect(self._process_finished)
        process.errorOccurred.connect(self._process_error)
        self._process = process
        self._set_state(ManagedState.STARTING)
        command_text = ' '.join([self._program, *self._arguments])
        logger.info(f'Starting ComfyUI: {command_text}')
        process.start(self._program, self._arguments)
        return True

    def wait_until_ready(self, timeout_seconds: float = DEFAULT_READY_TIMEOUT_SECONDS,
                         poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS) -> None:
        """Poll the server until it answers, then emit `wait_result_signal` once.

        Emits `WaitResult.READY` and moves to `READY` once the server reports this instance's arguments. Emits `FAILED`
        as soon as the process exits or is stopped, or at once if it isn't running. Emits `TIMED_OUT` if the timeout
        passes first, leaving the process running. Emits `READY` at once if already ready, and does nothing while a
        poll is in progress.
        """
        assert_main_thread('ManagedComfyUI.wait_until_ready')
        if self._poll_task is not None:
            return
        if self._state == ManagedState.READY:
            self.wait_result_signal.emit(WaitResult.READY)
            return
        if self._state != ManagedState.STARTING:
            self.wait_result_signal.emit(WaitResult.FAILED)
            return
        cancelled = threading.Event()
        expected_argv = self._arguments
        action = partial(_poll_until_ready, self._health_check, self.url, expected_argv,
                         self._clock() + timeout_seconds, poll_interval_seconds, self._clock, cancelled)
        task = _ReadyPollTask(action)
        task.result_signal.connect(self._poll_result)
        task.finish_signal.connect(self._poll_finished)
        self._poll_task = task
        self._poll_cancelled = cancelled
        task.start()

    def stop(self) -> None:
        """Ask the process to exit, killing it if it hasn't after the grace period. Does nothing if not running."""
        assert_main_thread('ManagedComfyUI.stop')
        if self._process is None or not self.is_running or self._stopping:
            return
        self._stopping = True
        was_polling = self._poll_task is not None
        self._cancel_poll()
        if was_polling:
            self.wait_result_signal.emit(WaitResult.FAILED)
        if self._process.state() == QProcess.ProcessState.NotRunning:
            self._set_state(ManagedState.STOPPED)
            return
        logger.info('Stopping ComfyUI')
        self._process.terminate()
        self._kill_timer.start()

    @Slot()
    def _kill(self) -> None:
        if self._process is not None and self._stopping \
                and self._process.state() != QProcess.ProcessState.NotRunning:
            logger.warning('ComfyUI did not exit after the stop grace period, killing it')
            self._process.kill()

    @Slot()
    def _read_output(self) -> None:
        if self._process is None:
            return
        text = self._partial_line + self._decoder.decode(self._process.readAllStandardOutput().data())
        self._emit_lines(text)

    def _emit_lines(self, text: str, final: bool = False) -> None:
        # A trailing '\r' may be the first half of a '\r\n' split across reads, so it waits for the next read:
        held_back = '\r' if text.endswith('\r') and not final else ''
        lines = _LINE_BREAK_PATTERN.split(text[:len(text) - len(held_back)])
        self._partial_line = lines.pop() + held_back
        if final:
            if self._partial_line.rstrip('\r') != '':
                lines.append(self._partial_line.rstrip('\r'))
            self._partial_line = ''
        # Escapes are removed from whole lines only, so a sequence split across reads is still matched:
        for line in lines:
            self.log_signal.emit(_TERMINAL_ESCAPE_PATTERN.sub('', line))

    def _flush_output(self) -> None:
        self._emit_lines(self._partial_line + self._decoder.decode(b'', final=True), final=True)

    @Slot(int, QProcess.ExitStatus)
    def _process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        if self._process is not None:
            self._read_output()
        self._flush_output()
        self._kill_timer.stop()
        if self._stopping:
            logger.info(f'ComfyUI stopped (exit code {exit_code})')
            self._exited(ManagedState.STOPPED)
        else:
            logger.error(f'ComfyUI exited unexpectedly: exit code {exit_code}, {exit_status.name}')
            self._exited(ManagedState.CRASHED)

    @Slot(QProcess.ProcessError)
    def _process_error(self, error: QProcess.ProcessError) -> None:
        # `finished` follows every error except a failed start, and a stop request may report a crash:
        if error != QProcess.ProcessError.FailedToStart:
            return
        error_text = self._process.errorString() if self._process is not None else error.name
        logger.error(f'ComfyUI failed to start: {error_text}')
        self._exited(ManagedState.CRASHED)

    def _exited(self, state: ManagedState) -> None:
        was_polling = self._poll_task is not None
        self._cancel_poll()
        self._stopping = False
        self._set_state(state)
        if was_polling:
            self.wait_result_signal.emit(WaitResult.FAILED)

    @Slot(object)
    def _poll_result(self, result: WaitResult) -> None:
        if self.sender() is not self._poll_task or self._state != ManagedState.STARTING:
            return
        self._release_poll()
        if result == WaitResult.READY:
            self._set_state(ManagedState.READY)
        self.wait_result_signal.emit(result)

    @Slot()
    def _poll_finished(self) -> None:
        sender = self.sender()
        if isinstance(sender, _ReadyPollTask):
            sender.result_signal.disconnect(self._poll_result)
            sender.finish_signal.disconnect(self._poll_finished)
        if sender is self._poll_task:
            self._release_poll()

    def _cancel_poll(self) -> None:
        """Stop the poll in progress, if any. Its result, if it arrives later, is ignored."""
        if self._poll_cancelled is not None:
            self._poll_cancelled.set()
        self._release_poll()

    def _release_poll(self) -> None:
        self._poll_task = None
        self._poll_cancelled = None

    def _discard_process(self) -> None:
        if self._process is not None:
            for signal in (self._process.readyReadStandardOutput, self._process.finished,
                           self._process.errorOccurred):
                signal.disconnect()
            self._process.deleteLater()
            self._process = None

    def _set_state(self, state: ManagedState) -> None:
        if state != self._state:
            self._state = state
            self.state_signal.emit(state)
