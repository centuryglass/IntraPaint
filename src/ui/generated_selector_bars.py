"""The generated image selector's top and bottom bars: what a batch is, how it is viewed, and what to do with it.

Each bar folds its lower priority controls into a popover or menu when the selector is too narrow for them, so the
primary action, Close and the view mode always show. The bars emit intents and show the state the selector passes in.
They hold no batch state.
"""
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy, QToolTip, \
    QVBoxLayout, QWidget

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.ui.button_weight import ButtonWeight, set_button_weight
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.field_factory import create_control_widget
from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from src.ui.widget.keycap_badge import KeycapBadge
from src.ui.widget.option_filmstrip import MAX_DIGIT_KEY
from src.ui.widget.panel_header import PanelPopover
from src.util.visual.text_drawing_utils import get_key_display_string, left_button_hint_text, \
    middle_button_hint_text, rich_text_key_hint, rich_text_key_hints, vertical_scroll_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.generated_selector_bars'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SELECTION_TITLE = _tr('Choose a result')
VIEW_GRID_LABEL = _tr('Grid')
VIEW_SINGLE_LABEL = _tr('Single')
VIEW_GRID_TOOLTIP = _tr('Show every option')
VIEW_SINGLE_TOOLTIP = _tr('Show the focused option up close')
VIEW_OPTIONS_BUTTON_TEXT = _tr('View')
VIEW_OPTIONS_BUTTON_TOOLTIP = _tr('Show selection, zoom to changes and full resolution')
CHANGE_ZOOM_CHECKBOX_LABEL = _tr('Zoom to changes')
SHOW_SELECTION_OUTLINES_LABEL = _tr('Show selection')
FULL_RESOLUTION_LABEL = _tr('Full resolution')

CANCEL_BUTTON_TEXT = _tr('Cancel')
CANCEL_BUTTON_TOOLTIP = _tr('Stop generating and return to the editor.')
CLOSE_BUTTON_TEXT = _tr('Close')
CLOSE_BUTTON_TOOLTIP = _tr('Close without choosing. These options stay available to re-open.')
STOP_BUTTON_TEXT = _tr('Stop')
STOP_BUTTON_TOOLTIP = _tr('Stop generating and keep the finished options.')
STOPPING_BUTTON_TEXT = _tr('Stopping...')
PREVIOUS_BUTTON_TEXT = _tr('‹ Previous')
NEXT_BUTTON_TEXT = _tr('Next ›')
PREVIOUS_BUTTON_TOOLTIP = _tr('Previous option ({key})')
NEXT_BUTTON_TOOLTIP = _tr('Next option ({key})')
SEND_TO_LAYER_BUTTON_TEXT = _tr('Send to new layer')
SAVE_TO_FILE_BUTTON_TEXT = _tr('Save to file...')
MORE_BUTTON_TEXT = _tr('More')
USE_OPTION_BUTTON_TEXT = _tr('Use option {index}')
USE_ORIGINAL_BUTTON_TEXT = _tr('Keep original')
USE_BUTTON_TOOLTIP = _tr('Apply the focused option and return to the editor.')
USE_BUTTON_WAITING_TOOLTIP = _tr('This option is still generating.')
HINT_BUTTON_TOOLTIP = _tr('Controls')
ENTER_KEY_NAME = _tr('Enter')

GRID_CONTROL_HINT = _tr('{left_key}{right_key} browse &nbsp; {first_key}-{last_key} open option &nbsp; '
                        '{up_key} single view &nbsp; {pan_modifier}+{left_mouse_icon} or {middle_mouse_icon} pan '
                        '&nbsp; {zoom_in_key}{zoom_out_key} zoom')
SINGLE_CONTROL_HINT = _tr('{compare_key} hold: original &nbsp; {left_key}{right_key} browse &nbsp; '
                          '{down_key} back to grid &nbsp; {pan_modifier}+{left_mouse_icon} or {middle_mouse_icon} pan '
                          '&nbsp; {v_scroll_icon} zoom')

VIEW_GRID = 'grid'
VIEW_SINGLE = 'single'
# Below this selector width, Send to new layer and Save to file fold into the More menu:
MORE_FOLD_WIDTH = 1100


