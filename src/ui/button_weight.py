"""The four push button weights: primary, standard, flat and danger.

`InkStyle` draws a weight from the push button's properties, so a panel sets one with `set_button_weight` and adds no
per-widget stylesheet. Every icon-only button also gets a tooltip naming its action and key.
"""
from enum import Enum

from PySide6.QtWidgets import QPushButton

from src.ui.ink_style import PRIMARY_BUTTON_PROPERTY, SIGNAL_PROPERTY


class ButtonWeight(Enum):
    """How much visual weight a push button carries, from the panel's main action down to a quiet one."""
    PRIMARY = 'primary'
    STANDARD = 'standard'
    FLAT = 'flat'
    DANGER = 'danger'


def set_button_weight(button: QPushButton, weight: ButtonWeight) -> None:
    """Gives a push button one of the four button weights, replacing any weight it had before.

    - PRIMARY: the raised accent sticker. A panel has at most one, and every Generate button uses it.
    - STANDARD: the default look.
    - FLAT: no fill or outline until hovered.
    - DANGER: signal-colored text, for actions that discard work. Place it apart from the buttons beside it, with
      a spacer or its own row.

    Other styles draw PRIMARY and DANGER buttons as standard ones.
    """
    button.setProperty(PRIMARY_BUTTON_PROPERTY, weight == ButtonWeight.PRIMARY)
    button.setProperty(SIGNAL_PROPERTY, weight == ButtonWeight.DANGER)
    button.setFlat(weight == ButtonWeight.FLAT)
    button.update()


def button_weight(button: QPushButton) -> ButtonWeight:
    """Returns the weight of a push button, as set by `set_button_weight`, `set_primary_button` or `set_signal`."""
    if button.property(PRIMARY_BUTTON_PROPERTY):
        return ButtonWeight.PRIMARY
    if button.property(SIGNAL_PROPERTY):
        return ButtonWeight.DANGER
    return ButtonWeight.FLAT if button.isFlat() else ButtonWeight.STANDARD
