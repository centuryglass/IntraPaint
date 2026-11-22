"""Tests `ManagedComfyUI`'s state transitions and log streaming, with a fake process and an injected health check."""
from typing import Optional
from unittest.mock import patch

from PySide6.QtCore import QByteArray, QObject, QProcess, QThread
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.controller.image_generation.backend_install.managed_comfyui import LISTEN_HOST, ManagedComfyUI, \
    ManagedState, WaitResult, server_arguments
from src.util.async_task import AsyncTask
from test.base_test_case import IntraPaintTestCase

INSTALL_PATH = '/opt/ComfyUI'
LAUNCH_COMMAND = ['/opt/ComfyUI/venv/bin/python', '/opt/ComfyUI/main.py', '--lowvram']
PORT = 8189
EXPECTED_ARGV = ['/opt/ComfyUI/main.py', '--lowvram', '--listen', LISTEN_HOST, '--port', str(PORT)]


class _FakeProcess(QProcess):
    """A `QProcess` that never launches anything: tests emit its signals to play the child's part."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.started_with: Optional[tuple[str, list[str]]] = None
        self.terminated = False
        self.killed = False
        self.running = False
        self.pending_output = b''

    def start(self, program: str, arguments: list[str]) -> None:  # type: ignore[override]
        """Record the command, and run until a test ends it."""
        self.started_with = (program, list(arguments))
        self.running = True

    def state(self) -> QProcess.ProcessState:  # type: ignore[override]
        """Running from `start` until `exit` or `fail_to_start`."""
        return QProcess.ProcessState.Running if self.running else QProcess.ProcessState.NotRunning

    def terminate(self) -> None:
        """Record the request; the test decides whether the process obeys."""
        self.terminated = True

    def kill(self) -> None:
        """Record the kill."""
        self.killed = True

    def readAllStandardOutput(self) -> QByteArray:  # type: ignore[override]
        """Return and clear the output queued by `write_output`."""
        output, self.pending_output = self.pending_output, b''
        return QByteArray(output)

    def write_output(self, output: bytes) -> None:
        """Queue output and announce it, as the child writing to stdout would."""
        self.pending_output += output
        self.readyReadStandardOutput.emit()

    def exit(self, exit_code: int = 0) -> None:
        """End the process."""
        self.running = False
        self.finished.emit(exit_code, QProcess.ExitStatus.NormalExit)

    def fail_to_start(self) -> None:
        """Report a failed start, which Qt follows with no `finished` signal."""
        self.running = False
        self.errorOccurred.emit(QProcess.ProcessError.FailedToStart)


class _FakeClock:
    """A clock that advances by `step` seconds each time it is read."""

    def __init__(self, step: float = 1.0) -> None:
        self.now = 0.0
        self.step = step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


class ManagedComfyUITest(IntraPaintTestCase):
    """Drives `ManagedComfyUI` through every transition without a server or a real process."""

    def setUp(self) -> None:
        super().setUp()
        self.processes: list[_FakeProcess] = []
        self.health_responses: list[Optional[list[str]]] = []
        self.checked_urls: list[str] = []
        self.started_tasks: list[AsyncTask] = []
        self.states: list[ManagedState] = []
        self.wait_results: list[WaitResult] = []
        self.log_lines: list[str] = []
        self.log_threads: list[QThread] = []
        self.clock = _FakeClock()
        self.managed = ManagedComfyUI(INSTALL_PATH, LAUNCH_COMMAND, PORT, process_factory=self._create_process,
                                      health_check=self._health_check, clock=self.clock)
        self.managed.state_signal.connect(self.states.append)
        self.managed.wait_result_signal.connect(self.wait_results.append)
        self.managed.log_signal.connect(self._log)
        # Poll tasks are queued, not run, so each test decides when the poll happens:
        self._task_patch = patch.object(AsyncTask, 'start', lambda task: self.started_tasks.append(task))
        self._task_patch.start()

    def tearDown(self) -> None:
        self._task_patch.stop()
        self.managed.deleteLater()
        self.managed = None  # type: ignore[assignment]
        self.processes.clear()
        self.started_tasks.clear()
        super().tearDown()

    def _create_process(self, parent: QObject) -> QProcess:
        process = _FakeProcess(parent)
        self.processes.append(process)
        return process

    def _health_check(self, url: str) -> Optional[list[str]]:
        self.checked_urls.append(url)
        return self.health_responses.pop(0) if len(self.health_responses) > 0 else None

    def _log(self, line: str) -> None:
        self.log_lines.append(line)
        self.log_threads.append(QThread.currentThread())

    def _run_poll(self) -> None:
        """Run the queued poll task to completion on this thread."""
        self.assertEqual(len(self.started_tasks), 1)
        self.started_tasks.pop().run()

    @property
    def process(self) -> _FakeProcess:
        """The most recently created fake process."""
        return self.processes[-1]

    def test_start_launches_on_local_port(self) -> None:
        """`start` runs the launch command from the install folder, listening on localhost at the port."""
        self.assertTrue(self.managed.start())
        self.assertEqual(self.process.started_with, (LAUNCH_COMMAND[0], EXPECTED_ARGV))
        self.assertEqual(self.process.workingDirectory(), INSTALL_PATH)
        self.assertEqual(self.process.processEnvironment().value('PYTHONUNBUFFERED'), '1')
        self.assertEqual(self.states, [ManagedState.STARTING])
        self.assertEqual(self.managed.url, f'http://{LISTEN_HOST}:{PORT}')
        self.assertFalse(self.managed.start(), 'a second start while running does nothing')
        self.assertEqual(len(self.processes), 1)

    def test_start_then_ready(self) -> None:
        """The poll retries until the server reports this instance's arguments, then reports ready."""
        self.managed.start()
        self.health_responses = [None, None, list(EXPECTED_ARGV)]
        self.managed.wait_until_ready(timeout_seconds=100, poll_interval_seconds=0)
        self._run_poll()
        self.assertEqual(self.checked_urls, [self.managed.url] * 3)
        self.assertEqual(self.wait_results, [WaitResult.READY])
        self.assertEqual(self.states, [ManagedState.STARTING, ManagedState.READY])
        self.managed.wait_until_ready()
        self.assertEqual(self.wait_results, [WaitResult.READY, WaitResult.READY])
        self.assertEqual(self.started_tasks, [], 'waiting while ready polls nothing')

    def test_start_then_timeout(self) -> None:
        """A poll that never sees the server times out and leaves the process running."""
        self.managed.start()
        # Another ComfyUI already on the port reports other arguments, so it never counts as ready:
        self.health_responses = [['main.py']] * 10
        self.managed.wait_until_ready(timeout_seconds=3, poll_interval_seconds=0)
        self._run_poll()
        self.assertEqual(self.wait_results, [WaitResult.TIMED_OUT])
        self.assertEqual(self.managed.state, ManagedState.STARTING)
        self.assertFalse(self.process.terminated)

    def test_start_then_process_exits(self) -> None:
        """A process exiting while the poll runs fails the wait at once, and the poll's late result is ignored."""
        self.managed.start()
        self.managed.wait_until_ready(timeout_seconds=100, poll_interval_seconds=0)
        self.process.exit(1)
        self.assertEqual(self.wait_results, [WaitResult.FAILED])
        self.assertEqual(self.states, [ManagedState.STARTING, ManagedState.CRASHED])
        self.health_responses = [list(EXPECTED_ARGV)]
        self._run_poll()
        self.assertEqual(self.wait_results, [WaitResult.FAILED])
        self.assertEqual(self.managed.state, ManagedState.CRASHED)
        self.assertEqual(self.checked_urls, [], 'a cancelled poll checks nothing')

    def test_crash_after_ready(self) -> None:
        """A ready process exiting without `stop` crashes, and can be started again."""
        self.managed.start()
        self.health_responses = [list(EXPECTED_ARGV)]
        self.managed.wait_until_ready(poll_interval_seconds=0)
        self._run_poll()
        self.process.exit(0)
        self.assertEqual(self.states, [ManagedState.STARTING, ManagedState.READY, ManagedState.CRASHED])
        self.assertEqual(self.wait_results, [WaitResult.READY])
        self.assertTrue(self.managed.start())
        self.assertEqual(len(self.processes), 2)
        self.assertEqual(self.managed.state, ManagedState.STARTING)

    def test_failed_start(self) -> None:
        """A process that can't launch crashes, and a wait after that fails."""
        self.managed.start()
        self.process.fail_to_start()
        self.assertEqual(self.states, [ManagedState.STARTING, ManagedState.CRASHED])
        self.managed.wait_until_ready()
        self.assertEqual(self.wait_results, [WaitResult.FAILED])
        self.assertEqual(self.started_tasks, [])

    def test_stop_never_started_is_noop(self) -> None:
        """Stopping an instance that never started does nothing, and waiting on it fails."""
        self.managed.stop()
        self.assertEqual(self.processes, [])
        self.assertEqual(self.states, [])
        self.managed.wait_until_ready()
        self.assertEqual(self.wait_results, [WaitResult.FAILED])

    def test_stop_terminates(self) -> None:
        """`stop` asks the process to exit, and its exit is a clean stop, not a crash."""
        self.managed.start()
        self.managed.stop()
        self.assertTrue(self.process.terminated)
        self.assertEqual(self.managed.state, ManagedState.STARTING)
        self.process.exit(0)
        self.assertEqual(self.states, [ManagedState.STARTING, ManagedState.STOPPED])
        self.assertFalse(self.process.killed)
        self.managed.stop()
        self.assertEqual(self.states, [ManagedState.STARTING, ManagedState.STOPPED])

    def test_stop_kills_after_grace_period(self) -> None:
        """A process that ignores `terminate` is killed when the grace period ends."""
        self.managed.start()
        self.managed.stop()
        self.assertFalse(self.process.killed)
        # The grace period's timer, fired directly rather than waited for:
        self.managed._kill_timer.timeout.emit()  # pylint: disable=protected-access
        self.assertTrue(self.process.killed)
        self.process.exit(-9)
        self.assertEqual(self.managed.state, ManagedState.STOPPED)

    def test_stop_while_waiting_fails_wait(self) -> None:
        """Stopping during a wait fails the wait, and the cancelled poll's result is ignored."""
        self.managed.start()
        self.managed.wait_until_ready(poll_interval_seconds=0)
        self.managed.stop()
        self.assertEqual(self.wait_results, [WaitResult.FAILED])
        self.health_responses = [list(EXPECTED_ARGV)]
        self._run_poll()
        self.process.exit(0)
        self.assertEqual(self.wait_results, [WaitResult.FAILED])
        self.assertEqual(self.states, [ManagedState.STARTING, ManagedState.STOPPED])

    def test_log_lines_reach_signal_on_main_thread(self) -> None:
        """Output is split into lines across reads, including split line breaks and characters, and flushed on exit."""
        self.managed.start()
        snowman = '☃'.encode('utf-8')
        for chunk in (b'Starting server\r', b'\nTo see the GUI go to: http://127.0.0.1:8189\n',
                      b'progress 50%\rprogress 100%\n', b'weather: ' + snowman[:1], snowman[1:] + b'\n',
                      b'last line without break'):
            self.process.write_output(chunk)
        self.process.exit(0)
        self.assertEqual(self.log_lines, ['Starting server', 'To see the GUI go to: http://127.0.0.1:8189',
                                          'progress 50%', 'progress 100%', 'weather: ☃',
                                          'last line without break'])
        main_thread = QApplication.instance().thread()
        self.assertTrue(all(thread is main_thread for thread in self.log_threads))

    def test_server_arguments_replace_port_and_listen(self) -> None:
        """Any `--port` or `--listen` in the launch command is replaced by the managed ones."""
        command = ['python', 'main.py', '--listen', '--port', '9000', '--cpu', '--listen=0.0.0.0', '--port=1']
        self.assertEqual(server_arguments(command, 8200),
                         ['main.py', '--cpu', '--listen', LISTEN_HOST, '--port', '8200'])
        self.assertEqual(server_arguments(['python', 'main.py', '--listen', '0.0.0.0'], 8200),
                         ['main.py', '--listen', LISTEN_HOST, '--port', '8200'])

    def test_from_cache(self) -> None:
        """`from_cache` builds the saved install, or returns None when no launch command is saved."""
        self.assertIsNone(ManagedComfyUI.from_cache())
        cache = Cache()
        cache.set(Cache.MANAGED_COMFYUI_PATH, INSTALL_PATH)
        cache.set(Cache.MANAGED_COMFYUI_LAUNCH_COMMAND, LAUNCH_COMMAND)
        cache.set(Cache.MANAGED_COMFYUI_PORT, 8300)
        managed = ManagedComfyUI.from_cache()
        assert managed is not None
        self.assertEqual(managed.url, f'http://{LISTEN_HOST}:8300')
        self.assertEqual(managed.state, ManagedState.STOPPED)
        managed.deleteLater()