def _with_keycap(control: QWidget, key_text: str) -> tuple[QWidget, KeycapBadge]:
    """Returns a row holding `control` and a keycap showing the key that does the same thing."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(control)
    badge = KeycapBadge(key_text)
    layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignVCenter)
    return row, badge


def _fits(layout: QHBoxLayout, width: int) -> bool:
    """Returns whether a bar's visible controls fit in `width`."""
    layout.invalidate()
    return layout.minimumSize().width() <= width


class SelectorTopBar(QWidget):
    """The title, batch status, grid or single view control, and view options.

    The view options show in the bar, or behind a "View" button when the bar is too narrow. Each option has a
    checkbox in both places, kept in step through its `AppConfig` value.
    """

    view_mode_changed = Signal(str)
    """Emitted with `VIEW_GRID` or `VIEW_SINGLE` when the user picks a view."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel(SELECTION_TITLE)
        title_font = title_label.font()
        title_font.setBold(True)
        title_label.setFont(title_font)
        self._layout.addWidget(title_label)
        self._status_label = QLabel()
        self._status_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._status_label.setMinimumWidth(1)
        self._status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._layout.addWidget(self._status_label, stretch=1)

        self._view_mode_control = SegmentedControl([Segment(VIEW_GRID, VIEW_GRID_LABEL, tooltip=VIEW_GRID_TOOLTIP),
                                                    Segment(VIEW_SINGLE, VIEW_SINGLE_LABEL,
                                                            tooltip=VIEW_SINGLE_TOOLTIP)],
                                                   DisplayMode.LABEL)
        self._view_mode_control.valueChanged.connect(self.view_mode_changed)
        view_mode_row, self._view_mode_keycap = _with_keycap(self._view_mode_control, '')
        self._layout.addWidget(view_mode_row)

        self._view_options = QWidget()
        popover_content = QWidget()
        self._view_checkboxes: list[tuple[CheckBox, CheckBox]] = []
        for container_layout in (QHBoxLayout(self._view_options), QVBoxLayout(popover_content)):
            container_layout.setContentsMargins(0, 0, 0, 0)
            boxes = []
            for config_key, label in ((AppConfig.SHOW_SELECTIONS_IN_GENERATION_OPTIONS, SHOW_SELECTION_OUTLINES_LABEL),
                                      (AppConfig.SELECTION_SCREEN_ZOOMS_TO_CHANGED, CHANGE_ZOOM_CHECKBOX_LABEL),
                                      (AppConfig.SHOW_OPTIONS_FULL_RESOLUTION, FULL_RESOLUTION_LABEL)):
                checkbox = create_control_widget(AppConfig(), config_key)
                assert isinstance(checkbox, CheckBox)
                checkbox.setText(label)
                container_layout.addWidget(checkbox)
                boxes.append(checkbox)
            self._view_checkboxes.append((boxes[0], boxes[1]))
        self._reason_label = QLabel()
        self._reason_label.setWordWrap(True)
        self._reason_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        popover_content.layout().addWidget(self._reason_label)
        self._layout.addWidget(self._view_options)
        self._popover = PanelPopover(self)
        self._popover.set_content(popover_content)
        self._view_options_button = QPushButton(VIEW_OPTIONS_BUTTON_TEXT)
        self._view_options_button.setToolTip(VIEW_OPTIONS_BUTTON_TOOLTIP)
        self._view_options_button.clicked.connect(lambda: self._popover.popup_below(self._view_options_button))
        self._view_options_button.hide()
        self._layout.addWidget(self._view_options_button)

    @property
    def selection_outline_checkbox(self) -> CheckBox:
        """The "Show selection" checkbox in the bar."""
        return self._view_checkboxes[0][0]

    @property
    def change_zoom_checkbox(self) -> CheckBox:
        """The "Zoom to changes" checkbox in the bar."""
        return self._view_checkboxes[0][1]

    def set_status(self, text: str) -> None:
        """Shows the batch details, or the ready count while a run fills the batch."""
        self._status_label.setText(text)

    def set_view_mode(self, view_mode: str) -> None:
        """Shows `VIEW_GRID` or `VIEW_SINGLE` as the current view, and the key that switches between them."""
        self._view_mode_control.set_value(view_mode)
        self._view_mode_keycap.set_text(get_key_display_string(KeyConfig().get(KeyConfig.ZOOM_TOGGLE),
                                                               rich_text=False))

    def set_option_reasons(self, selection_reason: str, zoom_reason: str) -> None:
        """Disables "Show selection" and "Zoom to changes" when their reasons aren't empty, with the reason as the
        tooltip. The popover also shows the zoom reason as text."""
        for selection_box, zoom_box in self._view_checkboxes:
            selection_box.setEnabled(selection_reason == '')
            selection_box.setToolTip(selection_reason)
            zoom_box.setEnabled(zoom_reason == '')
            zoom_box.setToolTip(zoom_reason)
        self._reason_label.setText(zoom_reason)
        self._reason_label.setVisible(zoom_reason != '')

    def fit(self, width: int) -> None:
        """Moves the view options behind the "View" button when the bar is narrower than they need."""
        self._view_options.show()
        self._view_options_button.hide()
        if not _fits(self._layout, width):
            self._view_options.hide()
            self._view_options_button.show()


@dataclass(frozen=True)
class ButtonBarState:
    """What the bottom bar offers, from the run state and the focused option."""
    generating: bool
    has_results: bool
    stopped: bool
    focus_index: int
    focus_ready: bool
    option_count: int
    single_view: bool


class SelectorButtonBar(QWidget):
    """Close or Cancel, Stop, the control hints, Previous and Next, the secondary actions and the primary action.

    - Before any option is ready during a run, Close reads Cancel, and Stop is hidden.
    - Stop shows only while a run fills a batch that holds results.
    - Send to new layer and Save to file fold into a "More" menu below `MORE_FOLD_WIDTH`. The hints fold into a "?"
      button, and then Previous and Next drop their labels, when the bar is narrower than they need.
    """

    close_requested = Signal()
    stop_requested = Signal()
    previous_requested = Signal()
    next_requested = Signal()
    send_requested = Signal()
    save_requested = Signal()
    use_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.close_button = QPushButton(CANCEL_BUTTON_TEXT)
        self.close_button.clicked.connect(self.close_requested)
        close_row, _ = _with_keycap(self.close_button, get_key_display_string(Qt.Key.Key_Escape, rich_text=False))
        self._layout.addWidget(close_row)
        self.stop_button = QPushButton(STOP_BUTTON_TEXT)
        self.stop_button.setToolTip(STOP_BUTTON_TOOLTIP)
        self.stop_button.clicked.connect(self.stop_requested)
        self._layout.addWidget(self.stop_button)

        self._layout.addStretch(1)
        self._hint_label = QLabel()
        self._hint_label.setTextFormat(Qt.TextFormat.RichText)
        self._layout.addWidget(self._hint_label)
        self._hint_button = QPushButton('?')
        self._hint_button.setToolTip(HINT_BUTTON_TOOLTIP)
        self._hint_button.clicked.connect(
            lambda: QToolTip.showText(self._hint_button.mapToGlobal(QPoint(0, 0)), self._hint_label.text(),
                                      self._hint_button))
        self._hint_button.hide()
        self._layout.addWidget(self._hint_button)
        self._layout.addStretch(1)

        key_config = KeyConfig()
        self._prev_button = QPushButton(PREVIOUS_BUTTON_TEXT)
        self._prev_button.clicked.connect(self.previous_requested)
        self._prev_button.setToolTip(PREVIOUS_BUTTON_TOOLTIP.format(
            key=get_key_display_string(key_config.get_keycodes(KeyConfig.MOVE_LEFT), rich_text=False)))
        self._layout.addWidget(self._prev_button)
        self._next_button = QPushButton(NEXT_BUTTON_TEXT)
        self._next_button.clicked.connect(self.next_requested)
        self._next_button.setToolTip(NEXT_BUTTON_TOOLTIP.format(
            key=get_key_display_string(key_config.get_keycodes(KeyConfig.MOVE_RIGHT), rich_text=False)))
        self._layout.addWidget(self._next_button)

        self._send_button = QPushButton(SEND_TO_LAYER_BUTTON_TEXT)
        self._send_button.clicked.connect(self.send_requested)
        self._layout.addWidget(self._send_button)
        self._save_button = QPushButton(SAVE_TO_FILE_BUTTON_TEXT)
        self._save_button.clicked.connect(self.save_requested)
        self._layout.addWidget(self._save_button)
        self._more_menu = QMenu(self)
        self._send_action = self._more_menu.addAction(SEND_TO_LAYER_BUTTON_TEXT)
        self._send_action.triggered.connect(self.send_requested)
        self._save_action = self._more_menu.addAction(SAVE_TO_FILE_BUTTON_TEXT)
        self._save_action.triggered.connect(self.save_requested)
        self._more_button = QPushButton(MORE_BUTTON_TEXT)
        self._more_button.setMenu(self._more_menu)
        self._more_button.hide()
        self._layout.addWidget(self._more_button)

        self.use_button = QPushButton()
        set_button_weight(self.use_button, ButtonWeight.PRIMARY)
        self.use_button.clicked.connect(self.use_requested)
        use_row, _ = _with_keycap(self.use_button, ENTER_KEY_NAME)
        self._layout.addWidget(use_row)

    def set_state(self, state: ButtonBarState) -> None:
        """Updates the buttons' text, visibility and enabled state, and the hints for the current view."""
        if state.generating and not state.has_results:
            self.close_button.setText(CANCEL_BUTTON_TEXT)
            self.close_button.setToolTip(CANCEL_BUTTON_TOOLTIP)
        else:
            self.close_button.setText(CLOSE_BUTTON_TEXT)
            self.close_button.setToolTip(CLOSE_BUTTON_TOOLTIP)
        self.stop_button.setVisible(state.generating and state.has_results)
        self.stop_button.setEnabled(not state.stopped)
        self.stop_button.setText(STOPPING_BUTTON_TEXT if state.stopped else STOP_BUTTON_TEXT)

        self.use_button.setText(USE_ORIGINAL_BUTTON_TEXT if state.focus_index == 0
                                else USE_OPTION_BUTTON_TEXT.format(index=state.focus_index))
        self.use_button.setEnabled(state.focus_ready)
        self.use_button.setToolTip(USE_BUTTON_TOOLTIP if state.focus_ready else USE_BUTTON_WAITING_TOOLTIP)
        for control in (self._send_button, self._save_button, self._send_action, self._save_action):
            control.setEnabled(state.focus_ready)
        stepping = state.option_count > 1
        self._prev_button.setEnabled(stepping)
        self._next_button.setEnabled(stepping)
        self._hint_label.setText(_control_hint(state.single_view, state.option_count))
        self._hint_button.setToolTip(self._hint_label.text())

    def fit(self, width: int) -> None:
        """Folds the secondary actions, hints and stepping labels until the bar fits in `width`."""
        fold_more = width < MORE_FOLD_WIDTH
        self._send_button.setVisible(not fold_more)
        self._save_button.setVisible(not fold_more)
        self._more_button.setVisible(fold_more)
        self._prev_button.setText(PREVIOUS_BUTTON_TEXT)
        self._next_button.setText(NEXT_BUTTON_TEXT)
        self._hint_label.show()
        self._hint_button.hide()
        if not _fits(self._layout, width):
            self._hint_label.hide()
            self._hint_button.show()
            if not _fits(self._layout, width):
                self._prev_button.setText('‹')
                self._next_button.setText('›')


