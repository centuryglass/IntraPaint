"""Tests the foreground/background color operations in color_controller."""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller import color_controller
from src.controller.color_controller import MAX_RECENT_COLORS, MAX_SAVED_COLORS
from src.tools.draw_tool import DrawTool
from test.base_test_case import IntraPaintTestCase
from test.tools.tool_test_case import ToolTestCase


class ColorControllerTest(IntraPaintTestCase):
    """Tests the foreground/background color operations in color_controller."""

    def test_new_keys_load_defaults_from_old_cache_files(self) -> None:
        """The test cache file predates the background and recent color keys, so they load their defaults."""
        self.assertEqual(Cache().get(Cache.BACKGROUND_COLOR), '#ffffffff')
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), [])
        self.assertEqual(color_controller.background(), QColor(Qt.GlobalColor.white))

    def test_set_color_writes_lowercase_argb(self) -> None:
        """Config.set_color stores colors as lowercase #aarrggbb strings, whatever form they came from."""
        Cache().set_color(Cache.LAST_BRUSH_COLOR, QColor('#80ABCDEF'))
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#80abcdef')
        Cache().set_color(Cache.BACKGROUND_COLOR, Qt.GlobalColor.red)
        self.assertEqual(Cache().get(Cache.BACKGROUND_COLOR), '#ffff0000')

    def test_swap_exchanges_colors(self) -> None:
        """swap() writes each color to the other key, in canonical form, without touching recent colors."""
        Cache().set(Cache.LAST_BRUSH_COLOR, '#FF112233')
        Cache().set(Cache.BACKGROUND_COLOR, '#80445566')
        color_controller.swap()
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#80445566')
        self.assertEqual(Cache().get(Cache.BACKGROUND_COLOR), '#ff112233')
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), [])

    def test_reset_sets_black_and_white(self) -> None:
        """reset() sets an opaque black foreground and an opaque white background."""
        Cache().set(Cache.LAST_BRUSH_COLOR, '#80112233')
        Cache().set(Cache.BACKGROUND_COLOR, '#80445566')
        color_controller.reset()
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#ff000000')
        self.assertEqual(Cache().get(Cache.BACKGROUND_COLOR), '#ffffffff')
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), [])

    def test_only_commits_record_recent_colors(self) -> None:
        """A browsing write leaves recent colors alone; a committed one adds the color to the front."""
        color_controller.set_foreground(QColor('#ff00ff00'), commit=False)
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), [])
        color_controller.set_foreground(QColor('#ff0000ff'))
        color_controller.set_background(QColor('#ffff0000'))
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#ff0000ff')
        self.assertEqual(Cache().get(Cache.BACKGROUND_COLOR), '#ffff0000')
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), ['#ffff0000', '#ff0000ff'])

    def test_recent_colors_dedupe(self) -> None:
        """Committing a color already in the list moves it to the front, matching across letter case."""
        Cache().set(Cache.RECENT_COLORS, ['#FF111111', '#ff222222', '#ff333333'])
        color_controller.commit_color(QColor('#ff111111'))
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), ['#ff111111', '#ff222222', '#ff333333'])
        color_controller.commit_color(QColor('#ff333333'))
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), ['#ff333333', '#ff111111', '#ff222222'])
        self.assertEqual(color_controller.recent_colors(),
                         [QColor('#ff333333'), QColor('#ff111111'), QColor('#ff222222')])

    def test_recent_colors_cap(self) -> None:
        """The recent colors list keeps the newest MAX_RECENT_COLORS colors."""
        for i in range(MAX_RECENT_COLORS + 4):
            color_controller.commit_color(QColor(i, 0, 0))
        recent = Cache().get(Cache.RECENT_COLORS)
        self.assertEqual(len(recent), MAX_RECENT_COLORS)
        self.assertEqual(recent[0], QColor(MAX_RECENT_COLORS + 3, 0, 0).name(QColor.NameFormat.HexArgb))
        self.assertEqual(recent[-1], QColor(4, 0, 0).name(QColor.NameFormat.HexArgb))

    def test_invalid_recent_entries_are_dropped(self) -> None:
        """Saved entries that aren't colors are skipped when reading and dropped on the next commit."""
        Cache().set(Cache.RECENT_COLORS, ['not a color', '#ff222222'])
        self.assertEqual(color_controller.recent_colors(), [QColor('#ff222222')])
        color_controller.commit_color(QColor('#ff111111'))
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), ['#ff111111', '#ff222222'])

    def test_save_color_appends_without_duplicates(self) -> None:
        """save_color adds new colors to the end in canonical form and ignores a color already saved."""
        AppConfig().set(AppConfig.SAVED_COLORS, [])
        color_controller.save_color(QColor('#FF112233'))
        color_controller.save_color(QColor('#80445566'))
        color_controller.save_color(QColor('#ff112233'))
        self.assertEqual(AppConfig().get(AppConfig.SAVED_COLORS), ['#ff112233', '#80445566'])

    def test_remove_saved_color(self) -> None:
        """remove_saved_color drops one color by index, along with blank and invalid entries."""
        AppConfig().set(AppConfig.SAVED_COLORS, ['#ff112233', '', 'not a color', '#80445566', '#ff778899'])
        self.assertEqual([color.name(QColor.NameFormat.HexArgb) for color in color_controller.saved_colors()],
                         ['#ff112233', '#80445566', '#ff778899'])
        color_controller.remove_saved_color(1)
        self.assertEqual(AppConfig().get(AppConfig.SAVED_COLORS), ['#ff112233', '#ff778899'])
        color_controller.remove_saved_color(5)
        self.assertEqual(AppConfig().get(AppConfig.SAVED_COLORS), ['#ff112233', '#ff778899'])

    def test_insert_saved_color_adds_or_moves(self) -> None:
        """insert_saved_color inserts a new color before an index, and moves a saved color there instead of
        duplicating it."""
        AppConfig().set(AppConfig.SAVED_COLORS, ['#ff000001', '#ff000002', '#ff000003'])
        color_controller.insert_saved_color(QColor('#ff000009'), 1)
        self.assertEqual(AppConfig().get(AppConfig.SAVED_COLORS), ['#ff000001', '#ff000009', '#ff000002', '#ff000003'])
        color_controller.insert_saved_color(QColor('#ff000001'), 3)
        self.assertEqual(AppConfig().get(AppConfig.SAVED_COLORS), ['#ff000009', '#ff000002', '#ff000001', '#ff000003'])
        color_controller.insert_saved_color(QColor('#ff000003'), 0)
        self.assertEqual(AppConfig().get(AppConfig.SAVED_COLORS), ['#ff000003', '#ff000009', '#ff000002', '#ff000001'])


