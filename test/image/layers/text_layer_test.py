"""Tests TextLayer geometry, text edits and their undo history, transforms, and conversion to an image layer.

Text rendering differs across platforms and installed fonts, so these tests check sizes, bounds and where content
lands within the layer, never individual glyph pixels.
"""
from PySide6.QtCore import QSize, QRect, QPoint, QPointF, Qt
from PySide6.QtGui import QTransform, QColor, QFont, QImage

from src.config.application_config import AppConfig
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer_group import LayerGroup
from src.image.layers.text_layer import TextLayer, MAX_NAME_LENGTH_BEFORE_TRUNC
from src.image.text_rect import TextRect, DEFAULT_SIZE
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_content_bounds, image_is_fully_transparent
from src.util.visual.text_drawing_utils import find_text_size
from test.base_test_case import IntraPaintTestCase

LAYER_SIZE = QSize(200, 60)
IMAGE_SIZE = QSize(256, 256)

# Largest gap allowed between aligned text and the layer edge it is aligned to:
ALIGN_MARGIN = 10


def _text_rect(text: str = 'Text', size: QSize = LAYER_SIZE,
               alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft) -> TextRect:
    text_rect = TextRect()
    font = QFont()
    font.setPixelSize(20)
    text_rect.font = font
    text_rect.text = text
    text_rect.size = size
    text_rect.text_color = QColor(Qt.GlobalColor.black)
    text_rect.text_alignment = alignment
    return text_rect


def _content_bounds(layer: TextLayer) -> QRect:
    image = layer.get_qimage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    return image_content_bounds(image)


