"""Search and pick extra networks (currently LoRA models) to add to the prompt, as a grid of cards.

Clicking a card adds the network's `<lora:name:weight>` tag to the prompt or removes it. The weight slider edits the
tag of the selected card. `_TAG_TYPE` is the only LoRA-specific part of the tag handling.
"""
import re
from typing import Optional

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QImage, QMouseEvent, QIcon, QPainter, QPalette, QColor
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, QScrollArea, \
    QApplication, QSizePolicy

from src.config.cache import Cache
from src.ui.input_fields.line_edit import LineEdit
from src.ui.input_fields.slider_field import SliderField
from src.ui.layout.bordered_widget import BorderedWidget
from src.ui.layout.flow_layout import FlowWidget
from src.ui.widget.image_widget import ImageWidget
from src.util.shared_constants import APP_ICON_PATH

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.window.extra_network_window'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


PAGE_TITLE = _tr('LoRA Models')

CLOSE_BUTTON_LABEL = _tr('Close')
PLACEHOLDER_TEXT = _tr('LoRA')
SEARCH_PLACEHOLDER = _tr('Search LoRA models')
WEIGHT_LABEL = _tr('Weight')
WEIGHT_TOOLTIP = _tr('Weight of the selected LoRA in the prompt. Add the LoRA to the prompt to change it.')
IN_PROMPT_LABEL = _tr('In prompt')
NO_MATCHES_LABEL = _tr('No LoRA models match the search.')

LORA_KEY_NAME = 'name'
LORA_KEY_ALIAS = 'alias'
LORA_KEY_PATH = 'path'
LORA_KEY_METADATA = 'metadata'

# The prompt tag type. Other network types use the same `<type:name:weight>` form.
_TAG_TYPE = 'lora'
DEFAULT_WEIGHT = 1.0
MIN_WEIGHT = -2.0
MAX_WEIGHT = 2.0
WEIGHT_STEP = 0.05

PREVIEW_SIZE = 150
PLACEHOLDER_HEIGHT = 60
CARD_SPACING = 6
SELECTED_LINE_WIDTH = 4
DEFAULT_LINE_WIDTH = 1
DIALOG_SIZE = QSize(720, 560)


def _tag_pattern(lora: dict[str, str]) -> re.Pattern[str]:
    return re.compile('<' + _TAG_TYPE + ':' + re.escape(lora[LORA_KEY_NAME]) + r':(-?[\d.]+)>')


def _prompt_lora_match(lora: dict[str, str]) -> Optional[re.Match[str]]:
    """Returns the match for the LoRA's tag in the prompt, or None if the prompt doesn't contain it."""
    return _tag_pattern(lora).search(Cache().get(Cache.PROMPT))


def _format_weight(weight: float) -> str:
    return str(round(weight, 2))


def _prompt_lora_weight(lora: dict[str, str]) -> Optional[float]:
    match = _prompt_lora_match(lora)
    if match is None:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return DEFAULT_WEIGHT


def _placeholder_image(size: QSize, palette: QPalette) -> QImage:
    """Returns a themed stand-in thumbnail: the palette's button color with the placeholder text in its text color."""
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(palette.color(QPalette.ColorRole.Button))
    painter = QPainter(image)
    text_color = QColor(palette.color(QPalette.ColorRole.ButtonText))
    text_color.setAlphaF(0.6)
    painter.setPen(text_color)
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, PLACEHOLDER_TEXT)
    painter.end()
    return image


