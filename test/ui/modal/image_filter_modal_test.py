"""Tests that `ImageFilterModal` debounces input changes and keeps preview rendering off the calling thread."""
import sys
from typing import Any, Optional
from unittest.mock import patch

from PySide6.QtGui import QImage
from shiboken6 import delete, isValid
from PySide6.QtWidgets import QBoxLayout

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
        if isValid(self.modal):
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
        self.modal._param_inputs[0].set_value(value)

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

    def test_render_finishing_after_dialog_deleted_is_ignored(self) -> None:
        """A render that finishes after its dialog was deleted does not touch the deleted widgets."""
        task = self.started.pop(0)
        delete(self.modal)
        self.assertFalse(isValid(self.modal))
        errors: list[BaseException] = []
        # PySide reports an exception raised in a slot through sys.excepthook rather than raising it.
        with patch.object(sys, 'excepthook', lambda _type, value, _tb: errors.append(value)):
            task.run()
        self.assertEqual([], errors)


class ImageFilterModalLayoutTest(IntraPaintTestCase):
    """The preview sits beside the controls, fits the screen, and can show the original."""

    def setUp(self) -> None:
        super().setUp()
        self._patch = patch.object(AsyncTask, 'start', lambda task: task.run())
        self._patch.start()
        self.big = QImage(4000, 3000, QImage.Format.Format_ARGB32)
        self.big.fill(0xff00ff00)
        self.small = QImage(4, 4, QImage.Format.Format_ARGB32)
        self.small.fill(0xffff0000)
        self.modal = ImageFilterModal('Blur', 'desc', [Parameter('value', TYPE_INT, 1, 'value', 0, 100, 1)],
                                      lambda _: (lambda: self.big), lambda _: None,
                                      prepare_original=lambda: (lambda: self.small))

    def tearDown(self) -> None:
        self._patch.stop()
        self.modal.deleteLater()
        super().tearDown()

    def test_size_hint_ignores_image_size(self) -> None:
        """A large preview image doesn't enlarge the dialog."""
        self.assertLess(self.modal.sizeHint().width(), 1200)
        self.assertLess(self.modal.sizeHint().height(), 900)

    def test_apply_button_names_filter(self) -> None:
        """The confirm button carries the filter's name."""
        self.assertIn('Blur', self.modal._apply_button.text())  # pylint: disable=protected-access

    def test_layout_follows_aspect(self) -> None:
        """Wide windows put the preview left of the controls, tall windows put it above."""
        body = self.modal._body  # pylint: disable=protected-access
        self.modal.show()
        self.modal.resize(900, 500)
        self.assertEqual(QBoxLayout.Direction.LeftToRight, body.direction())
        self.modal.resize(500, 900)
        self.assertEqual(QBoxLayout.Direction.TopToBottom, body.direction())
        self.modal.resize(900, 500)
        self.assertEqual(QBoxLayout.Direction.LeftToRight, body.direction())

    def test_compare_button_shows_original(self) -> None:
        """Holding the compare button shows the original image, and releasing it shows the preview."""
        preview = self.modal._preview  # pylint: disable=protected-access
        self.assertIs(preview.shown_image(), self.big)
        compare_button = self.modal._compare_button  # pylint: disable=protected-access
        compare_button.pressed.emit()
        self.assertIs(preview.shown_image(), self.small)
        compare_button.released.emit()
        self.assertIs(preview.shown_image(), self.big)
