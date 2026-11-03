"""Tests the LoRA window's search, prompt marks, click-to-toggle and weight slider."""
import sys
from typing import Optional

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.ui.window.extra_network_window import ExtraNetworkWindow
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


def _lora(name: str, alias: Optional[str] = None) -> dict[str, str]:
    return {'name': name, 'alias': alias or name, 'path': f'/models/{name}.safetensors', 'metadata': '{}'}


class ExtraNetworkWindowTest(IntraPaintTestCase):
    """Builds the window over three LoRAs with an empty prompt."""

    def setUp(self) -> None:
        super().setUp()
        Cache().set(Cache.PROMPT, '')
        image = QImage(QSize(200, 100), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.red)
        self.window = ExtraNetworkWindow([_lora('add_detail'), _lora('film_grain', 'Grain (v2)'), _lora('a.b+c')],
                                         {'add_detail': image, 'film_grain': None})
        self.window.show()

    def _click(self, index: int) -> None:
        QTest.mouseClick(self.window._cards[index], Qt.MouseButton.LeftButton, pos=QPoint(5, 5))

    def test_click_adds_and_removes_tag(self) -> None:
        """A card click toggles its tag and its mark."""
        self._click(0)
        self.assertEqual(Cache().get(Cache.PROMPT), '<lora:add_detail:1.0>')
        self.assertTrue(self.window._cards[0].in_prompt)
        self._click(0)
        self.assertEqual(Cache().get(Cache.PROMPT), '')
        self.assertFalse(self.window._cards[0].in_prompt)

    def test_marks_existing_prompt_loras(self) -> None:
        """Cards for LoRAs already in the prompt start marked, including names with regex characters."""
        Cache().set(Cache.PROMPT, 'x <lora:a.b+c:0.5>')
        window = ExtraNetworkWindow([_lora('a.b+c'), _lora('aXb+c')], {})
        self.assertEqual([card.in_prompt for card in window._cards], [True, False])

    def test_weight_slider_rewrites_tag(self) -> None:
        """The slider edits only the selected LoRA's tag, and is disabled while it isn't in the prompt."""
        self.assertFalse(self.window._weight.isEnabled())
        self._click(1)
        self.assertTrue(self.window._weight.isEnabled())
        self.window._weight.set_value(0.65)
        self.assertEqual(Cache().get(Cache.PROMPT), '<lora:film_grain:0.65>')
        self.window._weight.set_value(-0.5)
        self.assertEqual(Cache().get(Cache.PROMPT), '<lora:film_grain:-0.5>')
        self._click(1)
        self.assertFalse(self.window._weight.isEnabled())

    def test_selecting_shows_prompt_weight(self) -> None:
        """Selecting a LoRA already in the prompt loads its weight without rewriting the prompt."""
        Cache().set(Cache.PROMPT, '<lora:add_detail:0.4> <lora:film_grain:1.5>')
        window = ExtraNetworkWindow([_lora('add_detail'), _lora('film_grain')], {})
        window._selected = window._cards[1]
        window._sync_weight_field()
        self.assertEqual(window._weight.value(), 1.5)
        self.assertEqual(Cache().get(Cache.PROMPT), '<lora:add_detail:0.4> <lora:film_grain:1.5>')

    def test_search_filters_by_name_and_alias(self) -> None:
        """Search matches names and aliases ignoring case, and reports an empty result."""
        self.window._search.setText('GRAIN')
        self.assertEqual([not card.isHidden() for card in self.window._cards], [False, True, False])
        self.window._search.setText('zzz')
        self.assertFalse(self.window._no_matches.isHidden())
        self.window._search.setText('')
        self.assertTrue(all(not card.isHidden() for card in self.window._cards))
        self.assertTrue(self.window._no_matches.isHidden())
