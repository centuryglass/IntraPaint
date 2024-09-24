"""Panel holding pen pressure control checkboxes."""
from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QToolButton, QWidget

from src.config.cache import Cache
from src.ui.layout.bordered_widget import BorderedWidget
from src.util.shared_constants import PROJECT_DIR, ICON_SIZE

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.pen_pressure_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


LABEL_TEXT_PEN_PRESSURE = _tr('Pen Pressure:')
LABEL_TEXT_SIZE = _tr('Size:')
LABEL_TEXT_OPACITY = _tr('Opacity:')
LABEL_TEXT_HARDNESS = _tr('Hardness:')

ICON_PATH_SIZE = f'{PROJECT_DIR}/resources/icons/tool_modes/size.svg'
ICON_PATH_OPACITY = f'{PROJECT_DIR}/resources/icons/tool_modes/opacity.svg'
ICON_PATH_HARDNESS = f'{PROJECT_DIR}/resources/icons/tool_modes/hardness.svg'
ICON_PATH_SIZE_ACTIVE = f'{PROJECT_DIR}/resources/icons/tool_modes/size_active.svg'
ICON_PATH_OPACITY_ACTIVE = f'{PROJECT_DIR}/resources/icons/tool_modes/opacity_active.svg'
ICON_PATH_HARDNESS_ACTIVE = f'{PROJECT_DIR}/resources/icons/tool_modes/hardness_active.svg'


class PenPressurePanel(BorderedWidget):
    """Panel holding pen pressure control checkboxes."""

    def __init__(self, size_cache_key: Optional[str] = None, opacity_cache_key: Optional[str] = None,
                 hardness_key: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(2)
        self._layout.setContentsMargins(1, 1, 1, 1)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        if size_cache_key is None and opacity_cache_key is None and hardness_key is None:
            self.setVisible(False)
            return
        label = QLabel(LABEL_TEXT_PEN_PRESSURE)
        self._layout.addWidget(label)
        checkbox_layout = QHBoxLayout()
        checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for cache_key, icon_path, active_icon_path, label_text in (
                (size_cache_key, ICON_PATH_SIZE, ICON_PATH_SIZE_ACTIVE, LABEL_TEXT_SIZE),
                (opacity_cache_key, ICON_PATH_OPACITY, ICON_PATH_OPACITY_ACTIVE, LABEL_TEXT_OPACITY),
                (hardness_key, ICON_PATH_HARDNESS, ICON_PATH_HARDNESS_ACTIVE, LABEL_TEXT_HARDNESS)):
            if cache_key is not None:
                if checkbox_layout.count() > 0:
                    checkbox_layout.addStretch(1)

                label = QLabel(label_text)
                checkbox_layout.addWidget(label)
                checkbox_button = _PressureToggle(cache_key, icon_path, active_icon_path)
                label.setBuddy(checkbox_button)
                checkbox_layout.addWidget(checkbox_button)
        self._layout.addLayout(checkbox_layout)


class _PressureToggle(QToolButton):

    def __init__(self, key: str, icon_path: str, active_icon_path) -> None:
        super().__init__()
        inactive_icon = QIcon(icon_path)
        active_icon = QIcon(active_icon_path)
        self.setToolTip(Cache().get_tooltip(key))
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.setCheckable(True)
        self.setIcon(inactive_icon)

        def _on_button_toggle(checked: bool) -> None:
            self.setIcon(active_icon if checked else inactive_icon)
            if Cache().get(key) != checked:
                Cache().set(key, checked)

        self.toggled.connect(_on_button_toggle)
        self.setChecked(Cache().get(key))

        def _on_config_update(enabled: bool) -> None:
            self.setChecked(enabled)

        Cache().connect(self, key, _on_config_update)
