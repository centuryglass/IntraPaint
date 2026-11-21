"""Shared base class and helpers for IntraPaint tests.

- `IntraPaintTestCase` installs a fresh `AppContext` (`install_test_context`) before and after every test, so each
  test gets new global services.
- `assert_image_matches_golden` compares a rendered image to a committed golden image. It's the one code path for
  golden images.
- `assert_images_equal` compares two images the test produced, saving both to a temporary directory on failure.
- `assert_json_matches_snapshot` compares JSON-compatible data to a committed JSON snapshot.

All three assertions are also available as IntraPaintTestCase methods.

`press_key` sends a key press the way a window receives one, so `HotkeyFilter` bindings handle it.

Updating a golden image or snapshot: run the failing test, check the `*_tested.png` or `*_tested.json` it wrote next
to the committed file, then replace the committed file with it. A test that passes deletes any `*_tested` file left
over from an earlier failure.
"""
import difflib
import importlib
import json
import os
import pkgutil
import shutil
import sys
import tempfile
import unittest
from typing import Any, Optional
from unittest.mock import MagicMock

import numpy as np
from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt, SignalInstance
from PySide6.QtGui import QImage, QKeyEvent, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLayoutItem, QWidget
from shiboken6 import getAllValidWrappers

from src.app_context import AppContext, AppService, install_context
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.ui.theme import apply_appearance_config
from test import qt_cycles

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_RESOURCE_DIR = os.path.join(PROJECT_ROOT, 'test', 'resources')
TEST_IMAGE_DIR = os.path.join(TEST_RESOURCE_DIR, 'test_images')

TESTED_IMAGE_SUFFIX = '_tested.png'
TESTED_SNAPSHOT_SUFFIX = '_tested.json'

# Image comparisons convert both images to this format, so a format difference alone can't fail a test. Switching it to
# ARGB32 breaks existing goldens: unpremultiplying rounds visually identical pixels to different values.
COMPARISON_FORMAT = QImage.Format.Format_ARGB32_Premultiplied


def apply_fixture_appearance() -> None:
    """Applies the style, theme and font size from the app config fixture to the application."""
    apply_appearance_config(AppConfig())


def app_appearance() -> dict[str, Any]:
    """Returns the application-wide font, style, stylesheet and palette, which every widget's layout depends on."""
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    style = app.style()
    return {
        'font': app.font().toString(),
        'style': f'{type(style).__name__}({style.name()})',
        'stylesheet': app.styleSheet(),
        'palette': QPalette(app.palette())
    }


def held_input() -> list[str]:
    """Returns the mouse buttons and keyboard modifiers the application still counts as held, by name.

    `QTest` press events set this state and only a matching release clears it, so a test that presses without
    releasing leaves it set for every later test. Listeners such as `GenerationAreaController.follow_selection` wait
    while a button is held.
    """
    buttons = QApplication.mouseButtons()
    modifiers = QApplication.keyboardModifiers()
    held = [button.name for button in Qt.MouseButton if button != Qt.MouseButton.NoButton and button in buttons
            and button.value & (button.value - 1) == 0]
    held.extend(modifier.name for modifier in Qt.KeyboardModifier
                if modifier != Qt.KeyboardModifier.NoModifier and modifier in modifiers
                and modifier.value & (modifier.value - 1) == 0)
    return held


def release_held_input() -> None:
    """Clears the held mouse buttons and keyboard modifiers by sending releases to a temporary widget."""
    widget = QWidget()
    widget.show()
    try:
        for button in Qt.MouseButton:
            if button != Qt.MouseButton.NoButton and button in QApplication.mouseButtons():
                QTest.mouseRelease(widget, button)
        QTest.keyRelease(widget, Qt.Key.Key_unknown, Qt.KeyboardModifier.NoModifier)
    finally:
        widget.hide()
        widget.deleteLater()


# The committed config fixture each test context's configs load a copy of:
CONFIG_FIXTURES: dict[type, str] = {
    AppConfig: 'app_config_test.json',
    KeyConfig: 'key_config_test.json',
    Cache: 'cache_test.json'
}
_config_copy_dir: Optional[str] = None


