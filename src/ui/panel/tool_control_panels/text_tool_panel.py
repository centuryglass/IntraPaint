"""Text tool control panel: the text box first, then Font, Style, Position and size, Advanced and Preview sections.

The panel is a view over one `TextRect`, which it stores in `Cache.TEXT_TOOL_PARAMS` and sends to the text tool with
`text_rect_changed`. X and Y are the layer position, sent with `offset_changed`.

- Font: a filter field over the font list, with each family drawn in its own font, then Size with a px / pt choice.
  Its smaller form is an editable font combo whose completer filters the same way.
- Style: Bold, Italic, Underline and Strikethrough toggles, alignment, the text and background colors with "Fill
  behind text", and Box fit. Box fit is one choice over the `TextRect` scale mode: Free, Fit font
  (`scale_text_to_bounds`) or Fit box (`scale_bounds_to_text`). An "Overflows" badge shows while the text is larger
  than its box.
- Position and size: the shared `GeometryBlock`.
- Advanced: Stretch, Overline, Fixed pitch and Kerning, collapsed by default.
- Preview: the text drawn in its box, with a legend. It is decorative: it hides where it doesn't fit.

The panel is a `src.ui.layout.panel_fit.FitContent`, planned in the space the Tools panel gives it:
- Side: one column, or two where they fit across, with the preview beside the text box. The panel scrolls.
- Strip: columns of up to `STRIP_SECTION_MAX_WIDTH`: the text box over the preview, Font, Style, then Position and
  size over Advanced. Section headers are optional.
- Advanced is optional: a plan without room for it moves it to `overflow_content`, which the Tools panel shows in its
  More popover.
"""
import os.path
from typing import Callable, Optional

from PySide6.QtCore import QEvent, QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QCompleter, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.text_rect import SCALE_MODE_BOUNDS_TO_TEXT, SCALE_MODE_NONE, SCALE_MODE_TEXT_TO_BOUNDS, TextRect
from src.ui.ink_style import signal_color
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.geometry_block import HEIGHT, WIDTH, X, Y, GeometryBlock, bind_step_keys
from src.ui.input_fields.number_field import FIELD_HEIGHT, NumberField
from src.ui.input_fields.plain_text_edit import PlainTextEdit
from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from src.ui.input_fields.slider_field import SliderField
from src.ui.layout.dock_panel import QWIDGETSIZE_MAX
from src.ui.layout.panel_fit import REQUIRED, FitItem, FitPlanner, Orientation, Placement
from src.ui.panel.tool_control_panels.fit_tool_panel import FitToolPanel
from src.ui.panel.tool_control_panels.text_preview import TextPreview, text_overflows
from src.ui.widget.color_button import ColorButton
from src.ui.widget.panel_section import PanelSection
from src.undo_stack import UndoStack
from src.util.shared_constants import PROJECT_DIR
from src.util.signals_blocked import signals_blocked

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.text_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


TEXT_INPUT_PLACEHOLDER = _tr('Enter text')
FONT_SECTION_TITLE = _tr('Font')
STYLE_SECTION_TITLE = _tr('Style')
POSITION_SECTION_TITLE = _tr('Position and size')
ADVANCED_SECTION_TITLE = _tr('Advanced')
PREVIEW_SECTION_TITLE = _tr('Preview')
FONT_FILTER_PLACEHOLDER = _tr('Type to filter fonts')
FONT_LIST_TOOLTIP = _tr('Font family')
SIZE_LABEL = _tr('Size')
SIZE_TOOLTIP = _tr('Font size')
SIZE_KEYS_TOOLTIP = _tr('{description}\nKeys: {decrease} / {increase}')
UNIT_PIXELS = _tr('px')
UNIT_POINTS = _tr('pt')
UNIT_PIXELS_TOOLTIP = _tr('Font size in pixels')
UNIT_POINTS_TOOLTIP = _tr('Font size in points')
PIXEL_SUFFIX = _tr(' px')
POINT_SUFFIX = _tr(' pt')
FONT_SUMMARY = _tr('{family}, {size}')

BOLD_LABEL = _tr('Bold')
ITALIC_LABEL = _tr('Italic')
UNDERLINE_LABEL = _tr('Underline')
STRIKETHROUGH_LABEL = _tr('Strikethrough')
OVERLINE_LABEL = _tr('Overline')
FIXED_PITCH_LABEL = _tr('Fixed pitch')
KERNING_LABEL = _tr('Kerning')
ALIGN_LEFT_LABEL = _tr('Align left')
ALIGN_CENTER_LABEL = _tr('Align center')
ALIGN_RIGHT_LABEL = _tr('Align right')
TEXT_COLOR_LABEL = _tr('Text')
BACKGROUND_COLOR_LABEL = _tr('Background')
TEXT_COLOR_NOTE = _tr('Same as brush color')
TEXT_COLOR_TOOLTIP = _tr('Text color. It is the same color the brush uses.')
BACKGROUND_COLOR_TOOLTIP = _tr('Background color, drawn behind the text while "Fill behind text" is on')
FILL_BACKGROUND_LABEL = _tr('Fill behind text')
FILL_BACKGROUND_TOOLTIP = _tr('Fill the text box with the background color')
BOX_FIT_LABEL = _tr('Box fit')
BOX_FIT_FREE = _tr('Free')
BOX_FIT_FONT = _tr('Fit font')
BOX_FIT_BOX = _tr('Fit box')
BOX_FIT_FREE_TOOLTIP = _tr('Free: the font size and the box size are set separately')
BOX_FIT_FONT_TOOLTIP = _tr('Fit font: the font size changes to fit the text in the box')
BOX_FIT_BOX_TOOLTIP = _tr('Fit box: the box resizes to fit the text')
OVERFLOW_BADGE = _tr('Overflows')
OVERFLOW_TOOLTIP = _tr('The text is larger than its box, so part of it is cut off. Enlarge the box, or pick Fit font '
                       'or Fit box.')
