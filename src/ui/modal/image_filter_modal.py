"""Popup modal window that applies an arbitrary image filtering action.

The preview fills the left of the window and the filter's controls sit in a column on the right. A window taller than
it is wide stacks them instead. Holding the compare button, or the compare modifier key, shows the unfiltered image.
"""
from dataclasses import dataclass
from typing import Callable, Optional, TypeAlias, Any

from shiboken6 import isValid
from PySide6.QtCore import QEvent, QRect, QSize, Signal, QTimer
from PySide6.QtGui import QImage, QIcon, QKeyEvent, QPainter, QPaintEvent, QResizeEvent, Qt
from PySide6.QtWidgets import (QApplication, QBoxLayout, QDialog, QLabel, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from src.config.key_config import KeyConfig
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.field_factory import create_input_widget
from src.ui.input_fields.segmented_control import DisplayMode, MAX_SEGMENTS, Segment, SegmentedControl
from src.ui.input_fields.slider_field import number_field_for_parameter
from src.ui.ink_style import set_signal
from src.ui.layout.label_column_layout import normalize_row_label
from src.ui.modal.controls_column import ControlsColumn, fit_dialog_to_screen, stack_body_for_size
from src.ui.modal.dialog_footer import DialogFooter
from src.ui.modal.modal_parent import modal_parent
from src.ui.widget.panel_section import PanelSection
from src.util.async_task import AsyncTask
from src.util.parameter import Parameter, TYPE_FLOAT, TYPE_INT, TYPE_STR
from src.util.shared_constants import APP_ICON_PATH
from src.util.visual.geometry_utils import get_scaled_placement
from src.util.visual.text_drawing_utils import get_key_display_string

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.image_filter_modal'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SELECTED_ONLY_LABEL = _tr('Change selected areas only')
ACTIVE_ONLY_LABEL = _tr('Change active layer only')
SCOPE_SECTION_TITLE = _tr('Scope')
APPLY_BUTTON_TEXT = _tr('Apply {filter_name}')
COMPARE_BUTTON_TEXT = _tr('Hold to compare')
COMPARE_BUTTON_TOOLTIP = _tr('Hold to show the original image.')
COMPARE_BUTTON_TOOLTIP_WITH_KEY = _tr('Hold to show the original image. Holding {key} does the same.')
MIN_PREVIEW_SIZE = 240
PREFERRED_PREVIEW_SIZE = QSize(520, 420)
CONTROLS_COLUMN_WIDTH = 300
# Delay after the last input change before a preview render starts, so slider drags don't queue a render per tick.
PREVIEW_DEBOUNCE_MS = 100
COMPARE_BUTTON_MARGIN = 8

# parameters: filter_param_values: list
FilterFunction: TypeAlias = Callable[[list[Any]], Optional[QImage]]
# Runs on the main thread and returns a function that renders the preview and is safe to run on a worker thread.
PreviewPreparer: TypeAlias = Callable[[list[Any]], Callable[[], Optional[QImage]]]
# Like `PreviewPreparer`, for the same region of the image with no filter applied.
OriginalPreparer: TypeAlias = Callable[[], Callable[[], Optional[QImage]]]


class _FilterPreview(QWidget):
    """Shows the filtered preview scaled to fit with its aspect ratio kept, or the original while comparing.

    The size hint is independent of the image size, so a large image never makes the dialog larger than the screen.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._image: Optional[QImage] = None
        self._original: Optional[QImage] = None
        self._comparing = False
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(QSize(MIN_PREVIEW_SIZE, MIN_PREVIEW_SIZE))
        self.compare_button = QPushButton(COMPARE_BUTTON_TEXT, self)
        self.compare_button.setAutoDefault(False)
        self.compare_button.pressed.connect(lambda: self.set_comparing(True))
        self.compare_button.released.connect(lambda: self.set_comparing(False))

    @property
    def image(self) -> Optional[QImage]:
        """The filtered preview image."""
        return self._image

    @image.setter
    def image(self, image: Optional[QImage]) -> None:
        self._image = image
        self.update()

    @property
    def original(self) -> Optional[QImage]:
        """The unfiltered image over the same region, if the filter provides one."""
        return self._original

    @original.setter
    def original(self, image: Optional[QImage]) -> None:
        self._original = image
        self.update()

    @property
    def comparing(self) -> bool:
        """Whether the original is shown in place of the preview."""
        return self._comparing

    def set_comparing(self, comparing: bool) -> None:
        """Shows the original in place of the preview, or the preview again."""
        if comparing == self._comparing:
            return
        self._comparing = comparing
        self.update()

    def shown_image(self) -> Optional[QImage]:
        """Returns the image the widget currently draws."""
        if self._comparing and self._original is not None:
            return self._original
        return self._image

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns a fixed preferred size."""
        return PREFERRED_PREVIEW_SIZE

    def resizeEvent(self, event: QResizeEvent) -> None:  # pylint: disable=invalid-name
        """Keeps the compare button in the bottom left corner."""
        super().resizeEvent(event)
        button_size = self.compare_button.sizeHint()
        self.compare_button.setGeometry(COMPARE_BUTTON_MARGIN, self.height() - button_size.height()
                                        - COMPARE_BUTTON_MARGIN, button_size.width(), button_size.height())

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the shown image scaled to the widget, keeping its aspect ratio."""
        image = self.shown_image()
        if image is None or image.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        bounds: QRect = get_scaled_placement(self.size(), image.size(), 2)
        painter.drawImage(bounds, image)
        painter.end()


@dataclass
class _ParameterControl:
    """A parameter's widget (with its label, where it has one) and the functions that read and write its value."""
    widget: QWidget
    value: Callable[[], Any]
    set_value: Callable[[Any], None]
    changed: Any


def _build_parameter_control(parameter: Parameter) -> _ParameterControl:
    """Creates the control for a filter parameter: a slider field for a number, a segmented control for a short list
    of options, and the generic input widget for anything else."""
    label = normalize_row_label(parameter.name)
    if parameter.type_name in (TYPE_INT, TYPE_FLOAT):
        field = number_field_for_parameter(parameter)
        field.set_label(label)
        return _ParameterControl(field, field.value, field.set_value, field.valueChanged)
    if parameter.type_name == TYPE_STR and parameter.options is not None and 2 <= len(
            parameter.options) <= MAX_SEGMENTS:
        # The options are the stored values, so the segments carry them raw:
        options = [str(option) for option in parameter.options]
        control = SegmentedControl([Segment(option, option) for option in options], display_mode=DisplayMode.LABEL,
                                   combo_fallback=True)
        if isinstance(parameter.default_value, str):
            control.set_value(parameter.default_value)
        control.setToolTip(parameter.description)
        return _ParameterControl(_labeled(label, control, parameter.description), control.value, control.set_value,
                                 control.valueChanged)
    widget = create_input_widget(parameter)
    if isinstance(widget, CheckBox):
        widget.setText(label)
        return _ParameterControl(widget, widget.value, widget.setValue, widget.valueChanged)
    return _ParameterControl(_labeled(label, widget, parameter.description), widget.value, widget.setValue,
                             widget.valueChanged)


def _labeled(label: str, widget: QWidget, description: str) -> QWidget:
    """Puts a label above a control."""
    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 0, 0, 0)
    container_layout.setSpacing(2)
    label_widget = QLabel(label)
    label_widget.setBuddy(widget)
    label_widget.setToolTip(description)
    container_layout.addWidget(label_widget)
    container_layout.addWidget(widget)
    return container


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
                 filter_active_layer_only_default: bool = True,
                 prepare_original: Optional[OriginalPreparer] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(modal_parent(parent))
        self.setModal(True)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle(title)
        self._preview = _FilterPreview(self)
        self._param_inputs: list[_ParameterControl] = []
        self._prepare_preview = prepare_preview
        self._prepare_original = prepare_original
        self._preview_task: Optional[AsyncTask] = None
        self._preview_stale = False
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self._start_preview)
        self._apply_filter = apply_filter

        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        controls_layout.addWidget(description_label)
        for param in parameters:
            control = _build_parameter_control(param)
            self._param_inputs.append(control)
            controls_layout.addWidget(control.widget)
            control.changed.connect(self._schedule_preview)

        self._selected_only_checkbox = CheckBox()
        set_signal(self._selected_only_checkbox)
        self._selected_only_checkbox.setText(SELECTED_ONLY_LABEL)
        self._selected_only_checkbox.valueChanged.connect(self.filter_selection_only)
        self._selected_only_checkbox.setChecked(filter_selection_only_default)
        self._selected_only_checkbox.stateChanged.connect(self._schedule_preview)

        self._active_only_checkbox = CheckBox()
        self._active_only_checkbox.setText(ACTIVE_ONLY_LABEL)
        self._active_only_checkbox.valueChanged.connect(self.filter_active_only)
        self._active_only_checkbox.setChecked(filter_active_layer_only_default)
        self._active_only_checkbox.stateChanged.connect(self._schedule_preview)

        scope_body = QWidget()
        scope_layout = QVBoxLayout(scope_body)
        scope_layout.setContentsMargins(0, 0, 0, 0)
        scope_layout.addWidget(self._selected_only_checkbox)
        scope_layout.addWidget(self._active_only_checkbox)
        controls_layout.addWidget(PanelSection(SCOPE_SECTION_TITLE, scope_body))
        controls_layout.addStretch(1)

        scroll = ControlsColumn(controls, CONTROLS_COLUMN_WIDTH)
        self._controls_scroll = scroll

        self._footer = DialogFooter(APPLY_BUTTON_TEXT.format(filter_name=title), self)
        self._footer.accepted.connect(self._apply_change)
        self._footer.rejected.connect(self.close)
        self._apply_button = self._footer.confirm_button
        assert self._footer.cancel_button is not None
        self._cancel_button = self._footer.cancel_button

        self._body = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._body.addWidget(self._preview, stretch=1)
        self._body.addWidget(scroll)
        self._layout = QVBoxLayout(self)
        self._layout.addLayout(self._body, stretch=1)
        self._layout.addWidget(self._footer)

        self._update_compare_hint()
        KeyConfig().connect(self, KeyConfig.COMPARE_ORIGINAL_MODIFIER, self._update_compare_hint)
        self._preview.compare_button.setVisible(prepare_original is not None)
        self._fit_to_screen()
        self._start_preview()

    def _fit_to_screen(self) -> None:
        """Opens the dialog no larger than a fraction of the available screen."""
        fit_dialog_to_screen(self, self.sizeHint())

    def _update_compare_hint(self, *_) -> None:
        key_text = get_key_display_string(KeyConfig().get(KeyConfig.COMPARE_ORIGINAL_MODIFIER), rich_text=False)
        tooltip = COMPARE_BUTTON_TOOLTIP_WITH_KEY.format(key=key_text) if key_text else COMPARE_BUTTON_TOOLTIP
        self._preview.compare_button.setToolTip(tooltip)

    def resizeEvent(self, event: QResizeEvent) -> None:  # pylint: disable=invalid-name
        """Stacks the preview over the controls while the window is taller than it is wide."""
        super().resizeEvent(event)
        stack_body_for_size(self._body, self._controls_scroll, event.size().width(), event.size().height())

    def _compare_from_modifiers(self, modifiers: Qt.KeyboardModifier) -> None:
        held = KeyConfig.modifier_held(KeyConfig.COMPARE_ORIGINAL_MODIFIER, held_modifiers=modifiers)
        self._preview.set_comparing((held or self._preview.compare_button.isDown())
                                    and self._prepare_original is not None)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # pylint: disable=invalid-name
        """Shows the original while the compare modifier is held."""
        self._compare_from_modifiers(event.modifiers())
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # pylint: disable=invalid-name
        """Shows the preview again when the compare modifier is released."""
        self._compare_from_modifiers(event.modifiers())
        super().keyReleaseEvent(event)

    def changeEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """Stops comparing when the window loses focus, since the release would go elsewhere."""
        if event.type() == QEvent.Type.ActivationChange and not self.isActiveWindow():
            self._preview.set_comparing(False)
        super().changeEvent(event)

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
        param_values = [control.value() for control in self._param_inputs]
        render = self._prepare_preview(param_values)
        render_original = self._prepare_original() if self._prepare_original is not None else None
        result: list[Optional[QImage]] = []
        original_result: list[Optional[QImage]] = []

        def _run() -> None:
            result.append(render())
            if render_original is not None:
                original_result.append(render_original())

        task = AsyncTask(_run)
        self._preview_task = task

        # _finish must not reference task: the task's connection holds _finish, so that would leave a reference cycle.
        def _finish() -> None:
            if not isValid(self):  # The dialog was deleted while the render ran.
                return
            self._preview_task = None
            if result and result[0] is not None:
                self._preview.image = result[0]
            if original_result and original_result[0] is not None:
                self._preview.original = original_result[0]
            if self._preview_stale:
                self._start_preview()
        task.finish_signal.connect(_finish)
        task.start()

    def _apply_change(self) -> None:
        param_values = [control.value() for control in self._param_inputs]
        self._apply_filter(param_values)
        self.close()
