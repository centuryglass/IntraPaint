"""Shape drawing utility functions"""
from enum import Enum
from typing import Optional

from PySide6.QtCore import QRect, QLineF, QPointF
from PySide6.QtGui import QPainterPath
from PySide6.QtWidgets import QApplication

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.shape_tool_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SHAPE_MODE_ELLIPSE_LABEL = _tr('Ellipse')
SHAPE_MODE_RECTANGLE_LABEL = _tr('Rectangle')
SHAPE_MODE_POLYGON_LABEL = _tr('Polygon')
SHAPE_MODE_STAR_LABEL = _tr('Star')


class ShapeMode(Enum):
    """Shape drawing mode definitions"""
    ELLIPSE = 0
    RECTANGLE = 1
    POLYGON = 2
    STAR = 3

    def display_text(self) -> str:
        """Gets appropriate display text for the mode."""
        match self:
            case ShapeMode.ELLIPSE:
                return SHAPE_MODE_ELLIPSE_LABEL
            case ShapeMode.RECTANGLE:
                return SHAPE_MODE_RECTANGLE_LABEL
            case ShapeMode.POLYGON:
                return SHAPE_MODE_POLYGON_LABEL
            case ShapeMode.STAR:
                return SHAPE_MODE_STAR_LABEL

    @staticmethod
    def is_valid_mode_str(mode_str: str) -> bool:
        """Return whether a string is a valid ShapeMode label."""
        return mode_str in (SHAPE_MODE_STAR_LABEL, SHAPE_MODE_RECTANGLE_LABEL, SHAPE_MODE_POLYGON_LABEL,
                            SHAPE_MODE_STAR_LABEL)

    @staticmethod
    def from_text(display_text: str) -> 'ShapeMode':
        """Gets the appropriate mode for a given mode name."""
        mode_names = {
            SHAPE_MODE_ELLIPSE_LABEL: ShapeMode.ELLIPSE,
            SHAPE_MODE_RECTANGLE_LABEL: ShapeMode.RECTANGLE,
            SHAPE_MODE_POLYGON_LABEL: ShapeMode.POLYGON,
            SHAPE_MODE_STAR_LABEL: ShapeMode.STAR
        }
        if display_text in mode_names:
            return mode_names[display_text]
        raise ValueError(f'Invalid mode name {display_text}')

    def painter_path(self, bounds: QRect, radius: Optional[float], vertex_count: Optional[int] = None,
                     inner_radius: Optional[float] = None, angle_offset: float = 0.0) -> QPainterPath:
        """Given a set of basic parameters, get a QPainterPath representing a shape."""
        path = QPainterPath()
        center = bounds.center()
        match self:
            case ShapeMode.ELLIPSE:
                if radius is None:
                    raise ValueError('Radius must be provided for ShapeMode.ELLIPSE')
                path.addEllipse(center, radius, radius)
            case ShapeMode.RECTANGLE:
                path.addRect(bounds)
            case ShapeMode.POLYGON:
                if radius is None:
                    raise ValueError('Radius must be provided for ShapeMode.POLYGON')
                if vertex_count is None:
                    raise ValueError('Vertex count must be provided for ShapeMode.POLYGON')
                line = QLineF(center, QPointF(center.x() + radius, center.y()))
                for i in range(vertex_count):
                    angle = 360 / vertex_count * i + angle_offset
                    line.setAngle(angle)
                    poly_point = line.p2().toPoint()
                    if i == 0:
                        path.moveTo(poly_point)
                    else:
                        path.lineTo(poly_point)
                path.closeSubpath()
            case ShapeMode.STAR:
                if radius is None:
                    raise ValueError('Radius must be provided for ShapeMode.STAR')
                if vertex_count is None:
                    raise ValueError('Vertex count must be provided for ShapeMode.STAR')
                if inner_radius is None:
                    raise ValueError('Inner radius must be provided for ShapeMode.STAR')
                line1 = QLineF(center, QPointF(center.x() + radius, center.y()))
                line2 = QLineF(center, QPointF(center.x() + inner_radius, center.y()))
                for i in range(vertex_count):
                    angle = 360 / vertex_count * i + angle_offset
                    line1.setAngle(angle)
                    poly_point = line1.p2().toPoint()
                    if i == 0:
                        path.moveTo(poly_point)
                    else:
                        path.lineTo(poly_point)
                    angle2 = 360 / vertex_count * (i + 0.5) + angle_offset
                    line2.setAngle(angle2)
                    inner_point = line2.p2().toPoint()
                    path.lineTo(inner_point)
                path.closeSubpath()
            case _:
                raise ValueError(f'Unhandled mode {self}')
        return path
