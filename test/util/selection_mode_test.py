"""Tests selection mode resolution from the add, subtract and replace modifiers, and how modes combine shapes with a
   selection."""
import numpy as np
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QImage, QPainterPath, QColor

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.util.visual.image_utils import image_data_as_numpy_8bit
from src.util.visual.selection_mode import SelectionMode, selection_mode_for_gesture, stored_selection_mode, \
    compose_selection_path, compose_selection_image
from test.base_test_case import IntraPaintTestCase

SHIFT = Qt.KeyboardModifier.ShiftModifier
ALT = Qt.KeyboardModifier.AltModifier
CTRL = Qt.KeyboardModifier.ControlModifier
META = Qt.KeyboardModifier.MetaModifier
SIZE = QSize(20, 10)
EXISTING = QRect(0, 0, 12, 10)
SHAPE = QRect(8, 2, 10, 6)


def _selection_image(rect: QRect) -> QImage:
    image = QImage(SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    image_data_as_numpy_8bit(image)[rect.top():rect.bottom() + 1, rect.left():rect.right() + 1, :] = 255
    return image


def _mask(image: QImage) -> np.ndarray:
    return image_data_as_numpy_8bit(image)[:, :, 3] > 0


def _rect_mask(rect: QRect) -> np.ndarray:
    return _mask(_selection_image(rect))


class SelectionModeTest(IntraPaintTestCase):
    """Tests SelectionMode and its helpers."""

    def test_stored_mode_defaults_to_add(self) -> None:
        """Add is the default mode."""
        self.assertEqual(stored_selection_mode(), SelectionMode.ADD)
        self.assertEqual(Cache().get(Cache.SELECTION_MODE), SelectionMode.ADD.value)

    def test_stored_mode_matches_cache_options(self) -> None:
        """Every mode is an option of the cache value."""
        Cache().restore_default_options(Cache.SELECTION_MODE)
        self.assertEqual(Cache().get_options(Cache.SELECTION_MODE), [mode.value for mode in SelectionMode])

    def test_modifiers_override_stored_mode(self) -> None:
        """Shift adds, Alt subtracts, both intersect, and no modifier keeps the stored mode."""
        for stored in SelectionMode:
            self.assertEqual(selection_mode_for_gesture(stored, Qt.KeyboardModifier.NoModifier), stored)
            self.assertEqual(selection_mode_for_gesture(stored, SHIFT), SelectionMode.ADD)
            self.assertEqual(selection_mode_for_gesture(stored, ALT), SelectionMode.SUBTRACT)
            self.assertEqual(selection_mode_for_gesture(stored, SHIFT | ALT), SelectionMode.INTERSECT)

    def test_replace_modifier_takes_priority(self) -> None:
        """Ctrl+Shift replaces, also with Alt held, and Ctrl alone or Ctrl+Alt don't."""
        for stored in SelectionMode:
            self.assertEqual(selection_mode_for_gesture(stored, CTRL | SHIFT), SelectionMode.REPLACE)
            self.assertEqual(selection_mode_for_gesture(stored, CTRL | SHIFT | ALT), SelectionMode.REPLACE)
        self.assertEqual(selection_mode_for_gesture(SelectionMode.ADD, CTRL), SelectionMode.ADD)
        self.assertEqual(selection_mode_for_gesture(SelectionMode.ADD, CTRL | ALT), SelectionMode.SUBTRACT)

    def test_unrelated_modifiers_keep_stored_mode(self) -> None:
        """A modifier bound to neither selection modifier doesn't change the mode."""
        self.assertEqual(selection_mode_for_gesture(SelectionMode.REPLACE, CTRL), SelectionMode.REPLACE)

    def test_modifiers_follow_key_config(self) -> None:
        """Rebinding the subtract modifier moves the override to the new key, so Alt can be freed from the window
           manager."""
        KeyConfig().set(KeyConfig.SELECTION_SUBTRACT_MODIFIER, 'Meta')
        self.assertEqual(selection_mode_for_gesture(SelectionMode.ADD, META), SelectionMode.SUBTRACT)
        self.assertEqual(selection_mode_for_gesture(SelectionMode.ADD, ALT), SelectionMode.ADD)

    def test_compose_path(self) -> None:
        """Each mode combines a path with the selection, changing pixels outside the path only for replace and
           intersect."""
        path = QPainterPath()
        path.addRect(SHAPE)
        existing = _rect_mask(EXISTING)
        shape = _rect_mask(SHAPE)
        expected = {SelectionMode.ADD: existing | shape, SelectionMode.SUBTRACT: existing & ~shape,
                    SelectionMode.REPLACE: shape, SelectionMode.INTERSECT: existing & shape}
        for mode, expected_mask in expected.items():
            image = _selection_image(EXISTING)
            compose_selection_path(image, path, QColor(Qt.GlobalColor.red), mode)
            np.testing.assert_array_equal(_mask(image), expected_mask, err_msg=mode.value)

    def test_compose_image(self) -> None:
        """Each mode combines a mask image with the selection the same way as a path."""
        existing = _rect_mask(EXISTING)
        shape = _rect_mask(SHAPE)
        expected = {SelectionMode.ADD: existing | shape, SelectionMode.SUBTRACT: existing & ~shape,
                    SelectionMode.REPLACE: shape, SelectionMode.INTERSECT: existing & shape}
        for mode, expected_mask in expected.items():
            image = _selection_image(EXISTING)
            compose_selection_image(image, _selection_image(SHAPE), mode)
            np.testing.assert_array_equal(_mask(image), expected_mask, err_msg=mode.value)
