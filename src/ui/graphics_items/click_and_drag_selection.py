"""An object that creates a temporary graphics item used to visualize clicking and dragging to select a region."""
from typing import Optional

from PySide6.QtCore import QRect, QPoint, QSize, QPointF, QLineF
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPen, QBrush, QColor, QTransform, QPolygonF, QPainterPath
from PySide6.QtWidgets import QGraphicsScene, QGraphicsRectItem, QGraphicsEllipseItem, QApplication

from src.config.key_config import KeyConfig
from src.util.shared_constants import FLOAT_MAX

DEFAULT_SELECTION_LINE_COLOR = Qt.GlobalColor.black
DEFAULT_SELECTION_LINE_WIDTH = 2.0
DEFAULT_SELECTION_FILL_COLOR = QColor(100, 100, 100)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.graphics_items.click_and_drag_selection'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SELECTION_MODE_RECT = _tr('Rectangle')
SELECTION_MODE_ELLIPSE = _tr('Ellipse')


class ClickAndDragSelection:
    """An object that creates a temporary graphics item used to visualize clicking and dragging to select a region."""

    def __init__(self, scene: QGraphicsScene) -> None:
        self._scene = scene
        self._selection_shape: Optional[QGraphicsRectItem | QGraphicsEllipseItem] = None
        self._mode = SELECTION_MODE_RECT
        self._pen: QPen = QPen(DEFAULT_SELECTION_LINE_COLOR, DEFAULT_SELECTION_LINE_WIDTH)
        self._brush: QBrush = QBrush(DEFAULT_SELECTION_FILL_COLOR, Qt.BrushStyle.DiagCrossPattern)
        self._last_bounds: Optional[QRect] = None
        self._transform = QTransform()

    @property
    def last_selection_bounds(self) -> Optional[QRect]:
        """Return the bounds from the last selection, or None if no selection has happened yet."""
        return QRect(self._last_bounds) if self._last_bounds is not None else None

    @property
    def mode(self) -> str:
        """Return the active selection mode."""
        return self._mode

    @mode.setter
    def mode(self, new_mode: str) -> None:
        if new_mode == self._mode:
            return
        if new_mode not in (SELECTION_MODE_ELLIPSE, SELECTION_MODE_RECT):
            raise ValueError(f'Unexpected selection mode {new_mode}')
        self._mode = new_mode
        if self._selection_shape is not None:
            bounds = self._remove_scene_item()
            assert bounds is not None
            self._create_scene_item(bounds)

    @property
    def selecting(self) -> bool:
        """Return whether a selection is currently in-progress."""
        return self._selection_shape is not None

    @property
    def transform(self) -> QTransform:
        """Access the transformation applied to the selection graphics item."""
        return QTransform(self._transform)

    @transform.setter
    def transform(self, transform: QTransform) -> None:
        """Sets the transformation applied to the selection."""
        if transform == self._transform:
            return
        assert transform.isInvertible()
        self._transform = QTransform(transform)
        if self._selection_shape is not None:
            self._selection_shape.setTransform(self._transform)

    def start_selection(self, start_point: QPoint) -> None:
        """Start a new selection.

        Parameters:
        -----------
        start_point: QPoint
            The initial selection point, as an untransformed scene coordinate.
        """
        start_point = self._transform.inverted()[0].map(start_point)
        if self.selecting:
            self._remove_scene_item()
        self._create_scene_item(QRect(start_point, QSize(0, 0)))

    def drag_to(self, drag_point: QPoint) -> None:
        """Continue a selection.

        Parameters:
        -----------
        drag_point: QPoint
            The point where the mouse is currently placed, as an untransformed scene coordinate.
        """
        drag_point = self._transform.inverted()[0].map(drag_point)
        if not self.selecting:
            self.start_selection(drag_point)
            return
        assert self._selection_shape is not None
        rect = self._selection_shape.rect()
        if KeyConfig.modifier_held(KeyConfig.FIXED_ASPECT_MODIFIER):
            x_size = drag_point.x() - rect.x()
            y_size = drag_point.y() - rect.y()
            point_options = [
                QPointF(drag_point.x(), rect.y() + x_size),
                QPointF(drag_point.x(), rect.y() - x_size),
                QPointF(rect.x() + y_size, drag_point.y()),
                QPointF(rect.x() - y_size, drag_point.y())
            ]
            min_distance = FLOAT_MAX
            bottom_right = None
            for point in point_options:
                distance_from_mouse = QLineF(QPointF(drag_point), point).length()
                if distance_from_mouse < min_distance:
                    min_distance = distance_from_mouse
                    bottom_right = point
            assert bottom_right is not None
        else:
            bottom_right = drag_point
        rect.setCoords(rect.x(), rect.y(), bottom_right.x(), bottom_right.y())
        self._selection_shape.setRect(rect)

    def end_selection(self, end_point: QPoint) -> QPolygonF:
        """Finish a selection, and return the selected rectangle in the scene.
        Parameters:
        -----------
        end_point: QPoint
            The point where the selection finished, as an untransformed scene coordinate.
        Returns:
        -------
        QPolygonF
            The final selected rectangle or ellipse, transformed back into scene coordinates.
        """
        self.drag_to(end_point)
        selection = self._remove_scene_item()
        assert selection is not None
        if self._mode == SELECTION_MODE_RECT:
            return self._transform.map(QRectF(selection))
        else:
            assert self._mode == SELECTION_MODE_ELLIPSE
            path = QPainterPath()
            path.addEllipse(selection)
            return self._transform.map(path.toFillPolygon())

    def set_pen(self, pen: QPen) -> None:
        """Set the selection item's line drawing pen."""
        self._pen = pen
        if self._selection_shape is not None:
            self._selection_shape.setPen(pen)

    def set_brush(self, brush: QBrush) -> None:
        """set the selection item's fill brush."""
        self._brush = brush
        if self._selection_shape is not None:
            self._selection_shape.setBrush(brush)

    def _active_selection_bounds(self) -> Optional[QRect]:
        if self._selection_shape is None:
            return None
        return self._selection_shape.rect().toAlignedRect()

    def _remove_scene_item(self) -> Optional[QRect]:
        if self._selection_shape is None:
            return None
        bounds = self._active_selection_bounds()
        self._scene.removeItem(self._selection_shape)
        self._selection_shape = None
        return bounds

    def _create_scene_item(self, initial_bounds: QRect) -> None:
        if self._selection_shape is not None:
            self._remove_scene_item()
        if self._mode == SELECTION_MODE_RECT:
            self._selection_shape = QGraphicsRectItem(initial_bounds)
        else:
            assert self._mode == SELECTION_MODE_ELLIPSE
            self._selection_shape = QGraphicsEllipseItem(initial_bounds)
        self._selection_shape.setTransform(self._transform)
        self._selection_shape.setPen(self._pen)
        self._selection_shape.setBrush(self._brush)
        self._scene.addItem(self._selection_shape)
