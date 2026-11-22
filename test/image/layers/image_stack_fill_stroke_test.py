"""Tests ImageStack.fill_selected and ImageStack.stroke_selection on a non-rectangular selection.

The selection is a rectangle with a hole, plus a separate square, so the outline has inner and outer edges. Results are
checked against goldens of the painted layer's image, and every operation must be one undo step that leaves the other
layers alone.
"""
from unittest.mock import patch

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QTransform

from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack, StrokePosition
from src.image.layers.text_layer import TextLayer
from src.image.text_rect import TextRect
from src.undo_stack import UndoStack
from src.util.visual.image_utils import create_transparent_image, image_data_as_numpy_8bit
from test.image.layers.image_stack_state import ImageStackOpTestCase, StackState, MIN_GEN_AREA, MAX_GEN_AREA

GOLDEN_DIR = 'test/resources/test_images/fill_stroke_selection'
FILL_PNG = f'{GOLDEN_DIR}/fill_selected.png'
STROKE_PNG = {position: f'{GOLDEN_DIR}/stroke_{position.value}.png' for position in StrokePosition}
CONFIRM_RENDER_TEXT = 'src.image.layers.non_destructive_layer.request_confirmation'

CANVAS = QSize(64, 48)
OUTER = QRect(8, 8, 36, 28)
HOLE = QRect(20, 16, 12, 10)
SQUARE = QRect(50, 6, 8, 8)
# The painted layer sits offset from the canvas, and doesn't cover the canvas's right side:
LAYER_OFFSET = QPoint(4, 2)
LAYER_SIZE = QSize(50, 44)
FILL_COLOR = QColor(255, 0, 0, 160)
STROKE_COLOR = QColor(0, 0, 255)
STROKE_WIDTH = 3


