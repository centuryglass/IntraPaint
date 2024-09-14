"""View, apply, and update saved stable-diffusion WebUI prompt info."""
import json
import logging
from typing import Dict, Optional, TypeAlias, List

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QHBoxLayout, QListWidget, QListWidgetItem, QLabel, QPushButton, \
    QVBoxLayout, QApplication

from src.config.cache import Cache
from src.ui.input_fields.line_edit import LineEdit
from src.ui.input_fields.plain_text_edit import PlainTextEdit
from src.util.shared_constants import APP_ICON_PATH

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.window.prompt_style_window'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


NAME_LABEL = _tr('Name:')
PROMPT_LABEL = _tr('Prompt:')
NEGATIVE_LABEL = _tr('Negative:')
ADD_BUTTON_LABEL = _tr('Add to prompt')
REPLACE_BUTTON_LABEL = _tr('Replace prompt')
SAVE_BUTTON_LABEL = _tr('Save changes')
CLOSE_BUTTON_LABEL = _tr('Close')

NAME_KEY = 'name'
PROMPT_KEY = 'prompt'
NEGATIVE_KEY = 'negative_prompt'
TextField: TypeAlias = PlainTextEdit | LineEdit


class PromptStyleWindow(QDialog):
    """View, apply, and update saved stable-diffusion WebUI prompt info."""

    should_save_changes = Signal(list)

    def __init__(self, save_enabled: bool = False) -> None:
        """View, apply, and update saved stable-diffusion WebUI prompt info."""
        super().__init__()
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self._save_enabled = save_enabled
        self._layout = QVBoxLayout(self)

        cache = Cache()
        self._style_options = []
        for style in cache.get(Cache.STYLES):
            assert isinstance(style, str)
            try:
                self._style_options.append(json.loads(style))
            except json.JSONDecodeError as err:
                logger.error(f'Prompt style parse failed: {err}')

        self._style_list = QListWidget()
        self._style_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._style_list.itemSelectionChanged.connect(self._update_preview)
        self._layout.addWidget(self._style_list)
        for style in self._style_options:
            assert isinstance(style, dict)
            QListWidgetItem(style[NAME_KEY], self._style_list)

        name_row = QHBoxLayout()
        self._layout.addLayout(name_row)
        name_row.addWidget(QLabel(NAME_LABEL), stretch=0)
        self._name_box = LineEdit()
        name_row.addWidget(self._name_box, stretch=1)

        self._layout.addWidget(QLabel(PROMPT_LABEL))
        self._prompt_box = PlainTextEdit()
        self._layout.addWidget(self._prompt_box)
        self._layout.addWidget(QLabel(NEGATIVE_LABEL))
        self._negative_box = PlainTextEdit()
        self._layout.addWidget(self._negative_box)

        button_layout = QHBoxLayout()
        self._layout.addLayout(button_layout)
        append_button = QPushButton()
        append_button.setText(ADD_BUTTON_LABEL)
        append_button.clicked.connect(self._append_prompt)
        button_layout.addWidget(append_button, stretch=1)
        button_layout.addStretch(1)

        replace_button = QPushButton()
        replace_button.setText(REPLACE_BUTTON_LABEL)
        replace_button.clicked.connect(self._replace_prompt)
        button_layout.addWidget(replace_button, stretch=1)
        button_layout.addStretch(1)

        text_fields: List[TextField] = [self._name_box, self._prompt_box, self._negative_box]
        for text_field in text_fields:
            text_field.valueChanged.connect(self._update_cached_styles)

        if save_enabled:
            self._save_button = QPushButton()
            self._save_button.setEnabled(False)
            self._save_button.setText(SAVE_BUTTON_LABEL)
            self._save_button.clicked.connect(lambda: self.should_save_changes.emit(self._style_options))
            button_layout.addWidget(self._save_button)
            button_layout.addStretch(1)

        close_button = QPushButton()
        close_button.setText(CLOSE_BUTTON_LABEL)
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button, stretch=1)

    def _get_selected_style(self) -> Optional[Dict[str, str]]:
        index = self._style_list.currentRow()
        if index is None:
            return None
        return self._style_options[index]

    def _append_prompt(self) -> None:
        selected = self._get_selected_style()
        if selected is None:
            return
        cache = Cache()
        prompt = cache.get(Cache.PROMPT)
        cache.set(Cache.PROMPT, f'{prompt} {selected[PROMPT_KEY]}')
        negative = cache.get(Cache.NEGATIVE_PROMPT)
        cache.set(Cache.NEGATIVE_PROMPT, f'{negative} {selected[NEGATIVE_KEY]}')

    def _replace_prompt(self) -> None:
        selected = self._get_selected_style()
        if selected is None:
            return
        cache = Cache()
        cache.set(Cache.PROMPT, selected[PROMPT_KEY])
        cache.set(Cache.NEGATIVE_PROMPT, selected[NEGATIVE_KEY])

    def _update_preview(self) -> None:
        selected = self._get_selected_style()
        text_fields: List[TextField] = [self._name_box, self._prompt_box, self._negative_box]
        field_keys = (NAME_KEY, PROMPT_KEY, NEGATIVE_KEY)
        if selected is None:
            for box in text_fields:
                box.valueChanged.disconnect(self._update_cached_styles)
                box.setValue('')
                box.setReadOnly(True)
                box.valueChanged.connect(self._update_cached_styles)
        else:
            for box, key in zip(text_fields, field_keys):
                box.valueChanged.disconnect(self._update_cached_styles)
                if self._save_enabled:
                    box.setReadOnly(False)
                box.setValue(selected[key])
                box.valueChanged.connect(self._update_cached_styles)

    def _update_cached_styles(self) -> None:
        selected = self._get_selected_style()
        if selected is None:
            return

        text_fields: List[TextField] = [self._name_box, self._prompt_box, self._negative_box]
        field_keys = (NAME_KEY, PROMPT_KEY, NEGATIVE_KEY)
        for box, key in zip(text_fields, field_keys):
            field_value = box.value()
            current_value = selected[key]
            if current_value != field_value:
                self._save_button.setEnabled(True)
                selected[key] = field_value
