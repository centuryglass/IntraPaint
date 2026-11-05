"""Shows a key binding to the user, drawn as raised keycaps, and follows its config value."""
from typing import Optional

from PySide6.QtCore import Qt, QRect, QPoint, QPointF, QSize
from PySide6.QtGui import QKeySequence, QPainter, QPaintEvent, QFont
from PySide6.QtWidgets import QLabel, QWidget

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.util.visual.key_hint_text import key_hint_labels, shortest_key_label
from src.util.visual.keycap import KEYCAP_SEPARATOR, draw_keycap_row, keycap_colors, keycap_font, keycap_row_size


class KeyHintLabel(QLabel):
    """Shows a key binding to the user, drawn as one raised keycap per alternative binding.

    The labels come from `key_hint_labels`, and the keycaps are drawn by `draw_keycap_row`.
    """

    def __init__(self, keys: Optional[QKeySequence | Qt.KeyboardModifier | str] = None,
                 config_key: Optional[str] = None,
                 parent: Optional[QWidget] = None):
        super().__init__('', parent=parent)
        self._labels: list[str] = []
        font = QFont()
        self._default_size = AppConfig().get(AppConfig.KEY_HINT_FONT_SIZE)
        font.setPointSize(self._default_size)
        self.setFont(font)
        self.setTextFormat(Qt.TextFormat.RichText)
        self._saved_size: Optional[QSize] = None
        self._compact = False
        self._shortest_only = False
        self._key_codes: Optional[QKeySequence | Qt.KeyboardModifier | str] = None
        self._config_key = config_key
        if keys is None and config_key is not None:
            keys = KeyConfig().get(config_key)
        self._update_text(keys)
        if config_key is not None:
            KeyConfig().connect(self, config_key, self._key_update_slot)

        def _update_size(size: int) -> None:
            updated_font = QFont(self.font())
            updated_font.setPointSize(size)
            self.setFont(updated_font)
        AppConfig().connect(self, AppConfig.KEY_HINT_FONT_SIZE, _update_size)
        # A bound method of this widget is dropped when it is destroyed, before it would run.
        self.destroyed.connect(lambda: self._disconnect_config())  # pylint: disable=unnecessary-lambda

    def _disconnect_config(self) -> None:
        """Removes the config registrations. Runs from `destroyed`, so it also covers deletion with a parent."""
        AppConfig().disconnect(self, AppConfig.KEY_HINT_FONT_SIZE)
        if self._config_key is not None:
            KeyConfig().disconnect(self, self._config_key)

    def _key_font(self) -> QFont:
        """Returns the bold font the key text is drawn in."""
        return keycap_font(self.font())

    # Naming conventions must match Qt:
    # pylint: disable=invalid-name
    def sizeHint(self) -> QSize:
        """Returns the size of the keycap row."""
        if self._saved_size is None:
            self._saved_size = keycap_row_size(self._labels, self._key_font())
        return QSize(self._saved_size)

    def minimumSizeHint(self) -> QSize:
        """Returns the size hint, since a smaller label cuts off the keycap."""
        return self.sizeHint()

    def setText(self, text: str) -> None:
        """Update label text, clearing saved text size calculations."""
        self._saved_size = None
        super().setText(text)

    def setFont(self, font: QFont) -> None:
        """Update label font, clearing saved text size calculations."""
        self._saved_size = None
        super().setFont(font)

    def paintEvent(self, event: Optional[QPaintEvent]):
        """Draw the keycaps and their key text."""
        if len(self._labels) == 0:
            super().paintEvent(event)
            return
        own_bounds = QRect(QPoint(), self.size())
        text_bounds = QRect(QPoint(), keycap_row_size(self._labels, self._key_font()))
        alignment = self.alignment()
        if alignment & Qt.AlignmentFlag.AlignHCenter == Qt.AlignmentFlag.AlignHCenter:
            text_bounds.moveLeft((own_bounds.width() - text_bounds.width()) // 2)
        elif alignment & Qt.AlignmentFlag.AlignRight == Qt.AlignmentFlag.AlignRight:
            text_bounds.moveLeft(own_bounds.width() - text_bounds.width())
        if alignment & Qt.AlignmentFlag.AlignVCenter == Qt.AlignmentFlag.AlignVCenter:
            text_bounds.moveTop((own_bounds.height() - text_bounds.height()) // 2)
        elif alignment & Qt.AlignmentFlag.AlignBottom == Qt.AlignmentFlag.AlignBottom:
            text_bounds.moveTop(own_bounds.height() - text_bounds.height())
        painter = QPainter(self)
        painter.setClipRect(own_bounds)
        draw_keycap_row(painter, QPointF(text_bounds.topLeft()), self._labels, self._key_font(), self.palette())
        painter.end()

    @property
    def compact(self) -> bool:
        """Whether modifiers show as symbols, such as "⇧S" for "Shift+S"."""
        return self._compact

    def set_compact(self, compact: bool) -> None:
        """Shows modifiers as symbols, or as names if `compact` is false."""
        if compact != self._compact:
            self._compact = compact
            self._update_text(self._key_codes)

    @property
    def shortest_only(self) -> bool:
        """Whether only the shortest of several key combinations shows."""
        return self._shortest_only

    def set_shortest_only(self, shortest_only: bool) -> None:
        """Shows only the shortest key combination, or the first of those tied for shortest, or all of them if
        `shortest_only` is false."""
        if shortest_only != self._shortest_only:
            self._shortest_only = shortest_only
            self._update_text(self._key_codes)

    @property
    def labels(self) -> list[str]:
        """Returns the label of each keycap shown."""
        return list(self._labels)

    def _update_text(self, key_codes: Optional[QKeySequence | Qt.KeyboardModifier | str]) -> None:
        self._key_codes = key_codes
        labels = key_hint_labels(key_codes, self._compact)
        self._labels = shortest_key_label(labels) if self._shortest_only else labels
        key_display_str = KEYCAP_SEPARATOR.join(self._labels)
        for invalid_str, replacement in (('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;'), ('"', '&quot;'),
                                         ("'", '&apos;')):
            key_display_str = key_display_str.replace(invalid_str, replacement)
        if key_display_str == '':
            self.setText('')
            return
        text_color = keycap_colors(self.palette())[2].name()
        self.setText(f'<span style="color: {text_color};"><strong>{key_display_str}</strong></span>')

    def _key_update_slot(self, key_string: str) -> None:
        self._update_text(key_string)