class FillStrokeSelectionTest(ImageStackOpTestCase):
    """Builds [painted, bottom], where painted is half covered in green, and selects a ring and a square."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(CANVAS, CANVAS, MIN_GEN_AREA, MAX_GEN_AREA, UndoStack())
        image = create_transparent_image(LAYER_SIZE)
        painter = QPainter(image)
        painter.fillRect(QRect(0, 0, LAYER_SIZE.width() // 2, LAYER_SIZE.height()), QColor(0, 200, 0))
        painter.end()
        self.painted = self.image_stack.create_layer('painted', image, layer_index=0)
        self.painted.set_transform(QTransform.fromTranslate(LAYER_OFFSET.x(), LAYER_OFFSET.y()))
        self.bottom = self.add_layer('bottom', 4, CANVAS, min_alpha=80)
        self.image_stack.active_layer = self.painted
        selection_layer = self.image_stack.selection_layer
        with selection_layer.borrow_image() as mask_image:
            assert mask_image is not None
            mask_image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(mask_image)
            painter.fillRect(OUTER, Qt.GlobalColor.red)
            painter.fillRect(SQUARE, Qt.GlobalColor.red)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(HOLE, Qt.GlobalColor.transparent)
            painter.end()
        UndoStack().clear()

    def assert_only_layer_changed(self, before: StackState, after: StackState, changed: ImageLayer) -> None:
        """Asserts that every layer but `changed` has the same pixels and properties before and after."""
        self.assertEqual([state.layer for state in before.layers], [state.layer for state in after.layers])
        for before_layer, after_layer in zip(before.layers, after.layers):
            if before_layer.layer is changed:
                continue
            name = before_layer.properties['name']
            self.assertEqual(before_layer.properties, after_layer.properties, name)
            if before_layer.image is not None:
                assert after_layer.image is not None
                self.assert_images_equal(after_layer.image, before_layer.image, name)

    def test_fill_selected(self) -> None:
        """Fill paints the color over the selected part of the active layer only, in one undo step."""
        before, after = self.assert_undo_redo(lambda: self.image_stack.fill_selected(FILL_COLOR))
        self.assert_only_layer_changed(before, after, self.painted)
        self.assert_image_matches_golden(self.painted.image, FILL_PNG)

    def assert_strokes(self, position: StrokePosition) -> None:
        """Asserts that a stroke outlines the selection's outer, hole and square edges on the active layer only."""
        before, after = self.assert_undo_redo(
            lambda: self.image_stack.stroke_selection(STROKE_COLOR, STROKE_WIDTH, position))
        self.assert_only_layer_changed(before, after, self.painted)
        self.assert_image_matches_golden(self.painted.image, STROKE_PNG[position])

    def test_stroke_inside(self) -> None:
        """An inside stroke runs along the selection edge, within the selection."""
        self.assert_strokes(StrokePosition.INSIDE)

    def test_stroke_center(self) -> None:
        """A centered stroke straddles the selection edge."""
        self.assert_strokes(StrokePosition.CENTER)

    def test_stroke_outside(self) -> None:
        """An outside stroke runs along the selection edge, outside the selection."""
        self.assert_strokes(StrokePosition.OUTSIDE)

    def test_stroke_inside_stays_in_selection(self) -> None:
        """An inside stroke paints no pixel outside the selection, and an outside stroke none inside it."""
        selected = image_data_as_numpy_8bit(self.image_stack.get_layer_selection_mask(self.painted))[:, :, 3] > 0
        for position, allowed in ((StrokePosition.INSIDE, selected), (StrokePosition.OUTSIDE, ~selected)):
            with self.subTest(position=position):
                original = image_data_as_numpy_8bit(self.painted.image).copy()
                self.image_stack.stroke_selection(STROKE_COLOR, STROKE_WIDTH, position)
                changed = (image_data_as_numpy_8bit(self.painted.image) != original).any(axis=2)
                UndoStack().undo()
                self.assertTrue(changed.any())
                self.assertFalse((changed & ~allowed).any())

    def test_fill_keeps_alpha_lock(self) -> None:
        """Filling an alpha-locked layer recolors its opaque half and leaves its transparent half transparent."""
        self.painted.alpha_locked = True
        UndoStack().clear()
        alpha_before = image_data_as_numpy_8bit(self.painted.image)[:, :, 3].copy()
        self.image_stack.fill_selected(QColor(255, 0, 0))
        pixels = image_data_as_numpy_8bit(self.painted.image)
        self.assertTrue((pixels[:, :, 3] == alpha_before).all())
        local_point = OUTER.topLeft() - LAYER_OFFSET
        self.assertEqual(QColor(255, 0, 0), self.painted.image.pixelColor(local_point))

    def test_group_is_not_painted(self) -> None:
        """Fill and stroke do nothing while a group is active."""
        group = self.add_group('group')
        self.image_stack.active_layer = group
        UndoStack().clear()
        before = self.capture()
        self.image_stack.fill_selected(FILL_COLOR)
        self.image_stack.stroke_selection(STROKE_COLOR, STROKE_WIDTH, StrokePosition.CENTER)
        self.capture().assert_matches(before, 'group')
        self.assertEqual(0, UndoStack().undo_count())

    def test_text_layer_renders_to_image_when_confirmed(self) -> None:
        """Filling a text layer asks to render it to an image layer, and does nothing if declined."""
        text_layer = self.image_stack.create_text_layer(TextRect('text'), self.image_stack.layer_stack, 0)
        self.image_stack.active_layer = text_layer
        UndoStack().clear()
        with patch(CONFIRM_RENDER_TEXT, return_value=False):
            self.image_stack.fill_selected(FILL_COLOR)
        self.assertIs(text_layer, self.image_stack.active_layer)
        self.assertEqual(0, UndoStack().undo_count())
        with patch(CONFIRM_RENDER_TEXT, return_value=True):
            self.image_stack.fill_selected(FILL_COLOR)
        self.assertNotIsInstance(self.image_stack.active_layer, TextLayer)
        self.assertEqual(1, UndoStack().undo_count())
