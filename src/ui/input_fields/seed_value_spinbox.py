"""A widget packaging a seed value input with 'randomize' and 'repeat' buttons."""
from typing import cast, Callable, Any

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import Qt, QIcon
from PySide6.QtWidgets import QWidget, QApplication, QHBoxLayout, QToolButton, QSizePolicy

from src.config.cache import Cache
from src.ui.input_fields.big_int_spinbox import BigIntSpinbox
from src.util.shared_constants import PROJECT_DIR, SMALL_ICON_SIZE

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.input_fields.seed_value_spinbox'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


TOOLTIP_REUSE_LAST = _tr('Reuse last seed value')
TOOLTIP_RANDOMIZE = _tr('Use a random seed')

ICON_PATH_REUSE_LAST_BUTTON = f'{PROJECT_DIR}/resources/icons/repeat.svg'
ICON_PATH_RANDOMIZE_BUTTON = f'{PROJECT_DIR}/resources/icons/randomize.svg'


class SeedValueSpinbox(QWidget):
    """A widget packaging a seed value input with 'randomize' and 'repeat' buttons."""

    valueChanged = Signal(str)

    def __init__(self, seed_cache_key: str, last_seed_cache_key: str) -> None:
        super().__init__()
        cache = Cache()
        self.setToolTip(cache.get_tooltip(seed_cache_key))
        self._seed_key = seed_cache_key
        self._last_seed_key = last_seed_cache_key

        self._layout = QHBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._layout.setSpacing(2)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._repeat_button = QToolButton()
        self._randomize_button = QToolButton()

        def _repeat_last() -> None:
            cache.set(self._seed_key, int(cache.get(self._last_seed_key)))

        def _randomize() -> None:
            cache.set(self._seed_key, -1)

        tool_button: QToolButton
        icon_path: str
        tooltip: str
        on_click: Callable[[], None]
        for tool_button, icon_path, tooltip, on_click in ((self._repeat_button, ICON_PATH_REUSE_LAST_BUTTON,
                                                           TOOLTIP_REUSE_LAST, _repeat_last),
                                                          (self._randomize_button, ICON_PATH_RANDOMIZE_BUTTON,
                                                           TOOLTIP_RANDOMIZE, _randomize)):
            tool_button.setToolTip(tooltip)
            tool_button.setContentsMargins(2, 2, 2, 2)
            icon = QIcon(icon_path)
            tool_button.setIcon(icon)
            tool_button.setIconSize(QSize(SMALL_ICON_SIZE, SMALL_ICON_SIZE))
            tool_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            tool_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            tool_button.clicked.connect(on_click)
            self._layout.addWidget(tool_button)
        self._seed_value_field = cast(BigIntSpinbox, Cache().get_control_widget(seed_cache_key))
        self._layout.addWidget(self._seed_value_field, stretch=1)
        self._seed_value_field.valueChanged.connect(self.valueChanged)

    def value(self) -> int:
        """Returns the current seed value."""
        return self._seed_value_field.value()

    def setValue(self, value: int) -> None:
        """Sets a new seed value."""
        self._seed_value_field.setValue(value)

    def stepBy(self, steps: int) -> None:
        """Offset the current value based on current step size and some integer step count."""
        self._seed_value_field.stepBy(steps)

    def stepEnabled(self) -> Any:
        """Returns whether incrementing/decrementing the value by steps is enabled."""
        return self._seed_value_field.stepEnabled()

    # noinspection PyPep8Naming
    def singleStep(self) -> int:
        """Returns the amount the spinbox value changes when controls are clicked once. """
        return self._seed_value_field.singleStep()

    def minimum(self) -> int:
        """Returns the current minimum accepted value."""
        return self._seed_value_field.minimum()

    def maximum(self) -> int:
        """Returns the current maximum accepted value."""
        return self._seed_value_field.maximum()
