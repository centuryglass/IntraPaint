"""Tests that `ImageFilterModal` debounces input changes and keeps preview rendering off the calling thread."""
from typing import Any, Optional
from unittest.mock import patch

from PySide6.QtGui import QImage

from src.ui.modal.image_filter_modal import ImageFilterModal
from src.util.async_task import AsyncTask
from src.util.parameter import Parameter, TYPE_INT
from test.base_test_case import IntraPaintTestCase


class ImageFilterModalPreviewTest(IntraPaintTestCase):
    """Preview renders are queued, not run inline, and changes made during a render collapse into one more render."""

    def setUp(self) -> None:
        super().setUp()
        self.prepared: list[list[Any]] = []
        self.started: list[AsyncTask] = []
        self._patch = patch.object(AsyncTask, 'start', lambda task: self.started.append(task))
        self._patch.start()
        self.modal = ImageFilterModal('test', 'test filter', [Parameter('value', TYPE_INT, 1, 'value', 0, 100, 1)],
                                      self._prepare, lambda _: None)

    def tearDown(self) -> None:
        self._patch.stop()
        self.modal.deleteLater()
        super().tearDown()

    def _prepare(self, values: list[Any]):
        self.prepared.append(values)
        return lambda: QImage(4, 4, QImage.Format.Format_ARGB32)

    def _finish_render(self) -> None:
        self.started.pop(0).run()

    def _timer_active(self) -> bool:
        return self.modal._preview_timer.isActive()  # pylint: disable=protected-access

    def _fire_timer(self) -> None:
        """Runs what the debounce timer would run when it expires, without waiting for it."""
        self.modal._preview_timer.timeout.emit()  # pylint: disable=protected-access

    def _set_value(self, value: int) -> None:
        # pylint: disable-next=protected-access
        self.modal._param_inputs[0].setValue(value)

    def test_initial_preview_is_queued_not_run_inline(self) -> None:
        """Opening the dialog prepares one preview and leaves the render for the worker."""
        self.assertEqual(1, len(self.prepared))
        self.assertEqual(1, len(self.started))

    def test_input_changes_wait_for_debounce(self) -> None:
        """Changing a value starts the timer and prepares nothing until it fires."""
        self._finish_render()
        self._set_value(5)
        self._set_value(6)
        self.assertTrue(self._timer_active())
        self.assertEqual(1, len(self.prepared))
        self._fire_timer()
        self.assertEqual(2, len(self.prepared))
        self.assertEqual([6], self.prepared[-1])

    def test_changes_during_render_collapse_into_one_more_render(self) -> None:
        """Values entered while a render runs are skipped except the latest, which renders after it finishes."""
        for value in (5, 6, 7):
            self._set_value(value)
            self._fire_timer()
        self.assertEqual(1, len(self.prepared))
        self._finish_render()
        self.assertEqual(2, len(self.prepared))
        self.assertEqual([7], self.prepared[-1])
        self._finish_render()
        self.assertEqual(2, len(self.prepared))
        self.assertEqual(0, len(self.started))

    def test_finished_render_sets_preview_image(self) -> None:
        """The rendered image reaches the preview widget."""
        self._finish_render()
        image: Optional[QImage] = self.modal._preview.image  # pylint: disable=protected-access
        self.assertIsNotNone(image)
        assert image is not None
        self.assertEqual(4, image.width())
