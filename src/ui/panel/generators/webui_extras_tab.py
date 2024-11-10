"""UI for setting extended options related to the WebUI Stable Diffusion generator."""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QSizePolicy

from src.config.cache import Cache
from src.ui.input_fields.seed_value_spinbox import SeedValueSpinbox
from src.ui.layout.divider import Divider
from src.ui.panel.generators.stable_diffusion_panel import ExtrasTab
from src.util.layout import clear_layout, synchronize_widths
from src.util.shared_constants import BUTTON_TEXT_GENERATE, BUTTON_TOOLTIP_GENERATE


class WebUIExtrasTab(ExtrasTab):
    """UI for setting extended options related to the WebUI Stable Diffusion generator."""

    def __init__(self) -> None:
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._orientation = Qt.Orientation.Horizontal

        cache = Cache()

        self._subseed_spinbox = SeedValueSpinbox(Cache.WEBUI_SUBSEED, Cache.WEBUI_LAST_SUBSEED)
        self._subseed_label = QLabel(cache.get_label(Cache.WEBUI_SUBSEED))
        self._subseed_label.setToolTip(self._subseed_spinbox.toolTip())
        self._subseed_label.setBuddy(self._subseed_spinbox)

        self._last_subseed_textbox = Cache().get_control_widget(Cache.WEBUI_LAST_SUBSEED)
        self._last_subseed_textbox.setReadOnly(True)
        self._last_subseed_label = QLabel(Cache().get_label(Cache.WEBUI_LAST_SUBSEED))
        self._last_subseed_label.setToolTip(self._last_subseed_textbox.toolTip())
        self._last_subseed_label.setBuddy(self._last_subseed_textbox)

        self._subseed_strength_slider = cache.get_control_widget(Cache.WEBUI_SUBSEED_STRENGTH)
        self._subseed_strength_label = QLabel(cache.get_label(Cache.WEBUI_SUBSEED_STRENGTH))
        self._subseed_strength_label.setToolTip(self._subseed_strength_slider.toolTip())
        self._subseed_strength_label.setBuddy(self._subseed_strength_slider)

        self._seed_resize_checkbox = cache.get_control_widget(Cache.WEBUI_SEED_RESIZE_ENABLED)
        self._seed_resize_checkbox.setText(cache.get_label(cache.WEBUI_SEED_RESIZE_ENABLED))
        self._seed_resize_input = cache.get_control_widget(Cache.WEBUI_SEED_RESIZE)

        def _enable_seed_resize_input(enabled: bool) -> None:
            self._seed_resize_input.setEnabled(enabled)

        cache.connect(self, Cache.WEBUI_SEED_RESIZE_ENABLED, _enable_seed_resize_input)
        _enable_seed_resize_input(cache.get(Cache.WEBUI_SEED_RESIZE_ENABLED))

        self._tiling_checkbox = cache.get_control_widget(Cache.WEBUI_TILING)
        self._tiling_checkbox.setText(cache.get_label(Cache.WEBUI_TILING))

        self._face_restore_checkbox = cache.get_control_widget(Cache.WEBUI_RESTORE_FACES)
        self._face_restore_checkbox.setText(cache.get_label(Cache.WEBUI_RESTORE_FACES))

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
                row_layout.addWidget(right_side_widget, stretch=1)
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
                (self._subseed_strength_label, self._subseed_strength_slider),
                (self._tiling_checkbox, None),
                (self._face_restore_checkbox, None)
            ]

            right_column_rows: list[tuple[QWidget, Optional[QWidget]]] = [
                (self._seed_resize_checkbox, None),
                (self._seed_resize_input, None),
                (self._subseed_label, self._subseed_spinbox),
                (self._last_subseed_label, self._last_subseed_textbox),
            ]

            for column_layout, row_structure in ((left_column, left_column_rows), (right_column, right_column_rows)):
                left_column_widgets: list[QWidget] = []
                right_column_widgets: list[QWidget] = []
                for left_widget, right_widget in row_structure:
                    _build_row(column_layout, left_widget, right_widget, left_column_widgets, right_column_widgets)
                synchronize_widths(left_column_widgets)
                synchronize_widths(right_column_widgets)
            right_column.insertStretch(right_column.count() - 2, 100)
            right_column.addWidget(self._extra_generate_button)

        else:  # Vertical:
            self._layout.setSpacing(2)
            self._layout.setContentsMargins(2, 2, 2, 2)

            layout_rows: list[tuple[QWidget, Optional[QWidget]]] = [
                (self._subseed_label, self._subseed_spinbox),
                (self._last_subseed_label, self._last_subseed_textbox),
                (self._subseed_strength_label, self._subseed_strength_slider),
                (self._seed_resize_checkbox, None),
                (self._seed_resize_input, None),
                (self._tiling_checkbox, None),
                (self._face_restore_checkbox, None)
            ]
            left_column_widgets = []
            right_column_widgets = []
            for left_widget, right_widget in layout_rows:
                _build_row(self._layout, left_widget, right_widget, left_column_widgets, right_column_widgets)
            synchronize_widths(left_column_widgets)
            synchronize_widths(right_column_widgets)
            self._layout.addStretch(100)
            self._layout.addWidget(self._extra_generate_button)
