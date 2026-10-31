"""Popup modal asking how to save a multi-layer image as an animation."""
from typing import Optional

from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from PySide6.QtGui import QIcon

from src.config.cache import Cache
from src.ui.modal.dialog_footer import DialogFooter
from src.util.shared_constants import APP_ICON_PATH
from src.util.visual.image_format_utils import AnimationSaveOptions

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.animation_save_modal'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


WINDOW_TITLE = _tr('Save animation')
INFO_LABEL = _tr('Each top-level layer is saved as one frame, with the bottom layer first. A frame lasts as long as '
                 'the "(120ms)" tag at the end of its layer name says.')
SAVE_BUTTON_LABEL = _tr('Save animation')


class AnimationSaveModal(QDialog):
    """Popup modal asking whether to save an animation, and with which frame duration and loop count.

    The last choices are kept in `Cache`.
    """

    def __init__(self, parent: Optional[QWidget] = None, allow_flattened: bool = True) -> None:
        super().__init__(parent)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setModal(True)
        self.setWindowTitle(WINDOW_TITLE)
        self._confirmed = False
        cache = Cache()

        info_label = QLabel(INFO_LABEL, self)
        info_label.setWordWrap(True)

        self._mode_checkbox = cache.get_control_widget(Cache.ANIMATION_SAVE_AS_ANIMATION)
        self._mode_checkbox.setText(cache.get_label(Cache.ANIMATION_SAVE_AS_ANIMATION))
        self._mode_checkbox.setToolTip(cache.get_tooltip(Cache.ANIMATION_SAVE_AS_ANIMATION))
        if not allow_flattened:
            self._mode_checkbox.setValue(True)
            self._mode_checkbox.setEnabled(False)

        self._duration_label = QLabel(cache.get_label(Cache.ANIMATION_FRAME_DURATION), self)
        self._duration_field = cache.get_control_widget(Cache.ANIMATION_FRAME_DURATION)
        duration_row = QWidget(self)
        duration_row.setToolTip(cache.get_tooltip(Cache.ANIMATION_FRAME_DURATION))
        duration_layout = QHBoxLayout(duration_row)
        duration_layout.addWidget(self._duration_label)
        duration_layout.addWidget(self._duration_field, stretch=1)

        self._loop_forever_checkbox = cache.get_control_widget(Cache.ANIMATION_LOOP_FOREVER)
        self._loop_forever_checkbox.setText(cache.get_label(Cache.ANIMATION_LOOP_FOREVER))
        self._loop_forever_checkbox.setToolTip(cache.get_tooltip(Cache.ANIMATION_LOOP_FOREVER))

        self._loop_count_label = QLabel(cache.get_label(Cache.ANIMATION_LOOP_COUNT), self)
        self._loop_count_field = cache.get_control_widget(Cache.ANIMATION_LOOP_COUNT)
        self._loop_count_row = QWidget(self)
        self._loop_count_row.setToolTip(cache.get_tooltip(Cache.ANIMATION_LOOP_COUNT))
        loop_count_layout = QHBoxLayout(self._loop_count_row)
        loop_count_layout.addWidget(self._loop_count_label)
        loop_count_layout.addWidget(self._loop_count_field, stretch=1)

        self._animation_controls = (duration_row, self._loop_forever_checkbox, self._loop_count_row)
        self._mode_checkbox.valueChanged.connect(self._update_enabled_controls)
        self._loop_forever_checkbox.valueChanged.connect(self._update_enabled_controls)
        self._update_enabled_controls()

        footer = DialogFooter(SAVE_BUTTON_LABEL, self)
        footer.accepted.connect(self._confirm)
        footer.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        for widget in (info_label, self._mode_checkbox, *self._animation_controls, footer):
            layout.addWidget(widget)

    def _update_enabled_controls(self, _=None) -> None:
        as_animation = bool(self._mode_checkbox.value())
        for widget in self._animation_controls:
            widget.setEnabled(as_animation)
        self._loop_count_row.setEnabled(as_animation and not self._loop_forever_checkbox.value())

    def _confirm(self) -> None:
        self._confirmed = True
        self.accept()

    def show_animation_save_modal(self) -> tuple[bool, Optional[AnimationSaveOptions]]:
        """Shows the modal. Returns whether the user confirmed, and if so the options for an animation save, or None
        for a flattened save."""
        self.exec()
        if not self._confirmed:
            return False, None
        if not self._mode_checkbox.value():
            return True, None
        return True, saved_animation_options()


def saved_animation_options() -> AnimationSaveOptions:
    """Returns the animation options last chosen in the save modal, from `Cache`."""
    cache = Cache()
    loop_count = 0 if cache.get(Cache.ANIMATION_LOOP_FOREVER) else cache.get(Cache.ANIMATION_LOOP_COUNT)
    return AnimationSaveOptions(cache.get(Cache.ANIMATION_FRAME_DURATION), loop_count)
