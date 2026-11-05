"""A small row of raised keycaps showing a fixed key binding, for panel section headers and panel headers.

Unlike `KeyHintLabel`, it reads no config: the owner passes the binding and updates it when the binding changes. It
paints from the palette, so it follows palette changes without caching colors.
"""
from typing import Optional

from PySide6.QtCore import QPointF, QSize
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

from src.util.visual.key_hint_text import key_hint_labels
from src.util.visual.keycap import draw_keycap_row, keycap_font, keycap_row_size


class KeycapBadge(QWidget):
    """Draws a key binding as one keycap per alternative, as `key_hint_labels` formats it."""

    # Whether keycaps draw their labels. Image tests that must not depend on fonts turn it off:
    DRAW_TEXT = True

    def __init__(self, text: str = '', parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._text = text
        self._labels = key_hint_labels(text)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    @property
    def text(self) -> str:
        """Returns the key binding, such as "Shift+S,K"."""
        return self._text

    @property
    def labels(self) -> list[str]:
        """Returns the label of each keycap shown."""
        return list(self._labels)

    def set_text(self, text: str) -> None:
        """Changes the key binding and resizes the badge to fit."""
        if text != self._text:
            self._text = text
            self._labels = key_hint_labels(text)
            self.updateGeometry()
            self.update()

    def sizeHint(self) -> QSize:
        """Returns the size of the keycap row."""
        return keycap_row_size(self._labels, keycap_font(self.font()))

    def minimumSizeHint(self) -> QSize:
        """Returns the same size as `sizeHint`."""
        return self.sizeHint()

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the keycaps in the palette's keycap colors."""
        painter = QPainter(self)
        draw_keycap_row(painter, QPointF(0, 0), self._labels, keycap_font(self.font()), self.palette(),
                        draw_text=self.DRAW_TEXT)
        painter.end()
