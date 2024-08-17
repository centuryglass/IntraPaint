"""Provides a control panel class for the text tool."""
from typing import Optional, Callable

from PySide6.QtCore import Signal, QSize, QPoint, QRect
from PySide6.QtGui import QFont, QFontDatabase, Qt, QImage, QColor, QPainter, QResizeEvent, QIcon
from PySide6.QtWidgets import QApplication, QWidget, QListWidget, QGridLayout, QLabel, QSizePolicy, QComboBox, \
    QVBoxLayout, QScrollArea, QPushButton

from src.config.cache import Cache
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.plain_text_edit import PlainTextEdit
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox
from src.ui.widget.brush_color_button import BrushColorButton
from src.ui.widget.image_widget import ImageWidget
from src.util.display_size import find_text_size, max_font_size
from src.util.geometry_utils import get_scaled_placement, fill_outside_rect
from src.util.image_utils import create_transparent_image
from src.util.shared_constants import PROJECT_DIR, SHORT_LABEL_X_POS, SHORT_LABEL_Y_POS, SHORT_LABEL_WIDTH, \
    SHORT_LABEL_HEIGHT, INT_MAX

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.text_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


LABEL_TEXT_FONT_FAMILY = _tr('Font:')
LABEL_TEXT_FONT_SIZE = _tr('Font Size:')
LABEL_TEXT_TEXT_INPUT = _tr('Enter Text:')
LABEL_TEXT_FONT_STRETCH = _tr('Stretch')
BUTTON_TEXT_FONT_COLOR = _tr('Text Color')
BUTTON_TEXT_BACKGROUND_COLOR = _tr('Background Color')
BUTTON_TEXT_BOUNDS_TO_TEXT = _tr('Bounds to Text Size')
TOOLTIP_BOUNDS_TO_TEXT = _tr('Update width and height to fit the current text exactly.')
BUTTON_TEXT_FONT_SIZE_TO_BOUNDS = _tr('Resize Font to Bounds')
TOOLTIP_FONT_SIZE_TO_BOUNDS = _tr('Change the font size to the largest size that will fit in the text bounds.')
TOOLTIP_COLOR = _tr('Set text color')
TOOLTIP_BACKGROUND_COLOR = _tr('Set text background color')

LABEL_TEXT_ALIGNMENT_DROPDOWN = _tr('Alignment:')
OPTION_TEXT_LEFT_ALIGN = _tr('Left')
OPTION_TEXT_CENTER_ALIGN = _tr('Center')
OPTION_TEXT_RIGHT_ALIGN = _tr('Right')

OPTION_TEXT_PIXEL_SIZE_FORMAT = _tr('Pixels')
OPTION_TEXT_POINT_SIZE_FORMAT = _tr('Point')

LABEL_TEXT_CHECKBOX_CONTAINER = _tr('Text Style:')
CHECKBOX_LABEL_BOLD = _tr('Bold')
CHECKBOX_LABEL_ITALIC = _tr('Italic')
CHECKBOX_LABEL_OVERLINE = _tr('Overline')
CHECKBOX_LABEL_STRIKEOUT = _tr('Strikeout')
CHECKBOX_LABEL_UNDERLINE = _tr('Underline')
CHECKBOX_LABEL_FIXED_PITCH = _tr('Fixed Pitch')
CHECKBOX_LABEL_KERNING = _tr('Kerning')
CHECKBOX_LABEL_FILL_BACKGROUND = _tr('Fill Background')


# Icons:
ICON_BOLD = f'{PROJECT_DIR}/resources/icons/text/bold.svg'
ICON_ITALIC = f'{PROJECT_DIR}/resources/icons/text/italic.svg'
ICON_OVERLINE = f'{PROJECT_DIR}/resources/icons/text/overline.svg'
ICON_STRIKETHROUGH = f'{PROJECT_DIR}/resources/icons/text/strikethrough.svg'
ICON_UNDERLINE = f'{PROJECT_DIR}/resources/icons/text/underline.svg'
ICON_FIXED_PITCH = f'{PROJECT_DIR}/resources/icons/text/fixed_pitch.svg'
ICON_KERNING = f'{PROJECT_DIR}/resources/icons/text/kerning.svg'
ICON_FILL_BACKGROUND = f'{PROJECT_DIR}/resources/icons/text/fill_background.svg'

