"""Shared setup for the request-payload snapshot tests of the Stable Diffusion generators.

These are characterization tests: each one sets cached generation settings, runs a generator's request-building path
synchronously against `FakeSdBackend`, and compares the POST requests it sent with a committed JSON snapshot under
`SNAPSHOT_DIR`. A snapshot diff means a request changed, so a change that alters one must explain the diff.

`run_upscale` also drives the full upscale path synchronously, so tests can check how the result is applied to the
image stack and its undo history.
"""
import os
import sys
from argparse import Namespace
from typing import Any, Optional
from unittest import mock
from unittest.mock import MagicMock

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QApplication

from src.api.controlnet.controlnet_constants import CONTROLNET_REUSE_IMAGE_CODE
from src.api.controlnet.controlnet_model import ControlNetModel
from src.api.controlnet.controlnet_preprocessor import ControlNetPreprocessor
from src.api.controlnet.controlnet_unit import ControlNetUnit, ControlKeyType
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.image_generator import ImageGenerator
from src.image.layers.image_stack import ImageStack
from src.undo_stack import UndoStack
from src.util.async_task import AsyncTask
from src.util.shared_constants import UPSCALED_LAYER_NAME
from test.base_test_case import IntraPaintTestCase, TEST_IMAGE_DIR, PROJECT_ROOT
from test.controller.image_generation.fake_sd_backend import FakeSdBackend, RecordedRequest, snapshot_requests

app = QApplication.instance() or QApplication(sys.argv)

SNAPSHOT_DIR = os.path.join(PROJECT_ROOT, 'test', 'resources', 'sd_request_snapshots')
SOURCE_IMAGE = os.path.join(TEST_IMAGE_DIR, 'source.png')
FAKE_SERVER_URL = 'http://sd.invalid:7860'

GENERATION_AREA = QRect(150, 50, 300, 300)
GENERATION_SIZE = QSize(512, 512)
SELECTION_BOUNDS = QRect(250, 150, 80, 60)
# Below and right of the selection, inside the generation area, so it stretches the inpaint full-res crop:
CONTEXT_PIN = QPoint(420, 320)
UPSCALE_SIZE = QSize(1200, 800)

LORA_NAME = 'detail_lora'
LORA_FILE = 'detail_lora.safetensors'
TEST_SEED = 1234


class StatusRecorder:
    """Stands in for the status SignalInstance a generator emits progress and seed updates through."""

    def __init__(self) -> None:
        self.emitted: list[Any] = []

    def emit(self, value: Any) -> None:
        """Records an emitted value."""
        self.emitted.append(value)


