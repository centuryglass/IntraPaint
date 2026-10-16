"""Tests GeometryBlock: the ratio lock, the temporary lock, value display, scrub ranges and step keys. Events are
synthesized, and nothing waits on the event loop."""
import sys
from unittest.mock import MagicMock

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from src.config.key_config import KeyConfig
from src.ui.input_fields.geometry_block import (ANGLE, GeometryBlock, HEIGHT, SCALE_X, SCALE_Y, WIDTH, X, Y,
                                                bind_step_keys)
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class GeometryBlockTest(IntraPaintTestCase):
    """Tests GeometryBlock."""

    def test_rows_follow_flags(self) -> None:
        """Scale and angle fields exist only when requested."""
        base = GeometryBlock()
        self.assertEqual([name for name in (X, Y, WIDTH, HEIGHT) if base.has_field(name)], [X, Y, WIDTH, HEIGHT])
        self.assertFalse(base.has_field(SCALE_X))
        self.assertFalse(base.has_field(ANGLE))
        full = GeometryBlock(show_scale=True, show_angle=True, integer=False)
        self.assertTrue(full.has_field(SCALE_X) and full.has_field(SCALE_Y) and full.has_field(ANGLE))

    def test_values_show_units(self) -> None:
        """Whole pixels show no decimals, and angle and scale carry their units."""
        block = GeometryBlock(show_scale=True, show_angle=True, integer=False)
        block.set_values(x=128, w=512.0, scale_x=0.75, angle=12)
        self.assertEqual(block.field(X).value_text(), '128 px')
        self.assertEqual(block.field(WIDTH).value_text(), '512 px')
        self.assertEqual(block.field(SCALE_X).value_text(), '0.75x')
        self.assertEqual(block.field(ANGLE).value_text(), '12 deg')

    def test_summary(self) -> None:
        """The summary reads position, then size."""
        block = GeometryBlock()
        block.set_values(x=128, y=64, w=512, h=384)
        self.assertEqual(block.summary_text(), '128, 64 - 512 x 384')

    def test_set_value_is_silent_and_edits_emit(self) -> None:
        """Owner updates emit nothing, and user edits emit the field name and value."""
        block = GeometryBlock()
        changes: list[tuple[str, object]] = []
        block.valueChanged.connect(lambda name, value: changes.append((name, value)))
        block.set_value(X, 10)
        self.assertEqual(changes, [])
        block.field(X).set_value(20)
        self.assertEqual(changes, [(X, 20)])

    def test_typed_values_outside_the_scrub_range(self) -> None:
        """The fill ranges don't limit typed values."""
        block = GeometryBlock()
        block.set_image_size(QSize(100, 100))
        block.field(X).set_value(5000)
        self.assertEqual(block.value(X), 5000)
        block.field(X).set_value(-5000)
        self.assertEqual(block.value(X), -5000)

    def test_scrub_ranges_follow_image_size(self) -> None:
        """X scrubs from minus one image width to two, and W from 0 to two."""
        block = GeometryBlock()
        block.set_image_size(QSize(200, 100))
        block.resize(300, 60)
        x_field, width_field = block.field(X), block.field(WIDTH)
        x_field.resize(200, 24)
        width_field.resize(200, 24)
        self.assertAlmostEqual(x_field._fill_fraction(), 1 / 3)  # pylint: disable=protected-access
        block.set_value(X, 200)
        self.assertAlmostEqual(x_field._fill_fraction(), 2 / 3)  # pylint: disable=protected-access
        block.set_value(WIDTH, 200)
        self.assertAlmostEqual(width_field._fill_fraction(), 0.5)  # pylint: disable=protected-access
        # A full-width drag spans the whole scrub range:
        self.assertEqual(x_field._scrub_delta(200), 600)  # pylint: disable=protected-access

    def test_lock_keeps_ratio_from_either_side(self) -> None:
        """With the lock on, editing W or H moves the other, and both changes are reported."""
        block = GeometryBlock()
        block.set_values(w=200, h=100)
        block.set_ratio_locked(True)
        changes: list[tuple[str, object]] = []
        block.valueChanged.connect(lambda name, value: changes.append((name, value)))
        block.field(WIDTH).set_value(400)
        self.assertEqual(block.value(HEIGHT), 200)
        self.assertEqual(changes, [(WIDTH, 400), (HEIGHT, 200)])
        block.field(HEIGHT).set_value(50)
        self.assertEqual(block.value(WIDTH), 100)

    def test_unlocked_edits_are_independent(self) -> None:
        """Without the lock, W and H don't affect each other."""
        block = GeometryBlock()
        block.set_values(w=200, h=100)
        block.field(WIDTH).set_value(400)
        self.assertEqual(block.value(HEIGHT), 100)

    def test_lock_links_scale(self) -> None:
        """The lock also keeps the Scale X : Scale Y ratio."""
        block = GeometryBlock(show_scale=True, integer=False)
        block.set_values(scale_x=1.0, scale_y=2.0)
        block.set_ratio_locked(True)
        block.field(SCALE_X).set_value(0.5)
        self.assertAlmostEqual(block.value(SCALE_Y), 1.0)

    def test_temporary_lock_leaves_stored_setting(self) -> None:
        """A held modifier locks the ratio for now, shows a dotted outline, and releases back to unlocked."""
        block = GeometryBlock()
        block.set_values(w=200, h=100)
        toggles: list[bool] = []
        block.ratioLockToggled.connect(toggles.append)
        block.set_temporary_lock(True)
        self.assertTrue(block.effective_ratio_locked())
        self.assertFalse(block.ratio_locked())
        self.assertFalse(block.lock_button().isChecked())
        self.assertTrue(block.lock_button().temporary())
        block.field(WIDTH).set_value(400)
        self.assertEqual(block.value(HEIGHT), 200)
        block.set_temporary_lock(False)
        self.assertFalse(block.effective_ratio_locked())
        self.assertFalse(block.lock_button().temporary())
        self.assertEqual(toggles, [])
        block.field(WIDTH).set_value(100)
        self.assertEqual(block.value(HEIGHT), 200)

    def test_temporary_lock_is_not_marked_when_already_locked(self) -> None:
        """A stored lock shows as checked, not dotted, when the modifier is also held."""
        block = GeometryBlock()
        block.set_ratio_locked(True)
        block.set_temporary_lock(True)
        self.assertTrue(block.lock_button().isChecked())
        self.assertFalse(block.lock_button().temporary())

    def test_step_keys_move_the_right_field_in_the_right_direction(self) -> None:
        """Move keys step X and Y, pan keys step W and H, rotate keys step the angle, and the speed multiplier scales
        the step."""
        block = GeometryBlock(show_angle=True, integer=False)
        block.set_values(x=10, y=10, w=100, h=100, angle=0)
        registered: dict[str, object] = {}
        hotkey_filter = MagicMock()
        hotkey_filter.register_speed_modified_keybinding.side_effect = (
            lambda _id, action, key: registered.setdefault(key, action))
        KeyConfig()
        bind_step_keys(block, hotkey_filter, KeyConfig, lambda: True)
        expectations = [(KeyConfig.MOVE_LEFT, X, -1), (KeyConfig.MOVE_RIGHT, X, 1), (KeyConfig.MOVE_UP, Y, -1),
                        (KeyConfig.MOVE_DOWN, Y, 1), (KeyConfig.PAN_LEFT, WIDTH, -1), (KeyConfig.PAN_RIGHT, WIDTH, 1),
                        (KeyConfig.PAN_DOWN, HEIGHT, -1), (KeyConfig.PAN_UP, HEIGHT, 1),
                        (KeyConfig.ROTATE_CCW_KEY, ANGLE, -1), (KeyConfig.ROTATE_CW_KEY, ANGLE, 1)]
        for key, name, sign in expectations:
            with self.subTest(key=key):
                before = {other: block.value(other) for other in (X, Y, WIDTH, HEIGHT, ANGLE)}
                self.assertTrue(registered[key](3))  # type: ignore[operator]
                for other, old in before.items():
                    expected = old + sign * 3 * block.key_step(name) if other == name else old
                    self.assertAlmostEqual(block.value(other), expected)

    def test_step_keys_respect_predicate_and_list_in_tooltips(self) -> None:
        """Keys do nothing while the predicate is false, and each field's tooltip names its keys."""
        block = GeometryBlock()
        registered: dict[str, object] = {}
        hotkey_filter = MagicMock()
        hotkey_filter.register_speed_modified_keybinding.side_effect = (
            lambda _id, action, key: registered.setdefault(key, action))
        KeyConfig()
        bind_step_keys(block, hotkey_filter, KeyConfig, lambda: False)
        self.assertFalse(registered[KeyConfig.MOVE_RIGHT](1))  # type: ignore[operator]
        self.assertEqual(block.value(X), 0)
        self.assertIn(KeyConfig().get(KeyConfig.MOVE_RIGHT), block.field(X).toolTip())

    def test_horizontal_layout_puts_rows_on_one_line(self) -> None:
        """The short-strip form puts all four fields on one row, and the stacked form uses two."""
        block = GeometryBlock()
        block.resize(600, 80)
        block.show()
        self.assertGreater(block.field(WIDTH).y(), block.field(X).y())
        block.set_horizontal(True)
        block.resize(600, 40)
        self.assertEqual(block.field(WIDTH).y(), block.field(X).y())
        self.assertLess(block.field(X).x(), block.field(Y).x())
        block.set_horizontal(False)
        self.assertEqual(block.horizontal(), False)

    def test_stacked_columns_line_up(self) -> None:
        """X lines up over W and Y over H, with the lock between W and H."""
        block = GeometryBlock()
        block.resize(300, 60)
        block.show()
        self.assertEqual(block.field(X).x(), block.field(WIDTH).x())
        self.assertEqual(block.field(Y).x(), block.field(HEIGHT).x())
        self.assertGreater(block.lock_button().x(), block.field(WIDTH).x())
        self.assertLess(block.lock_button().x(), block.field(HEIGHT).x())

    def test_limits(self) -> None:
        """Owner-set limits clamp typed values."""
        block = GeometryBlock()
        block.set_limits(WIDTH, 64, 1024)
        block.field(WIDTH).set_value(5000)
        self.assertEqual(block.value(WIDTH), 1024)
        block.field(WIDTH).set_value(1)
        self.assertEqual(block.value(WIDTH), 64)