ICON_LEFT = f'{PROJECT_DIR}/resources/icons/text/left.svg'
ICON_RIGHT = f'{PROJECT_DIR}/resources/icons/text/right.svg'
ICON_CENTER = f'{PROJECT_DIR}/resources/icons/text/center.svg'

MAX_FONT_SIZE = 1000
MAX_STRETCH = 4000


class TextRect:
    """Data class specifying a block of text, along with exactly where and how it should be rendered."""

    def __init__(self, to_copy: Optional['TextRect'] = None) -> None:
        if to_copy is not None:
            self._text = to_copy.text
            self._font = to_copy.font
            self._text_color = to_copy.text_color
            self._background_color = to_copy.background_color
            self._bounds = to_copy.bounds
            self._text_alignment = to_copy.text_alignment
            self._fill_background = to_copy.fill_background
        else:
            self._text = ''
            self._font = QApplication.font()
            self._text_color = QColor()
            self._background_color = QColor()
            self._bounds = QRect()
            self._text_alignment = Qt.AlignmentFlag.AlignLeft
            self._fill_background = False

    @property
    def text(self) -> str:
        """Returns the rendered text."""
        return self._text

    @text.setter
    def text(self, new_text: str) -> None:
        self._text = new_text

    @property
    def font(self) -> QFont:
        """Returns a copy of the text drawing font."""
        return QFont(self._font)

    @font.setter
    def font(self, new_font: QFont) -> None:
        self._font = QFont(new_font)

    @property
    def text_color(self) -> QColor:
        """Returns the text color."""
        return QColor(self._text_color)

    @text_color.setter
    def text_color(self, new_color: QColor) -> None:
        self._text_color = QColor(new_color)

    @property
    def background_color(self) -> QColor:
        """Returns the text background color (possibly not rendered)."""
        return QColor(self._background_color)

    @background_color.setter
    def background_color(self, new_color: QColor) -> None:
        self._background_color = QColor(new_color)

    @property
    def bounds(self) -> QRect:
        """Returns the text bounds."""
        return QRect(self._bounds)

    @bounds.setter
    def bounds(self, new_bounds: QRect) -> None:
        self._bounds = QRect(new_bounds)

    @property
    def text_alignment(self) -> Qt.AlignmentFlag:
        """Returns the text alignment."""
        return self._text_alignment

    @text_alignment.setter
    def text_alignment(self, new_alignment: Qt.AlignmentFlag) -> None:
        self._text_alignment = new_alignment

    @property
    def fill_background(self) -> bool:
        """Returns whether the background should be filled."""
        return self._fill_background

    @fill_background.setter
    def fill_background(self, should_fill: bool) -> None:
        self._fill_background = should_fill

    def render(self, painter: QPainter) -> None:
        """Renders the text into a painter."""
        painter.save()
        if self._fill_background:
            painter.fillRect(self._bounds, self._background_color)
        painter.setFont(self._font)
        painter.setPen(self._text_color)
        painter.setRenderHint(QPainter.RenderHint.LosslessImageRendering, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.drawText(self._bounds, self._text, self._text_alignment)


class TextToolPanel(QWidget):
    """Provides a control panel class for the text tool."""

    text_rect_changed = Signal(TextRect)

    def __init__(self) -> None:
        super().__init__()
        self._text_rect = TextRect()
        self._layout = QGridLayout(self)
        self._orientation = Qt.Orientation.Horizontal
        self._change_signal_enabled = True
        self._calculated_size = QSize()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Load cached font:
        cache = Cache()
        selected_font_family = cache.get(Cache.LAST_FONT_FAMILY)
        if len(selected_font_family) == 0:
            selected_font = QApplication.font()
            selected_font_family = selected_font.family()
            cache.set(Cache.LAST_FONT_FAMILY, selected_font_family)
        else:
            selected_font = QFont(selected_font_family)
        self._text_rect.font = selected_font
        cache.connect(self, Cache.LAST_FONT_FAMILY, self._font_family_config_change_slot)

        # Text entry and previewing:
        self._preview = ImageWidget(QImage())
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._text_box = PlainTextEdit()
        self._text_box.setPlaceholderText(LABEL_TEXT_TEXT_INPUT)
        self._text_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._text_box.setValue(self._text_rect.text)
        self._text_box.valueChanged.connect(self._text_changed_slot)

        # Text size:
        font_size_format = OPTION_TEXT_PIXEL_SIZE_FORMAT
        font_size = selected_font.pixelSize()
        if font_size <= 0:
            font_size = selected_font.pointSize()
            font_size_format = OPTION_TEXT_POINT_SIZE_FORMAT

        self._size_slider = IntSliderSpinbox()
        self._size_slider.setMinimum(1)
        self._size_slider.setMaximum(MAX_FONT_SIZE)
        self._size_slider.setValue(font_size)
        self._size_slider.setText(LABEL_TEXT_FONT_SIZE)

        self._size_type_dropdown = QComboBox()
        self._size_type_dropdown.addItem(OPTION_TEXT_PIXEL_SIZE_FORMAT)
        self._size_type_dropdown.addItem(OPTION_TEXT_POINT_SIZE_FORMAT)
        self._size_type_dropdown.setCurrentText(font_size_format)
        self._size_slider.setValue(font_size)
        self._size_slider.valueChanged.connect(self._size_change_slot)
        self._size_type_dropdown.currentIndexChanged.connect(self._size_format_change_slot)

        self._stretch_spinbox = IntSliderSpinbox()
        self._stretch_spinbox.setText(LABEL_TEXT_FONT_STRETCH)
        self._stretch_spinbox.set_slider_included(False)
        self._stretch_spinbox.setMinimum(0)
        self._stretch_spinbox.setMaximum(MAX_STRETCH)
        self._stretch_spinbox.setValue(selected_font.stretch())
        self._stretch_spinbox.setEnabled(not QFontDatabase.isBitmapScalable(selected_font.family()))
        self._stretch_spinbox.valueChanged.connect(self._stretch_change_slot)

        # Text placement:
        def _init_spinbox(label: str, change_slot: Callable[[int], None], allow_negative: bool) -> IntSliderSpinbox:
            spinbox = IntSliderSpinbox()
            spinbox.setText(label)
            spinbox.set_slider_included(False)
            if not allow_negative:
                spinbox.setMinimum(0)
            spinbox.setMaximum(INT_MAX)
            spinbox.valueChanged.connect(change_slot)
            return spinbox
        self._x_input = _init_spinbox(SHORT_LABEL_X_POS, self._text_x_changed_slot, True)
        self._y_input = _init_spinbox(SHORT_LABEL_Y_POS, self._text_y_changed_slot, True)
        self._width_input = _init_spinbox(SHORT_LABEL_WIDTH, self._text_width_changed_slot, False)
        self._height_input = _init_spinbox(SHORT_LABEL_HEIGHT, self._text_height_changed_slot, False)

        self._bounds_to_font_size_button = QPushButton()
        self._bounds_to_font_size_button.setText(BUTTON_TEXT_BOUNDS_TO_TEXT)
        self._bounds_to_font_size_button.setToolTip(TOOLTIP_BOUNDS_TO_TEXT)
        self._bounds_to_font_size_button.clicked.connect(self._resize_bounds_to_font)

        self._font_size_to_bounds_button = QPushButton()
        self._font_size_to_bounds_button.setText(BUTTON_TEXT_FONT_SIZE_TO_BOUNDS)
        self._font_size_to_bounds_button.setToolTip(TOOLTIP_FONT_SIZE_TO_BOUNDS)
        self._font_size_to_bounds_button.clicked.connect(self._resize_font_to_bounds)

        # Text feature checkboxes:
        self._checkbox_label = QLabel(LABEL_TEXT_CHECKBOX_CONTAINER)
        self._checkbox_container = QWidget()
        self._checkbox_layout = QVBoxLayout(self._checkbox_container)
        self._checkbox_scroll = QScrollArea()
        self._checkbox_scroll.setWidget(self._checkbox_container)
        self._checkbox_scroll.setWidgetResizable(True)
        self._checkbox_label.setBuddy(self._checkbox_container)
        self._checkbox_container.setSizePolicy(QSizePolicy.Policy.Preferred,
                                               QSizePolicy.Policy.MinimumExpanding)
        self._checkbox_scroll.setSizePolicy(QSizePolicy.Policy.Preferred,
                                               QSizePolicy.Policy.Expanding)

        def _init_checkbox(label: str, icon_path: str, getter: Callable[[QFont], bool],
                           setter: Callable[[QFont, bool], None]) -> CheckBox:
            checkbox = CheckBox()
            checkbox.setText(label)
            checkbox.setIcon(QIcon(icon_path))
            change_handler = self._get_boolean_change_handler(getter, setter)
            checkbox.valueChanged.connect(change_handler)
            self._checkbox_layout.addWidget(checkbox)
            return checkbox
        self._bold_checkbox = _init_checkbox(CHECKBOX_LABEL_BOLD, ICON_BOLD, lambda font: font.bold(),
                                             lambda font, value: font.setBold(value))
        self._italic_checkbox = _init_checkbox(CHECKBOX_LABEL_ITALIC, ICON_ITALIC, lambda font: font.italic(),
                                               lambda font, value: font.setItalic(value))
        self._overline_checkbox = _init_checkbox(CHECKBOX_LABEL_OVERLINE, ICON_OVERLINE,
                                                 lambda font: font.overline(),
                                                 lambda font, value: font.setOverline(value))
        self._strikethrough_checkbox = _init_checkbox(CHECKBOX_LABEL_STRIKEOUT, ICON_STRIKETHROUGH,
                                                      lambda font: font.strikeOut(),
                                                      lambda font, value: font.setStrikeOut(value))
        self._underline_checkbox = _init_checkbox(CHECKBOX_LABEL_UNDERLINE, ICON_UNDERLINE,
                                                  lambda font: font.underline(),
                                                  lambda font, value: font.setUnderline(value))
        self._fixed_pitch_checkbox = _init_checkbox(CHECKBOX_LABEL_FIXED_PITCH, ICON_FIXED_PITCH,
                                                    lambda font: font.fixedPitch(),
                                                    lambda font, value: font.setFixedPitch(value))
        self._kerning_checkbox = _init_checkbox(CHECKBOX_LABEL_KERNING, ICON_KERNING,
                                                lambda font: font.kerning(),
                                                lambda font, value: font.setKerning(value))
        self._fill_background_checkbox = CheckBox()
        self._fill_background_checkbox.setText(CHECKBOX_LABEL_FILL_BACKGROUND)
        self._fill_background_checkbox.setIcon(QIcon(ICON_FILL_BACKGROUND))
        self._fill_background_checkbox.toggled.connect(self._fill_background_change_slot)
        self._checkbox_layout.addWidget(self._fill_background_checkbox)

        self._alignment_label = QLabel(LABEL_TEXT_ALIGNMENT_DROPDOWN)
        self._alignment_dropdown = QComboBox()
        self._alignment_label.setBuddy(self._alignment_dropdown)
        self._alignment_dropdown.addItem(QIcon(ICON_LEFT), OPTION_TEXT_LEFT_ALIGN, userData=Qt.AlignmentFlag.AlignLeft)
        self._alignment_dropdown.addItem(QIcon(ICON_CENTER), OPTION_TEXT_CENTER_ALIGN,
                                         userData=Qt.AlignmentFlag.AlignVCenter)
        self._alignment_dropdown.addItem(QIcon(ICON_RIGHT), OPTION_TEXT_RIGHT_ALIGN,
                                         userData=Qt.AlignmentFlag.AlignRight)
        align_index = self._alignment_dropdown.findData(self._text_rect.text_alignment)
        assert align_index >= 0
        self._alignment_dropdown.setCurrentIndex(align_index)
        self._alignment_dropdown.currentIndexChanged.connect(self._alignment_change_slot)

        # Text color control:
        self._color_button = BrushColorButton()
        self._color_button.setText(BUTTON_TEXT_FONT_COLOR)
        self._color_button.setToolTip(TOOLTIP_COLOR)
        self._background_color_button = BrushColorButton(Cache.BACKGROUND_COLOR)
        self._background_color_button.setText(BUTTON_TEXT_BACKGROUND_COLOR)
        self._background_color_button.setToolTip(TOOLTIP_BACKGROUND_COLOR)

        self._color = self._color_button.color
        self._background_color = self._background_color_button.color
        cache.connect(self, Cache.LAST_BRUSH_COLOR, self._color_change_slot)
        cache.connect(self, Cache.BACKGROUND_COLOR, self._background_color_change_slot)

        # Font selection panel:
        self._font_list_label = QLabel(LABEL_TEXT_FONT_FAMILY)
        self._font_list = QListWidget()
        self._font_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        font_families = [font for font in QFontDatabase.families() if QFontDatabase.isScalable(font)
                               and not QFontDatabase.isPrivateFamily(font)]
        fonts = [QFont(family) for family in font_families]
        for font in fonts:
            font_family = font.family()
            self._font_list.addItem(font_family)
            new_item = self._font_list.item(self._font_list.count() - 1)
            new_item.setFont(font)
            new_item.setToolTip(font_family)
            if selected_font_family == font_family:
                self._font_list.setCurrentItem(new_item)
        self._font_list.currentTextChanged.connect(self._font_family_change_slot)
        self._font_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Final layout:
        self._build_layout()
        self._draw_preview()

    def _build_layout(self) -> None:
        while self._layout.count() > 0:
            self._layout.takeAt(0)
        if self._orientation == Qt.Orientation.Horizontal:
            self._layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(self._font_list_label, 0, 0)
            self._layout.addWidget(self._font_list, 1, 0, 6, 2)

            self._layout.addWidget(self._checkbox_label, 0, 3)
            self._layout.addWidget(self._checkbox_scroll, 1, 3, 6, 1)

            self._layout.addWidget(self._preview, 0, 4, 4, 4, Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(self._text_box, 3, 4, 3, 4)
            self._layout.addWidget(self._size_slider, 6, 4, 1, 3)
            self._layout.addWidget(self._size_type_dropdown, 6, 7)

            self._layout.addWidget(self._font_size_to_bounds_button, 3, 8)
            self._layout.addWidget(self._bounds_to_font_size_button, 4, 8)
            self._layout.addWidget(self._color_button, 3, 9)
            self._layout.addWidget(self._background_color_button, 4, 9)
            self._layout.addWidget(self._alignment_label, 5, 8)
            self._layout.addWidget(self._alignment_dropdown, 5, 9)
            self._layout.addWidget(self._stretch_spinbox, 6, 8, 1, 2)

            self._layout.addWidget(self._x_input, 1, 8)
            self._layout.addWidget(self._y_input, 2, 8)
            self._layout.addWidget(self._width_input, 1, 9)
            self._layout.addWidget(self._height_input, 2, 9)

        else:
            assert self._orientation == Qt.Orientation.Vertical
            self._layout.setRowStretch(3, 0)
            self._layout.setColumnStretch(1, 0)
            self._layout.setColumnStretch(2, 0)

            self._layout.addWidget(self._text_box, 0, 0, 2, 3)
            self._layout.addWidget(self._color_button, 0, 3)
            self._layout.addWidget(self._background_color_button, 1, 3)
            self._layout.addWidget(self._preview, 2, 0, 4, 4, Qt.AlignmentFlag.AlignTop)
            self._layout.addWidget(self._size_slider, 6, 0, 1, 3)
            self._layout.addWidget(self._size_type_dropdown, 6, 3)

            self._layout.addWidget(self._x_input, 7, 0)
            self._layout.addWidget(self._y_input, 8, 0)
            self._layout.addWidget(self._width_input, 7, 1)
            self._layout.addWidget(self._height_input, 8, 1)

            self._layout.addWidget(self._font_size_to_bounds_button, 7, 2, 1, 2)
            self._layout.addWidget(self._bounds_to_font_size_button, 8, 2, 1, 2)

            self._layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignLeft \
                                      | Qt.AlignmentFlag.AlignTop)
            self._layout.addWidget(self._font_list_label, 10, 0)
            self._layout.addWidget(self._font_list, 11, 0, 7, 2)

            self._layout.addWidget(self._checkbox_label, 10, 2, 1, 2)
            self._layout.addWidget(self._checkbox_scroll, 11, 2, 3, 2)
            self._layout.addWidget(self._alignment_label, 14, 2)
            self._layout.addWidget(self._alignment_dropdown, 14, 3)
            self._layout.addWidget(self._stretch_spinbox, 15, 2, 1, 2)

        self._font_list.scrollToItem(self._font_list.currentItem())

    @property
    def text_rect(self) -> TextRect:
        """Returns the full set of text drawing properties."""
        return TextRect(self._text_rect)

    @text_rect.setter
    def text_rect(self, new_params: TextRect) -> None:
        self._change_signal_enabled = False
        self._text_rect = TextRect(new_params)

        self._text_box.setPlainText(new_params.text)

        # Update font controls:
        new_font = self._text_rect.font
        list_items = self._font_list.findItems(new_font.family(), Qt.MatchFlag.MatchExactly)
        assert len(list_items) > 0
        self._font_list.setCurrentItem(list_items[0])
        self._font_list.scrollToItem(list_items[0])
        font_size_format = OPTION_TEXT_PIXEL_SIZE_FORMAT
        font_size = new_font.pixelSize()
        if font_size <= 0:
            font_size = new_font.pointSize()
            font_size_format = OPTION_TEXT_POINT_SIZE_FORMAT
        self._size_slider.setValue(font_size)
        self._size_type_dropdown.setCurrentText(font_size_format)
        self._bold_checkbox.setChecked(new_font.bold())
        self._italic_checkbox.setChecked(new_font.italic())
        self._overline_checkbox.setChecked(new_font.overline())
        self._strikethrough_checkbox.setChecked(new_font.strikeOut())
        self._underline_checkbox.setChecked(new_font.underline())
        self._fixed_pitch_checkbox.setChecked(new_font.fixedPitch())
        self._kerning_checkbox.setChecked(new_font.kerning())
        self._stretch_spinbox.setValue(new_font.stretch())
        self._stretch_spinbox.setEnabled(not QFontDatabase.isBitmapScalable(new_font.family()))

        # Update bounds:
        new_bounds = self._text_rect.bounds
        self._x_input.setValue(new_bounds.x())
        self._y_input.setValue(new_bounds.y())
        self._width_input.setValue(new_bounds.width())
        self._height_input.setValue(new_bounds.height())

        # Alignment:
        align_index = self._alignment_dropdown.findData(self._text_rect.text_alignment)
        assert align_index >= 0
        self._alignment_dropdown.setCurrentIndex(align_index)

        self._fill_background_checkbox.setChecked(self._text_rect.fill_background)
        self._change_signal_enabled = True
        self._handle_change()

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Update the panel orientation."""
        if self._orientation != orientation:
            self._orientation = orientation
            self._build_layout()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Adjust preview and text box size limits based on orientation and panel size."""
        self._preview.setMaximumHeight(self.height() // 4 if self._orientation == Qt.Orientation.Horizontal else
                                       self.height() // 10)
        self._text_box.setMaximumHeight(self._checkbox_label.sizeHint().height() * 4)

    def _draw_preview(self) -> None:
        """Redraws the text preview image."""
        entered_text = self._text_rect.text
        selected_font = self._text_rect.font
        text_bounds = self._text_rect.bounds
        text_alignment = self._text_rect.text_alignment
        text = '       ' if len(entered_text) == 0 else entered_text
        text_size = find_text_size(text, selected_font)
        self._calculated_size = text_size
        if text_size.width() == 0:
            if not self._preview.image.isNull():
                self._preview.image.fill(self._background_color)
            return
        image_size = QSize(text_bounds.size())
        image_size.setWidth(max(image_size.width(), text_size.width()))
        image_size.setHeight(max(image_size.height(), text_size.height()))
        scaled_size = get_scaled_placement(self._preview.size(), image_size).size()
        scale = scaled_size.width() / image_size.width()
        if scale == 0.0:
            scale = 1.0
            scaled_size = image_size
        assert not scaled_size.isEmpty()
        preview_image = self._preview.image
        if preview_image.isNull() or preview_image.size() != scaled_size:
            preview_image = create_transparent_image(scaled_size)
        preview_image.fill(self._background_color)

        drawn_font = QFont(selected_font)
        if self._size_type_dropdown.currentText() == OPTION_TEXT_PIXEL_SIZE_FORMAT:
            drawn_font.setPixelSize(round(drawn_font.pixelSize() * scale))
        else:
            drawn_font.setPointSize(int(drawn_font.pointSize() * scale))
        painter = QPainter(preview_image)
        painter.setFont(drawn_font)

        painter.setRenderHint(QPainter.RenderHint.LosslessImageRendering, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(self._text_rect.text_color)
        painter.drawText(QRect(QPoint(1, 1), scaled_size), text, text_alignment | Qt.AlignmentFlag.AlignVCenter)
        painter.drawRect(QRect(QPoint(), scaled_size))
        if not text_bounds.isEmpty() and text_size != text_bounds.size():
            preview_text_size = text_bounds.size() * scale
            painter.setPen(Qt.GlobalColor.red)
            painter.drawRect(QRect(QPoint(), preview_text_size))
            painter.setOpacity(0.5)
            fill_outside_rect(painter, QRect(QPoint(), preview_image.size()), QRect(QPoint(), preview_text_size),
                              Qt.GlobalColor.red)
            painter.setOpacity(1.0)
        painter.end()
        self._preview.image = preview_image

        preview_palette = self._preview.palette()
        preview_palette.setColor(self._preview.backgroundRole(), self._background_color)
        self._preview.setPalette(preview_palette)
        self._preview.setAutoFillBackground(True)
        self.update()

    # Signal handlers for text controls:

    def _resize_bounds_to_font(self) -> None:
        if self._calculated_size.isEmpty():
            self._draw_preview()
            assert self._calculated_size.width() > 0 and self._calculated_size.height() > 0
        text_bounds = self._text_rect.bounds
        self._text_rect.bounds = QRect(text_bounds.topLeft(), self._calculated_size)
        self._width_input.setValue(self._calculated_size.width())
        self._height_input.setValue(self._calculated_size.height())
        self._handle_change()

    def _resize_font_to_bounds(self) -> None:
        entered_text = self._text_rect.text
        selected_font = self._text_rect.font
        text_bounds = self._text_rect.bounds
        max_pt_size = max_font_size(entered_text, selected_font, text_bounds.size())
        if self._size_type_dropdown.currentText() == OPTION_TEXT_PIXEL_SIZE_FORMAT:
            pixel_size = round(max_pt_size / 0.75)
            if pixel_size > 0:
                self._size_slider.setValue(pixel_size)
        elif max_pt_size > 0:
            self._size_slider.setValue(max_pt_size)

    def _handle_change(self) -> None:
        if self._change_signal_enabled:
            self._draw_preview()
            self.text_rect_changed.emit(self._text_rect)

    def _font_family_change_slot(self, font_family: str) -> None:
        Cache().set(Cache.LAST_FONT_FAMILY, font_family)
        font = self._text_rect.font
        if font.family() != font_family:
            font.setFamily(font_family)
            self._stretch_spinbox.setEnabled(not QFontDatabase.isBitmapScalable(font_family))
            self._text_rect.font = font
            self._handle_change()

    def _font_family_config_change_slot(self, font_family: str) -> None:
        selected_in_list = self._font_list.selectedItems()[0].text()
        if selected_in_list != font_family:
            list_items = self._font_list.findItems(font_family, Qt.MatchFlag.MatchExactly)
            if len(list_items) == 0:  # Invalid cache item
                Cache().set(Cache.LAST_FONT_FAMILY, selected_in_list)
                return
            self._font_list.setCurrentItem(list_items[0])

    def _text_changed_slot(self, text: str) -> None:
        if self._text_rect.text != text:
            self._text_rect.text = text
            self._handle_change()

    def _color_change_slot(self, color_str: str) -> None:
        color = QColor(color_str)
        if self._text_rect.text_color != color:
            self._text_rect.text_color = color
            self._handle_change()

    def _background_color_change_slot(self, color_str: str) -> None:
        background_color = QColor(color_str)
        if background_color != self._text_rect.background_color:
            self._text_rect.background_color = background_color
            self._handle_change()

    def _fill_background_change_slot(self, fill_background: bool) -> None:
        if fill_background != self._text_rect.fill_background:
            self._text_rect.fill_background = fill_background
            self._handle_change()

    def _get_boolean_change_handler(self, getter: Callable[[QFont], bool],
                                    setter: Callable[[QFont, bool], None]) -> Callable[[bool], None]:
        def _change_handler(new_value: bool) -> None:
            selected_font = self._text_rect.font
            if getter(selected_font) != new_value:
                setter(selected_font, new_value)
                self._text_rect.font = selected_font
                self._handle_change()
        return _change_handler

    def _alignment_change_slot(self, align_index: int) -> None:
        alignment = self._alignment_dropdown.itemData(align_index)
        assert isinstance(alignment, Qt.AlignmentFlag)
        if self._text_rect.text_alignment != alignment:
            self._text_rect.text_alignment = alignment
            self._handle_change()

    def _size_change_slot(self, size: int) -> None:
        selected_font = self._text_rect.font
        if self._size_type_dropdown.currentText() == OPTION_TEXT_POINT_SIZE_FORMAT:
            selected_font.setPointSize(size)
        else:
            selected_font.setPixelSize(size)
        self._text_rect.font = selected_font
        self._handle_change()

    def _stretch_change_slot(self, stretch: int) -> None:
        selected_font = self._text_rect.font
        if stretch != selected_font.stretch():
            selected_font.setStretch(stretch)
            self._text_rect.font = selected_font
            self._handle_change()

    def _size_format_change_slot(self, _) -> None:
        self._size_change_slot(self._size_slider.value())

    def _text_x_changed_slot(self, x_coordinate: int) -> None:
        text_bounds = self._text_rect.bounds
        if x_coordinate != text_bounds.x():
            text_bounds.moveLeft(x_coordinate)
            self._text_rect.bounds = text_bounds
            self._handle_change()

    def _text_y_changed_slot(self, y_coordinate: int) -> None:
        text_bounds = self._text_rect.bounds
        if y_coordinate != text_bounds.y():
            text_bounds.moveTop(y_coordinate)
            self._text_rect.bounds = text_bounds
            self._handle_change()

    def _text_width_changed_slot(self, width: int) -> None:
        text_bounds = self._text_rect.bounds
        if width != text_bounds.width():
            text_bounds.setWidth(width)
            self._text_rect.bounds = text_bounds
            self._handle_change()

    def _text_height_changed_slot(self, height: int) -> None:
        text_bounds = self._text_rect.bounds
        if height != text_bounds.width():
            text_bounds.setHeight(height)
            self._text_rect.bounds = text_bounds
            self._handle_change()