class SdGeneratorTestCase(IntraPaintTestCase):
    """Builds an image stack and cached generation settings, and serves Stable Diffusion requests offline.

    Subclasses set `snapshot_subdir` and create `self.generator` in setUp, after calling this setUp.
    """

    snapshot_subdir = ''

    def setUp(self) -> None:
        super().setUp()
        self.backend = FakeSdBackend()
        self.backend.start()
        self.addCleanup(self.backend.stop)

        self.image_stack = ImageStack(QSize(600, 400), GENERATION_AREA.size(), QSize(8, 8), QSize(10240, 10240))
        source_image = QImage(SOURCE_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        assert not source_image.isNull(), f'failed to load {SOURCE_IMAGE}'
        self.image_stack.create_layer('source', source_image)
        self.image_stack.generation_area = GENERATION_AREA
        with self.image_stack.selection_layer.borrow_image() as mask_image:
            painter = QPainter(mask_image)
            painter.fillRect(SELECTION_BOUNDS, Qt.GlobalColor.black)
            painter.end()

        cache = Cache()
        cache.restore_default_options(Cache.EDIT_MODE)
        cache.set(Cache.GENERATION_SIZE, GENERATION_SIZE)
        cache.set(Cache.PROMPT, f'a lighthouse on a cliff <lora:{LORA_NAME}:0.8>')
        cache.set(Cache.NEGATIVE_PROMPT, 'blurry')
        cache.set(Cache.SEED, str(TEST_SEED))
        cache.set(Cache.BATCH_SIZE, 2)
        cache.set(Cache.BATCH_COUNT, 2)
        cache.set(Cache.SAMPLING_STEPS, 20)
        cache.set(Cache.GUIDANCE_SCALE, 6.5)
        cache.set(Cache.DENOISING_STRENGTH, 0.6)
        cache.set(Cache.INPAINT_FULL_RES, False)
        cache.set(Cache.INPAINT_FULL_RES_PADDING, 32)
        cache.set(Cache.SD_MODEL, 'dreamshaper_8.safetensors', add_missing_options=True)
        cache.set(Cache.LORA_MODELS, [{'name': LORA_NAME, 'alias': LORA_NAME, 'path': LORA_FILE}])
        AppConfig().set(AppConfig.MASK_BLUR, 4)

        self.status = StatusRecorder()
        self.generated_images: dict[int, QImage] = {}
        self.generator: Optional[ImageGenerator] = None

    @staticmethod
    def server_args() -> Namespace:
        """Returns the command line arguments a generator reads its server URL from."""
        return Namespace(server_url=FAKE_SERVER_URL)

    def capture_generated_images(self, generator: ImageGenerator) -> None:
        """Records generated images on the test case, in place of loading them into the main window."""

        def _cache_generated_image(image: QImage, index: int) -> None:
            self.generated_images[index] = image

        generator._cache_generated_image = _cache_generated_image  # type: ignore # pylint: disable=protected-access

    def run_generate(self) -> None:
        """Runs the generator's generate method on the current settings, in the calling thread."""
        assert self.generator is not None
        image, mask = self.generator.get_generation_inputs()
        self.generator.generate(self.status, image, mask)  # type: ignore

    def run_upscale(self, new_size: QSize) -> None:
        """Runs the generator's upscale method to completion in the calling thread, applying the result."""
        assert self.generator is not None
        self.generator._window = MagicMock()  # type: ignore # pylint: disable=protected-access
        with mock.patch.object(AsyncTask, 'start', AsyncTask.run):
            self.assertTrue(self.generator.upscale(new_size))

    def assert_upscale_applied_as_one_undo_step(self) -> None:
        """Upscaling resizes the image, adds the result as the active layer, and one undo reverts both."""
        initial_size = self.image_stack.size
        initial_layers = self.image_stack.all_layers()
        source_layer = self.image_stack.active_layer
        initial_transform = source_layer.transform
        UndoStack().clear()
        self.run_upscale(UPSCALE_SIZE)
        self.assertEqual(self.image_stack.size, UPSCALE_SIZE)
        active_layer = self.image_stack.active_layer
        self.assertEqual(active_layer.name, UPSCALED_LAYER_NAME)
        self.assertEqual(active_layer.size, UPSCALE_SIZE)
        self.assertEqual(source_layer.transform.m11(), UPSCALE_SIZE.width() / initial_size.width())
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(self.image_stack.size, initial_size)
        self.assertEqual(self.image_stack.all_layers(), initial_layers)
        self.assertEqual(source_layer.transform, initial_transform)
        UndoStack().redo()
        self.assertEqual(self.image_stack.size, UPSCALE_SIZE)
        self.assertEqual(len(self.image_stack.all_layers()), len(initial_layers) + 1)

    @staticmethod
    def controlnet_unit(key_type: ControlKeyType, model_name: str, preprocessor: ControlNetPreprocessor,
                        image_string: str = CONTROLNET_REUSE_IMAGE_CODE) -> str:
        """Returns a serialized, enabled ControlNet unit."""
        unit = ControlNetUnit(key_type)
        unit.enabled = True
        unit.model = ControlNetModel(model_name)
        unit.preprocessor = preprocessor
        unit.image_string = image_string
        unit.control_strength.value = 0.75
        unit.control_start.value = 0.1
        unit.control_end.value = 0.9
        return unit.serialize()

    def assert_requests_match_snapshot(self, name: str, requests: Optional[list[RecordedRequest]] = None,
                                       replacements: Optional[dict[str, str]] = None) -> None:
        """Compares recorded POST requests with the committed snapshot `<snapshot_subdir>/<name>.json`."""
        if requests is None:
            requests = self.backend.posts()
        snapshot_path = os.path.join(SNAPSHOT_DIR, self.snapshot_subdir, f'{name}.json')
        self.assert_json_matches_snapshot(snapshot_requests(requests, replacements), snapshot_path)


def solid_image(size: QSize, color: QColor | Qt.GlobalColor) -> QImage:
    """Returns an opaque single-color image, used as fake generated output."""
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return image
