"""View available extra networks/models."""
import logging
import re
from typing import Dict, Optional, List, cast

from PySide6.QtCore import Qt, QSize, QPoint, Signal
from PySide6.QtGui import QImage, QPainter, QMouseEvent, QIcon
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, \
    QVBoxLayout, QWidget, QScrollArea

from src.config.application_config import AppConfig
from src.ui.layout.bordered_widget import BorderedWidget
from src.ui.widget.image_widget import ImageWidget
from src.util.display_size import max_font_size
from src.util.shared_constants import APP_ICON_PATH

logger = logging.getLogger(__name__)


PAGE_TITLE = 'Lora Models'

ADD_BUTTON_LABEL = 'Add to prompt'
REMOVE_BUTTON_LABEL = 'Remove from prompt'
CLOSE_BUTTON_LABEL = 'Close'

LORA_KEY_NAME = 'name'
LORA_KEY_ALIAS = 'alias'
LORA_KEY_PATH = 'path'
LORA_KEY_METADATA = 'metadata'
PLACEHOLDER_TEXT = 'LORA'

PREVIEW_SIZE = 150


class ExtraNetworkWindow(QDialog):
    """View available extra networks/models."""

    def __init__(self, loras: List[Dict[str, str]], images: Dict[str, Optional[QImage]]) -> None:
        super().__init__()

        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self._layout = QVBoxLayout(self)
        self._loras: List[Dict[str, str]] = []
        self._list_items: List[_LoraItem] = []
        self._image_placeholder: Optional[QImage] = None

        for lora in loras:
            self._loras.append(lora.copy())

        self._lora_list = QWidget()
        self._lora_scroll = QScrollArea()
        self._lora_scroll.setWidget(self._lora_list)
        self._lora_scroll.setWidgetResizable(True)
        self._layout.addWidget(self._lora_scroll)

        list_layout = QVBoxLayout(self._lora_list)
        for lora in self._loras:
            lora_name = lora[LORA_KEY_NAME]
            if lora_name in images:
                thumbnail = images[lora_name]
            else:
                thumbnail = self._missing_image_placeholder()
            if thumbnail is None:
                thumbnail = self._missing_image_placeholder()
            list_item = _LoraItem(lora, thumbnail)
            list_item.selected.connect(self._update_selections)
            self._list_items.append(list_item)
            list_layout.addWidget(list_item)

        button_layout = QHBoxLayout()
        self._layout.addLayout(button_layout)
        self._prompt_button = QPushButton()
        self._prompt_button.setText(ADD_BUTTON_LABEL)
        self._prompt_button.clicked.connect(self._add_remove_prompt)
        button_layout.addWidget(self._prompt_button, stretch=1)
        button_layout.addStretch(1)
        close_button = QPushButton()
        close_button.setText(CLOSE_BUTTON_LABEL)
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button, stretch=1)

    def _update_selections(self, selected_lora: BorderedWidget) -> None:
        for lora_item in self._list_items:
            if lora_item.is_selected and lora_item != selected_lora:
                lora_item.is_selected = False
        selected_lora = cast(_LoraItem, selected_lora)
        if _prompt_lora_match(selected_lora.lora) is not None:
            self._prompt_button.setText(REMOVE_BUTTON_LABEL)
        else:
            self._prompt_button.setText(ADD_BUTTON_LABEL)

    def _missing_image_placeholder(self) -> QImage:
        if self._image_placeholder is not None:
            return self._image_placeholder
        self._image_placeholder = QImage(QSize(PREVIEW_SIZE, PREVIEW_SIZE), QImage.Format.Format_ARGB32_Premultiplied)
        self._image_placeholder.fill(Qt.GlobalColor.black)
        painter = QPainter(self._image_placeholder)
        painter.setPen(Qt.GlobalColor.white)
        font = painter.font()
        pt_size = max_font_size(PLACEHOLDER_TEXT, font, QSize(PREVIEW_SIZE, PREVIEW_SIZE))
        font.setPointSize(pt_size)
        painter.setFont(font)
        painter.drawText(QPoint(0, PREVIEW_SIZE // 2), PLACEHOLDER_TEXT)
        painter.end()
        return self._image_placeholder

    def _add_remove_prompt(self) -> None:
        selected_lora: Optional[Dict[str, str]] = None
        for lora_item in self._list_items:
            if lora_item.is_selected:
                selected_lora = lora_item.lora
                break
        if selected_lora is None:
            return
        lora_match = _prompt_lora_match(selected_lora)
        prompt = AppConfig().get(AppConfig.PROMPT)
        if lora_match is not None:
            prompt = prompt[:lora_match.start()] + prompt[lora_match.end():]
            self._prompt_button.setText(ADD_BUTTON_LABEL)
        else:
            prompt = prompt + f' <lora:{selected_lora[LORA_KEY_NAME]}:1.0>'
            self._prompt_button.setText(REMOVE_BUTTON_LABEL)
        AppConfig().set(AppConfig.PROMPT, prompt)


def _prompt_lora_match(lora: Dict[str, str]) -> Optional[re.Match[str]]:
    prompt = AppConfig().get(AppConfig.PROMPT)
    pattern = re.compile('<lora:' + lora[LORA_KEY_NAME] + r':[\d.]+>')
    return re.search(pattern, prompt)


class _LoraItem(BorderedWidget):
    """Represents a Lora model"""

    selected = Signal(BorderedWidget)

    def __init__(self, lora: Dict[str, str], thumbnail: QImage) -> None:
        super().__init__()
        self._lora = lora
        self._selected = False
        self._layout = QHBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        image_widget = ImageWidget(thumbnail)
        image_widget.setMinimumSize(PREVIEW_SIZE, PREVIEW_SIZE)
        image_widget.setMaximumSize(PREVIEW_SIZE, PREVIEW_SIZE)
        self._layout.addWidget(image_widget, stretch=0)
        self._layout.addStretch(1)
        label = QLabel(lora[LORA_KEY_NAME])
        self._layout.addWidget(label, stretch=2)

    @property
    def lora(self) -> Dict[str, str]:
        """Returns the Lora model data associated with this item."""
        return self._lora

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Select this item when left-clicked."""
        assert event is not None
        if event.button() == Qt.MouseButton.LeftButton and not self.is_selected:
            self.is_selected = True

    @property
    def is_selected(self) -> bool:
        """Returns whether this item is currently the selected item."""
        return self._selected

    @is_selected.setter
    def is_selected(self, is_selected: bool) -> None:
        if self._selected == is_selected:
            return
        self._selected = is_selected
        self.line_width = 6 if is_selected else 2
        if is_selected:
            self.selected.emit(self)
