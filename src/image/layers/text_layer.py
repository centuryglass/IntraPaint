"""Represents a layer in the image holding text data."""
from typing import Any, Optional

from PySide6.QtCore import Signal, QPoint, QPointF
from PySide6.QtGui import QImage, QTransform

from src.image.composite_mode import CompositeMode
from src.image.layers.non_destructive_layer import NonDestructiveLayer
from src.image.ora_extensions import OraWriteContext
from src.image.text_rect import TextRect
from src.util.cached_data import CachedData

# Attribute on a text layer's extended_data.xml entry holding its `TextRect.serialize()` JSON.
ORA_TEXT_DATA_TAG = 'text-data'

MAX_NAME_LENGTH_BEFORE_TRUNC = 10


class TextLayer(NonDestructiveLayer):
    """Represents a layer in the image holding text data."""

    text_data_changed = Signal(TextRect)

    def __init__(self, text_rect: Optional[TextRect]):
        """
        Initializes a new layer with text data.

        Parameters
        ----------
        text_rect: TextRect, optional
            New text rendering data.
        """
        super().__init__(self._get_name_from_text(text_rect))
        self._text_rect = text_rect if text_rect is not None else TextRect()
        self._image_cache = CachedData(self._text_rect.render_to_image())
        self.set_size(self._text_rect.size)

    @property
    def offset(self) -> QPointF:
        """Access the offset component of the layer transformation."""
        x_off = self.transform.dx()
        y_off = self.transform.dy()
        return QPointF(x_off, y_off)

    @offset.setter
    def offset(self, new_offset: QPoint | QPointF) -> None:
        transform = self.transform
        transform *= QTransform.fromTranslate(new_offset.x() - transform.dx(), new_offset.y() - transform.dy())
        self.transform = transform

    @property
    def text_rect(self) -> TextRect:
        """Returns text and text placement data for the layer."""
        return TextRect(self._text_rect)

    @text_rect.setter
    def text_rect(self, new_text: TextRect) -> None:
        """Updates the layer text content, adding the change to the undo history."""
        if self._text_rect != new_text:
            self._apply_combinable_change(new_text, self._text_rect, self.set_text_rect,
                                          'text_layer.text_rect')

    def get_qimage(self) -> QImage:
        """Return layer image data as an ARGB32 formatted QImage."""
        if self._image_cache.valid:
            return self._image_cache.data

        image = self._text_rect.render_to_image()
        self._image_cache.data = image
        return image

    def set_text_rect(self, new_text: TextRect) -> None:
        """Updates the layer text content without adding the change to the undo history."""
        if self._text_rect != new_text:
            new_text = TextRect(new_text)
            self._text_rect = new_text
            self._image_cache.invalidate()
            self.invalidate_pixmap()
            self.set_name(self._get_name_from_text())
            self.set_size(new_text.size)
            self.text_data_changed.emit(new_text)
            if self.visible and self.opacity > 0.0:
                self.signal_content_changed(self.bounds)

    def ora_extension_data(self, context: OraWriteContext) -> dict[str, str]:
        """Saves the text data so the layer reloads as an editable text layer."""
        return {ORA_TEXT_DATA_TAG: self._text_rect.serialize()}

    # LAYER/IMAGE FUNCTIONS:

    def copy(self) -> 'TextLayer':
        """Creates a copy of this layer."""
        layer = TextLayer(self._text_rect)
        layer.set_opacity(self.opacity)
        layer.set_visible(self.visible)
        layer.set_composition_mode(self.composition_mode)
        layer.set_transform(super()._get_transform())
        return layer

    def save_state(self) -> Any:
        """Export the current layer state, so it can be restored later."""
        return TextLayerState(self.name,
                              self.visible,
                              self.opacity,
                              self.composition_mode,
                              super()._get_transform(),
                              self.locked,
                              self.text_rect)

    def restore_state(self, saved_state: Any) -> None:
        """Restore the layer state from a previous saved state."""
        assert isinstance(saved_state, TextLayerState)
        self.set_name(saved_state.name)
        self.set_visible(saved_state.visible)
        self.set_opacity(saved_state.opacity)
        self.set_composition_mode(saved_state.mode)
        self.set_transform(saved_state.transform)
        self.set_text_rect(saved_state.text_rect)
        self.set_locked(saved_state.locked)

    # INTERNAL:

    def _get_name_from_text(self, text_rect: Optional[TextRect] = None) -> str:
        if not hasattr(self, '_text_rect'):
            name = '' if text_rect is None else text_rect.text
        else:
            name = self._text_rect.text if text_rect is None else text_rect.text
        if len(name) > MAX_NAME_LENGTH_BEFORE_TRUNC:
            name = f'{name[:MAX_NAME_LENGTH_BEFORE_TRUNC]}...'
        return f'"{name}"'


class TextLayerState:
    """Preserves a copy of a text layer's state."""

    def __init__(self, name: str, visible: bool, opacity: float, mode: CompositeMode,
                 transform: QTransform, locked: bool, text_rect: TextRect) -> None:
        self.name = name
        self.visible = visible
        self.opacity = opacity
        self.mode = mode
        self.transform = transform
        self.locked = locked
        self.text_rect = text_rect