def install_test_context() -> AppContext:
    """Installs and returns a fresh `AppContext` whose configs load new copies of the `CONFIG_FIXTURES` files.

    The copies are rewritten for every context, in one temporary directory, so a test that saves config changes can't
    change the committed fixtures or what the next test loads. `remove_test_config_copies` deletes the directory.
    """
    global _config_copy_dir  # pylint: disable=global-statement
    if _config_copy_dir is None:
        _config_copy_dir = tempfile.mkdtemp(prefix='intrapaint-test-config-')
    arguments: dict[type, tuple[str]] = {}
    for config_class, file_name in CONFIG_FIXTURES.items():
        copy_path = os.path.join(_config_copy_dir, file_name)
        shutil.copyfile(os.path.join(TEST_RESOURCE_DIR, file_name), copy_path)
        arguments[config_class] = (copy_path,)
    context = AppContext(arguments)
    install_context(context)
    return context


def remove_test_config_copies() -> None:
    """Deletes the directory of config copies `install_test_context` writes to."""
    global _config_copy_dir  # pylint: disable=global-statement
    if _config_copy_dir is not None:
        shutil.rmtree(_config_copy_dir, ignore_errors=True)
        _config_copy_dir = None


def import_src_modules() -> None:
    """Imports every module under `src/` except the legacy `src/glid_3_xl/`, skipping any that fail to import (missing
    optional dependencies)."""
    src_dir = os.path.join(PROJECT_ROOT, 'src')
    for module_info in pkgutil.walk_packages([src_dir], prefix='src.'):
        if module_info.name.startswith('src.glid_3_xl'):
            continue
        try:
            importlib.import_module(module_info.name)
        except ImportError:
            continue


def stored_service_instances() -> list[str]:
    """Returns the module-level and class-level attributes under `src/` that hold a global service instance, by name.

    Such an attribute keeps the instance of the context that was installed when it was set, after a new context
    replaces it."""
    import_src_modules()
    found: list[str] = []
    for module_name, module in list(sys.modules.items()):
        if not module_name.startswith('src.') or module_name.startswith('src.glid_3_xl'):
            continue
        for name, member in list(vars(module).items()):
            if isinstance(type(member), AppService):
                found.append(f'{module_name}.{name}')
            elif isinstance(member, type) and member.__module__ == module_name:
                found.extend(f'{module_name}.{member.__qualname__}.{attribute}'
                             for attribute, value in list(vars(member).items())
                             if isinstance(type(value), AppService))
    return sorted(found)


def parentless_widgets() -> set[QWidget]:
    """Returns every widget with no parent, or an empty set when no QApplication exists."""
    if QApplication.instance() is None:
        return set()
    return {widget for widget in QApplication.topLevelWidgets() if widget.parentWidget() is None}