STRETCH_LABEL = _tr('Stretch')
STRETCH_TOOLTIP = _tr('Stretches the font horizontally, as a percentage of its normal width')
STRETCH_BITMAP_TOOLTIP = _tr('Stretch is unavailable for bitmap fonts, which cannot be stretched')
STRETCH_AUTO = _tr('auto')
PERCENT_SUFFIX = _tr('%')
PREVIEW_LEGEND = _tr('Outline = text box.\nTurns red when the text does not fit.')
PREVIEW_FITS = _tr('fits box')
PREVIEW_OVERFLOWS = _tr('overflows')

ICON_PATH_BOLD = f'{PROJECT_DIR}/resources/icons/text/bold.svg'
ICON_PATH_ITALIC = f'{PROJECT_DIR}/resources/icons/text/italic.svg'
ICON_PATH_OVERLINE = f'{PROJECT_DIR}/resources/icons/text/overline.svg'
ICON_PATH_STRIKETHROUGH = f'{PROJECT_DIR}/resources/icons/text/strikethrough.svg'
ICON_PATH_UNDERLINE = f'{PROJECT_DIR}/resources/icons/text/underline.svg'
ICON_PATH_FIXED_PITCH = f'{PROJECT_DIR}/resources/icons/text/fixed_pitch.svg'
ICON_PATH_KERNING = f'{PROJECT_DIR}/resources/icons/text/kerning.svg'
ICON_PATH_BOUNDS_TO_TEXT = f'{PROJECT_DIR}/resources/icons/text/scale_bounds_to_text.svg'
ICON_PATH_TEXT_TO_BOUNDS = f'{PROJECT_DIR}/resources/icons/text/scale_text_to_bounds.svg'
ICON_PATH_LEFT_ALIGN = f'{PROJECT_DIR}/resources/icons/text/left.svg'
ICON_PATH_RIGHT_ALIGN = f'{PROJECT_DIR}/resources/icons/text/right.svg'
ICON_PATH_CENTER_ALIGN = f'{PROJECT_DIR}/resources/icons/text/center.svg'

MAX_FONT_SIZE = 1000
MAX_STRETCH = 4000
DEFAULT_STRETCH = 100
UNIT_PX = 'px'
UNIT_PT = 'pt'
_ALIGNMENTS = {
    'left': Qt.AlignmentFlag.AlignLeft,
    'center': Qt.AlignmentFlag.AlignHCenter,
    'right': Qt.AlignmentFlag.AlignRight,
}
# Lines of text the text box shows at its smallest, and rows the font list shows at its smallest:
TEXT_BOX_MIN_LINES = 3
FONT_LIST_MIN_ROWS = 4
MIN_FONT_COMBO_CHARACTERS = 10
SECTION_SPACING = 10
ICON_SIZE = 16
FREE_ICON_LINE_WIDTH = 1.5

# The planned items, in placement order:
COLUMNS_ITEM = FitItem(REQUIRED, 2)
FONT_ITEM = FitItem(REQUIRED, 2)
STYLE_ITEM = FitItem(REQUIRED, 2)
PREVIEW_ITEM = FitItem(1)
ADVANCED_ITEM = FitItem(2)
HEADERS_ITEM = FitItem(3)
# Forms of the columns item, which only a side panel uses:
TWO_COLUMNS = 0
ONE_COLUMN = 1
# Forms of the font item:
FONT_LIST = 0
FONT_COMBO = 1
# Forms of the style item:
ROOMY = 0
COMPACT = 1


def _font_size(font: QFont) -> tuple[int, str]:
    """Returns a font's size and its unit: pixels if it has a pixel size, points otherwise."""
    if font.pixelSize() > 0:
        return font.pixelSize(), UNIT_PX
    return max(font.pointSize(), 1), UNIT_PT


def _free_box_icon(color: QColor) -> QIcon:
    """Draws the Free box fit icon: an empty box."""
    pixmap = QPixmap(ICON_SIZE * 2, ICON_SIZE * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(color, FREE_ICON_LINE_WIDTH * 2))
    inset = ICON_SIZE / 2
    painter.drawRect(QRectF(inset, inset, ICON_SIZE, ICON_SIZE))
    painter.end()
    return QIcon(pixmap)


