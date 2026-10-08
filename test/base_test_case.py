"""Shared base class and helpers for IntraPaint tests.

- `IntraPaintTestCase` resets the singletons that carry state between tests, before and after every test.
- `assert_image_matches_golden` compares a rendered image to a committed golden image. It's the one code path for
  golden images.
- `assert_images_equal` compares two images the test produced, saving both to a temporary directory on failure.
- `assert_json_matches_snapshot` compares JSON-compatible data to a committed JSON snapshot.

All three assertions are also available as IntraPaintTestCase methods.

Updating a golden image or snapshot: run the failing test, check the `*_tested.png` or `*_tested.json` it wrote next
to the committed file, then replace the committed file with it. A test that passes deletes any `*_tested` file left
over from an earlier failure.
"""
import difflib
import json
import os
import tempfile
import unittest
from typing import Any, Optional

import numpy as np
from PySide6.QtGui import QImage

from src.config.a1111_config import A1111Config
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.undo_stack import UndoStack
from src.util.singleton import Singleton

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_RESOURCE_DIR = os.path.join(PROJECT_ROOT, 'test', 'resources')
TEST_IMAGE_DIR = os.path.join(TEST_RESOURCE_DIR, 'test_images')

TESTED_IMAGE_SUFFIX = '_tested.png'
TESTED_SNAPSHOT_SUFFIX = '_tested.json'

# Image comparisons convert both images to this format, so a format difference alone can't fail a test. Switching it to
# ARGB32 breaks existing goldens: unpremultiplying rounds visually identical pixels to different values.
COMPARISON_FORMAT = QImage.Format.Format_ARGB32_Premultiplied


def reset_singletons() -> None:
    """Discards all changes to config values and undo history, all config change connections, and all hotkey bindings
    and modifier connections."""
    # pylint: disable=protected-access
    AppConfig()._reset()
    KeyConfig()._reset()
    Cache()._reset()
    # A1111Config is only created when the WebUI generator connects. Creating it here would leave it in a state no
    # test expects.
    if A1111Config in Singleton._instances:
        A1111Config()._reset()
    UndoStack().clear()
    # HotkeyFilter needs a QApplication to construct, and an instance that doesn't exist has no state to reset.
    if HotkeyFilter.shared_instance is not None:
        HotkeyFilter.shared_instance._reset()


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


class IntraPaintTestCase(unittest.TestCase):
    """Base class for IntraPaint tests, keeping tests independent of the order they run in.

    Config values, config connections, the undo history and hotkey bindings are singletons that persist across tests.
    They're reset before each test, so it starts from the test config defaults, and again after it, so it can't leave
    state behind for tests that don't use this class. The working directory is the project root during every test, since resources
    and the config definitions load from paths relative to it.

    Subclasses that override setUp or tearDown must call the superclass implementation: setUp first, tearDown last.
    """

    def setUp(self) -> None:
        super().setUp()
        os.chdir(PROJECT_ROOT)
        reset_singletons()

    def tearDown(self) -> None:
        reset_singletons()
        super().tearDown()

    def assert_image_matches_golden(self, actual: QImage, golden_path: str, msg: Optional[str] = None) -> None:
        """Asserts that an image has the same pixels as a committed golden image. See assert_image_matches_golden."""
        assert_image_matches_golden(actual, golden_path, msg)

    def assert_images_equal(self, actual: QImage, expected: QImage, msg: Optional[str] = None) -> None:
        """Asserts that two images have the same pixels. See assert_images_equal."""
        assert_images_equal(actual, expected, msg)

    def assert_json_matches_snapshot(self, actual: Any, snapshot_path: str, msg: Optional[str] = None) -> None:
        """Asserts that JSON-compatible data matches a committed snapshot. See assert_json_matches_snapshot."""
        assert_json_matches_snapshot(actual, snapshot_path, msg)
