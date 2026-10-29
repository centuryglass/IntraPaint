"""
Provides an interface for choosing between AI-generated changes to selected image content.

The selector is a view of the `GenerationSession`'s current batch: it shows the options, tracks which one has focus,
and turns clicks and keys into session calls. It never leaves the user on a page that holds only the original image:
while nothing has arrived it offers only Cancel, and a run that ends with nothing closes it.
"""
import logging
import math
import sys
import time
from typing import Callable, Optional, cast

from PySide6.QtCore import Qt, QRect, QSizeF, QRectF, QEvent, Signal, QPointF, QObject, QPoint, QVariantAnimation
from PySide6.QtGui import QImage, QResizeEvent, QPixmap, QWheelEvent, QMouseEvent, QKeyEvent, QPolygonF, \
    QSinglePointEvent, QAction
from PySide6.QtWidgets import QApplication, QMenu, QGraphicsItem, QWidget, QGraphicsPixmapItem, QVBoxLayout

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller.image_generation.apply_option import ApplyOutcome, ApplyResult
from src.controller.image_generation.generation_session import GenerationSession
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.ui.generated_option_view import GeneratedOptionView, ImageOption, OverlayState
from src.ui.generated_selector_bars import ButtonBarState, SelectorButtonBar, SelectorTopBar, VIEW_GRID, VIEW_SINGLE
from src.ui.graphics_items.outline import Outline
from src.ui.graphics_items.selection_outline import SelectionOutline
from src.ui.graphics_items.toast_message import ToastMessageItem
from src.ui.loading.loading_design import LoadingDesign
from src.ui.loading.loading_designs import default_loading_designs, pick_design
from src.ui.modal.modal_utils import open_image_file, SAVE_IMAGE_MODE, show_warning_dialog
from src.ui.widget.option_filmstrip import OptionFilmstrip, THUMB_SIZE
from src.util.shared_constants import TIMELAPSE_MODE_FLAG, EDIT_MODE_INPAINT
from src.util.validation import assert_valid_index
from src.util.visual.geometry_utils import get_scaled_placement
from src.util.visual.pil_image_utils import pil_image_scaling
from src.util.visual.text_drawing_utils import get_key_display_string

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.generated_image_selector'

logger = logging.getLogger(__name__)


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


BATCH_DETAILS = _tr('{mode}, {width} x {height}, {count} options')
READY_COUNT = _tr('{ready} of {total} ready')
READY_COUNT_WITH_PROGRESS = _tr('{ready} of {total} ready - {progress}')
REASON_NOT_INPAINTED = _tr('Only inpainted options have a selection.')
REASON_NO_SMALLER_CHANGE = _tr('Zoom to changes needs a selection smaller than the generation area.')

ORIGINAL_CONTENT_LABEL = _tr('Original image content')
LABEL_TEXT_IMAGE_OPTION = _tr('Option {index}')

MENU_ACTION_SELECT = _tr('Select this option')
MENU_ACTION_SAVE_TO_FILE = _tr('Save to new file')
MENU_ACTION_SEND_TO_NEW_LAYER = _tr('Send to new layer')

TOAST_MESSAGE_SAVED = _tr('Saved image option to {image_path}')
TOAST_MESSAGE_LAYER_CREATED = _tr('Created new layer "{layer_name}"')
TOAST_MESSAGE_SAVE_CANCELED = _tr('Cancelled saving image option to file.')

WARNING_TITLE_INSERT_FAILED = _tr('Failed to insert into layer "{layer_name}"')
WARNING_MESSAGE_1_LAYER_LOCKED = _tr('Changes were blocked because the layer is locked. ')
WARNING_MESSAGE_1_LAYER_HIDDEN = _tr('Changes were blocked because the layer is hidden. ')
WARNING_MESSAGE_1_NOT_IMAGE = _tr('The active layer is not an image layer, image content cannot be inserted. ')
WARNING_MESSAGE_2_CREATED_NEW = _tr('Image content was added as new layer "{new_layer_name}"')

VIEW_MARGIN = 6
IMAGE_MARGIN_FRACTION = 1 / 6
SCROLL_DEBOUNCE_MS = 100
FILMSTRIP_SMALL_THUMB_SIZE = 44
# Below this selector height, filmstrip thumbnails use the small size:
FILMSTRIP_SMALL_HEIGHT = 720


_MODIFIER_KEYS = {Qt.KeyboardModifier.AltModifier: Qt.Key.Key_Alt,
                  Qt.KeyboardModifier.ControlModifier: Qt.Key.Key_Control,
                  Qt.KeyboardModifier.ShiftModifier: Qt.Key.Key_Shift,
                  Qt.KeyboardModifier.MetaModifier: Qt.Key.Key_Meta}


