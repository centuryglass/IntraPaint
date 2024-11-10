"""UI for setting extended options related to the ComfyUI Stable Diffusion generator."""
from typing import cast, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication, QPushButton, QHBoxLayout, QSizePolicy

from src.config.cache import Cache
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox
from src.ui.layout.divider import Divider
from src.ui.panel.generators.stable_diffusion_panel import ExtrasTab
from src.util.layout import clear_layout, synchronize_widths
from src.util.shared_constants import BUTTON_TEXT_GENERATE, BUTTON_TOOLTIP_GENERATE

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.panel.generators.comfyui_extras_tab'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


BUTTON_TEXT_CLEAR_MEMORY = _tr('Clear Memory')
TOOLTIP_CLEAR_MEMORY = _tr('Removed cached models from GPU memory within ComfyUI.')


class ComfyUIExtrasTab(ExtrasTab):
    """UI for setting extended options related to the ComfyUI Stable Diffusion generator."""

    clear_comfyui_memory_signal = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._orientation = Qt.Orientation.Horizontal

        cache = Cache()
        self._model_config_dropdown = cache.get_control_widget(Cache.COMFYUI_MODEL_CONFIG)
        self._model_config_label = QLabel(cache.get_label(Cache.COMFYUI_MODEL_CONFIG))
        self._model_config_label.setToolTip(self._model_config_dropdown.toolTip())
        self._model_config_label.setBuddy(self._model_config_dropdown)

        self._inpainting_model_checkbox = cache.get_control_widget(Cache.COMFYUI_INPAINTING_MODEL)
        self._inpainting_model_checkbox.setText(cache.get_label(Cache.COMFYUI_INPAINTING_MODEL))

        self._tiled_vae_checkbox = cache.get_control_widget(Cache.COMFYUI_TILED_VAE)
        self._tiled_vae_checkbox.setText(cache.get_label(Cache.COMFYUI_TILED_VAE))

        self._vae_tile_slider = cast(IntSliderSpinbox, cache.get_control_widget(Cache.COMFYUI_TILED_VAE_TILE_SIZE))
        self._vae_tile_label = QLabel(cache.get_label(Cache.COMFYUI_TILED_VAE_TILE_SIZE))
        self._vae_tile_label.setToolTip(self._vae_tile_slider.toolTip())
        self._vae_tile_label.setBuddy(self._vae_tile_slider)

        def _enable_tile_inputs(enabled: bool) -> None:
            self._vae_tile_label.setEnabled(enabled)
            self._vae_tile_slider.setEnabled(enabled)
        cache.connect(self, Cache.COMFYUI_TILED_VAE, _enable_tile_inputs)
        _enable_tile_inputs(cache.get(Cache.COMFYUI_TILED_VAE))

        self._clear_memory_button = QPushButton()
        self._clear_memory_button.setText(BUTTON_TEXT_CLEAR_MEMORY)
        self._clear_memory_button.setToolTip(TOOLTIP_CLEAR_MEMORY)
        self._clear_memory_button.clicked.connect(self.clear_comfyui_memory_signal)
        self._clear_memory_button.setSizePolicy(QSizePolicy.Policy.MinimumExpanding,
                                                  QSizePolicy.Policy.MinimumExpanding)

        self._extra_generate_button = QPushButton()
        self._extra_generate_button.setText(BUTTON_TEXT_GENERATE)
        self._extra_generate_button.setToolTip(BUTTON_TOOLTIP_GENERATE)
        self._extra_generate_button.clicked.connect(self.generate_signal)
        self._extra_generate_button.setSizePolicy(QSizePolicy.Policy.MinimumExpanding,
                                                  QSizePolicy.Policy.MinimumExpanding)

        self.build_layout()

    def orientation(self) -> Qt.Orientation:
        """Returns the panel's orientation."""
        return self._orientation

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Update the panel orientation."""
        if orientation == self._orientation:
            return
        self._orientation = orientation
        self.build_layout()

    def build_layout(self) -> None:
        """Clear and rebuild the layout using the current orientation."""

        clear_layout(self._layout)

        def _build_row(vertical_layout: QVBoxLayout, left_side_widget: QWidget, right_side_widget: Optional[QWidget],
                       left_side_list: list[QWidget], right_side_list: list[QWidget]) -> None:

            if right_side_widget is None:
                vertical_layout.addWidget(left_side_widget)
            else:
                left_side_list.append(left_side_widget)
                right_side_list.append(right_side_widget)
                row_layout = QHBoxLayout()
                row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                row_layout.setSpacing(2)
                row_layout.setContentsMargins(1, 1, 1, 1)
                row_layout.addWidget(left_side_widget)
                row_layout.addWidget(right_side_widget)
                vertical_layout.addLayout(row_layout)

        if self._orientation == Qt.Orientation.Horizontal:
            self._layout.setSpacing(0)
            self._layout.setContentsMargins(0, 0, 0, 0)

            main_layout = QHBoxLayout()
            main_layout.setSpacing(0)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self._layout.addLayout(main_layout)

            left_column = QVBoxLayout()
            left_column.setSpacing(2)
            left_column.setContentsMargins(2, 2, 2, 2)
            left_column.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

            right_column = QVBoxLayout()
            right_column.setSpacing(2)
            right_column.setContentsMargins(2, 2, 2, 2)
            right_column.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

            main_layout.addLayout(left_column, stretch=30)
            main_layout.addWidget(Divider(Qt.Orientation.Vertical))
            main_layout.addLayout(right_column, stretch=10)

            left_column_rows: list[tuple[QWidget, Optional[QWidget]]] = [
                (self._model_config_label, self._model_config_dropdown),
                (self._inpainting_model_checkbox, None),
                (self._tiled_vae_checkbox, None),
                (self._vae_tile_label, self._vae_tile_slider)
            ]

            # Right side is empty for now, besides the buttons that get manually added at the end.
            right_column_rows: list[tuple[QWidget, Optional[QWidget]]] = []

            for column_layout, row_structure in ((left_column, left_column_rows), (right_column, right_column_rows)):
                left_column_widgets: list[QWidget] = []
                right_column_widgets: list[QWidget] = []
                for left_widget, right_widget in row_structure:
                    _build_row(column_layout, left_widget, right_widget, left_column_widgets, right_column_widgets)
                synchronize_widths(left_column_widgets)
                synchronize_widths(right_column_widgets)
            right_column.addStretch(100)
            right_column.addWidget(self._clear_memory_button)
            right_column.addWidget(self._extra_generate_button)

        else:  # Vertical:
            self._layout.setSpacing(2)
            self._layout.setContentsMargins(2, 2, 2, 2)

            left_column_widgets = []
            right_column_widgets = []

            layout_rows: list[tuple[QWidget, Optional[QWidget]]] = [
                (self._model_config_label, self._model_config_dropdown),
                (self._inpainting_model_checkbox, None),
                (self._tiled_vae_checkbox, None),
                (self._vae_tile_label, self._vae_tile_slider)
            ]
            for left_widget, right_widget in layout_rows:
                _build_row(self._layout, left_widget, right_widget, left_column_widgets, right_column_widgets)
            synchronize_widths(left_column_widgets)
            synchronize_widths(right_column_widgets)
            self._layout.addStretch(100)
            self._layout.addWidget(self._clear_memory_button)
            self._layout.addWidget(self._extra_generate_button)