def _control_hint(single_view: bool, option_count: int) -> str:
    """Returns one line of keycap hints for the grid or single view."""
    config = KeyConfig()

    def _keys(config_key: str) -> str:
        return rich_text_key_hints(config.get(config_key))

    shared = {'left_key': _keys(KeyConfig.MOVE_LEFT),
              'right_key': _keys(KeyConfig.MOVE_RIGHT),
              'pan_modifier': _keys(KeyConfig.PAN_VIEW_MODIFIER),
              'left_mouse_icon': left_button_hint_text(),
              'middle_mouse_icon': middle_button_hint_text()}
    if single_view:
        return SINGLE_CONTROL_HINT.format(compare_key=_keys(KeyConfig.COMPARE_ORIGINAL_MODIFIER),
                                          down_key=_keys(KeyConfig.MOVE_DOWN),
                                          v_scroll_icon=vertical_scroll_hint_text(),
                                          **shared)
    last_digit = max(min(option_count - 1, MAX_DIGIT_KEY), 0)
    return GRID_CONTROL_HINT.format(first_key=rich_text_key_hint('0'),
                                    last_key=rich_text_key_hint(str(last_digit)),
                                    up_key=_keys(KeyConfig.MOVE_UP),
                                    zoom_in_key=_keys(KeyConfig.ZOOM_IN),
                                    zoom_out_key=_keys(KeyConfig.ZOOM_OUT),
                                    **shared)
