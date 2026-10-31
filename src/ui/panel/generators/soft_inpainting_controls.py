"""Soft inpainting controls for the Mask section of the Stable Diffusion panel.

The checkbox, a hint about narrow mask blur and a fold of backend-specific settings. The settings' fields are built from
the `ParameterDef` list the connected backend published (`soft_inpainting_adapter`), as the ControlNet panel builds its
preprocessor fields. The controls hide while the backend lacks soft inpainting. The widget itself stays shown, since
a `REQUIRED` panel item can't be hidden, and takes no height while all its controls are hidden.
"""
from functools import partial
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.sd_adapters.soft_inpainting_adapter import (
    SOFT_INPAINTING_MIN_USEFUL_MASK_BLUR, load_parameter_defs, load_values, save_value)
from src.ui.ink_style import caution_color
from src.ui.layout.panel_fit import FIELD_MAX_WIDTH
from src.ui.widget.panel_section import PanelSection
from src.ui.widget.parameter_def_widget import create_parameter_field, create_parameter_widget, \
    is_numeric_field_parameter
from src.util.parameter_def_labels import parameter_label, parameter_tooltip

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.generators.soft_inpainting_controls'


def _tr(*args):
    """Any text desired should be translated using _tr. Never use QApplication.translate directly."""
    return QApplication.translate(TR_ID, *args)


LABEL_SETTINGS = _tr('Soft inpainting settings')
HINT_NARROW_BLUR = _tr('Soft inpainting works best with a mask blur of {blur} or more: the blurred edge sets how '
                       'gradually the content changes.')


class SoftInpaintingControls(QWidget):
    """The soft inpainting checkbox, narrow blur hint and settings fold.

    Attributes
    ----------
    checkbox: QWidget
        The `Cache.SOFT_INPAINTING` checkbox.
    hint: QLabel
        Shown while soft inpainting is on and the mask blur is below `SOFT_INPAINTING_MIN_USEFUL_MASK_BLUR`.
    fold: PanelSection
        Holds the backend's settings, shown while soft inpainting is on and the backend lists any.
    layout_changed: Signal
        Emitted after a change in which of the controls are visible, so the panel can plan its layout again.
    """

    layout_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        cache = Cache()
        self.checkbox = cache.get_control_widget(Cache.SOFT_INPAINTING)
        self.checkbox.setText(cache.get_label(Cache.SOFT_INPAINTING))
        self.hint = QLabel(HINT_NARROW_BLUR.format(blur=SOFT_INPAINTING_MIN_USEFUL_MASK_BLUR))
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(f'color: {caution_color().name()};')
        self._parameter_body = QWidget()
        self._parameter_layout = QVBoxLayout(self._parameter_body)
        self._parameter_layout.setContentsMargins(0, 0, 0, 0)
        self.fold = PanelSection(LABEL_SETTINGS, self._parameter_body, expanded=False)
        self.fold.expanded_changed.connect(lambda _expanded: self.layout_changed.emit())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for control in (self.checkbox, self.hint, self.fold):
            layout.addWidget(control)

        for key in (Cache.SOFT_INPAINTING_AVAILABLE, Cache.SOFT_INPAINTING):
            cache.connect(self, key, self._visibility_changed)
        AppConfig().connect(self, AppConfig.MASK_BLUR, self._visibility_changed)
        cache.connect(self, Cache.SOFT_INPAINTING_PARAMETERS, self._parameters_changed)
        self._rebuild_parameters()
        self._apply_visibility()

    def _apply_visibility(self) -> None:
        cache = Cache()
        available = cache.get(Cache.SOFT_INPAINTING_AVAILABLE)
        enabled = available and cache.get(Cache.SOFT_INPAINTING)
        narrow = AppConfig().get(AppConfig.MASK_BLUR) < SOFT_INPAINTING_MIN_USEFUL_MASK_BLUR
        self.checkbox.setVisible(available)
        self.hint.setVisible(enabled and narrow)
        self.fold.setVisible(enabled and self._parameter_layout.count() > 0)

    def _visibility_changed(self, *_) -> None:
        self._apply_visibility()
        self.layout_changed.emit()

    def _parameters_changed(self, *_) -> None:
        self._rebuild_parameters()
        self._visibility_changed()

    def _rebuild_parameters(self) -> None:
        """Replaces the settings' fields with ones for the backend's current settings."""
        while self._parameter_layout.count() > 0:
            item = self._parameter_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        saved = load_values()
        for parameter in load_parameter_defs():
            value: Any = saved.get(parameter.key, parameter.default_value)
            on_changed = partial(save_value, parameter.key)
            if is_numeric_field_parameter(parameter):
                field = create_parameter_field(parameter, value, on_changed)
                field.setMaximumWidth(FIELD_MAX_WIDTH)
                self._parameter_layout.addWidget(field)
            else:
                widget = create_parameter_widget(parameter, value, on_changed)
                widget.setToolTip(parameter_tooltip(parameter))
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.addWidget(QLabel(parameter_label(parameter)))
                row_layout.addWidget(widget)
                self._parameter_layout.addWidget(row)