def delete_widgets_created_since(existing: set[QWidget]) -> None:
    """Deletes every widget with no parent that isn't in `existing`, along with its children.

    A widget connected to a closure that captures it, from one of its own children's signals, is a reference cycle
    that passes through Qt, so Python never collects it. Deleting it through Qt is the only way to free it.
    """
    if QApplication.instance() is None:
        return
    for widget in parentless_widgets() - existing:
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def press_key(widget: QWidget, key: Qt.Key, modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
    """Sends a key press to the QWindow of a widget's window, which forwards it to that window's focus widget.

    `HotkeyFilter` only sees key presses sent to a QWindow, so this watches the window first. The window doesn't need
    to be shown or focused.
    """
    window = widget.window()
    window.winId()  # Creates the QWindow.
    handle = window.windowHandle()
    assert handle is not None
    HotkeyFilter.instance().watch_window(handle)
    QApplication.sendEvent(handle, QKeyEvent(QEvent.Type.KeyPress, key, modifiers))


def tested_image_path(golden_path: str) -> str:
    """Returns the path where a golden comparison writes the tested image when it fails."""
    return os.path.splitext(golden_path)[0] + TESTED_IMAGE_SUFFIX


def _image_pixels(image: QImage) -> np.ndarray:
    """Returns a 32-bit image's pixels as a (height, width, 4) array, without line padding."""
    assert image.format() == COMPARISON_FORMAT
    width, height = image.width(), image.height()
    line_bytes = np.frombuffer(image.constBits(), dtype=np.uint8).reshape((height, image.bytesPerLine()))
    return line_bytes[:, :width * 4].reshape((height, width, 4))


def _describe_difference(actual: QImage, expected: QImage) -> str:
    if actual.size() != expected.size():
        return f'size {actual.width()}x{actual.height()} != expected {expected.width()}x{expected.height()}'
    differences = np.abs(_image_pixels(actual).astype(np.int16) - _image_pixels(expected).astype(np.int16))
    differing_pixels = int(np.count_nonzero(differences.max(axis=2)))
    pixel_count = actual.width() * actual.height()
    return (f'{differing_pixels} of {pixel_count} pixels differ, by up to {int(differences.max())} in a channel '
            '(compared premultiplied)')


def assert_image_matches_golden(actual: QImage, golden_path: str, msg: Optional[str] = None) -> None:
    """Asserts that an image has the same pixels as a committed golden image.

    Both images are converted to COMPARISON_FORMAT before comparing. On failure, the tested image is saved next to the
    golden as `<golden name>_tested.png` so it can be checked by eye and committed as the new golden if it's correct.
    That includes a missing golden, so a new golden image can be created by running its test once.

    Parameters
    ----------
        actual: QImage
            The image the test produced.
        golden_path: str
            Path to the committed golden image, absolute or relative to the project root.
        msg: Optional[str]
            Extra context to include in the failure message.
    """
    if not os.path.isabs(golden_path):
        golden_path = os.path.join(PROJECT_ROOT, golden_path)
    tested_path = tested_image_path(golden_path)
    actual = actual.convertToFormat(COMPARISON_FORMAT)
    golden = QImage(golden_path)
    if golden.isNull():
        problem = f'golden image {golden_path} is missing or unreadable'
    else:
        golden = golden.convertToFormat(COMPARISON_FORMAT)
        if actual == golden:
            if os.path.isfile(tested_path):
                os.remove(tested_path)
            return
        problem = f'image does not match golden {golden_path}: {_describe_difference(actual, golden)}'
    if not actual.save(tested_path):
        raise AssertionError(f'{problem}, and saving the tested image to {tested_path} failed')
    message = f'{problem}. Check {tested_path} by eye, and replace the golden with it if it is correct.'
    raise AssertionError(message if msg is None else f'{msg}: {message}')


def assert_images_equal(actual: QImage, expected: QImage, msg: Optional[str] = None) -> None:
    """Asserts that two images have the same pixels, comparing them in COMPARISON_FORMAT.

    Use this when the test computes the expected image itself, and assert_image_matches_golden when it's committed.
    On failure, both images are saved to a new temporary directory, named in the failure message.
    """
    actual = actual.convertToFormat(COMPARISON_FORMAT)
    expected = expected.convertToFormat(COMPARISON_FORMAT)
    if actual == expected:
        return
    problem = f'images differ: {_describe_difference(actual, expected)}'
    output_dir = tempfile.mkdtemp(prefix='intrapaint-image-diff-')
    actual_path = os.path.join(output_dir, 'actual.png')
    expected_path = os.path.join(output_dir, 'expected.png')
    if actual.save(actual_path) and expected.save(expected_path):
        problem = f'{problem}. Saved {actual_path} and {expected_path}'
    raise AssertionError(problem if msg is None else f'{msg}: {problem}')


def _snapshot_text(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + '\n'


def assert_json_matches_snapshot(actual: Any, snapshot_path: str, msg: Optional[str] = None) -> None:
    """Asserts that JSON-compatible data matches a committed JSON snapshot file.

    Data is compared as text, serialized with sorted keys and two-space indents, which is also the committed format.
    On failure, the actual data is saved next to the snapshot as `<snapshot name>_tested.json`, and the failure
    message includes a diff. That includes a missing snapshot, so a new snapshot can be created by running its test
    once.

    Parameters
    ----------
        actual: Any
            The data the test produced. It must be serializable with json.dumps.
        snapshot_path: str
            Path to the committed snapshot, absolute or relative to the project root.
        msg: Optional[str]
            Extra context to include in the failure message.
    """
    if not os.path.isabs(snapshot_path):
        snapshot_path = os.path.join(PROJECT_ROOT, snapshot_path)
    tested_path = os.path.splitext(snapshot_path)[0] + TESTED_SNAPSHOT_SUFFIX
    actual_text = _snapshot_text(actual)
    if os.path.isfile(snapshot_path):
        with open(snapshot_path, encoding='utf-8') as snapshot_file:
            expected_text = snapshot_file.read()
        if actual_text == expected_text:
            if os.path.isfile(tested_path):
                os.remove(tested_path)
            return
        diff = ''.join(difflib.unified_diff(expected_text.splitlines(keepends=True),
                                            actual_text.splitlines(keepends=True), snapshot_path, tested_path))
        problem = f'data does not match snapshot {snapshot_path}:\n{diff}'
    else:
        problem = f'snapshot {snapshot_path} is missing'
        os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
    with open(tested_path, 'w', encoding='utf-8') as tested_file:
        tested_file.write(actual_text)
    message = f'{problem}\nCheck {tested_path}, and replace the snapshot with it if it is correct.'
    raise AssertionError(message if msg is None else f'{msg}: {message}')


def layout_item_wrapper_count() -> int:
    """Returns the number of live Python wrappers of layout items (`QWidgetItem`, `QSpacerItem` and the like).

    Layouts are layout items too, and are not counted. Wrappers come from Python code that constructs an item, from
    `QLayout.itemAt`, `itemAtPosition` and `takeAt`, and from `addLayout` given a filled child. A test that leaves
    some behind ran code that wraps items it should not keep. See `test/layout_item_calls_test.py`.
    """
    return sum(1 for wrapper in getAllValidWrappers() if isinstance(wrapper, QLayoutItem)
               and not isinstance(wrapper, QObject))


class IntraPaintTestCase(unittest.TestCase):
    """Base class for IntraPaint tests, keeping tests independent of the order they run in.

    A fresh `AppContext` is installed before each test (`install_test_context`), so it gets new config, undo history,
    app state and hotkey services loaded from the test config fixtures. Another is installed after it, closing the
    test's services, so it can't leave state or connections behind for tests that don't use this class. Widgets with
    no parent that the test created are deleted after it, with their children, and the system clipboard is cleared. The working directory is the project
    root during every test, since resources and the config definitions load from paths relative to it.

    A test fails if it changes the application's font, style, stylesheet or palette without restoring them, since every
    later test's layout depends on them. The fixture appearance is reapplied after such a test.

    A test also fails if it leaves a mouse button or keyboard modifier held (`held_input`), since the state is
    application-wide. It is released after such a test.

    Subclasses that override setUp or tearDown must call the superclass implementation: setUp first, tearDown last.
    """

    def setUp(self) -> None:
        super().setUp()
        os.chdir(PROJECT_ROOT)
        install_test_context()
        self._existing_widgets = parentless_widgets()
        self._layout_item_wrappers = layout_item_wrapper_count()
        self._appearance = app_appearance()

    def tearDown(self) -> None:
        install_test_context()
        # Clipboard content set from Python must not outlive the test: the offscreen platform deletes it after the
        # interpreter shuts down, which crashes the test process on exit.
        QApplication.clipboard().clear()
        delete_widgets_created_since(self._existing_widgets)
        del self._existing_widgets
        qt_cycles.collect()
        leaked = layout_item_wrapper_count() - self._layout_item_wrappers
        del self._layout_item_wrappers
        changed_appearance = [key for key, value in app_appearance().items() if value != self._appearance[key]]
        del self._appearance
        if len(changed_appearance) > 0:
            apply_fixture_appearance()
        held = held_input()
        if len(held) > 0:
            release_held_input()
        super().tearDown()
        self.assertEqual(held, [], 'The test left mouse buttons or keyboard modifiers held without releasing them')
        self.assertLessEqual(leaked, 0, f'{leaked} layout item wrappers outlived the test (see'
                                        f' layout_item_wrapper_count)')
        self.assertEqual(changed_appearance, [], 'The test changed the application appearance without restoring it')

    def connect_mock(self, signal: SignalInstance) -> MagicMock:
        """Returns a MagicMock connected to `signal`, disconnected and cleared when the test ends.

        Qt holds a connected mock where the garbage collector can't see it, so a mock left connected keeps every
        argument it recorded alive for the rest of the run. A `MagicMock` is itself a reference cycle, so its recorded
        arguments are also cleared, or the cycle check counts a recorded wrapper such as the signal's sender.
        """
        listener = MagicMock()
        signal.connect(listener)

        def _release() -> None:
            signal.disconnect(listener)
            listener.reset_mock()
        self.addCleanup(_release)
        return listener

    def assert_image_matches_golden(self, actual: QImage, golden_path: str, msg: Optional[str] = None) -> None:
        """Asserts that an image has the same pixels as a committed golden image. See assert_image_matches_golden."""
        assert_image_matches_golden(actual, golden_path, msg)

    def assert_images_equal(self, actual: QImage, expected: QImage, msg: Optional[str] = None) -> None:
        """Asserts that two images have the same pixels. See assert_images_equal."""
        assert_images_equal(actual, expected, msg)

    def assert_json_matches_snapshot(self, actual: Any, snapshot_path: str, msg: Optional[str] = None) -> None:
        """Asserts that JSON-compatible data matches a committed snapshot. See assert_json_matches_snapshot."""
        assert_json_matches_snapshot(actual, snapshot_path, msg)
