"""Tests for GenerationAreaToolPanel: its sync with the generation area, its size presets and its resolution line."""
import sys

from PySide6.QtCore import QSize, QRect
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller.generation_area_controller import apply_generation_area_frame, record_generation_area_size
from src.image.layers.image_stack import ImageStack
from src.ui.input_fields.geometry_block import HEIGHT, WIDTH, X, Y
from src.ui.panel.tool_control_panels.generation_area_tool_panel import GenerationAreaToolPanel, EMPTY_SLOT_TEXT, \
    RECENT_FRAME_COUNT
from src.util.generation_area_utils import RESOLUTION_RULE_MANUAL
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

IMAGE_SIZE = QSize(1024, 640)
MAX_AREA_SIZE = QSize(10240, 10240)


class GenerationAreaToolPanelTest(IntraPaintTestCase):
    """Tests that the panel's fields and presets follow and set the generation area."""

    def setUp(self) -> None:
        super().setUp()
        Cache().set(Cache.RECENT_GENERATION_AREA_SIZES, [])
        self.image_stack = ImageStack(IMAGE_SIZE, QSize(384, 384), QSize(8, 8), MAX_AREA_SIZE)
        self.panel = GenerationAreaToolPanel(self.image_stack)
        self.geometry = self.panel.geometry_block

    def _assert_fields_match_area(self) -> None:
        area = self.image_stack.generation_area
        for name, value in ((X, area.x()), (Y, area.y()), (WIDTH, area.width()), (HEIGHT, area.height())):
            self.assertEqual(self.geometry.value(name), value, name)

    def _slot_texts(self) -> list[str]:
        return [button.text() for button in self.panel.recent_buttons]

    def _type_custom(self, text: str) -> None:
        self.panel.custom_input.setText(text)
        self.panel.custom_input.returnPressed.emit()

    def test_centered_shrink_past_old_range(self) -> None:
        """Shrinking around the center moves x and y past the old field limits, and the fields still follow."""
        self.image_stack.generation_area = QRect(320, 192, 384, 384)
        apply_generation_area_frame(self.image_stack, QSize(128, 128))
        self.assertEqual(self.image_stack.generation_area, QRect(448, 320, 128, 128))
        self._assert_fields_match_area()

    def test_growth_below_old_value(self) -> None:
        """Growing the area lowers the position limits below the old values, and the fields still follow."""
        self.image_stack.generation_area = QRect(800, 500, 128, 128)
        apply_generation_area_frame(self.image_stack, QSize(512, 512))
        self.assertEqual(self.image_stack.generation_area, QRect(512, 128, 512, 512))
        self._assert_fields_match_area()

    def test_field_edit_sets_area(self) -> None:
        """Changing a field moves or resizes the area."""
        self.image_stack.generation_area = QRect(0, 0, 384, 384)
        self.geometry.field(X).set_value(100)
        self.geometry.field(HEIGHT).set_value(200)
        self.assertEqual(self.image_stack.generation_area, QRect(100, 0, 384, 200))

    def test_ratio_lock_keeps_ratio_across_edits(self) -> None:
        """With the lock on, repeated width edits keep the ratio the lock captured, without rounding drift."""
        self.image_stack.generation_area = QRect(0, 0, 384, 256)
        self.geometry.set_ratio_locked(True)
        for width in (100, 333, 50, 384):
            self.geometry.field(WIDTH).set_value(width)
        self.assertEqual(self.image_stack.generation_area.size(), QSize(384, 256))
        self._assert_fields_match_area()

    def test_typed_size_is_recorded(self) -> None:
        """A typed width becomes a recent size, and wheel-like steps don't."""
        self.image_stack.generation_area = QRect(0, 0, 384, 384)
        width_field = self.geometry.field(WIDTH)
        width_field.set_value(300)
        self.assertEqual(Cache().get(Cache.RECENT_GENERATION_AREA_SIZES), [])
        width_field.entryCommitted.emit()
        self.assertEqual(Cache().get(Cache.RECENT_GENERATION_AREA_SIZES), ['300x384'])

    def test_oversized_typed_frame(self) -> None:
        """A typed size too large for a C int selects the largest area that fits."""
        self._type_custom('99999999999999999')
        self.assertEqual(self.image_stack.generation_area, QRect(0, 0, 1024, 640))
        self._assert_fields_match_area()

    def test_custom_field_parses_sizes(self) -> None:
        """The Custom field takes one side or two, and clears after applying them."""
        self._type_custom('256')
        self.assertEqual(self.image_stack.generation_area.size(), QSize(256, 256))
        self.assertEqual(self.panel.custom_input.text(), '')
        self._type_custom('640x480')
        self.assertEqual(self.image_stack.generation_area.size(), QSize(640, 480))
        self.assertFalse(self.panel.custom_invalid())

    def test_custom_field_rejects_other_text_with_hint(self) -> None:
        """Other text leaves the area alone, keeps the text and shows the hint until the text is edited."""
        area = self.image_stack.generation_area
        self._type_custom('big')
        self.assertEqual(self.image_stack.generation_area, area)
        self.assertEqual(self.panel.custom_input.text(), 'big')
        self.assertTrue(self.panel.custom_invalid())
        self.assertFalse(self.panel.custom_hint.isHidden())
        self.panel.custom_input.textEdited.emit('bi')
        self.assertFalse(self.panel.custom_invalid())
        self.assertTrue(self.panel.custom_hint.isHidden())

    def test_empty_recent_slots_show_disabled(self) -> None:
        """Every Recent slot is present from the start, and the empty ones are disabled."""
        self.assertEqual(len(self.panel.recent_buttons), RECENT_FRAME_COUNT)
        self.assertEqual(self._slot_texts(), [EMPTY_SLOT_TEXT] * RECENT_FRAME_COUNT)
        self.assertFalse(any(button.isEnabled() for button in self.panel.recent_buttons))
        record_generation_area_size(QSize(300, 200))
        self.assertEqual(self._slot_texts(), ['300x200'] + [EMPTY_SLOT_TEXT] * (RECENT_FRAME_COUNT - 1))
        self.assertTrue(self.panel.recent_buttons[0].isEnabled())
        self.assertFalse(self.panel.recent_buttons[1].isEnabled())

    def test_recent_slots_keep_positions(self) -> None:
        """A size keeps its slot as newer sizes are added and as it is used again."""
        for width in (100, 200, 300):
            record_generation_area_size(QSize(width, 100))
        self.assertEqual(self._slot_texts(), ['100x100', '200x100', '300x100', EMPTY_SLOT_TEXT])
        record_generation_area_size(QSize(400, 100))
        self.assertEqual(self._slot_texts(), ['100x100', '200x100', '300x100', '400x100'])
        self.panel.recent_buttons[0].click()
        self.assertEqual(self.image_stack.generation_area.size(), QSize(100, 100))
        self.assertEqual(self._slot_texts(), ['100x100', '200x100', '300x100', '400x100'])
        # 200x100 is now the oldest, so the new size takes its slot:
        record_generation_area_size(QSize(500, 100))
        self.assertEqual(self._slot_texts(), ['100x100', '500x100', '300x100', '400x100'])

    def test_previous_button(self) -> None:
        """Previous switches to the last other size, names its key, and is disabled until there is one."""
        key = KeyConfig().get(KeyConfig.PREVIOUS_GENERATION_FRAME_KEY)
        self.assertIn(key, self.panel.previous_button.toolTip())
        self.assertFalse(self.panel.previous_button.isEnabled())
        apply_generation_area_frame(self.image_stack, QSize(300, 300))
        apply_generation_area_frame(self.image_stack, QSize(200, 200))
        self.assertTrue(self.panel.previous_button.isEnabled())
        self.panel.previous_button.click()
        self.assertEqual(self.image_stack.generation_area.size(), QSize(300, 300))

    def test_fit_buttons(self) -> None:
        """Full image and Square resize the area to the image and to its largest square."""
        self.panel.full_image_button.click()
        self.assertEqual(self.image_stack.generation_area, QRect(0, 0, 1024, 640))
        self.panel.square_button.click()
        self.assertEqual(self.image_stack.generation_area.size(), QSize(640, 640))

    def test_resolution_line_hidden_without_backend(self) -> None:
        """The Sent to generator section is hidden until a Stable Diffusion panel is loaded."""
        self.assertFalse(self.panel.resolution_shown())
        self.assertTrue(self.panel.generator_section.isHidden())
        self.panel.set_resolution_shown(True)
        self.assertFalse(self.panel.generator_section.isHidden())
        self.panel.set_resolution_shown(False)
        self.assertTrue(self.panel.generator_section.isHidden())

    def test_resolution_line_follows_cache(self) -> None:
        """The line names the resolution and rule, and Edit asks for the generation panel."""
        cache = Cache()
        cache.set(Cache.GENERATION_RESOLUTION_RULE, RESOLUTION_RULE_MANUAL)
        cache.set(Cache.GENERATION_SIZE, QSize(640, 448))
        self.assertEqual(self.panel.resolution_label.text(), 'Generates at 640 x 448')
        self.assertEqual(self.panel.rule_label.text(), 'Manual')
        self.assertEqual(self.panel.resolution_summary(), 'Generates at 640 x 448, Manual')
        requests: list[bool] = []
        self.panel.edit_resolution_requested.connect(lambda: requests.append(True))
        self.panel.edit_resolution_button.click()
        self.assertEqual(requests, [True])