def _full_saved_list() -> list[str]:
    return [f'#ff0000{index:02x}' for index in range(MAX_SAVED_COLORS)]


class SavedColorsCapTest(IntraPaintTestCase):
    """Tests the MAX_SAVED_COLORS cap on saved colors."""

    def test_save_color_stops_at_cap(self) -> None:
        """A full list refuses new colors and reports it, and a color already saved is refused too."""
        full = _full_saved_list()
        AppConfig().set(AppConfig.SAVED_COLORS, full[:-1])
        self.assertFalse(color_controller.saved_colors_full())
        self.assertTrue(color_controller.save_color(QColor(full[-1])))
        self.assertTrue(color_controller.saved_colors_full())
        self.assertFalse(color_controller.save_color(QColor('#ffabcdef')))
        self.assertFalse(color_controller.save_color(QColor(full[0])))
        self.assertEqual(AppConfig().get(AppConfig.SAVED_COLORS), full)

    def test_insert_into_full_list_only_moves(self) -> None:
        """A full list refuses a new color dropped into it, but still reorders a color already saved."""
        full = _full_saved_list()
        AppConfig().set(AppConfig.SAVED_COLORS, full)
        self.assertFalse(color_controller.insert_saved_color(QColor('#ffabcdef'), 0))
        self.assertEqual(AppConfig().get(AppConfig.SAVED_COLORS), full)
        self.assertTrue(color_controller.insert_saved_color(QColor(full[-1]), 0))
        self.assertEqual(AppConfig().get(AppConfig.SAVED_COLORS), [full[-1], *full[:-1]])

    def test_over_cap_config_is_truncated(self) -> None:
        """A hand-edited list past the cap reads as its first MAX_SAVED_COLORS colors, and the next change drops the
        rest."""
        full = _full_saved_list()
        AppConfig().set(AppConfig.SAVED_COLORS, [*full, '#ffabcdef', '#ff123456'])
        self.assertEqual([color.name(QColor.NameFormat.HexArgb) for color in color_controller.saved_colors()], full)
        self.assertEqual(color_controller.saved_color_index(QColor('#ffabcdef')), -1)
        color_controller.remove_saved_color(0)
        self.assertEqual(AppConfig().get(AppConfig.SAVED_COLORS), full[1:])

    def test_saved_color_index(self) -> None:
        """saved_color_index finds a color in canonical form, or returns -1."""
        AppConfig().set(AppConfig.SAVED_COLORS, ['#ff112233', '#80445566'])
        self.assertEqual(color_controller.saved_color_index(QColor('#80445566')), 1)
        self.assertEqual(color_controller.saved_color_index(QColor('#FF112233')), 0)
        self.assertEqual(color_controller.saved_color_index(QColor('#ff112234')), -1)


class SwapColorsDrawTest(ToolTestCase):
    """Tests that the draw tool paints with the foreground color after a swap."""

    def test_draw_after_swap_uses_old_background(self) -> None:
        """A stroke drawn after swap() paints the color that was the background."""
        Cache().set_color(Cache.LAST_BRUSH_COLOR, Qt.GlobalColor.black)
        Cache().set_color(Cache.BACKGROUND_COLOR, QColor('#ff00c000'))
        Cache().set(Cache.DRAW_TOOL_OPACITY, 1.0)
        Cache().set(Cache.DRAW_TOOL_HARDNESS, 1.0)
        Cache().set(Cache.DRAW_TOOL_BRUSH_SIZE, 9)
        layer = self.image_stack.create_layer()
        self.image_stack.active_layer = layer
        draw_tool = DrawTool(self.image_stack, self.image_viewer)
        self.tool_controller.add_tool(draw_tool)
        self.activate_tool(draw_tool)

        color_controller.swap()
        self.mouse_drag([QPoint(100, 100), QPoint(120, 100), QPoint(140, 100)])

        self.assertEqual(layer.image.pixelColor(QPoint(120, 100)), QColor('#ff00c000'))