class GeneratedImageSelector(QWidget):
    """Shows all images from an image generation operation, and lets the user use one, or close without choosing.

    The batches belong to the `GenerationSession`. Closing the selector stores the batch it showed if any images
    arrived, and `restore_previous_options` shows it again until another document is loaded. Callers pick the batch
    before showing the selector, with `start_new_options` or `restore_previous_options`, and call
    `finish_generation` when the run that fills it ends.

    One option always has focus. The primary button, Enter and the compare modifier act on it. The grid view shows
    every option, and the single view zooms to the focused one.
    """

    previous_options_available = Signal(bool)
    """Emitted when `can_restore_previous` changes."""

    def __init__(self,
                 image_stack: ImageStack,
                 session: GenerationSession,
                 close_selector: Callable,
                 loading_designs: Optional[tuple[LoadingDesign, ...]] = None) -> None:
        """Builds the selector around a session.

        `loading_designs` are the designs placeholder cells pick from, every design `default_loading_designs` finds by
        default.
        """
        super().__init__(None)
        self._image_stack = image_stack
        self._session = session
        # Scene items for the session's previous batch, by option index. Re-opening reuses them, because building an
        # item rescales its image.
        self._prev_option_items: list[ImageOption] = []
        session.previous_options_available.connect(self.previous_options_available)
        image_stack.document_changed.connect(self._on_document_changed)

        self._close_selector = close_selector
        self._option_items: list[ImageOption] = []
        self._outlines: list[Outline] = []
        self._selections: list[SelectionOutline] = []
        self._zoomed_in = False
        self._zoom_to_changes = AppConfig().get(AppConfig.SELECTION_SCREEN_ZOOMS_TO_CHANGED)
        self._zoom_index = 0
        self._hover_index: Optional[int] = None
        self._comparing = False
        self._progress_text = ''
        # The region "zoom to changes" zooms to in the batch showing, or None when it has none:
        self._change_bounds: Optional[QRect] = None
        self._last_scroll_time = time.time() * 1000
        self._toast_message: Optional[ToastMessageItem] = None

        self._base_option_offset = QPointF(0.0, 0.0)
        self._base_option_scale = 0.0
        self._option_scale_ratio = 1.0
        self._option_pos_offset = QPointF(0.0, 0.0)

        self._loading_designs = loading_designs if loading_designs is not None else default_loading_designs()
        self._loading_design = self._loading_designs[0]
        self._loading_phase = 0.0
        self._loading_animation = QVariantAnimation(self)
        self._loading_animation.setStartValue(0.0)
        self._loading_animation.setEndValue(1.0)
        self._loading_animation.setLoopCount(-1)
        self._loading_animation.valueChanged.connect(self._set_loading_phase)

        self._layout = QVBoxLayout(self)

        self._top_bar = SelectorTopBar(self)
        self._top_bar.view_mode_changed.connect(self._view_mode_changed)
        self._selection_outline_checkbox = self._top_bar.selection_outline_checkbox
        config = AppConfig()
        config.connect(self, AppConfig.SHOW_SELECTIONS_IN_GENERATION_OPTIONS, self.set_selection_outline_visibility)
        config.connect(self, AppConfig.SELECTION_SCREEN_ZOOMS_TO_CHANGED, self.zoom_to_changes)
        config.connect(self, AppConfig.SHOW_OPTIONS_FULL_RESOLUTION, self._set_full_resolution)
        self._layout.addWidget(self._top_bar)

        # Setup main option view widget:
        self._view = GeneratedOptionView()
        self._view.set_options(self._option_items)
        self._view.scale_changed.connect(self._scale_change_slot)
        self._view.offset_changed.connect(self._offset_change_slot)
        self._view.setMouseTracking(True)
        self._view.installEventFilter(self)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # Shows the original in place of the focused option while the compare modifier is held:
        self._compare_item = QGraphicsPixmapItem()
        self._compare_item.setVisible(False)
        scene = self._view.scene()
        assert scene is not None
        scene.addItem(self._compare_item)

        def _selection_scroll(dx, dy):
            if dx > 0:
                self._zoom_next()
            elif dx < 0:
                self._zoom_prev()
            if dy != 0 and (dy > 0) == self._zoomed_in:
                self.toggle_zoom(debounce=True)

        self._view.content_scrolled.connect(_selection_scroll)
        self._view.zoom_toggled.connect(self.toggle_zoom)
        self._layout.addWidget(self._view, stretch=255)

        self._filmstrip = OptionFilmstrip()
        self._filmstrip.option_clicked.connect(lambda idx: self._zoom_to_option(idx, True))
        self._filmstrip.hide()
        self._layout.addWidget(self._filmstrip)

        self._button_bar = SelectorButtonBar(self)
        self._button_bar.close_requested.connect(self._close)
        self._button_bar.stop_requested.connect(self.stop_generation)
        self._button_bar.previous_requested.connect(self._zoom_prev)
        self._button_bar.next_requested.connect(self._zoom_next)
        self._button_bar.send_requested.connect(lambda: self._send_to_new_layer(self._zoom_index))
        self._button_bar.save_requested.connect(lambda: self._save_to_file(self._zoom_index))
        self._button_bar.use_requested.connect(lambda: self._select_option_and_close(self._zoom_index))
        self._layout.addWidget(self._button_bar)

        key_config = KeyConfig()
        key_config.connect(self, KeyConfig.ZOOM_TOGGLE, self._update_controls)
        key_config.connect(self, KeyConfig.COMPARE_ORIGINAL_MODIFIER, self._update_controls)
        self.start_new_options()

    def _rebuild_scene(self, include_loading_images: bool, reused_items: Optional[list[ImageOption]] = None) -> None:
        """Rebuilds the view's scene items, view options and zoom state from the session's current batch.

        Parameters
        ----------
        include_loading_images : bool
            Whether to add placeholders up to the expected batch size.
        reused_items : list[ImageOption], optional
            Existing items for the batch's options, by index. An index without an item gets a new one.
        """
        # Clear old scene:
        scene = self._view.scene()
        assert scene is not None
        batch = self._session.current
        for scene_item_list in (self._selections, self._outlines, self._option_items):
            assert isinstance(scene_item_list, list)
            while len(scene_item_list) > 0:
                scene_item = scene_item_list.pop()
                self._remove_scene_item(scene_item)

        # Configure view options and change bounds from the batch's own generation context:
        self._change_bounds = batch.change_bounds if batch.edit_mode == EDIT_MODE_INPAINT else None
        self._update_view_options()

        # Add an item for each image the batch already holds. `add_image_option` would also append the image to the
        # batch, duplicating it.
        assert len(batch.option_images) > 0, 'option_data should always have an initial image!'
        for i, image in enumerate(batch.option_images):
            if reused_items is not None and i < len(reused_items):
                self._add_option_item(reused_items[i])
            else:
                label = ORIGINAL_CONTENT_LABEL if i == 0 else LABEL_TEXT_IMAGE_OPTION.format(index=i)
                self._add_option_item(ImageOption(image, label))

        if include_loading_images:
            cache = Cache()
            expected_count = cache.get(Cache.BATCH_SIZE) * cache.get(Cache.BATCH_COUNT)
            for i in range(len(self._option_items), expected_count + 1):
                self.add_image_option(batch.loading_image, i - 1)
            self._loading_design = pick_design(self._loading_designs, self._loading_design)
            self._loading_design.next_loop()
        self._progress_text = ''

        # Every showing starts on the full view of all options, focused on the original so the first step forward
        # opens option 1:
        self._zoom_index = 0
        self._hover_index = None
        self._set_comparing(False)
        self._clear_manual_view()
        self._zoomed_in = False
        self._apply_ideal_image_arrangement()
        if TIMELAPSE_MODE_FLAG in sys.argv:
            self._zoom_to_option(0)
        else:
            self._view.reset_scale()
        self._update_controls()

    def _remove_scene_item(self, scene_item: QGraphicsItem) -> None:
        scene = self._view.scene()
        assert scene is not None
        if isinstance(scene_item, SelectionOutline):
            scene_item.animated_outline = False
            scene_item.animated_fill = False
        if scene_item in scene.items():
            scene.removeItem(scene_item)

    def start_new_options(self, paste_mask: Optional[QImage] = None) -> None:
        """Begins a batch: captures the current image content and shows placeholders for the images to come.

        Inpainted options are clipped by paste_mask when they are applied, or by the selection if it is None.
        """
        self._session.begin(paste_mask)
        self._rebuild_scene(include_loading_images=True)

    def finish_generation(self) -> bool:
        """Ends the run that fills the batch showing: drops the placeholders no image arrived for.

        Returns whether any generated option arrived. When none did, the caller closes the selector and says why.
        """
        if not self._session.accepting_results:
            return True
        had_results = self._session.current.has_results()
        kept = self._session.finish_current()
        focused_item = self._option_items[self._zoom_index]
        removed = [i for i in range(len(self._option_items)) if i not in kept]
        for i in reversed(removed):
            for item_list in (self._option_items, self._outlines, self._selections):
                if i < len(item_list):
                    self._remove_scene_item(cast(list, item_list).pop(i))
        self._zoom_index = self._option_items.index(focused_item) if focused_item in self._option_items \
            else len(self._option_items) - 1
        self._hover_index = None
        self._progress_text = ''
        self._apply_ideal_image_arrangement()
        if self._zoomed_in:
            self._zoom_to_option(self._zoom_index, True)
        self._update_controls()
        return had_results

    def set_progress_text(self, text: str) -> None:
        """Shows a backend's progress text beside the ready count."""
        self._progress_text = text
        self._update_status_text()

    def stop_generation(self) -> None:
        """Asks the session to stop the running generation, keeping the options that arrived."""
        self._session.stop()
        self._update_controls()

    def archive_current_options(self) -> None:
        """Stores the batch that is showing for `restore_previous_options`, if any of its images arrived.

        Only the first call for each showing stores anything, so every path that closes the selector can call it.
        """
        # `_option_items` still matches the batch's images index for index until the placeholders are dropped:
        kept = self._session.archive_current()
        if kept is not None:
            self._prev_option_items = [self._option_items[i] for i in kept]

    def can_restore_previous(self) -> bool:
        """Returns whether a batch is stored and its generation area is still within the image."""
        return self._session.can_restore_previous()

    def restore_previous_options(self) -> None:
        """Shows the stored batch again."""
        batch = self._session.restore_previous()
        self._prev_option_items[0] = ImageOption(batch.option_images[0], ORIGINAL_CONTENT_LABEL)
        self._rebuild_scene(include_loading_images=False, reused_items=self._prev_option_items)

    def _on_document_changed(self) -> None:
        """Drops the scene items of the stored batch, which belongs to the replaced document."""
        self._prev_option_items = []

    def _close_and_archive(self) -> None:
        """Stores the batch that is showing, then closes the selector."""
        self._set_comparing(False)
        self.archive_current_options()
        self._close_selector()

    def _close(self) -> None:
        """Stops any generation still running, then closes without applying anything."""
        self._session.stop()
        self._close_and_archive()

    def _generating(self) -> bool:
        """Returns whether a run is still filling the batch showing."""
        return self._session.generating and self._session.accepting_results

    def _is_ready(self, option_index: int) -> bool:
        """Returns whether an option holds an image, not a loading placeholder."""
        batch = self._session.current
        return 0 <= option_index < len(batch.option_images) \
            and batch.option_images[option_index] is not batch.loading_image

    def _update_view_options(self) -> None:
        """Enables the view options that apply to the batch showing, and says why the others don't."""
        inpainted = self._session.current.edit_mode == EDIT_MODE_INPAINT
        zoom_reason = REASON_NOT_INPAINTED if not inpainted \
            else (REASON_NO_SMALLER_CHANGE if self._change_bounds is None else '')
        selection_reason = '' if inpainted else REASON_NOT_INPAINTED
        self._top_bar.set_option_reasons(selection_reason, zoom_reason)

    def _update_status_text(self) -> None:
        batch = self._session.current
        if self._generating():
            total = len(self._option_items) - 1
            ready = sum(1 for i in range(1, len(self._option_items)) if self._is_ready(i))
            if self._progress_text != '':
                text = READY_COUNT_WITH_PROGRESS.format(ready=ready, total=total, progress=self._progress_text)
            else:
                text = READY_COUNT.format(ready=ready, total=total)
        else:
            text = BATCH_DETAILS.format(mode=Cache().get_option_display(batch.edit_mode),
                                        width=batch.generation_area.width(), height=batch.generation_area.height(),
                                        count=len(self._option_items) - 1)
        self._top_bar.set_status(text)

    def _update_controls(self) -> None:
        """Updates the buttons, status text, hints and filmstrip for the batch, run state and focused option."""
        if len(self._option_items) == 0:
            return
        self._button_bar.set_state(ButtonBarState(generating=self._generating(),
                                                  has_results=self._session.current.has_results(),
                                                  stopped=self._session.stopped,
                                                  focus_index=self._zoom_index,
                                                  focus_ready=self._is_ready(self._zoom_index),
                                                  option_count=len(self._option_items),
                                                  single_view=self._zoomed_in))
        self._top_bar.set_view_mode(VIEW_SINGLE if self._zoomed_in else VIEW_GRID)
        self._update_status_text()
        self._filmstrip.setVisible(self._zoomed_in)
        self._filmstrip.set_options([item.image for item in self._option_items],
                                    [self._is_ready(i) for i in range(len(self._option_items))], self._zoom_index)
        if any(not self._is_ready(i) for i in range(len(self._option_items))):
            if not AppConfig().get(AppConfig.STATIC_LOADING_INDICATOR):
                self._loading_animation.setDuration(self._loading_design.duration_ms)
                if self._loading_animation.state() != QVariantAnimation.State.Running:
                    self._loading_animation.start()
            else:
                self._loading_phase = self._loading_design.rest_phase
        else:
            self._loading_animation.stop()
        self._fit_bars()
        self._update_overlay()

    def _fit_bars(self) -> None:
        """Folds bar controls into popovers and menus when the selector is too narrow for them."""
        margins = self._layout.contentsMargins()
        width = self.width() - margins.left() - margins.right()
        self._button_bar.fit(width)
        self._top_bar.fit(width)
        small = self.height() < FILMSTRIP_SMALL_HEIGHT
        self._filmstrip.set_thumb_size(FILMSTRIP_SMALL_THUMB_SIZE if small else THUMB_SIZE)

    def _add_option_selection_outline(self, idx: int) -> None:
        if len(self._option_items) <= idx:
            raise IndexError(f'Invalid option index {idx}')
        if len(self._selections) != idx:
            raise RuntimeError(f'Generating selection outline {idx}, unexpected outline count {len(self._selections)}'
                               f' found.')
        selection_crop = QPolygonF(QRectF(self._session.current.generation_area))
        origin = self._session.current.generation_area.topLeft()
        selection_polys = (poly.intersected(selection_crop).translated(-origin.x(), -origin.y())
                           for poly in self._session.current.selection_polys)
        polys = [QPolygonF(poly) for poly in selection_polys]
        outline = SelectionOutline(self._view, polys)
        outline.show_overlay = False
        outline.setScale(self._image_stack.width / self._session.current.generation_area.width())
        outline.setVisible(AppConfig().get(AppConfig.SHOW_SELECTIONS_IN_GENERATION_OPTIONS))
        self._selections.append(outline)

    def _add_option_item(self, new_option: ImageOption) -> None:
        """Adds an option's item to the end of the scene's option list, with its outlines."""
        scene = self._view.scene()
        assert scene is not None, 'Scene should have been created automatically and never cleared'
        new_option.setOpacity(1.0)
        new_option.refresh_pixmap()
        scene.addItem(new_option)
        self._option_items.append(new_option)
        idx = len(self._option_items) - 1
        # Add selections if the batch was inpainted:
        if self._session.current.edit_mode == EDIT_MODE_INPAINT:
            self._add_option_selection_outline(idx)
        assert len(self._outlines) == len(self._option_items) - 1
        self._outlines.append(Outline(scene, self._view))
        self._outlines[idx].outlined_region = self._option_items[idx].bounds

    def add_image_option(self, image: QImage, idx: int) -> None:
        """Add an image to the list of generated image options."""
        if not self._session.accepting_results:
            # A re-opened batch has no placeholders, so this is a late result from an earlier run.
            logger.info(f'Ignored image option {idx}: the batch showing was re-opened')
            return
        if not 0 <= idx < len(self._option_items):
            raise IndexError(f'invalid index {idx}, max is {len(self._option_items)}')
        idx += 1  # Original image gets index zero
        assert len(self._session.current.option_images) == len(self._option_items)
        self._session.add_image(image, idx - 1)
        if idx == len(self._option_items):
            self._add_option_item(ImageOption(image, LABEL_TEXT_IMAGE_OPTION.format(index=idx)))
        else:
            self._option_items[idx].image = image
            self._outlines[idx].outlined_region = self._option_items[idx].bounds
        self._apply_ideal_image_arrangement()
        self._update_controls()

    def toggle_zoom(self, zoom_index: Optional[int] = None, debounce: bool = False) -> None:
        """Toggle between the single view of the focused option and the grid of all of them.

        With `debounce`, a return to the grid soon after the last step is ignored, so a held key or a scroll gesture
        doesn't undo the step it made.
        """
        if zoom_index is not None:
            self._zoom_index = zoom_index
        if self._zoomed_in and debounce and not self._scroll_debounce_finished():
            return
        self._zoomed_in = not self._zoomed_in
        if self._zoomed_in:
            self._zoom_to_option(self._zoom_index, True)
        else:
            self._set_comparing(False)
            self._view.reset_scale()
            self._clear_manual_view()
            for option in self._option_items:
                option.setOpacity(1.0)
        self.resizeEvent(None)
        self._update_controls()

    def _view_mode_changed(self, value: str) -> None:
        if (value == VIEW_SINGLE) != self._zoomed_in:
            self.toggle_zoom()

    def zoom_to_changes(self, should_zoom: bool) -> None:
        """Zoom in to the updated area when inpainting small sections."""
        self._zoom_to_changes = should_zoom
        self._clear_manual_view()
        if self._zoom_to_changes:
            if not self._zoomed_in:
                self.toggle_zoom()
            self._zoom_to_option(self._zoom_index, True)
        elif self._zoomed_in:
            self._zoom_to_option(self._zoom_index, True)

    def set_selection_outline_visibility(self, show_selections: bool) -> None:
        """Set whether selection outlines are drawn."""
        for selection_outline in self._selections:
            selection_outline.setVisible(show_selections)

    def _set_full_resolution(self, _full_resolution: bool) -> None:
        """Re-renders the options at the resolution `AppConfig.SHOW_OPTIONS_FULL_RESOLUTION` picks."""
        for item in self._option_items:
            item.refresh_pixmap()
        self._set_comparing(False)
        self.resizeEvent(None)

    def resizeEvent(self, unused_event: Optional[QResizeEvent]):
        """Recalculate all bounds on resize and update view scale."""
        self._apply_ideal_image_arrangement()
        if self._zoomed_in:
            self._zoom_to_option(self._zoom_index, True)
        self._fit_bars()

    def _update_overlay(self) -> None:
        """Passes the focus, hover, compare and loading state to the view's overlays."""
        count = len(self._option_items)
        ready = [self._is_ready(i) for i in range(count)]
        # A placeholder generates while its backend batch is the first one with unfilled options:
        batch_size = max(Cache().get(Cache.BATCH_SIZE), 1)
        waiting = [i for i in range(1, count) if not ready[i]]
        running_batch = (waiting[0] - 1) // batch_size if waiting and self._generating() and not self._session.stopped \
            else None
        generating = [not ready[i] and i > 0 and (i - 1) // batch_size == running_batch for i in range(count)]
        compare_key = get_key_display_string(KeyConfig().get(KeyConfig.COMPARE_ORIGINAL_MODIFIER), rich_text=False)
        self._view.set_overlay_state(OverlayState(focus_index=self._zoom_index, single_view=self._zoomed_in,
                                                  hover_index=self._hover_index, comparing=self._comparing,
                                                  ready=ready, generating=generating, compare_key=compare_key,
                                                  loading_design=self._loading_design,
                                                  loading_phase=self._loading_phase,
                                                  margin_fraction=IMAGE_MARGIN_FRACTION))

    def _set_loading_phase(self, phase: float) -> None:
        if phase < self._loading_phase:
            self._loading_design.next_loop()
        self._loading_phase = phase
        self._update_overlay()

    def _set_comparing(self, comparing: bool) -> None:
        """Shows or hides the original in place of the focused option. Only the single view compares."""
        comparing = comparing and self._zoomed_in and 0 < self._zoom_index < len(self._option_items)
        if comparing == self._comparing and not comparing:
            return
        self._comparing = comparing
        if comparing:
            focused = self._option_items[self._zoom_index]
            original = self._option_items[0]
            pixmap = original.pixmap()
            if pixmap.size() != focused.size:
                pixmap = QPixmap.fromImage(pil_image_scaling(original.image, focused.size))
            self._compare_item.setPixmap(pixmap)
            self._compare_item.setPos(focused.pos())
            self._compare_item.setZValue(focused.zValue() + 0.5)
        self._compare_item.setVisible(comparing)
        self._update_overlay()

    def _show_context_menu(self, idx: int, pos: QPoint) -> None:
        menu = QMenu()
        menu.setTitle(ORIGINAL_CONTENT_LABEL if idx == 0 else LABEL_TEXT_IMAGE_OPTION.format(index=idx))

        def _add_action(name: str, action_callback: Callable[..., None]) -> QAction:
            action = menu.addAction(name)
            assert action is not None
            action.triggered.connect(action_callback)
            return action
        _add_action(MENU_ACTION_SELECT, lambda: self._select_option_and_close(idx))
        _add_action(MENU_ACTION_SAVE_TO_FILE, lambda: self._save_to_file(idx))
        _add_action(MENU_ACTION_SEND_TO_NEW_LAYER, lambda: self._send_to_new_layer(idx))
        menu.exec(self.mapToGlobal(pos))

    def _save_to_file(self, idx: int) -> None:
        """Asks for a path and saves an option there, at its largest resolution."""
        if not self._is_ready(idx):
            return
        self.setUpdatesEnabled(False)
        save_path = open_image_file(self, SAVE_IMAGE_MODE)
        self.setUpdatesEnabled(True)
        if save_path is not None:
            self._session.save_to_file(idx, save_path)
            self._toast_message = ToastMessageItem(TOAST_MESSAGE_SAVED.format(image_path=save_path), self._view)
        else:
            self._toast_message = ToastMessageItem(TOAST_MESSAGE_SAVE_CANCELED, self._view)

    def _send_to_new_layer(self, idx: int) -> None:
        """Copies an option into a new layer, and keeps the selector open."""
        if not self._is_ready(idx):
            return
        new_layer = self._session.send_to_new_layer(idx, self._option_items[idx].text)
        self._toast_message = ToastMessageItem(TOAST_MESSAGE_LAYER_CREATED.format(layer_name=new_layer.name),
                                               self._view)

    def _compare_key_event(self, event: QKeyEvent) -> None:
        """Starts or stops comparing as the compare modifier is pressed or released."""
        modifier = KeyConfig().get_modifier(KeyConfig.COMPARE_ORIGINAL_MODIFIER)
        modifiers = modifier if isinstance(modifier, list) else [modifier]
        keys = [_MODIFIER_KEYS[mod] for mod in modifiers if mod in _MODIFIER_KEYS]
        if event.key() in keys:
            self._set_comparing(event.type() == QEvent.Type.KeyPress)
        elif event.type() == QEvent.Type.KeyPress:
            self._set_comparing(KeyConfig.modifier_held(KeyConfig.COMPARE_ORIGINAL_MODIFIER,
                                                        held_modifiers=event.modifiers()))

    def _option_at(self, view_pos: QPoint) -> Optional[int]:
        scene_pos = self._view.widget_point_to_scene(view_pos).toPoint()
        for i, option in enumerate(self._option_items):
            if option.bounds.contains(scene_pos):
                return i
        return None

    def eventFilter(self, source: Optional[QObject], event: Optional[QEvent]):
        """Use horizontal scroll to move through selections, select items when clicked."""
        assert event is not None
        if event.type() == QEvent.Type.Wheel:
            if source is not self._view:
                # The view already handled this event. An ignored wheel event bubbles up to the main window,
                # which installs this same filter; without this check it would step a second time.
                return False
            event = cast(QWheelEvent, event)
            if event.angleDelta().x() > 0:
                self._zoom_next()
            elif event.angleDelta().x() < 0:
                self._zoom_prev()
            return event.angleDelta().x() != 0
        if event.type() in (QEvent.Type.WindowDeactivate, QEvent.Type.FocusOut):
            self._set_comparing(False)
            return False
        if event.type() == QEvent.Type.KeyRelease:
            self._compare_key_event(cast(QKeyEvent, event))
            return False
        if event.type() == QEvent.Type.KeyPress:
            event = cast(QKeyEvent, event)
            self._compare_key_event(event)
            if event.key() == Qt.Key.Key_Escape:
                if self._zoomed_in:
                    self.toggle_zoom()
                else:
                    self._close()
            elif event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
                if self._is_ready(self._zoom_index):
                    self._select_option_and_close(self._zoom_index)
            else:
                try:
                    num_value = int(event.text())
                    if 0 <= num_value < len(self._option_items):
                        self._zoom_to_option(num_value, True)
                        return True
                    return False
                except ValueError:
                    return False
            return True
        if event.type() == QEvent.Type.MouseButtonPress:
            event = cast(QMouseEvent, event)
            if source == self._view:
                view_pos = event.pos()
            else:
                view_pos = QPoint(self._view.x() + event.pos().x(), self._view.y() + event.pos().y())
            self._view.set_cursor_pos(view_pos)
            if KeyConfig.modifier_held(KeyConfig.PAN_VIEW_MODIFIER):
                return False  # Ctrl+click is for panning, don't select options
            if event.button() not in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
                return False
            idx = self._option_at(view_pos)
            if idx is not None and self._is_ready(idx):
                if event.button() == Qt.MouseButton.LeftButton:
                    self._select_option_and_close(idx)
                elif event.button() == Qt.MouseButton.RightButton and source == self._view:
                    self._show_context_menu(idx, event.pos())
                event.accept()
        if event.type() in (QEvent.Type.Enter, QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease):
            event = cast(QSinglePointEvent, event)
            if source == self._view:
                view_pos = event.position().toPoint()
            else:
                view_pos = event.position().toPoint() + self._view.geometry().topLeft()
            self._view.set_cursor_pos(view_pos)
            if source == self._view:
                self._set_hover_index(self._option_at(view_pos))
            return False
        if event.type() == QEvent.Type.Leave:
            self._view.set_cursor_pos(None)
            if source == self._view:
                self._set_hover_index(None)
        return False

    def _set_hover_index(self, idx: Optional[int]) -> None:
        if idx != self._hover_index:
            self._hover_index = idx
            self._update_overlay()

    def _offset_change_slot(self, offset: QPointF) -> None:
        if not self._zoomed_in:
            return
        self._option_pos_offset = QPointF(offset) - QPointF(self._base_option_offset)

    def _scale_change_slot(self, scale: float) -> None:
        if not self._zoomed_in:
            return
        if self._base_option_scale > 0:
            self._option_scale_ratio = scale / self._base_option_scale

    def _clear_manual_view(self) -> None:
        """Discards the manual pan and zoom, which are only meaningful in the frame they were made in."""
        self._option_pos_offset = QPointF(0.0, 0.0)
        self._option_scale_ratio = 1.0

    def _warn_if_blocked(self, outcome: ApplyOutcome, requested_layer: Layer, new_layer_name: str) -> None:
        """Warns that an option went to a new layer because `requested_layer` couldn't take it."""
        if outcome.result is ApplyResult.APPLIED:
            return
        warning_message = {ApplyResult.BLOCKED_NOT_IMAGE_LAYER: WARNING_MESSAGE_1_NOT_IMAGE,
                           ApplyResult.BLOCKED_LOCKED: WARNING_MESSAGE_1_LAYER_LOCKED,
                           ApplyResult.BLOCKED_HIDDEN: WARNING_MESSAGE_1_LAYER_HIDDEN}[outcome.result]
        warning_message += WARNING_MESSAGE_2_CREATED_NEW.format(new_layer_name=new_layer_name)
        show_warning_dialog(None, WARNING_TITLE_INSERT_FAILED.format(layer_name=requested_layer.name),
                            warning_message, AppConfig.WARN_WHEN_LOCK_FORCES_LAYER_CREATE)

    def _select_option_and_close(self, option_index: int) -> None:
        """Insert the selection and close this selector. A generation still running stops first."""
        self._session.stop()
        requested_layer = self._image_stack.active_layer
        new_layer_name = self._option_items[option_index].text
        outcome = self._session.choose(option_index, new_layer_name)
        if outcome is not None:
            self._warn_if_blocked(outcome, requested_layer, new_layer_name)
        self._close_and_archive()

    def _scroll_debounce_finished(self) -> bool:
        ms_time = time.time() * 1000
        if ms_time > self._last_scroll_time + SCROLL_DEBOUNCE_MS:
            self._last_scroll_time = ms_time
            return True
        return False

    def _zoom_to_option(self, option_index: Optional[int] = None, ignore_debounce: bool = False) -> None:
        assert_valid_index(option_index, self._option_items)
        if not ignore_debounce and not self._scroll_debounce_finished():
            return
        if not self._zoomed_in:
            self._zoomed_in = True
        if option_index is not None:
            self._zoom_index = option_index
        self._view.scale_changed.disconnect(self._scale_change_slot)
        self._view.offset_changed.disconnect(self._offset_change_slot)
        if self._zoom_to_changes and self._change_bounds is not None:
            bounds = QRect(self._change_bounds)
            offset = self._option_items[self._zoom_index].bounds.topLeft()
            bounds.translate(offset.x(), offset.y())
        else:
            bounds = self._option_items[self._zoom_index].bounds
        self._view.zoom_to_bounds(bounds)
        self._base_option_offset = self._view.offset
        self._base_option_scale = self._view.scene_scale
        self._view.offset = self._base_option_offset + self._option_pos_offset
        self._view.scale_without_fixed_scene_point(self._base_option_scale * self._option_scale_ratio)
        if not self._view.visible_scene_bounds.intersects(QRectF(bounds)):
            # The carried-over pan/zoom leaves the new option entirely off-screen: discard it instead.
            self._clear_manual_view()
            self._view.offset = self._base_option_offset
            self._view.scale_without_fixed_scene_point(self._base_option_scale)
        self._view.scale_changed.connect(self._scale_change_slot)
        self._view.offset_changed.connect(self._offset_change_slot)
        for i, option in enumerate(self._option_items):
            option.setOpacity(1.0 if not self._zoomed_in or i == self._zoom_index else 0.5)
        # A held compare modifier keeps comparing on the newly focused option:
        self._set_comparing(KeyConfig.modifier_held(KeyConfig.COMPARE_ORIGINAL_MODIFIER))
        self._update_controls()

    def _zoom_prev(self):
        idx = len(self._option_items) - 1 if self._zoom_index <= 0 else self._zoom_index - 1
        self._zoom_to_option(idx)

    def _zoom_next(self):
        idx = 0 if self._zoom_index >= len(self._option_items) - 1 else self._zoom_index + 1
        self._zoom_to_option(idx)

    def _apply_ideal_image_arrangement(self) -> None:
        """Arrange options in a grid within the scene, choosing grid dimensions to maximize use of available space."""
        if len(self._option_items) == 0:
            return
        view_width = self._view.size().width()
        view_height = self._view.size().height()
        # All options should have matching sizes:
        image_size = self._option_items[0].size
        option_count = len(self._option_items)
        image_margin = int(min(image_size.width(), image_size.height()) * IMAGE_MARGIN_FRACTION)

        def get_scale_factor_for_row_count(row_count: int):
            """Returns the largest image scale multiplier possible to fit images within row_count rows."""
            column_count = math.ceil(option_count / row_count)
            img_bounds = QRect(0, 0, view_width // column_count, view_height // row_count)
            img_rect = get_scaled_placement(img_bounds, image_size, image_margin)
            return img_rect.width() / image_size.width()

        num_rows = 1
        best_scale = 0
        for i in range(1, option_count + 1):
            scale = get_scale_factor_for_row_count(i)
            last_scale = scale
            if scale > best_scale:
                best_scale = scale
                num_rows = i
            elif scale < last_scale:
                break
        num_columns = math.ceil(option_count / num_rows)
        scene_size = QSizeF(num_columns * (image_size.width() + image_margin) - image_margin + VIEW_MARGIN * 2,
                            num_rows * (image_size.height() + image_margin) - image_margin + VIEW_MARGIN * 2)
        view_ratio = self._view.width() / max(self._view.height(), 1)
        scene_ratio = scene_size.width() / scene_size.height()
        scene_x0 = VIEW_MARGIN
        scene_y0 = VIEW_MARGIN
        if scene_ratio < view_ratio:
            new_width = int(view_ratio * scene_size.height())
            scene_x0 += int((new_width - scene_size.width()) / 2)
            scene_size.setWidth(new_width)
        elif scene_ratio > view_ratio:
            new_height = scene_size.width() // view_ratio
            scene_y0 += int((new_height - scene_size.height()) / 2)
            scene_size.setHeight(new_height)

        self._view.content_size = scene_size.toSize()
        for idx in range(option_count):
            row = idx // num_columns
            col = idx % num_columns
            x = scene_x0 + (image_size.width() + image_margin) * col
            y = scene_y0 + (image_size.height() + image_margin) * row
            self._option_items[idx].setPos(x, y)
            self._outlines[idx].outlined_region = self._option_items[idx].bounds
            if len(self._selections) > idx:
                selection = self._selections[idx]
                selection.setZValue(self._option_items[idx].zValue() + 1)
                scale = self._option_items[idx].bounds.width() / self._session.current.generation_area.width()
                selection.setScale(scale)
                selection.move_to(QPointF(x / selection.scale(), y / selection.scale()))
        if self._comparing:
            self._compare_item.setPos(self._option_items[self._zoom_index].pos())
