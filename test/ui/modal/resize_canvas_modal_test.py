"""Tests ResizeCanvasModal's size constraints, anchor grid and preview dragging."""
from PySide6.QtCore import QPoint, QSize
from PySide6.QtWidgets import QApplication, QLabel

from src.config.application_config import AppConfig
from src.image.layers.image_stack import ImageStack
from src.ui.input_fields import geometry_block
from src.ui.modal.controls_column import ControlsColumn
from src.ui.modal.resize_canvas_modal import ResizeCanvasModal
from src.undo_stack import UndoStack
from test.base_test_case import IntraPaintTestCase


def _modal(size: QSize = QSize(100, 80)) -> ResizeCanvasModal:
    return ResizeCanvasModal(ImageStack(size, size, size, size, UndoStack()))


class ResizeCanvasModalTest(IntraPaintTestCase):
    """Tests ResizeCanvasModal."""

    def test_minimum_size_does_not_follow_current_size(self) -> None:
        """Enlarging the modal leaves its minimum size hint unchanged, so it can shrink again."""
        modal = _modal(QSize(1024, 1024))
        modal.show()
        initial_minimum = modal.minimumSizeHint()
        modal.resize(1200, 1200)
        modal.resize(400, 400)
        self.assertEqual(modal.minimumSizeHint(), initial_minimum)
        self.assertEqual(modal.size(), QSize(400, 400).expandedTo(initial_minimum))

    def test_maximum_size_label_does_not_clip_controls(self) -> None:
        """The size label wraps instead of widening the side-by-side controls."""
        modal = _modal()
        try:
            modal.resize(960, 600)
            modal.show()
            maximum = AppConfig().get(AppConfig.MAX_IMAGE_SIZE)
            modal._geometry.field(geometry_block.WIDTH).set_value(maximum.width())
            modal._geometry.field(geometry_block.HEIGHT).set_value(maximum.height())
            # Model a long localized label without changing the test runner's language.
            modal._size_label.setText('Maximum canvas size 10000 x 10000 with a long translated size suffix')
            QApplication.processEvents()
            controls = modal._controls
            self.assertLessEqual(controls.widget().minimumSizeHint().width(), controls.viewport().width())
            self.assertEqual(controls.horizontalScrollBar().maximum(), 0)
        finally:
            modal.hide()

    def test_controls_column_can_scroll_genuinely_wide_content(self) -> None:
        """A control wider than the fixed column is reachable without widening the dialog."""
        label = QLabel('A single wide control')
        label.setMinimumWidth(500)
        column = ControlsColumn(label, 350)
        try:
            column.resize(350, 150)
            column.show()
            QApplication.processEvents()
            scrollbar = column.horizontalScrollBar()
            self.assertTrue(scrollbar.isVisible())
            self.assertGreater(scrollbar.maximum(), 0)
            scrollbar.setValue(scrollbar.maximum())
            self.assertEqual(label.geometry().right(), column.viewport().rect().right())
        finally:
            column.hide()

    def test_offset_fields_are_labelled_as_offsets(self) -> None:
        """The X and Y fields read as offsets, since they place the image within the new canvas."""
        modal = _modal()
        self.assertEqual(modal._geometry.field(geometry_block.X).label(), 'X-offset')  # pylint: disable=protected-access
        self.assertEqual(modal._geometry.field(geometry_block.Y).label(), 'Y-offset')  # pylint: disable=protected-access

    def test_anchor_places_content(self) -> None:
        """Choosing an anchor sets the offset that puts the old image at that cell."""
        modal = _modal()
        modal._geometry.field(geometry_block.WIDTH).set_value(200)  # pylint: disable=protected-access
        modal._geometry.field(geometry_block.HEIGHT).set_value(100)  # pylint: disable=protected-access
        modal._anchor_grid.anchorSelected.emit(1, 1)  # pylint: disable=protected-access
        size, offset = modal._new_size(), modal._offset()  # pylint: disable=protected-access
        self.assertEqual(size, QSize(200, 100))
        self.assertEqual(offset, QPoint(50, 10))
        modal._anchor_grid.anchorSelected.emit(2, 2)  # pylint: disable=protected-access
        self.assertEqual(modal._offset(), QPoint(100, 20))  # pylint: disable=protected-access

    def test_anchor_follows_size_changes(self) -> None:
        """A selected anchor keeps the content at that cell as the size changes."""
        modal = _modal()
        modal._anchor_grid.anchorSelected.emit(2, 2)  # pylint: disable=protected-access
        modal._geometry.field(geometry_block.WIDTH).set_value(180)  # pylint: disable=protected-access
        self.assertEqual(modal._offset(), QPoint(80, 0))  # pylint: disable=protected-access

    def test_preview_drag_moves_offset(self) -> None:
        """Dragging the preview sets the offset."""
        modal = _modal()
        modal._preview.offsetDragged.emit(QPoint(7, -3))  # pylint: disable=protected-access
        self.assertEqual(modal._offset(), QPoint(7, -3))  # pylint: disable=protected-access
        self.assertIsNone(modal._anchor_grid.anchor())  # pylint: disable=protected-access

    def test_confirm_returns_values(self) -> None:
        """Confirming returns the new size and offset; cancelling returns none."""
        modal = _modal()
        modal._geometry.field(geometry_block.WIDTH).set_value(120)  # pylint: disable=protected-access
        modal._confirm()  # pylint: disable=protected-access
        modal.exec = lambda: 0  # type: ignore[method-assign]
        self.assertEqual(modal.show_resize_modal(), (QSize(120, 80), QPoint(0, 0)))
        modal._cancel()  # pylint: disable=protected-access
        self.assertEqual(modal.show_resize_modal(), (None, None))
