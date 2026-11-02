"""The ComfyUI generator's settings for the Advanced section: model loading and tiled VAE encoding."""
from typing import Optional

from PySide6.QtWidgets import QApplication, QVBoxLayout

from src.config.cache import Cache
from src.ui.layout.label_column_layout import normalize_row_label
from src.ui.panel.generators.stable_diffusion_panel import (AdvancedControls, LabeledRows, config_slider_field,
                                                            group_label, option_combo_box)
from src.ui.input_fields.field_factory import create_control_widget

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.generators.comfyui_advanced_controls'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


GROUP_TITLE_MODEL_LOADING = _tr('Model loading')
GROUP_TITLE_ENCODING = _tr('Encoding')
LABEL_TILED_VAE = _tr('Tiled VAE encoding')
SUMMARY_MODEL_CONFIG = _tr('{config} config')
SUMMARY_INPAINTING_MODEL = _tr('inpainting model')
SUMMARY_TILED_VAE = _tr('tiled VAE {size}')


class ComfyUIAdvancedControls(AdvancedControls):
    """Model config, inpainting checkpoint loading, and tiled VAE encoding with its tile size."""

    def __init__(self) -> None:
        super().__init__()
        cache = Cache()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(group_label(GROUP_TITLE_MODEL_LOADING))
        self._model_config_dropdown = option_combo_box(cache, Cache.COMFYUI_MODEL_CONFIG, self)
        layout.addWidget(LabeledRows([(normalize_row_label(cache.get_label(Cache.COMFYUI_MODEL_CONFIG)),
                                       self._model_config_dropdown)]))
        self._inpainting_model_checkbox = create_control_widget(cache, Cache.COMFYUI_INPAINTING_MODEL)
        self._tiled_vae_checkbox = create_control_widget(cache, Cache.COMFYUI_TILED_VAE)
        self._tiled_vae_checkbox.setText(LABEL_TILED_VAE)
        self._tile_size_field = config_slider_field(cache, Cache.COMFYUI_TILED_VAE_TILE_SIZE, self, suffix=' px')

        def _enable_tile_size(enabled: bool) -> None:
            self._tile_size_field.setEnabled(enabled)

        cache.connect(self._tile_size_field, Cache.COMFYUI_TILED_VAE, _enable_tile_size)
        _enable_tile_size(bool(cache.get(Cache.COMFYUI_TILED_VAE)))
        layout.addWidget(self._inpainting_model_checkbox)
        layout.addWidget(group_label(GROUP_TITLE_ENCODING))
        layout.addWidget(self._tiled_vae_checkbox)
        layout.addWidget(self._tile_size_field)

    def summary(self) -> str:
        """Names the model config, and the inpainting checkpoint and tiled VAE settings that are on."""
        cache = Cache()
        parts = [SUMMARY_MODEL_CONFIG.format(config=cache.get(Cache.COMFYUI_MODEL_CONFIG))]
        if cache.get(Cache.COMFYUI_INPAINTING_MODEL):
            parts.append(SUMMARY_INPAINTING_MODEL)
        if cache.get(Cache.COMFYUI_TILED_VAE):
            parts.append(SUMMARY_TILED_VAE.format(size=cache.get(Cache.COMFYUI_TILED_VAE_TILE_SIZE)))
        return ', '.join(parts)

    def change_signals(self) -> list:
        """Returns the signals of the controls that `summary` reads."""
        return [self._model_config_dropdown.valueChanged, self._inpainting_model_checkbox.valueChanged,
                self._tiled_vae_checkbox.valueChanged, self._tile_size_field.valueChanged]
