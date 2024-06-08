"""
Finds appropriate contrast colors based on either QWidget palettes or calculated QColor luminance.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QColor

LUMINANCE_THRESHOLD = 0.179


def relative_luminance(color: QColor | Qt.GlobalColor) -> float:
    """Returns the relative luminance of a color."""
    if isinstance(color, Qt.GlobalColor):
        color = QColor(color)

    def adjust_component(c: float) -> float:
        """Calculated to fit W3C guidelines from https://www.w3.org/TR/WCAG20/#relativeluminancedef"""
        return (c / 12.92) if c <= 0.03928 else (((c + 0.055) / 1.055) ** 2.4)
    r = adjust_component(color.red() / 255)
    g = adjust_component(color.green() / 255)
    b = adjust_component(color.blue() / 255)
    return (0.2126 * r) + (0.7152 * g) + (0.0722 * b)


def contrast_color(source: QWidget | QColor) -> QColor:
    """Finds an appropriate contrast color for displaying against a QColor or QWidget source."""
    if isinstance(source, QWidget):
        return source.palette().color(source.foregroundRole())
    if isinstance(source, QColor):
        luminance = relative_luminance(source)
        return QColor(Qt.GlobalColor.white if luminance < LUMINANCE_THRESHOLD else Qt.GlobalColor.black)
    raise ValueError(f"Invalid contrast_color parameter {source}")
