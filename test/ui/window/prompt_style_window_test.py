"""Tests the prompt style window's selection actions, footer buttons and `{prompt}` highlighting."""
import json
import sys

from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.ui.window.prompt_style_window import PromptStyleWindow, PLACEHOLDER
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

STYLE = {'name': 'Cinematic', 'prompt': '{prompt}, film grain', 'negative_prompt': 'flat'}


class PromptStyleWindowTest(IntraPaintTestCase):
    """Builds the window over one saved style."""

    def setUp(self) -> None:
        super().setUp()
        Cache().set(Cache.STYLES, [json.dumps(STYLE)])
        Cache().set(Cache.PROMPT, 'a cat')
        Cache().set(Cache.NEGATIVE_PROMPT, 'blur')

    def test_actions_need_selection(self) -> None:
        """Add and Replace are disabled until a style is selected."""
        window = PromptStyleWindow(save_enabled=True)
        self.assertFalse(window._append_button.isEnabled())
        window._append_button.click()
        self.assertEqual(Cache().get(Cache.PROMPT), 'a cat')
        window._style_list.setCurrentRow(0)
        self.assertTrue(window._append_button.isEnabled())
        self.assertTrue(window._replace_button.isEnabled())

    def test_add_and_replace(self) -> None:
        """Add appends the selected style to the prompts, and Replace overwrites them."""
        window = PromptStyleWindow(save_enabled=True)
        window._style_list.setCurrentRow(0)
        window._append_button.click()
        self.assertEqual(Cache().get(Cache.PROMPT), 'a cat {prompt}, film grain')
        self.assertEqual(Cache().get(Cache.NEGATIVE_PROMPT), 'blur flat')
        window._replace_button.click()
        self.assertEqual(Cache().get(Cache.PROMPT), STYLE['prompt'])
        self.assertEqual(Cache().get(Cache.NEGATIVE_PROMPT), 'flat')

    def test_save_footer(self) -> None:
        """Save changes starts disabled, enables on an edit, and emits the edited styles."""
        window = PromptStyleWindow(save_enabled=True)
        assert window._save_button is not None
        self.assertFalse(window._save_button.isEnabled())
        window._style_list.setCurrentRow(0)
        window._name_box.setValue('Renamed')
        self.assertTrue(window._save_button.isEnabled())
        saved: list[list] = []
        window.should_save_changes.connect(saved.append)
        window._save_button.click()
        self.assertEqual(saved[0][0]['name'], 'Renamed')

    def test_read_only_has_no_save(self) -> None:
        """Without save support the footer offers only Close."""
        window = PromptStyleWindow()
        self.assertIsNone(window._save_button)

    def test_placeholder_highlighted(self) -> None:
        """Every `{prompt}` in an editor gets the highlight format, and other text doesn't."""
        window = PromptStyleWindow(save_enabled=True)
        window._style_list.setCurrentRow(0)
        formats = window._prompt_box.document().firstBlock().layout().formats()
        self.assertEqual([(f.start, f.length) for f in formats], [(0, len(PLACEHOLDER))])
