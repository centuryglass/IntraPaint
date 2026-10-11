"""How a selection tool combines a new shape with the existing selection.

`SelectionMode` is the persisted choice (`Cache.SELECTION_MODE`). `selection_mode_for_gesture` applies the add and
subtract modifiers on top of it for one gesture, and `compose_selection_path` and `compose_selection_image` apply the
result to a selection layer image.
"""
from enum import Enum
from typing import Optional

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QImage, QPainter, QPainterPath, QColor

from src.config.cache import Cache
from src.config.key_config import KeyConfig


class SelectionMode(Enum):
    """How a new shape combines with the existing selection. Values match the `Cache.SELECTION_MODE` options."""
    ADD = 'Add'
    SUBTRACT = 'Subtract'
    REPLACE = 'Replace'
    INTERSECT = 'Intersect'

    @property
    def keeps_unrelated_content(self) -> bool:
        """Whether pixels outside the new shape's bounds are left alone."""
        return self in (SelectionMode.ADD, SelectionMode.SUBTRACT)


def stored_selection_mode() -> SelectionMode:
    """Returns the mode saved in `Cache.SELECTION_MODE`, or ADD if the saved value is unrecognized."""
    try:
        return SelectionMode(Cache().get(Cache.SELECTION_MODE))
    except ValueError:
        return SelectionMode.ADD


def selection_mode_for_gesture(stored_mode: Optional[SelectionMode] = None,
                               held_modifiers: Optional[Qt.KeyboardModifier] = None) -> SelectionMode:
    """Returns the mode for a gesture that starts with the given modifiers held.

    The add modifier selects ADD, the subtract modifier selects SUBTRACT, and both together select INTERSECT. With
    neither held, the stored mode applies. `held_modifiers` defaults to the application's current modifiers.
    """
    if stored_mode is None:
        stored_mode = stored_selection_mode()
    add_held = KeyConfig.modifier_held(KeyConfig.SELECTION_ADD_MODIFIER, held_modifiers=held_modifiers)
    subtract_held = KeyConfig.modifier_held(KeyConfig.SELECTION_SUBTRACT_MODIFIER, held_modifiers=held_modifiers)
    if add_held and subtract_held:
        return SelectionMode.INTERSECT
    if add_held:
        return SelectionMode.ADD
    if subtract_held:
        return SelectionMode.SUBTRACT
    return stored_mode


def compose_selection_path(image: QImage, path: QPainterPath, color: QColor, mode: SelectionMode) -> None:
    """Combines a path with the selection in `image`, in place. The path is in image coordinates.

    Only the path's area changes for ADD and SUBTRACT. REPLACE and INTERSECT also clear everything outside it, so the
    caller must hand over the whole selection image.
    """
    painter = QPainter(image)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    if mode == SelectionMode.SUBTRACT:
        painter.fillPath(path, color)
    elif mode == SelectionMode.REPLACE:
        painter.fillRect(QRectF(image.rect()), color)
    elif mode == SelectionMode.INTERSECT:
        outside = QPainterPath()
        outside.addRect(QRectF(image.rect()))
        painter.fillPath(outside.subtracted(path), color)
    if mode in (SelectionMode.ADD, SelectionMode.REPLACE):
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.fillPath(path, color)
    painter.end()


def compose_selection_image(image: QImage, mask: QImage, mode: SelectionMode) -> None:
    """Combines `mask`, an image the same size as `image` where non-transparent pixels are selected, with the
       selection in `image`, in place."""
    painter = QPainter(image)
    if mode == SelectionMode.ADD:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    elif mode == SelectionMode.SUBTRACT:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
    elif mode == SelectionMode.REPLACE:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    else:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    painter.drawImage(0, 0, mask)
    painter.end()
