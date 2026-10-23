"""The WebUI generator's settings for the Advanced section: seed variation and resizing, tiling and face restoration."""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout

from src.config.cache import Cache
from src.ui.input_fields.seed_value_spinbox import SeedValueSpinbox
from src.ui.layout.label_column_layout import normalize_row_label
from src.ui.panel.generators.stable_diffusion_panel import (SUMMARY_ADVANCED_DEFAULT, AdvancedControls, LabeledRows,
                                                            config_slider_field, group_label)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.generators.webui_advanced_controls'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


GROUP_TITLE_SEED_VARIATION = _tr('Seed variation')
GROUP_TITLE_OUTPUT = _tr('Output')
LABEL_LAST_VARIATION_SEED = _tr('Last variation seed')
LABEL_RESIZE_SEED_FROM = _tr('Resize seed from')
VARIATION_OFF = _tr('Off', 'Variation strength is zero')
SUMMARY_VARIATION = _tr('variation {strength}')
SUMMARY_TILING = _tr('tiling')
SUMMARY_RESTORE_FACES = _tr('restore faces')
SUMMARY_SEED_RESIZE = _tr('seed resize')


class WebUIAdvancedControls(AdvancedControls):
    """Variation seed and strength, seed resizing, tiling and face restoration."""

    def __init__(self) -> None:
        super().__init__()
        cache = Cache()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(group_label(GROUP_TITLE_SEED_VARIATION))
        self._subseed_input = SeedValueSpinbox(Cache.WEBUI_SUBSEED, Cache.WEBUI_LAST_SUBSEED)
        layout.addWidget(LabeledRows([(normalize_row_label(cache.get_label(Cache.WEBUI_SUBSEED)),
                                       self._subseed_input)]))
        self._last_subseed_label = QLabel()
        self._last_subseed_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._last_subseed_label.setToolTip(cache.get_tooltip(Cache.WEBUI_LAST_SUBSEED))

        def _last_subseed_update(last_subseed: str) -> None:
            self._last_subseed_label.setText(f'{LABEL_LAST_VARIATION_SEED} {last_subseed}')

        cache.connect(self._last_subseed_label, Cache.WEBUI_LAST_SUBSEED, _last_subseed_update)
        _last_subseed_update(cache.get(Cache.WEBUI_LAST_SUBSEED))
        layout.addWidget(self._last_subseed_label)

        self._strength_field = config_slider_field(cache, Cache.WEBUI_SUBSEED_STRENGTH, self, zero_text=VARIATION_OFF)
        layout.addWidget(self._strength_field)

        self._seed_resize_checkbox = cache.get_control_widget(Cache.WEBUI_SEED_RESIZE_ENABLED)
        self._seed_resize_checkbox.setText(LABEL_RESIZE_SEED_FROM)
        self._seed_resize_input = cache.get_control_widget(Cache.WEBUI_SEED_RESIZE)
        self._seed_resize_input.setToolTip(cache.get_tooltip(Cache.WEBUI_SEED_RESIZE))

        def _enable_seed_resize_input(enabled: bool) -> None:
            self._seed_resize_input.setEnabled(enabled)

        cache.connect(self._seed_resize_input, Cache.WEBUI_SEED_RESIZE_ENABLED, _enable_seed_resize_input)
        _enable_seed_resize_input(cache.get(Cache.WEBUI_SEED_RESIZE_ENABLED))
        layout.addWidget(self._seed_resize_checkbox)
        layout.addWidget(self._seed_resize_input)

        self._tiling_checkbox = cache.get_control_widget(Cache.WEBUI_TILING)
        self._face_restore_checkbox = cache.get_control_widget(Cache.WEBUI_RESTORE_FACES)
        layout.addWidget(group_label(GROUP_TITLE_OUTPUT))
        layout.addWidget(self._tiling_checkbox)
        layout.addWidget(self._face_restore_checkbox)

    def summary(self) -> str:
        """Names the variation, seed resizing, tiling and face restoration settings that are on."""
        cache = Cache()
        parts: list[str] = []
        strength = cache.get(Cache.WEBUI_SUBSEED_STRENGTH)
        if strength > 0:
            parts.append(SUMMARY_VARIATION.format(strength=f'{strength:g}'))
        if cache.get(Cache.WEBUI_SEED_RESIZE_ENABLED):
            parts.append(SUMMARY_SEED_RESIZE)
        if cache.get(Cache.WEBUI_TILING):
            parts.append(SUMMARY_TILING)
        if cache.get(Cache.WEBUI_RESTORE_FACES):
            parts.append(SUMMARY_RESTORE_FACES)
        return ', '.join(parts) if parts else SUMMARY_ADVANCED_DEFAULT

    def change_signals(self) -> list:
        """Returns the signals of the controls that `summary` reads."""
        return [self._strength_field.valueChanged, self._seed_resize_checkbox.valueChanged,
                self._tiling_checkbox.valueChanged, self._face_restore_checkbox.valueChanged]
