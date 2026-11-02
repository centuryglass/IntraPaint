"""Popup modal window that applies an arbitrary image filtering action."""
from typing import Callable, Optional, TypeAlias, Any

from PySide6.QtCore import QSize, Signal, QTimer
from PySide6.QtGui import QImage, QIcon, Qt
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QWidget, QHBoxLayout, QPushButton, QApplication

from src.ui.ink_style import set_signal
from src.ui.input_fields.check_box import CheckBox
from src.ui.widget.image_widget import ImageWidget
from src.util.async_task import AsyncTask
from src.util.parameter import Parameter
from src.util.shared_constants import APP_ICON_PATH
from src.ui.input_fields.field_factory import DynamicFieldWidget, create_input_widget

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.image_filter_modal'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SELECTED_ONLY_LABEL = _tr('Change selected areas only')
ACTIVE_ONLY_LABEL = _tr('Change active layer only')
CANCEL_BUTTON_TEXT = _tr('Cancel')
APPLY_BUTTON_TEXT = _tr('Apply')
MIN_PREVIEW_SIZE = 450
# Delay after the last input change before a preview render starts, so slider drags don't queue a render per tick.
PREVIEW_DEBOUNCE_MS = 100

# parameters: filter_param_values: list
FilterFunction: TypeAlias = Callable[[list[Any]], Optional[QImage]]
# Runs on the main thread and returns a function that renders the preview and is safe to run on a worker thread.
PreviewPreparer: TypeAlias = Callable[[list[Any]], Callable[[], Optional[QImage]]]


class ImageFilterModal(QDialog):
    """Popup modal window that applies an arbitrary image filtering action."""

    filter_active_only = Signal(bool)
    filter_selection_only = Signal(bool)

    def __init__(self,
                 title: str,
                 description: str,
                 parameters: list[Parameter],
                 prepare_preview: PreviewPreparer,
                 apply_filter: FilterFunction,
                 filter_selection_only_default: bool = True,
                 filter_active_layer_only_default: bool = True) -> None:
        super().__init__()
        self.setModal(True)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self._preview = ImageWidget(None, self)
        self._preview.setMinimumSize(QSize(MIN_PREVIEW_SIZE, MIN_PREVIEW_SIZE))
        self._layout = QFormLayout(self)
        self._param_inputs: list[DynamicFieldWidget] = []
        self._prepare_preview = prepare_preview
        self._preview_task: Optional[AsyncTask] = None
        self._preview_stale = False
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self._start_preview)
        self._apply_filter = apply_filter

        self.setWindowTitle(title)
        label = QLabel(description)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._layout.addRow(label)
        for param in parameters:
            field_widget = create_input_widget(param)
            self._param_inputs.append(field_widget)
            self._layout.addRow(param.name, field_widget)
            field_widget.valueChanged.connect(self._schedule_preview)

        self._selected_only_checkbox = CheckBox()
        set_signal(self._selected_only_checkbox)
        self._layout.addRow(self._selected_only_checkbox)
        self._selected_only_checkbox.setText(SELECTED_ONLY_LABEL)
        self._selected_only_checkbox.valueChanged.connect(self.filter_selection_only)
        self._selected_only_checkbox.setChecked(filter_selection_only_default)
        self._selected_only_checkbox.stateChanged.connect(self._schedule_preview)

        self._active_only_checkbox = CheckBox()
        self._layout.addRow(self._active_only_checkbox)
        self._active_only_checkbox.setText(ACTIVE_ONLY_LABEL)
        self._active_only_checkbox.valueChanged.connect(self.filter_active_only)
        self._active_only_checkbox.setChecked(filter_active_layer_only_default)
        self._active_only_checkbox.stateChanged.connect(self._schedule_preview)

        self._layout.addRow(self._preview)
        self._button_row = QWidget(self)
        button_layout = QHBoxLayout(self._button_row)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_button = QPushButton()
        self._apply_button.setText(APPLY_BUTTON_TEXT)
        self._apply_button.clicked.connect(self._apply_change)
        button_layout.addWidget(self._apply_button, stretch=1)
        self._cancel_button = QPushButton()
        self._cancel_button.setText(CANCEL_BUTTON_TEXT)
        self._cancel_button.clicked.connect(self.close)
        button_layout.addWidget(self._cancel_button, stretch=1)
        self._layout.addRow(self._button_row)
        self._start_preview()

    def _schedule_preview(self, _=None) -> None:
        """Restart the debounce timer; the preview renders once input stops changing."""
        self._preview_timer.start()

    def _start_preview(self) -> None:
        """Render the preview on a worker thread. Changes made while a render runs trigger one more render after it,
        using the latest values; intermediate values are skipped."""
        self._preview_timer.stop()
        if self._preview_task is not None:
            self._preview_stale = True
            return
        self._preview_stale = False
        param_values = [widget.value() for widget in self._param_inputs]
        render = self._prepare_preview(param_values)
        result: list[Optional[QImage]] = []

        def _run() -> None:
            result.append(render())

        task = AsyncTask(_run)
        self._preview_task = task

        # _finish must not reference task: the task's connection holds _finish, so that would leave a reference cycle.
        def _finish() -> None:
            self._preview_task = None
            if result and result[0] is not None:
                self._preview.image = result[0]
            if self._preview_stale:
                self._start_preview()
        task.finish_signal.connect(_finish)
        task.start()

    def _apply_change(self) -> None:
        param_values = [widget.value() for widget in self._param_inputs]
        self._apply_filter(param_values)
        self.close()