class TextLayerGeometryTest(IntraPaintTestCase):
    """Layer size and where text lands within it, for each sizing mode, alignment and text shape."""

    def test_default_size(self) -> None:
        """A text layer created without text data takes TextRect's default size and has empty text."""
        layer = TextLayer(None)
        self.assertEqual(layer.size, DEFAULT_SIZE)
        self.assertEqual(layer.bounds, QRect(QPoint(), DEFAULT_SIZE))
        self.assertEqual(layer.text_rect.text, '')
        self.assertEqual(layer.name, '""')

    def test_size_follows_text_rect(self) -> None:
        """Layer size is the text rect's size, and the rendered image matches it."""
        layer = TextLayer(_text_rect())
        self.assertEqual(layer.size, LAYER_SIZE)
        self.assertEqual(layer.get_qimage().size(), LAYER_SIZE)

    def test_empty_text_renders_transparent(self) -> None:
        """Empty text keeps the layer size and renders nothing."""
        layer = TextLayer(_text_rect(''))
        self.assertEqual(layer.size, LAYER_SIZE)
        self.assertTrue(image_is_fully_transparent(layer.get_qimage()))

    def test_filled_background_covers_layer(self) -> None:
        """With fill_background set, content covers the whole layer, even with empty text."""
        text_rect = _text_rect('')
        text_rect.fill_background = True
        text_rect.background_color = QColor(Qt.GlobalColor.white)
        layer = TextLayer(text_rect)
        self.assertEqual(_content_bounds(layer), QRect(QPoint(), LAYER_SIZE))

    def test_name_from_text(self) -> None:
        """The layer name is the quoted text, truncated past MAX_NAME_LENGTH_BEFORE_TRUNC characters."""
        self.assertEqual(TextLayer(_text_rect('Short')).name, '"Short"')
        long_text = 'x' * (MAX_NAME_LENGTH_BEFORE_TRUNC + 5)
        self.assertEqual(TextLayer(_text_rect(long_text)).name, f'"{"x" * MAX_NAME_LENGTH_BEFORE_TRUNC}..."')

    def test_horizontal_alignment(self) -> None:
        """Text sits against the edge it is aligned to, and centered text is about equally far from both."""
        width = LAYER_SIZE.width()
        left = _content_bounds(TextLayer(_text_rect('Hi', alignment=Qt.AlignmentFlag.AlignLeft)))
        right = _content_bounds(TextLayer(_text_rect('Hi', alignment=Qt.AlignmentFlag.AlignRight)))
        center = _content_bounds(TextLayer(_text_rect('Hi', alignment=Qt.AlignmentFlag.AlignHCenter)))
        for bounds in (left, right, center):
            self.assertFalse(bounds.isEmpty())
        self.assertLessEqual(left.left(), ALIGN_MARGIN)
        self.assertGreater(width - left.right(), width // 2)
        self.assertGreaterEqual(right.right(), width - 1 - ALIGN_MARGIN)
        self.assertGreater(right.left(), width // 2)
        self.assertAlmostEqual(center.left(), width - 1 - center.right(), delta=ALIGN_MARGIN)
        # Glyph antialiasing at a different subpixel offset can cover one more pixel column.
        self.assertAlmostEqual(left.width(), right.width(), delta=1)

    def test_vertical_alignment(self) -> None:
        """Bottom-aligned text sits below top-aligned text, against the bottom edge."""
        height = 120
        size = QSize(LAYER_SIZE.width(), height)
        top = _content_bounds(TextLayer(_text_rect('Hi', size, Qt.AlignmentFlag.AlignTop)))
        bottom = _content_bounds(TextLayer(_text_rect('Hi', size, Qt.AlignmentFlag.AlignBottom)))
        self.assertLess(top.bottom(), height // 2)
        self.assertGreater(bottom.top(), height // 2)
        self.assertGreaterEqual(bottom.bottom(), height - 1 - ALIGN_MARGIN)

    def test_alignment_does_not_change_size(self) -> None:
        """Alignment moves text within the layer without changing the layer's size."""
        for alignment in (Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignRight, Qt.AlignmentFlag.AlignCenter,
                          Qt.AlignmentFlag.AlignBottom):
            self.assertEqual(TextLayer(_text_rect('Hi', alignment=alignment)).size, LAYER_SIZE, str(alignment))

    def test_multi_line_text_is_taller(self) -> None:
        """Each added line of text extends the drawn content downward."""
        size = QSize(LAYER_SIZE.width(), 150)
        one_line = _content_bounds(TextLayer(_text_rect('Line', size)))
        two_lines = _content_bounds(TextLayer(_text_rect('Line\nLine', size)))
        three_lines = _content_bounds(TextLayer(_text_rect('Line\nLine\nLine', size)))
        self.assertEqual(one_line.top(), two_lines.top())
        self.assertGreater(two_lines.bottom(), one_line.bottom())
        self.assertGreater(three_lines.bottom(), two_lines.bottom())
        self.assertEqual(one_line.width(), three_lines.width())

    def test_bounds_scaled_to_text(self) -> None:
        """With scale_bounds_to_text set, layer size is find_text_size's result for the text and font."""
        text_rect = _text_rect('Hi')
        text_rect.scale_bounds_to_text = True
        one_line_size = TextLayer(text_rect).size
        self.assertEqual(one_line_size, find_text_size('Hi', text_rect.font))

        text_rect.text = 'Hi\nHi'
        two_line_size = TextLayer(text_rect).size
        self.assertEqual(two_line_size.width(), one_line_size.width())
        self.assertEqual(two_line_size.height(), one_line_size.height() * 2)

        text_rect.text = 'Hi Hi Hi'
        self.assertGreater(TextLayer(text_rect).size.width(), one_line_size.width())

    def test_bounds_scaled_to_empty_text(self) -> None:
        """Empty text scaled to bounds still gets a non-empty layer, one line high."""
        text_rect = _text_rect('Hi')
        text_rect.scale_bounds_to_text = True
        line_height = text_rect.size.height()
        text_rect.text = ''
        layer = TextLayer(text_rect)
        self.assertFalse(layer.bounds.isEmpty())
        self.assertEqual(layer.size.height(), line_height)

    def test_bounds_scaled_to_font_size(self) -> None:
        """With scale_bounds_to_text set, a larger font makes a larger layer."""
        text_rect = _text_rect('Hi')
        text_rect.scale_bounds_to_text = True
        small_size = TextLayer(text_rect).size
        font = text_rect.font
        font.setPixelSize(40)
        text_rect.font = font
        large_size = TextLayer(text_rect).size
        self.assertGreater(large_size.width(), small_size.width())
        self.assertGreater(large_size.height(), small_size.height())

    def test_image_data_cannot_be_set(self) -> None:
        """Writing image data to a text layer raises, since it must be converted to an image layer first."""
        layer = TextLayer(_text_rect())
        with self.assertRaises(RuntimeError):
            layer.set_qimage(QImage(LAYER_SIZE, QImage.Format.Format_ARGB32_Premultiplied))
        with self.assertRaises(RuntimeError):
            layer.cut_masked(QImage(LAYER_SIZE, QImage.Format.Format_ARGB32_Premultiplied))


class TextLayerEditTest(IntraPaintTestCase):
    """Edits through TextLayer's setters, their signals, and their undo history."""

    def setUp(self) -> None:
        super().setUp()
        # Without time-based merging, each change is its own undo entry:
        AppConfig().set(AppConfig.UNDO_MERGE_INTERVAL, 0.0)
        self.layer = TextLayer(_text_rect('First'))

    def _edited(self, text: str = 'Second', size: QSize = QSize(120, 40)) -> TextRect:
        text_rect = self.layer.text_rect
        text_rect.text = text
        text_rect.size = size
        return text_rect

    def test_text_rect_is_a_copy(self) -> None:
        """Changing the TextRect the getter returns doesn't change the layer."""
        text_rect = self.layer.text_rect
        text_rect.text = 'Changed'
        self.assertEqual(self.layer.text_rect.text, 'First')

    def test_set_text_rect_updates_layer(self) -> None:
        """set_text_rect updates text, size, name and image, emits text_data_changed, and adds no undo entry."""
        emitted: list[TextRect] = []
        self.layer.text_data_changed.connect(emitted.append)
        new_text = self._edited()
        self.layer.set_text_rect(new_text)
        self.assertEqual(self.layer.text_rect.text, 'Second')
        self.assertEqual(self.layer.size, QSize(120, 40))
        self.assertEqual(self.layer.get_qimage().size(), QSize(120, 40))
        self.assertEqual(self.layer.name, '"Second"')
        self.assertEqual([text_rect.text for text_rect in emitted], ['Second'])
        self.assertEqual(UndoStack().undo_count(), 0)

    def test_text_edit_signals_content_change_once(self) -> None:
        """A same-size text edit reports the layer bounds as changed once, and an edit to a hidden layer reports
           nothing."""
        changes: list[QRect] = []
        self.layer.content_changed.connect(lambda _, rect: changes.append(rect))
        self.layer.set_text_rect(self._edited(size=LAYER_SIZE))
        self.assertEqual(changes, [QRect(QPoint(), LAYER_SIZE)])
        changes.clear()
        self.layer.set_visible(False)
        changes.clear()
        self.layer.set_text_rect(self._edited('Third', LAYER_SIZE))
        self.assertEqual(changes, [])

    def test_unchanged_text_rect_is_ignored(self) -> None:
        """Setting an equal TextRect adds no undo entry and emits nothing."""
        emitted: list[TextRect] = []
        self.layer.text_data_changed.connect(emitted.append)
        self.layer.text_rect = self.layer.text_rect
        self.assertEqual(UndoStack().undo_count(), 0)
        self.assertEqual(emitted, [])

    def test_text_rect_undo_redo(self) -> None:
        """The text_rect property adds one undo entry, and undo and redo restore text, size and name."""
        self.layer.text_rect = self._edited()
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(self.layer.text_rect.text, 'First')
        self.assertEqual(self.layer.size, LAYER_SIZE)
        self.assertEqual(self.layer.name, '"First"')
        UndoStack().redo()
        self.assertEqual(self.layer.text_rect.text, 'Second')
        self.assertEqual(self.layer.size, QSize(120, 40))
        self.assertEqual(self.layer.name, '"Second"')

    def test_each_property_change_undoes(self) -> None:
        """Changing any one TextRect property through the layer is undoable on its own."""
        def _color(text_rect: TextRect) -> None:
            text_rect.text_color = QColor(Qt.GlobalColor.red)

        def _background(text_rect: TextRect) -> None:
            text_rect.background_color = QColor(Qt.GlobalColor.blue)

        def _fill(text_rect: TextRect) -> None:
            text_rect.fill_background = True

        def _alignment(text_rect: TextRect) -> None:
            text_rect.text_alignment = Qt.AlignmentFlag.AlignRight

        def _font(text_rect: TextRect) -> None:
            font = text_rect.font
            font.setBold(True)
            text_rect.font = font

        original = self.layer.text_rect.serialize()
        for change in (_color, _background, _fill, _alignment, _font):
            text_rect = self.layer.text_rect
            change(text_rect)
            self.layer.text_rect = text_rect
            self.assertNotEqual(self.layer.text_rect.serialize(), original, change.__name__)
            UndoStack().undo()
            self.assertEqual(self.layer.text_rect.serialize(), original, change.__name__)

    def test_quick_edits_merge(self) -> None:
        """Text edits closer together than UNDO_MERGE_INTERVAL merge into one entry that restores the original."""
        AppConfig().set(AppConfig.UNDO_MERGE_INTERVAL, 60.0)
        for text in ('S', 'Se', 'Sec'):
            self.layer.text_rect = self._edited(text)
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(self.layer.text_rect.text, 'First')
        UndoStack().redo()
        self.assertEqual(self.layer.text_rect.text, 'Sec')

    def test_save_and_restore_state(self) -> None:
        """restore_state brings back the text, transform and layer properties save_state recorded."""
        state = self.layer.save_state()
        self.layer.set_text_rect(self._edited())
        self.layer.set_transform(QTransform.fromTranslate(30, 40))
        self.layer.set_opacity(0.5)
        self.layer.restore_state(state)
        self.assertEqual(self.layer.text_rect.text, 'First')
        self.assertEqual(self.layer.size, LAYER_SIZE)
        self.assertEqual(self.layer.transform, QTransform())
        self.assertEqual(self.layer.opacity, 1.0)


class TextLayerTransformTest(IntraPaintTestCase):
    """Text layer offsets and transforms, and conversion to an image layer."""

    def setUp(self) -> None:
        super().setUp()
        AppConfig().set(AppConfig.UNDO_MERGE_INTERVAL, 0.0)
        self.image_stack = ImageStack(IMAGE_SIZE, IMAGE_SIZE, IMAGE_SIZE, IMAGE_SIZE)
        text_rect = _text_rect('Text')
        text_rect.fill_background = True
        text_rect.background_color = QColor(Qt.GlobalColor.white)
        self.layer = self.image_stack.create_text_layer(text_rect)
        self.layer.set_transform(QTransform.fromTranslate(20, 30))
        UndoStack().clear()

    def test_offset_is_translation(self) -> None:
        """offset reads the transform's translation, and setting it moves the layer without other changes."""
        self.assertEqual(self.layer.offset, QPointF(20, 30))
        self.layer.offset = QPointF(5, 6)
        self.assertEqual(self.layer.transform, QTransform.fromTranslate(5, 6))
        self.assertEqual(self.layer.transformed_bounds, QRect(QPoint(5, 6), LAYER_SIZE))
        UndoStack().undo()
        self.assertEqual(self.layer.offset, QPointF(20, 30))

    def test_offset_keeps_rotation(self) -> None:
        """Setting the offset of a rotated layer moves it and keeps the rotation."""
        self.layer.rotate(90)
        rotated = self.layer.transform
        bounds = self.layer.transformed_bounds
        self.layer.offset = self.layer.offset + QPointF(10, -5)
        self.assertEqual(self.layer.transform, rotated * QTransform.fromTranslate(10, -5))
        self.assertEqual(self.layer.transformed_bounds, bounds.translated(10, -5))

    def test_rotate_bounds(self) -> None:
        """Rotating a quarter turn about the center swaps the transformed bounds' width and height."""
        center = QRect(QPoint(20, 30), LAYER_SIZE).center()
        self.layer.rotate(90)
        bounds = self.layer.transformed_bounds
        self.assertEqual(bounds.size(), LAYER_SIZE.transposed())
        self.assertLessEqual((bounds.center() - center).manhattanLength(), 2)
        self.assertEqual(self.layer.size, LAYER_SIZE)
        UndoStack().undo()
        self.assertEqual(self.layer.transform, QTransform.fromTranslate(20, 30))

    def test_flip_keeps_bounds(self) -> None:
        """Flipping a text layer leaves its transformed bounds in place and keeps it a text layer."""
        self.layer.flip_horizontal()
        self.assertEqual(self.layer.transformed_bounds, QRect(QPoint(20, 30), LAYER_SIZE))
        self.assertEqual(self.layer.transform.m11(), -1.0)
        self.assertIn(self.layer, self.image_stack.text_layers)

    def test_text_edit_keeps_transform(self) -> None:
        """Resizing the text keeps the layer's transform."""
        self.layer.rotate(90)
        transform = self.layer.transform
        text_rect = self.layer.text_rect
        text_rect.size = QSize(80, 20)
        self.layer.text_rect = text_rect
        self.assertEqual(self.layer.transform, transform)
        self.assertEqual(self.layer.size, QSize(80, 20))

    def test_copy(self) -> None:
        """copy makes an independent text layer with the same text, transform and layer properties."""
        self.layer.rotate(90)
        self.layer.set_opacity(0.5)
        copy = self.layer.copy()
        self.assertIsInstance(copy, TextLayer)
        self.assertEqual(copy.text_rect.serialize(), self.layer.text_rect.serialize())
        self.assertEqual(copy.transform, self.layer.transform)
        self.assertEqual(copy.transformed_bounds, self.layer.transformed_bounds)
        self.assertEqual(copy.opacity, 0.5)
        copy.set_text_rect(_text_rect('Other'))
        self.assertEqual(self.layer.text_rect.text, 'Text')

    def test_copy_as_image_layer(self) -> None:
        """copy_as_image_layer makes an image layer with the same image, name, transform and properties."""
        self.layer.rotate(90)
        self.layer.set_opacity(0.5)
        image_layer = self.layer.copy_as_image_layer()
        self.assertIsInstance(image_layer, ImageLayer)
        self.assertEqual(image_layer.name, self.layer.name)
        self.assertEqual(image_layer.transform, self.layer.transform)
        self.assertEqual(image_layer.transformed_bounds, self.layer.transformed_bounds)
        self.assertEqual(image_layer.opacity, 0.5)
        self.assertEqual(image_layer.image, self.layer.get_qimage())

    def test_replace_with_image_in_stack(self) -> None:
        """ImageStack.replace_text_layer_with_image swaps in an equivalent image layer that renders the same, and
           undo brings back the text layer."""
        self.layer.rotate(90)
        self.image_stack.flush_render()
        before = self.image_stack.qimage(crop_to_image=False)
        parent = self.layer.layer_parent
        assert isinstance(parent, LayerGroup)
        index = parent.get_layer_index(self.layer)

        image_layer = self.image_stack.replace_text_layer_with_image(self.layer)
        self.image_stack.flush_render()
        self.assertEqual(parent.get_layer_index(image_layer), index)
        self.assertEqual(self.image_stack.text_layers, [])
        self.assertIs(self.image_stack.active_layer, image_layer)
        self.assertEqual(image_layer.transformed_bounds, self.layer.transformed_bounds)
        self.assertEqual(self.image_stack.qimage(crop_to_image=False), before)

        UndoStack().undo()
        self.assertEqual(self.image_stack.text_layers, [self.layer])
        self.assertEqual(parent.get_layer_index(self.layer), index)
        self.assertIs(self.image_stack.active_layer, self.layer)

    def test_replace_with_image_layer(self) -> None:
        """TextLayer.replace_with_image_layer swaps in an image layer at the same index, and undo swaps back."""
        parent = self.layer.layer_parent
        assert isinstance(parent, LayerGroup)
        index = parent.get_layer_index(self.layer)
        image_layer = self.layer.replace_with_image_layer()
        self.assertEqual(parent.get_layer_index(image_layer), index)
        self.assertIsNone(parent.get_layer_index(self.layer))
        UndoStack().undo()
        self.assertEqual(parent.get_layer_index(self.layer), index)
        self.assertIsNone(parent.get_layer_index(image_layer))