class ExtraNetworkWindow(QDialog):
    """Search available extra networks and add them to or remove them from the prompt."""

    def __init__(self, loras: list[dict[str, str]], images: dict[str, Optional[QImage]]) -> None:
        super().__init__()
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle(PAGE_TITLE)
        self._loras: list[dict[str, str]] = [lora.copy() for lora in loras]
        self._cards: list[_LoraCard] = []
        self._selected: Optional[_LoraCard] = None
        layout = QVBoxLayout(self)

        self._search = LineEdit()
        self._search.setPlaceholderText(SEARCH_PLACEHOLDER)
        self._search.setClearButtonEnabled(True)
        self._search.valueChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

        self._grid = FlowWidget()
        self._grid.flow.setSpacing(CARD_SPACING)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._grid)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self._scroll, stretch=1)

        self._no_matches = QLabel(NO_MATCHES_LABEL)
        self._no_matches.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_matches.setVisible(False)
        layout.addWidget(self._no_matches)

        for lora in self._loras:
            thumbnail = images.get(lora[LORA_KEY_NAME])
            card = _LoraCard(lora, thumbnail)
            card.clicked.connect(self._toggle_card)
            self._cards.append(card)
            self._grid.flow.addWidget(card)

        footer = QHBoxLayout()
        layout.addLayout(footer)
        self._weight = SliderField(WEIGHT_LABEL, DEFAULT_WEIGHT, MIN_WEIGHT, MAX_WEIGHT, step=WEIGHT_STEP)
        self._weight.setToolTip(WEIGHT_TOOLTIP)
        self._weight.setEnabled(False)
        self._weight.valueChanged.connect(self._set_selected_weight)
        footer.addWidget(self._weight, stretch=1)
        footer.addStretch(1)
        close_button = QPushButton(CLOSE_BUTTON_LABEL)
        close_button.clicked.connect(self.close)
        footer.addWidget(close_button)
        self._refresh_marks()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns a size that shows several columns of cards."""
        return DIALOG_SIZE

    def _apply_filter(self, text: str) -> None:
        """Shows only the cards whose name or alias contains the search text, ignoring case."""
        needle = text.strip().lower()
        shown = 0
        for card in self._cards:
            lora = card.lora
            visible = needle in lora[LORA_KEY_NAME].lower() or needle in lora.get(LORA_KEY_ALIAS, '').lower()
            card.setVisible(visible)
            shown += int(visible)
        self._no_matches.setVisible(shown == 0 and len(self._cards) > 0)
        self._grid.updateGeometry()

    def _refresh_marks(self) -> None:
        for card in self._cards:
            card.in_prompt = _prompt_lora_match(card.lora) is not None
        self._sync_weight_field()

    def _sync_weight_field(self) -> None:
        weight = None if self._selected is None else _prompt_lora_weight(self._selected.lora)
        self._weight.setEnabled(weight is not None)
        if weight is not None:
            self._weight.blockSignals(True)
            self._weight.set_value(weight)
            self._weight.blockSignals(False)

    def _toggle_card(self, card: 'QWidget') -> None:
        """Selects the clicked card and adds its LoRA to the prompt, or removes it if the prompt already has it."""
        assert isinstance(card, _LoraCard)
        if self._selected is not None and self._selected is not card:
            self._selected.is_selected = False
        self._selected = card
        card.is_selected = True
        prompt = Cache().get(Cache.PROMPT)
        match = _prompt_lora_match(card.lora)
        if match is not None:
            prompt = prompt[:match.start()] + prompt[match.end():]
        else:
            tag = f'<{_TAG_TYPE}:{card.lora[LORA_KEY_NAME]}:{_format_weight(DEFAULT_WEIGHT)}>'
            prompt = f'{prompt} {tag}' if prompt else tag
        Cache().set(Cache.PROMPT, prompt)
        self._refresh_marks()

    def _set_selected_weight(self, weight: float) -> None:
        """Rewrites the selected LoRA's tag with the new weight."""
        if self._selected is None:
            return
        match = _prompt_lora_match(self._selected.lora)
        if match is None:
            return
        prompt = Cache().get(Cache.PROMPT)
        tag = f'<{_TAG_TYPE}:{self._selected.lora[LORA_KEY_NAME]}:{_format_weight(weight)}>'
        Cache().set(Cache.PROMPT, prompt[:match.start()] + tag + prompt[match.end():])


class _LoraCard(BorderedWidget):
    """A LoRA model's thumbnail, name and alias. Clicking it emits `clicked`."""

    clicked = Signal(QWidget)

    def __init__(self, lora: dict[str, str], thumbnail: Optional[QImage]) -> None:
        super().__init__()
        self._lora = lora
        self._selected = False
        self._in_prompt = False
        self.setFixedWidth(PREVIEW_SIZE + 2 * (SELECTED_LINE_WIDTH + 2))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(SELECTED_LINE_WIDTH + 2, SELECTED_LINE_WIDTH + 2,
                                  SELECTED_LINE_WIDTH + 2, SELECTED_LINE_WIDTH + 2)
        if thumbnail is None or thumbnail.isNull():
            thumbnail = _placeholder_image(QSize(PREVIEW_SIZE, PLACEHOLDER_HEIGHT), self.palette())
        elif thumbnail.width() > PREVIEW_SIZE or thumbnail.height() > PREVIEW_SIZE:
            thumbnail = thumbnail.scaled(PREVIEW_SIZE, PREVIEW_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
        image_widget = ImageWidget(thumbnail)
        image_widget.setFixedSize(PREVIEW_SIZE, thumbnail.height())
        image_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(image_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        name_label = self._add_label(lora[LORA_KEY_NAME])
        name_label.setToolTip(lora.get(LORA_KEY_PATH, lora[LORA_KEY_NAME]))
        alias = lora.get(LORA_KEY_ALIAS, '')
        if alias and alias != lora[LORA_KEY_NAME]:
            self._add_label(alias).setEnabled(False)
        self._mark = self._add_label(IN_PROMPT_LABEL)
        self._mark.setVisible(False)
        font = self._mark.font()
        font.setBold(True)
        self._mark.setFont(font)
        self._default_color = self.frame_color
        self._update_frame()

    def _add_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.layout().addWidget(label)  # type: ignore[union-attr]
        return label

    @property
    def lora(self) -> dict[str, str]:
        """Returns the LoRA model data this card shows."""
        return self._lora

    @property
    def in_prompt(self) -> bool:
        """Returns whether the prompt contains this card's LoRA."""
        return self._in_prompt

    @in_prompt.setter
    def in_prompt(self, in_prompt: bool) -> None:
        self._in_prompt = in_prompt
        self._mark.setVisible(in_prompt)
        self._update_frame()

    @property
    def is_selected(self) -> bool:
        """Returns whether this card is the window's selected card."""
        return self._selected

    @is_selected.setter
    def is_selected(self, selected: bool) -> None:
        self._selected = selected
        self._update_frame()

    def _update_frame(self) -> None:
        self.line_width = SELECTED_LINE_WIDTH if self._selected else DEFAULT_LINE_WIDTH
        if self._in_prompt:
            self.frame_color = self.palette().color(QPalette.ColorRole.Highlight)
        elif self._selected:
            self.frame_color = self.palette().color(QPalette.ColorRole.Text)
        else:
            self.frame_color = self._default_color

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name
        """Emits `clicked` on a left click."""
        assert event is not None
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
