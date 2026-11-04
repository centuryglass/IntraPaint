"""Base template for tools that use a MyPaint surface within an image layer."""
import datetime
import logging
import math
from typing import Optional, Callable

from PySide6.QtCore import Qt, QPoint, QLineF, QPointF, QEvent, QRect
from PySide6.QtGui import QCursor, QTabletEvent, QMouseEvent, QColor, QIcon, QWheelEvent, QPointingDevice
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig, BRUSH_OPACITY_PRESETS
from src.hotkey_filter import HotkeyFilter
from src.image.brush.layer_brush import LayerBrush
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.tools.base_tool import BaseTool
from src.ui.brush_crosshair import CROSSHAIR_GRID_SIZE, CrosshairVariant, crosshair_cursor
from src.ui.graphics_items.brush_outline import BrushOutline
from src.ui.graphics_items.temp_dashed_line_item import TempDashedLineItem
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.stroke_block import StrokeToolPanel
from src.util.visual.geometry_utils import closest_point_keeping_angle, closest_point_at_angle_option
from src.util.visual.text_drawing_utils import left_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.brush_tool'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


LINE_HINT = _tr('{modifier_or_modifiers}+{left_mouse_icon}: draw line')
FIXED_ANGLE_HINT = _tr('{modifier_or_modifiers}: fixed angle')

# The brush outline hides at or below this on-screen diameter, where the crosshair alone marks the brush:
MIN_OUTLINE_DIAMETER = CROSSHAIR_GRID_SIZE
MIN_LINE_PRESSURE = 0.5


