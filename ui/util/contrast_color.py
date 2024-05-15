"""
Finds appropriate contrast colors based on either QWidget palletes or calculated QColor luminances.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QColor

def contrast_color(source):
    """Finds an appropriate contrast color for displaying against a QColor or QWidget source."""
    if isinstance(source, QWidget):
        return source.palette().color(source.foregroundRole())
    if isinstance(source, QColor):
        # Calculated to fit W3C guidelines from https://www.w3.org/TR/WCAG20/#relativeluminancedef
        def adjust_component(c):
            return (c / 12.92) if c <= 0.03928 else (((c + 0.055)/1.055) ** 2.4)
        r = adjust_component(source.red() / 255)
        g = adjust_component(source.green() / 255)
        b = adjust_component(source.blue() / 255)
        relative_luminance = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
        return Qt.black if relative_luminance < 0.179 else Qt.white
    raise ValueError(f"Invalid contrast_color parameter {source}")
