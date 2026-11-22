"""Tests StrokeSelectionModal."""
from unittest.mock import patch

from PySide6.QtGui import QColor

from src.config.cache import Cache
from src.controller import color_controller
from src.image.layers.image_stack import StrokePosition
from src.ui.modal.stroke_selection_modal import StrokeSelectionModal
from test.base_test_case import IntraPaintTestCase


class StrokeSelectionModalTest(IntraPaintTestCase):
    """Tests StrokeSelectionModal."""

    def test_opens_with_remembered_values_and_foreground(self) -> None:
        """The dialog starts from the cached width and position, and the current foreground color."""
        Cache().set(Cache.STROKE_SELECTION_WIDTH, 7)
        Cache().set(Cache.STROKE_SELECTION_POSITION, StrokePosition.OUTSIDE.value)
        color_controller.set_foreground(QColor(10, 20, 30))
        modal = StrokeSelectionModal()
        with patch.object(StrokeSelectionModal, 'exec', lambda _: modal._confirm()):
            self.assertEqual((QColor(10, 20, 30), 7, StrokePosition.OUTSIDE), modal.show_stroke_modal())

    def test_confirm_saves_and_cancel_does_not(self) -> None:
        """Confirming saves the width and position, and canceling returns None and saves nothing."""
        modal = StrokeSelectionModal()
        modal._width_field.setValue(12)
        modal._position_control.set_value(StrokePosition.INSIDE.value)
        with patch.object(StrokeSelectionModal, 'exec', lambda _: None):
            self.assertIsNone(modal.show_stroke_modal())
        self.assertNotEqual(12, Cache().get(Cache.STROKE_SELECTION_WIDTH))
        modal = StrokeSelectionModal()
        modal._width_field.setValue(12)
        modal._position_control.set_value(StrokePosition.INSIDE.value)
        with patch.object(StrokeSelectionModal, 'exec', lambda _: modal._confirm()):
            result = modal.show_stroke_modal()
        assert result is not None
        self.assertEqual((12, StrokePosition.INSIDE), result[1:])
        self.assertEqual(12, Cache().get(Cache.STROKE_SELECTION_WIDTH))
        self.assertEqual(StrokePosition.INSIDE.value, Cache().get(Cache.STROKE_SELECTION_POSITION))