def brush_size_step(size: int) -> int:
    """Returns how much one size step changes a brush of `size` pixels: 1 for small brushes, a tenth of the size for
       larger ones."""
    return max(1, size // 10)

logger = logging.getLogger(__name__)


class BrushTool(BaseTool):
    """Base template for tools that use a LayerBrush to edit an image layer using drawing commands.

    BrushTool handles the connection between a layer and a LayerBrush, and the process of passing inputs to
    that brush. Implementations are responsible for providing their own control panel and configuring brush properties.
    """

    def __init__(self, activation_config_key: str,  label_text: str, tooltip_text: str, icon: QIcon,
                 image_stack: ImageStack, image_viewer: ImageViewer, brush: LayerBrush,
                 enable_selection_restrictions=True, follow_active_layer=True) -> None:
        super().__init__(activation_config_key, label_text, tooltip_text, icon, enable_selection_restrictions)
        self._layer: Optional[ImageLayer] = None
        self._drawing = False
        self._tablet_pressure: Optional[float] = None
        self._last_pressure: Optional[float] = None
        self._tablet_x_tilt: Optional[float] = None
        self._tablet_y_tilt: Optional[float] = None
        self._tablet_input: Optional[QPointingDevice.PointerType] = None
        self._tablet_event_timestamp = 0.0
        self._pressure_curve: list[float] = AppConfig().get(AppConfig.TABLET_PRESSURE_CURVE)

        def _update_pressure_curve(new_curve: list[float]) -> None:
            self._pressure_curve = new_curve
        AppConfig().connect(self, AppConfig.TABLET_PRESSURE_CURVE, _update_pressure_curve)

        self._last_pos: Optional[QPoint] = None
        self._fixed_angle: Optional[int] = None
        # Set while a fixed angle modifier held at the stroke's press has another meaning there:
        self._fixed_angle_suppressed = False
        scene = image_viewer.scene()
        assert scene is not None
        self._preview_line = TempDashedLineItem(scene)

        self._crosshair_variant = CrosshairVariant.PLAIN
        self._outline = BrushOutline(scene)

        self._image_stack = image_stack
        self._image_viewer = image_viewer
        image_viewer.view_changed.connect(self.update_brush_cursor)
        image_viewer.cursor_moved.connect(self._cursor_moved_slot)
        self._brush = brush

        for key, sign in ((KeyConfig.BRUSH_SIZE_DECREASE, -1), (KeyConfig.BRUSH_SIZE_INCREASE, 1)):
            def _size_change(steps=sign) -> bool:
                if not self.is_active:
                    return False
                self.adjust_brush_size(steps)
                return True

            binding_id = f'BrushTool_{id(self)}_{key}'
            HotkeyFilter.instance().register_config_keybinding(binding_id, _size_change, key)

        if enable_selection_restrictions:
            # Handle restricting changes to selection:
            def _set_restricted_to_selection(selected_only: bool) -> None:
                if not self.is_active or self._layer is None or self._layer == image_stack.selection_layer:
                    return
                if selected_only:
                    mask = image_stack.get_layer_selection_mask(self._layer)
                    self._brush.set_input_mask(mask)
                else:
                    self._brush.set_input_mask(None)

            Cache().connect(self, Cache.PAINT_SELECTION_ONLY, _set_restricted_to_selection)

        if follow_active_layer:
            # noinspection PyUnusedLocal
            def _selection_layer_update(*_args) -> None:
                if not Cache().get(Cache.PAINT_SELECTION_ONLY) or not self.is_active or self._layer is None \
                        or self._layer == image_stack.selection_layer:
                    return
                assert self._layer is not None
                mask = image_stack.get_layer_selection_mask(self._layer)
                self._brush.set_input_mask(mask)

            image_stack.selection_layer.content_changed.connect(_selection_layer_update)

            image_stack.active_layer_changed.connect(self._active_layer_change_slot)
            self.layer = image_stack.active_layer
        HotkeyFilter.instance().modifiers_changed.connect(self._modifier_change_slot)

    @staticmethod
    def brush_control_hints() -> str:
        """Get control hints for line and fixed angle modes, if enabled."""
        line_hint = LINE_HINT.format(left_mouse_icon=left_button_hint_text(),
                                     modifier_or_modifiers='{modifier_or_modifiers}')
        return (f'{BaseTool.modifier_hint(KeyConfig.LINE_MODIFIER, line_hint)}'
                f' - {BaseTool.modifier_hint(KeyConfig.FIXED_ANGLE_MODIFIER, FIXED_ANGLE_HINT)}')

    @property
    def crosshair_variant(self) -> CrosshairVariant:
        """Returns the crosshair design the tool's cursor uses."""
        return self._crosshair_variant

    @crosshair_variant.setter
    def crosshair_variant(self, variant: CrosshairVariant) -> None:
        self._crosshair_variant = variant
        if self.is_active:
            self._apply_crosshair()

    @property
    def brush_outline(self) -> BrushOutline:
        """Returns the scene item that shows the brush's footprint under the cursor."""
        return self._outline

    def _apply_crosshair(self) -> None:
        cursor = crosshair_cursor(self._crosshair_variant, self._image_viewer.devicePixelRatioF())
        if cursor is not self.cursor:
            self.cursor = cursor

    def set_disabled_cursor(self, use_disabled_cursor: bool) -> None:
        """Sets or removes the disabled cursor, hiding the brush outline while it shows."""
        super().set_disabled_cursor(use_disabled_cursor)
        self.update_brush_cursor()

    @property
    def layer(self) -> Optional[ImageLayer]:
        """Returns the active image layer."""
        return self._layer

    @layer.setter
    def layer(self, layer: Optional[ImageLayer]) -> None:
        """Sets or clears the connected image layer."""
        if self._layer is not None:
            self._layer.lock_changed.disconnect(self._layer_lock_slot)
        if not isinstance(layer, ImageLayer):
            layer = None
        self._layer = layer
        if layer is not None:
            layer.lock_changed.connect(self._layer_lock_slot)
            self._layer_lock_slot(layer, layer.locked or layer.parent_locked)
            if layer != self._image_stack.selection_layer and Cache().get(Cache.PAINT_SELECTION_ONLY):
                mask = self._image_stack.get_layer_selection_mask(layer)
                self._brush.set_input_mask(mask)
            else:
                self._brush.set_input_mask(None)
        if not self._active:
            return
        if layer is None or not isinstance(layer, ImageLayer):
            self._brush.connect_to_layer(None)
        else:
            self._brush.connect_to_layer(layer)
        control_panel = self.get_control_panel()
        should_enable = (layer is not None and isinstance(layer, ImageLayer) and not layer.locked
                         and not layer.parent_locked and layer.shown)
        if control_panel is not None:
            control_panel.setEnabled(should_enable)
        self.set_disabled_cursor(not should_enable)

    @property
    def brush(self) -> LayerBrush:
        """Access the tool's edited brush."""
        return self._brush

    def _layer_lock_slot(self, layer: ImageLayer, locked: bool) -> None:
        if not self.is_active:
            return
        assert self._layer is not None
        assert layer == self._layer or (isinstance(layer, LayerGroup) and layer.contains_recursive(self._layer))
        control_panel = self.get_control_panel()
        if control_panel is not None:
            control_panel.setEnabled(not locked)
        self.set_disabled_cursor(locked)

    @property
    def brush_size(self) -> int:
        """Gets the active brush size."""
        return self._brush.brush_size

    @brush_size.setter
    def brush_size(self, new_size: int):
        """Updates the active brush size."""
        self.set_brush_size(new_size)
        self.update_brush_cursor()

    def adjust_brush_size(self, steps: int) -> None:
        """Changes the brush size by some number of size steps, each of `brush_size_step` pixels."""
        size = self._brush.brush_size
        self.set_brush_size(max(size + steps * brush_size_step(size), 1))

    def _bind_opacity_preset_keys(self, set_opacity: Callable[[float], None]) -> None:
        """Binds the keys that set the opacity directly, active while this tool's controls are enabled and the canvas
           is showing."""
        def _preset(opacity: float) -> bool:
            control_panel = self.get_control_panel()  # pylint: disable=assignment-from-none  # Subclasses override it.
            if not self.is_active or control_panel is None or not control_panel.isEnabled() \
                    or not self._image_viewer.isVisible():
                return False
            set_opacity(opacity)
            return True
        for config_key, preset_opacity in BRUSH_OPACITY_PRESETS.items():
            HotkeyFilter.instance().register_config_keybinding(f'BrushTool_{id(self)}_{config_key}',
                                                               lambda value=preset_opacity: _preset(value), config_key)

    def set_brush_size(self, new_size: int) -> None:
        """Update the brush size."""
        self._brush.brush_size = max(new_size, 1)
        self.update_brush_cursor()

    @property
    def brush_color(self) -> QColor:
        """Gets the active brush color."""
        return self._brush.brush_color

    @brush_color.setter
    def brush_color(self, new_color: QColor | Qt.GlobalColor) -> None:
        """Updates the active brush color."""
        self._brush.brush_color = QColor(new_color)

    def _on_activate(self, restoring_after_delegation=False) -> None:
        """Connect the brush to the active layer."""
        if self._layer is not None:
            self.layer = self._layer  # Re-apply the connection
        else:
            self.layer = self._image_stack.active_layer
        self._apply_crosshair()
        self.update_brush_cursor()

    def _on_deactivate(self) -> None:
        """Disconnect from the image when the tool is inactive."""
        if self._drawing:
            self._drawing = False
            self._brush.end_stroke()
            self._after_stroke_end()
            self._tablet_input = None
            self._tablet_pressure = None
            self._tablet_x_tilt = None
            self._tablet_y_tilt = None
        self._preview_line.setVisible(False)
        self._outline.setVisible(False)
        self._brush.connect_to_layer(None)

    # Event handlers:
    def _stroke_to(self, image_coordinates: QPoint) -> None:
        """Draws coordinates with the brush, including tablet data if available."""
        if datetime.datetime.now().timestamp() > self._tablet_event_timestamp + 0.5:  # discard outdated tablet events
            self._tablet_input = None
            self._tablet_pressure = None
            self._tablet_x_tilt = None
            self._tablet_y_tilt = None
        if self._layer is not None:
            layer_coordinates = self._layer.map_from_image(image_coordinates)
        else:
            return
        if not self._image_stack.has_image:
            return
        if self._tablet_input == QPointingDevice.PointerType.Eraser:
            self._brush.eraser = True

        if self._fixed_angle_active() and self._last_pos is not None and self._last_pos != image_coordinates:
            last_pos = QPointF(self._last_pos)
            current_pos = QPointF(image_coordinates)
            if self._fixed_angle is None:
                closest_point_f, fixed_angle = closest_point_at_angle_option(last_pos, current_pos,
                                                                             list(range(0, 360, 45)))
                self._fixed_angle = round(fixed_angle)
                closest_point = closest_point_f.toPoint()
            else:
                closest_point = closest_point_keeping_angle(last_pos, current_pos, self._fixed_angle).toPoint()
            image_coordinates = closest_point
            layer_coordinates = self._layer.map_from_image(image_coordinates)
        if KeyConfig.modifier_held(KeyConfig.LINE_MODIFIER) and self._last_pos is not None:
            last_layer_coordinates = self._layer.map_from_image(self._last_pos)
            pressure = self._last_pressure if self._tablet_pressure is None else self._tablet_pressure
            if pressure is not None:
                pressure = max(pressure, MIN_LINE_PRESSURE)
            self._brush.stroke_to(last_layer_coordinates.x(), last_layer_coordinates.y(), pressure,
                                  self._tablet_x_tilt, self._tablet_y_tilt)
            self._brush.stroke_to(layer_coordinates.x(), layer_coordinates.y(), pressure,
                                  self._tablet_x_tilt, self._tablet_y_tilt)
            self._preview_line.setVisible(False)  # Hide it until it can update with new last_pos value
        else:
            self._brush.stroke_to(layer_coordinates.x(), layer_coordinates.y(), self._tablet_pressure,
                                  self._tablet_x_tilt, self._tablet_y_tilt)

        if self._tablet_input == QPointingDevice.PointerType.Eraser:
            self._brush.eraser = False
        self._last_pos = image_coordinates

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Starts drawing when the mouse is clicked in the scene."""
        if event is None or event.buttons() != Qt.MouseButton.LeftButton or not self._image_stack.has_image \
                or not self.validate_layer(self._layer, image_stack=self._image_stack):
            return False
        if self._drawing:
            self._brush.end_stroke()
        self._drawing = True
        self._fixed_angle = None
        self._last_pressure = None
        self._fixed_angle_suppressed = self._press_claims_fixed_angle_modifier()
        if self._fixed_angle_active() and not KeyConfig.modifier_held(KeyConfig.LINE_MODIFIER):
            self._last_pos = image_coordinates  # Update so previous clicks don't constrain the angle
        self._before_stroke_start()
        self._brush.start_stroke()
        self._stroke_to(image_coordinates)
        return True

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Receives a mouse move event, returning whether the tool consumed the event."""
        if self._layer is None or event is None or not self._image_stack.has_image:
            return False

        if KeyConfig.modifier_held(KeyConfig.LINE_MODIFIER) and self._last_pos is not None:
            self._preview_line.setVisible(True)
            line_end = QPointF(image_coordinates)
            if KeyConfig.modifier_held(KeyConfig.FIXED_ANGLE_MODIFIER):

                line_end, _ = closest_point_at_angle_option(QPointF(self._last_pos), line_end,
                                                            list(range(0, 360, 45)))
            half_px_offset = QPointF(0.5, 0.5)  # Draw from the center of the pixel, not the corner.
            self._preview_line.set_line(QLineF(QPointF(self._last_pos) + half_px_offset, line_end + half_px_offset))
        if event.buttons() == Qt.MouseButton.LeftButton:
            self._stroke_to(image_coordinates)
            return True
        return False

    def mouse_release(self, event: Optional[QMouseEvent], _image_coordinates: QPoint) -> bool:
        """Receives a mouse release event, returning whether the tool consumed the event."""
        if self._layer is None or event is None or not self._image_stack.has_image:
            return False
        if self._drawing:
            self._drawing = False
            self._brush.end_stroke()
            self._after_stroke_end()
            self._tablet_input = None
            self._tablet_pressure = None
            self._last_pressure = None
            self._tablet_x_tilt = None
            self._tablet_y_tilt = None
            return True
        return False

    def _fixed_angle_active(self) -> bool:
        """Returns whether the fixed angle modifier constrains the stroke: it is held, and if it was held at the press
           with another meaning, it has been released and pressed again since."""
        if not KeyConfig.modifier_held(KeyConfig.FIXED_ANGLE_MODIFIER):
            self._fixed_angle_suppressed = False
            return False
        return not self._fixed_angle_suppressed

    def _press_claims_fixed_angle_modifier(self) -> bool:
        """Returns whether the modifiers held at a stroke's press give the fixed angle modifier another meaning, so it
           constrains the stroke only once released and pressed again. Subclasses override this."""
        return False

    def _before_stroke_start(self) -> None:
        """Called once the stroke is allowed to start, before the brush begins it. Subclasses can prepare the layer."""

    def _after_stroke_end(self) -> None:
        """Called after the brush has drawn the last of a stroke. Subclasses can finish what
           `_before_stroke_start` set up."""

    def mouse_enter(self, _event: Optional[QEvent], _image_coordinates: QPoint) -> bool:
        """Show the line preview on enter if in line mode."""
        if KeyConfig.modifier_held(KeyConfig.LINE_MODIFIER):
            self._preview_line.setVisible(True)
            return True
        return False

    def mouse_exit(self, _event: Optional[QEvent], _image_coordinates: QPoint) -> bool:
        """Hide the line preview on exit."""
        self._preview_line.set_line(QLineF())
        self._preview_line.setVisible(False)
        return True

    def tablet_event(self, event: Optional[QTabletEvent], _image_coordinates: QPoint) -> bool:
        """Cache tablet data when received."""
        assert event is not None
        control_panel = self.get_control_panel()
        if isinstance(control_panel, StrokeToolPanel):
            control_panel.show_pressure_checkboxes()
            Cache().set(Cache.EXPECT_TABLET_INPUT, True)
        if event.pointerType() is not None:
            self._tablet_input = event.pointerType()
        if event.pressure() > 0.00001:
            if len(self._pressure_curve) < 2:
                logger.warning('Ignoring invalid pressure curve')
                pressure = event.pressure()
            else:
                float_index = (len(self._pressure_curve) - 1) * event.pressure()
                low_idx = math.floor(float_index)

                if low_idx == len(self._pressure_curve) - 1:
                    pressure = self._pressure_curve[-1]
                else:
                    low_value = self._pressure_curve[low_idx]
                    high_value = self._pressure_curve[low_idx + 1]
                    fraction = float_index - low_idx
                    pressure = low_value + fraction * (high_value - low_value)
            self._tablet_pressure = pressure
            self._last_pressure = pressure
        else:
            self._tablet_pressure = None
        self._tablet_x_tilt = event.xTilt()
        self._tablet_y_tilt = event.yTilt()
        self._tablet_event_timestamp = datetime.datetime.now().timestamp()
        return True

    def update_brush_cursor(self) -> None:
        """Sizes the brush outline to the brush at the current zoom, and moves it under the cursor.

        The outline shows only while the tool is active, the cursor is over the image viewer, input is enabled, and
        the brush is wider on screen than MIN_OUTLINE_DIAMETER.
        """
        viewer = self._image_viewer
        cursor_pos = viewer.cursor_pos
        view_scale = viewer.scene_scale
        if (not self.is_active or cursor_pos is None or self.cursor_disabled
                or self.brush_size * view_scale <= MIN_OUTLINE_DIAMETER):
            self._outline.setVisible(False)
            return
        self._outline.set_size(self.brush_size, view_scale)
        self._outline.setPos(viewer.widget_point_to_scene(cursor_pos))
        self._outline.setVisible(True)

    def _cursor_moved_slot(self, _widget_pos: Optional[QPoint]) -> None:
        if self.is_active:
            self.update_brush_cursor()

    def wheel_event(self, event: Optional[QWheelEvent]) -> bool:
        """Adjust brush size if scrolling horizontal."""
        assert event is not None
        if not hasattr(self, 'adjust_brush_size'):
            return False
        offset = 0
        if event.angleDelta().x() < 0:
            offset -= 1
        elif event.angleDelta().x() > 0:
            offset += 1
        if offset != 0:
            self.adjust_brush_size(offset)
            return True
        return False

    def _active_layer_change_slot(self, active_layer: Layer) -> None:
        if isinstance(active_layer, ImageLayer):
            self.layer = active_layer
        else:
            self.layer = None

    def _modifier_change_slot(self, modifiers: Qt.KeyboardModifier) -> None:
        if not self.is_active:
            return
        line_modifier = KeyConfig().get(KeyConfig.LINE_MODIFIER)
        if modifiers == line_modifier and self._last_pos is not None:
            cursor_pos = self._image_viewer.mapFromGlobal(QCursor.pos())
            if QRect(QPoint(), self._image_viewer.size()).contains(cursor_pos):
                self._preview_line.set_line(QLineF(QPointF(self._last_pos), QPointF(cursor_pos)))
                self._preview_line.setVisible(True)
        else:
            self._preview_line.setVisible(False)
