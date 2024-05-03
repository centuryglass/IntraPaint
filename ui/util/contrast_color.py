"""
Finds appropriate contrast colors based on either QWidget palletes or calculated QColor luminances.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QColor

def contrast_color(source): 
    if isinstance(source, QWidget):
        return source.palette().color(source.foregroundRole())
    if isinstance(source, QColor):
        # Calculated to fit W3C guidelines from https://www.w3.org/TR/WCAG20/#relativeluminancedef
        def adjustComponent(c):
            return (c / 12.92) if c <= 0.03928 else (((c + 0.055)/1.055) ** 2.4)
        r = adjustComponent(source.red() / 255)
        g = adjustComponent(source.green() / 255)
        b = adjustComponent(source.blue() / 255)
        relative_luminance = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
        return Qt.black if relative_luminance < 0.179 else Qt.white
    raise Exception(f"Invalid contrast_color parameter {source}")