class TextToolPanel(FitToolPanel):
    """Text tool control panel. Sets the text, font, style, colors, box fit, and the text layer's position and size.

    Without a host that calls `set_fit_space`, the panel plans for its own size when resized.
    """

    text_rect_changed = Signal(TextRect)
    offset_changed = Signal(QPoint)
    # Emitted after the controls show new values, for the section summaries:
    _values_shown = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._text_rect = TextRect()
        self._text_rect.font = QApplication.font()
        self._offset = QPoint()

        # Text box:
        self._text_box = PlainTextEdit(self)
        self._text_box.setPlaceholderText(TEXT_INPUT_PLACEHOLDER)
        self._text_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._text_box.valueChanged.connect(self._text_changed)
        self._text_box.focus_lost.connect(UndoStack().end_gesture)

        self._build_font_section()
        self._build_style_section()
        self._build_position_section()
        self._build_advanced_section()
        self._build_preview_section()

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(SECTION_SPACING)
        # The strip's last column, Position and size over Advanced:
        self._strip_column = QVBoxLayout()
        self._strip_column.setContentsMargins(0, 0, 0, 0)
        self._sections = (self._font_section, self._style_section, self._position_section, self._advanced_section,
                          self._preview_section)

        cache = Cache()
        cache.connect(self, Cache.LAST_BRUSH_COLOR, self._text_color_changed)
        cache.connect(self, Cache.TEXT_BACKGROUND_COLOR, self._background_color_changed)
        self._text_rect.text_color = self._text_color_button.color
        self._text_rect.background_color = self._background_color_button.color
        serialized_text = cache.get(Cache.TEXT_TOOL_PARAMS)
        if len(serialized_text) > 0:
            try:
                self._text_rect = TextRect.deserialize(serialized_text)
            except (KeyError, AssertionError):
                serialized_text = ''
        if len(serialized_text) == 0:
            cache.set(Cache.TEXT_TOOL_PARAMS, self._text_rect.serialize(True))

        def _key_predicate() -> bool:
            return self.isVisible() and self.isEnabled()
        key_filter = HotkeyFilter.instance()
        bind_step_keys(self._geometry, key_filter, KeyConfig, _key_predicate)
        for key, sign in ((KeyConfig.ROTATE_CCW_KEY, -1), (KeyConfig.ROTATE_CW_KEY, 1)):
            def _step_size(multiplier: int, direction=sign) -> bool:
                if not _key_predicate():
                    return False
                self._size_field.set_value(self._size_field.value() + direction * multiplier)
                return True
            key_filter.register_speed_modified_keybinding(f'_TextToolPanel_{id(self)}_size_{key}', _step_size, key)
        keys = KeyConfig()
        self._size_field.setToolTip(SIZE_KEYS_TOOLTIP.format(description=SIZE_TOOLTIP,
                                                             decrease=keys.get(KeyConfig.ROTATE_CCW_KEY),
                                                             increase=keys.get(KeyConfig.ROTATE_CW_KEY)))

        self._show_values()
        self._planner = FitPlanner([COLUMNS_ITEM, FONT_ITEM, STYLE_ITEM, PREVIEW_ITEM, ADVANCED_ITEM, HEADERS_ITEM],
                                   self._apply_fit, self._measure_fit)
        self._apply_fit(Orientation.SIDE, (ONE_COLUMN, FONT_LIST, ROOMY, 0, 0, 0))

    # -----------------------------------------------------------------------------------------------------------------
    # Controls
    # -----------------------------------------------------------------------------------------------------------------

    def _build_font_section(self) -> None:
        self._font_filter = QLineEdit(self)
        self._font_filter.setPlaceholderText(FONT_FILTER_PLACEHOLDER)
        self._font_filter.setClearButtonEnabled(True)
        self._font_filter.textChanged.connect(self._filter_fonts)
        self._font_list = QListWidget(self)
        self._font_list.setToolTip(FONT_LIST_TOOLTIP)
        self._font_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._font_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        for family in self._font_families():
            self._font_list.addItem(family)
            item = self._font_list.item(self._font_list.count() - 1)
            item.setFont(QFont(family))
            item.setToolTip(family)
        frame = self._font_list.frameWidth() * 2
        self._font_list.setMinimumHeight(self._font_list.fontMetrics().height() * FONT_LIST_MIN_ROWS + frame)
        self._font_list.currentTextChanged.connect(self._font_family_selected)

        self._font_combo = QComboBox(self)
        self._font_combo.setToolTip(FONT_LIST_TOOLTIP)
        self._font_combo.setModel(self._font_list.model())
        self._font_combo.setEditable(True)
        self._font_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._font_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._font_combo.setMinimumContentsLength(MIN_FONT_COMBO_CHARACTERS)
        self._font_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        completer = QCompleter(self._font_list.model(), self._font_combo)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._font_combo.setCompleter(completer)
        self._font_combo.currentIndexChanged.connect(self._font_combo_changed)
        line_edit = self._font_combo.lineEdit()
        assert line_edit is not None
        # The combo sizes its field to fit inside its own frame:
        line_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        line_edit.editingFinished.connect(self._restore_font_combo_text)

        self._size_field = SliderField(SIZE_LABEL, 12, 1, MAX_FONT_SIZE, suffix=PIXEL_SUFFIX, parent=self)
        self._size_field.valueChanged.connect(self._size_changed)
        self._size_unit = SegmentedControl([Segment(UNIT_PX, UNIT_PIXELS, tooltip=UNIT_PIXELS_TOOLTIP),
                                            Segment(UNIT_PT, UNIT_POINTS, tooltip=UNIT_POINTS_TOOLTIP)],
                                           DisplayMode.LABEL, parent=self)
        self._size_unit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._size_unit.valueChanged.connect(self._unit_changed)

        self._font_body = QWidget(self)
        self._font_layout = self._body_grid(self._font_body)
        self._font_section = PanelSection(FONT_SECTION_TITLE, self._font_body, parent=self)
        self._font_section.bind_summary(self._font_summary, self._values_shown)

    @staticmethod
    def _font_families() -> list[str]:
        """Adds the fonts under `AppConfig.ADDED_FONT_DIR` to the font database, then returns every scalable public
        family."""
        custom_font_dir = AppConfig().get(AppConfig.ADDED_FONT_DIR)
        if os.path.isdir(custom_font_dir):
            scan_dirs = [custom_font_dir]
            while len(scan_dirs) > 0:
                scan_dir = scan_dirs.pop(0)
                for file_path in os.listdir(scan_dir):
                    full_path = os.path.join(scan_dir, file_path)
                    if os.path.isdir(full_path):
                        scan_dirs.append(full_path)
                    else:
                        QFontDatabase.addApplicationFont(full_path)
        return [family for family in QFontDatabase.families() if QFontDatabase.isScalable(family)
                and not QFontDatabase.isPrivateFamily(family)]

    def _toggle_button(self, label: str, icon_path: str, getter: Callable[[QFont], bool],
                       setter: Callable[[QFont, bool], None]) -> QToolButton:
        button = QToolButton(self)
        button.setCheckable(True)
        button.setAutoRaise(True)
        button.setIcon(QIcon(icon_path))
        button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        button.setFixedSize(FIELD_HEIGHT, FIELD_HEIGHT)
        button.setToolTip(label)
        button.setAccessibleName(label)

        def _toggled(checked: bool) -> None:
            font = self._text_rect.font
            if getter(font) != checked:
                setter(font, checked)
                self._text_rect.font = font
                self._changed()

        button.toggled.connect(_toggled)
        self._font_toggles.append((button, getter))
        return button

    def _build_style_section(self) -> None:
        self._font_toggles: list[tuple[QToolButton, Callable[[QFont], bool]]] = []
        self._bold_button = self._toggle_button(BOLD_LABEL, ICON_PATH_BOLD, QFont.bold, QFont.setBold)
        self._italic_button = self._toggle_button(ITALIC_LABEL, ICON_PATH_ITALIC, QFont.italic, QFont.setItalic)
        self._underline_button = self._toggle_button(UNDERLINE_LABEL, ICON_PATH_UNDERLINE, QFont.underline,
                                                     QFont.setUnderline)
        self._strikethrough_button = self._toggle_button(STRIKETHROUGH_LABEL, ICON_PATH_STRIKETHROUGH,
                                                         QFont.strikeOut, QFont.setStrikeOut)
        self._style_toggles = (self._bold_button, self._italic_button, self._underline_button,
                               self._strikethrough_button)
        self._alignment_control = SegmentedControl(
            [Segment('left', ALIGN_LEFT_LABEL, ICON_PATH_LEFT_ALIGN),
             Segment('center', ALIGN_CENTER_LABEL, ICON_PATH_CENTER_ALIGN),
             Segment('right', ALIGN_RIGHT_LABEL, ICON_PATH_RIGHT_ALIGN)], DisplayMode.ICON, parent=self)
        self._alignment_control.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._alignment_control.valueChanged.connect(self._alignment_changed)

        self._text_color_label = QLabel(TEXT_COLOR_LABEL, self)
        self._text_color_button = self._swatch(Cache.LAST_BRUSH_COLOR, TEXT_COLOR_TOOLTIP)
        self._text_color_label.setBuddy(self._text_color_button)
        self._text_color_note = QLabel(TEXT_COLOR_NOTE, self)
        self._text_color_note.setToolTip(TEXT_COLOR_TOOLTIP)
        self._background_color_label = QLabel(BACKGROUND_COLOR_LABEL, self)
        self._background_color_button = self._swatch(Cache.TEXT_BACKGROUND_COLOR, BACKGROUND_COLOR_TOOLTIP)
        self._background_color_label.setBuddy(self._background_color_button)
        self._fill_checkbox = CheckBox(self)
        self._fill_checkbox.setText(FILL_BACKGROUND_LABEL)
        self._fill_checkbox.setToolTip(FILL_BACKGROUND_TOOLTIP)
        self._fill_checkbox.valueChanged.connect(self._fill_changed)

        self._box_fit_label = QLabel(BOX_FIT_LABEL, self)
        self._box_fit_control = SegmentedControl(
            [Segment(SCALE_MODE_NONE, BOX_FIT_FREE, _free_box_icon(self.palette().color(QPalette.ColorRole.Text)),
                     BOX_FIT_FREE_TOOLTIP),
             Segment(SCALE_MODE_TEXT_TO_BOUNDS, BOX_FIT_FONT, ICON_PATH_TEXT_TO_BOUNDS, BOX_FIT_FONT_TOOLTIP),
             Segment(SCALE_MODE_BOUNDS_TO_TEXT, BOX_FIT_BOX, ICON_PATH_BOUNDS_TO_TEXT, BOX_FIT_BOX_TOOLTIP)],
            DisplayMode.LABEL, parent=self)
        self._box_fit_label.setBuddy(self._box_fit_control)
        self._box_fit_control.valueChanged.connect(self._box_fit_changed)
        self._overflow_badge = QLabel(OVERFLOW_BADGE, self)
        self._overflow_badge.setToolTip(OVERFLOW_TOOLTIP)
        badge_font = QFont(self._overflow_badge.font())
        badge_font.setBold(True)
        self._overflow_badge.setFont(badge_font)
        self._update_badge_color()
        self._overflow_badge.setVisible(False)

        self._style_body = QWidget(self)
        self._style_layout = self._body_grid(self._style_body)
        # Rows of the Style grid that hold several controls in one cell, refilled by each arrangement:
        self._row_layouts = tuple(QHBoxLayout() for _ in range(2))
        for row_layout in self._row_layouts:
            row_layout.setContentsMargins(0, 0, 0, 0)
        self._style_section = PanelSection(STYLE_SECTION_TITLE, self._style_body, parent=self)
        self._style_section.bind_summary(self._style_summary, self._values_shown)

    def _swatch(self, key: str, tooltip: str) -> ColorButton:
        button = ColorButton(key, self)
        button.setText('')
        button.setToolTip(tooltip)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return button

    def _build_position_section(self) -> None:
        self._geometry = GeometryBlock(parent=self)
        self._geometry.valueChanged.connect(self._geometry_changed)
        self._position_section = PanelSection(POSITION_SECTION_TITLE, self._geometry, parent=self)
        self._position_section.bind_summary(self._geometry.summary_text, self._values_shown,
                                            self._geometry.valueChanged)

    def _build_advanced_section(self) -> None:
        self._stretch_field = NumberField(STRETCH_LABEL, DEFAULT_STRETCH, 0, MAX_STRETCH, suffix=PERCENT_SUFFIX,
                                          zero_text=STRETCH_AUTO, parent=self)
        self._stretch_field.valueChanged.connect(self._stretch_changed)
        self._overline_button = self._toggle_button(OVERLINE_LABEL, ICON_PATH_OVERLINE, QFont.overline,
                                                    QFont.setOverline)
        self._fixed_pitch_button = self._toggle_button(FIXED_PITCH_LABEL, ICON_PATH_FIXED_PITCH, QFont.fixedPitch,
                                                       QFont.setFixedPitch)
        self._kerning_button = self._toggle_button(KERNING_LABEL, ICON_PATH_KERNING, QFont.kerning,
                                                   QFont.setKerning)
        self._advanced_toggles = (self._overline_button, self._fixed_pitch_button, self._kerning_button)
        body = QWidget(self)
        layout = self._body_grid(body)
        layout.addWidget(self._stretch_field, 0, 0, 1, len(self._advanced_toggles) + 1)
        for column, button in enumerate(self._advanced_toggles):
            layout.addWidget(button, 1, column)
        layout.setColumnStretch(len(self._advanced_toggles), 1)
        self._advanced_section = PanelSection(ADVANCED_SECTION_TITLE, body, expanded=False, parent=self)
        self._advanced_section.bind_summary(self._advanced_summary, self._values_shown)

    def _build_preview_section(self) -> None:
        self._preview = TextPreview(self)
        self._preview_legend = QLabel(PREVIEW_LEGEND, self)
        legend_palette = QPalette(self._preview_legend.palette())
        legend_palette.setColor(QPalette.ColorRole.WindowText,
                                self.palette().color(QPalette.ColorRole.PlaceholderText))
        self._preview_legend.setPalette(legend_palette)
        body = QWidget(self)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._preview, stretch=1)
        layout.addWidget(self._preview_legend)
        self._preview_section = PanelSection(PREVIEW_SECTION_TITLE, body, parent=self)
        self._preview_section.bind_summary(self._preview_summary, self._values_shown)

    # -----------------------------------------------------------------------------------------------------------------
    # Access
    # -----------------------------------------------------------------------------------------------------------------

    @property
    def text_box(self) -> PlainTextEdit:
        """The text input field."""
        return self._text_box

    @property
    def geometry_block(self) -> GeometryBlock:
        """The X, Y, W and H fields."""
        return self._geometry

    @property
    def font_filter(self) -> QLineEdit:
        """The field that filters the font list."""
        return self._font_filter

    @property
    def font_list(self) -> QListWidget:
        """The font family list."""
        return self._font_list

    @property
    def font_combo(self) -> QComboBox:
        """The font family combo, the font list's smaller form."""
        return self._font_combo

    @property
    def box_fit_control(self) -> SegmentedControl:
        """The Free / Fit font / Fit box choice."""
        return self._box_fit_control

    @property
    def overflow_badge(self) -> QLabel:
        """The badge that shows while the text overflows its box."""
        return self._overflow_badge

    @property
    def preview_section(self) -> PanelSection:
        """The preview's section."""
        return self._preview_section

    @property
    def advanced_section(self) -> PanelSection:
        """The Advanced section."""
        return self._advanced_section

    def focus_text_input(self) -> None:
        """Pass keyboard focus to the text input field."""
        if not self._text_box.hasFocus():
            self._text_box.setFocus()

    def set_image_size(self, size: QSize) -> None:
        """Sets the image size the position and size fields scrub over."""
        self._geometry.set_image_size(size)

    @property
    def offset(self) -> QPoint:
        """Accesses the text layer offset."""
        return QPoint(self._offset)

    @offset.setter
    def offset(self, new_offset: QPoint) -> None:
        self._geometry.set_values(**{X: new_offset.x(), Y: new_offset.y()})
        if self._offset != new_offset:
            self._offset = QPoint(new_offset)
            self.offset_changed.emit(new_offset)

    @property
    def text_rect(self) -> TextRect:
        """Returns the full set of text drawing properties."""
        return TextRect(self._text_rect)

    @text_rect.setter
    def text_rect(self, new_params: TextRect) -> None:
        self._text_rect = TextRect(new_params)
        self._changed()

    # -----------------------------------------------------------------------------------------------------------------
    # Values
    # -----------------------------------------------------------------------------------------------------------------

    def _changed(self) -> None:
        """Shows the text rect, which auto scaling may have changed, then stores and sends it."""
        self._show_values()
        Cache().set(Cache.TEXT_TOOL_PARAMS, self._text_rect.serialize(True))
        self.text_rect_changed.emit(TextRect(self._text_rect))

    def _show_values(self) -> None:
        """Sets every control from the text rect without sending changes back."""
        text_rect = self._text_rect
        if self._text_box.value() != text_rect.text:
            with signals_blocked(self._text_box):
                self._text_box.setPlainText(text_rect.text)
        font = text_rect.font
        items = self._font_list.findItems(font.family(), Qt.MatchFlag.MatchExactly)
        if len(items) > 0 and self._font_list.currentItem() is not items[0]:
            with signals_blocked(self._font_list):
                self._font_list.setCurrentItem(items[0])
            self._font_list.scrollToItem(items[0])
        with signals_blocked(self._font_combo):
            self._font_combo.setCurrentIndex(self._font_list.currentRow())
        size, unit = _font_size(font)
        with signals_blocked(self._size_unit):
            self._size_unit.set_value(unit)
        with signals_blocked(self._size_field):
            self._size_field.set_suffix(PIXEL_SUFFIX if unit == UNIT_PX else POINT_SUFFIX)
            self._size_field.set_value(size)
        for button, getter in self._font_toggles:
            with signals_blocked(button):
                button.setChecked(getter(font))
        alignment = next((name for name, flag in _ALIGNMENTS.items() if flag == text_rect.text_alignment), 'left')
        with signals_blocked(self._alignment_control):
            self._alignment_control.set_value(alignment)
        with signals_blocked(self._fill_checkbox):
            self._fill_checkbox.setChecked(text_rect.fill_background)
        if text_rect.scale_text_to_bounds:
            box_fit = SCALE_MODE_TEXT_TO_BOUNDS
        elif text_rect.scale_bounds_to_text:
            box_fit = SCALE_MODE_BOUNDS_TO_TEXT
        else:
            box_fit = SCALE_MODE_NONE
        with signals_blocked(self._box_fit_control):
            self._box_fit_control.set_value(box_fit)
        self._text_color_button.color = text_rect.text_color
        self._background_color_button.color = text_rect.background_color
        self._geometry.set_values(**{WIDTH: text_rect.size.width(), HEIGHT: text_rect.size.height()})
        with signals_blocked(self._stretch_field):
            self._stretch_field.set_value(font.stretch() if font.stretch() != 0 else DEFAULT_STRETCH)
        bitmap = QFontDatabase.isBitmapScalable(font.family())
        self._stretch_field.setEnabled(not bitmap)
        self._stretch_field.setToolTip(STRETCH_BITMAP_TOOLTIP if bitmap else STRETCH_TOOLTIP)
        self._preview.set_text_rect(text_rect)
        overflows = text_overflows(text_rect)
        if overflows != self._overflow_badge.isVisibleTo(self._style_body):
            self._overflow_badge.setVisible(overflows)
            self._refit()
        self._values_shown.emit()

    def _text_changed(self, text: str) -> None:
        if self._text_rect.text != text:
            self._text_rect.text = text
            self._changed()

    def _font_family_selected(self, family: str) -> None:
        font = self._text_rect.font
        if family != '' and font.family() != family:
            font.setFamily(family)
            self._text_rect.font = font
            self._changed()

    def _font_combo_changed(self, index: int) -> None:
        item = self._font_list.item(index)
        if item is not None:
            self._font_family_selected(item.text())

    def _restore_font_combo_text(self) -> None:
        """Puts the selected family back in the combo's field after typing that matched none."""
        if self._font_combo.currentText() != self._text_rect.font.family():
            with signals_blocked(self._font_combo):
                self._font_combo.setCurrentIndex(self._font_list.currentRow())

    def _filter_fonts(self, text: str) -> None:
        """Shows only the font families that contain the filter text, ignoring case."""
        filter_text = text.strip().casefold()
        for row in range(self._font_list.count()):
            item = self._font_list.item(row)
            item.setHidden(filter_text not in item.text().casefold())

    def _size_changed(self, size: int | float) -> None:
        font = self._text_rect.font
        if self._size_unit.value() == UNIT_PT:
            font.setPointSize(int(size))
        else:
            font.setPixelSize(int(size))
        if _font_size(font) != _font_size(self._text_rect.font):
            self._text_rect.font = font
            self._changed()

    def _unit_changed(self, _unit: str) -> None:
        self._size_changed(self._size_field.value())

    def _alignment_changed(self, name: str) -> None:
        alignment = _ALIGNMENTS[name]
        if self._text_rect.text_alignment != alignment:
            self._text_rect.text_alignment = alignment
            self._changed()

    def _text_color_changed(self, color_str: str) -> None:
        color = QColor(color_str)
        if color.isValid() and self._text_rect.text_color != color:
            self._text_rect.text_color = color
            self._changed()

    def _background_color_changed(self, color_str: str) -> None:
        color = QColor(color_str)
        if color.isValid() and self._text_rect.background_color != color:
            self._text_rect.background_color = color
            self._changed()

    def _fill_changed(self, fill_background: bool) -> None:
        if fill_background != self._text_rect.fill_background:
            self._text_rect.fill_background = fill_background
            self._changed()

    def _box_fit_changed(self, mode: str) -> None:
        self._text_rect.scale_text_to_bounds = mode == SCALE_MODE_TEXT_TO_BOUNDS
        self._text_rect.scale_bounds_to_text = mode == SCALE_MODE_BOUNDS_TO_TEXT
        self._changed()

    def _geometry_changed(self, name: str, value: int | float) -> None:
        if name == X and value != self._offset.x():
            self.offset = QPoint(int(value), self._offset.y())
        elif name == Y and value != self._offset.y():
            self.offset = QPoint(self._offset.x(), int(value))
        elif name in (WIDTH, HEIGHT):
            size = self._text_rect.size
            if name == WIDTH:
                size.setWidth(int(value))
            else:
                size.setHeight(int(value))
            if size != self._text_rect.size:
                self._text_rect.size = size
                self._changed()

    def _stretch_changed(self, stretch: int | float) -> None:
        font = self._text_rect.font
        if int(stretch) != font.stretch():
            font.setStretch(int(stretch))
            self._text_rect.font = font
            self._changed()

    def _font_summary(self) -> str:
        return FONT_SUMMARY.format(family=self._text_rect.font.family(), size=self._size_field.value_text())

    def _style_summary(self) -> str:
        parts = [button.toolTip() for button in self._style_toggles if button.isChecked()]
        parts += [segment.label for segment in self._alignment_control.segments
                  if segment.value == self._alignment_control.value()]
        return ', '.join(parts)

    def _advanced_summary(self) -> str:
        return ', '.join([self._stretch_field.value_text()]
                         + [button.toolTip() for button in self._advanced_toggles if button.isChecked()])

    def _preview_summary(self) -> str:
        return PREVIEW_OVERFLOWS if text_overflows(self._text_rect) else PREVIEW_FITS

    def _update_badge_color(self) -> None:
        signal = signal_color()
        badge_palette = QPalette(self.palette())
        badge_palette.setColor(QPalette.ColorRole.WindowText,
                               signal if signal is not None else QColor(Qt.GlobalColor.red))
        self._overflow_badge.setPalette(badge_palette)

    def changeEvent(self, event: Optional[QEvent]) -> None:  # pylint: disable=invalid-name
        """Redraws the badge and the Free icon in the new colors after a palette change."""
        super().changeEvent(event)
        if event is not None and event.type() == QEvent.Type.PaletteChange:
            self._update_badge_color()
            self._box_fit_control.set_segment_icon(
                SCALE_MODE_NONE, _free_box_icon(self.palette().color(QPalette.ColorRole.Text)))

    # -----------------------------------------------------------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------------------------------------------------------

    def _apply_fit(self, orientation: Orientation, placement: Placement) -> None:
        columns, font_form, style_form, preview, advanced, headers = placement
        self._orientation = orientation
        strip = orientation == Orientation.STRIP
        show_headers = not strip or headers is not None
        for section in self._sections:
            section.set_header_visible(show_headers)
        self._arrange_font(font_form == FONT_COMBO)
        self._arrange_style(style_form == COMPACT, strip)
        if advanced is None:
            self._grid.removeWidget(self._advanced_section)
            self._overflow_layout.addWidget(self._advanced_section)
            self._advanced_section.set_header_visible(False)
        else:
            self._overflow_layout.removeWidget(self._advanced_section)
        self._arrange_sections(strip, columns == TWO_COLUMNS and not strip, preview is not None, advanced is not None)
        # Moving between the overflow and the panel reparents the section, which hides it:
        self._advanced_section.show()
        self._preview_section.setVisible(preview is not None)

    def _arrange_font(self, combo: bool) -> None:
        """Puts the filter over the font list, or the font combo, then Size with its unit."""
        layout = self._font_layout
        self._clear(layout, (self._font_filter, self._font_list, self._font_combo, self._size_field,
                             self._size_unit))
        if combo:
            layout.addWidget(self._font_combo, 0, 0, 1, 2)
        else:
            layout.addWidget(self._font_filter, 0, 0, 1, 2)
            layout.addWidget(self._font_list, 1, 0, 1, 2)
            layout.setRowStretch(1, 1)
        layout.addWidget(self._size_field, 2, 0)
        layout.addWidget(self._size_unit, 2, 1)
        layout.setColumnStretch(0, 1)
        for widget in (self._font_filter, self._font_list):
            widget.setVisible(not combo)
        self._font_combo.setVisible(combo)

    def _arrange_style(self, compact: bool, strip: bool) -> None:
        """Lays out the Style rows.

        - Roomy: the toggles with alignment at the row's end, then labeled Text, Background and Box fit rows, with the
          badge under Box fit.
        - Compact side: the toggles with alignment, then both swatches, then icon-only Box fit with "Fill behind
          text", and the badge under them.
        - Compact strip: the toggles with alignment, then both swatches with "Fill behind text", then icon-only Box
          fit with the badge.
        """
        layout = self._style_layout
        widgets = (*self._style_toggles, self._alignment_control, self._text_color_label, self._text_color_button,
                   self._text_color_note, self._background_color_label, self._background_color_button,
                   self._fill_checkbox, self._box_fit_label, self._box_fit_control, self._overflow_badge)
        self._clear(layout, widgets)
        for row_layout in self._row_layouts:
            while row_layout.count() > 0:
                row_layout.takeAt(0)
            layout.removeItem(row_layout)
        self._box_fit_control.set_display_mode(DisplayMode.ICON if compact else DisplayMode.LABEL)
        self._box_fit_control.setSizePolicy(QSizePolicy.Policy.Fixed if compact else QSizePolicy.Policy.Expanding,
                                            QSizePolicy.Policy.Fixed)
        toggle_count = len(self._style_toggles)
        for column, button in enumerate(self._style_toggles):
            layout.addWidget(button, 0, column)
        # Columns: one per toggle, a spare column, then the column alignment ends the first row in:
        spare = toggle_count
        end = toggle_count + 1
        width = end + 1
        rows = iter(self._row_layouts)
        if not compact:
            layout.addWidget(self._alignment_control, 0, end)
            layout.addWidget(self._text_color_label, 1, 0, 1, 2)
            self._add_row(next(rows), 1, 2, width - 2, (self._text_color_button, self._text_color_note))
            layout.addWidget(self._background_color_label, 2, 0, 1, 2)
            self._add_row(next(rows), 2, 2, width - 2, (self._background_color_button, self._fill_checkbox))
            layout.addWidget(self._box_fit_label, 3, 0, 1, 2)
            layout.addWidget(self._box_fit_control, 3, 2, 1, width - 2)
            layout.addWidget(self._overflow_badge, 4, 2, 1, width - 2)
        elif strip:
            layout.addWidget(self._alignment_control, 0, end)
            self._add_row(next(rows), 1, 0, width, (self._text_color_button, self._text_color_label,
                                                    self._background_color_button, self._background_color_label,
                                                    self._fill_checkbox))
            self._add_row(next(rows), 2, 0, width, (self._box_fit_control, self._overflow_badge))
        else:
            layout.addWidget(self._alignment_control, 0, end)
            self._add_row(next(rows), 1, 0, width, (self._text_color_button, self._text_color_label,
                                                    self._background_color_button, self._background_color_label))
            self._add_row(next(rows), 2, 0, width, (self._box_fit_control, self._fill_checkbox))
            layout.addWidget(self._overflow_badge, 3, 0, 1, width)
        layout.setColumnStretch(spare, 1)
        self._text_color_note.setVisible(not compact)
        self._box_fit_label.setVisible(not compact)

    def _add_row(self, row_layout: QHBoxLayout, row: int, column: int, column_span: int,
                 widgets: tuple[QWidget, ...]) -> None:
        """Adds widgets side by side in one Style grid cell, followed by spare room."""
        for widget in widgets:
            row_layout.addWidget(widget)
        row_layout.addStretch(1)
        self._style_layout.addLayout(row_layout, row, column, 1, column_span)

    def _arrange_sections(self, strip: bool, two_columns: bool, preview: bool, advanced: bool) -> None:
        """Places the text box and sections in strip columns, two side columns, or one, with spare room after them."""
        grid = self._grid
        self._clear(grid, (self._text_box, *self._sections))
        while self._strip_column.count() > 0:
            self._strip_column.takeAt(0)
        grid.removeItem(self._strip_column)
        if strip:
            # Spare height goes to the preview, to the text box without one, and to the font list:
            grid.addWidget(self._text_box, 0, 0, 1 if preview else 2, 1)
            if preview:
                grid.addWidget(self._preview_section, 1, 0)
            grid.addWidget(self._font_section, 0, 1, 2, 1)
            grid.addWidget(self._style_section, 0, 2, 2, 1, Qt.AlignmentFlag.AlignTop)
            self._strip_column.addWidget(self._position_section)
            if advanced:
                self._strip_column.addWidget(self._advanced_section)
            self._strip_column.addStretch(1)
            grid.addLayout(self._strip_column, 0, 3, 2, 1)
            grid.setRowStretch(1, 1)
            used_columns = 4
        elif two_columns:
            top = Qt.AlignmentFlag.AlignTop
            grid.addWidget(self._text_box, 0, 0, 1, 1 if preview else 2)
            if preview:
                grid.addWidget(self._preview_section, 0, 1)
            grid.addWidget(self._font_section, 1, 0, top)
            grid.addWidget(self._style_section, 1, 1, top)
            grid.addWidget(self._position_section, 2, 0, top)
            if advanced:
                grid.addWidget(self._advanced_section, 2, 1, top)
            grid.setRowStretch(3, 1)
            used_columns = 2
        else:
            widgets = [self._text_box, self._font_section, self._style_section, self._position_section]
            if advanced:
                widgets.append(self._advanced_section)
            if preview:
                widgets.append(self._preview_section)
            for row, widget in enumerate(widgets):
                grid.addWidget(widget, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.setRowStretch(len(widgets), 1)
            used_columns = 1
        if not strip:
            # The emptied column stays in the grid, which owns it, and takes no space there:
            grid.addLayout(self._strip_column, 0, used_columns)
        for column in range(used_columns):
            grid.setColumnStretch(column, 1)
        grid.setColumnStretch(used_columns, 0)
        frame = self._text_box.frameWidth() * 2 + int(self._text_box.document().documentMargin() * 2)
        self._text_box.setMinimumHeight(max(self._text_box.fontMetrics().lineSpacing() * TEXT_BOX_MIN_LINES + frame,
                                            self._text_box.minimumSizeHint().height()))
        self._text_box.setSizePolicy(QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Expanding if strip else QSizePolicy.Policy.Preferred)
        self._text_box.setMaximumHeight(QWIDGETSIZE_MAX if strip
                                        else max(self._text_box.minimumHeight(), self._text_box.sizeHint().height()))
        self._font_list.setMaximumHeight(QWIDGETSIZE_MAX if strip else self._font_list.sizeHint().height())
        for widget in (self._text_box, *self._sections):
            self._cap_width(widget)
