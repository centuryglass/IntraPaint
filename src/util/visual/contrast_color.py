"""
Finds appropriate contrast colors based on either QWidget palettes or calculated QColor luminance.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QColor

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


def contrast_ratio(first: QColor, second: QColor) -> float:
    """Returns the WCAG contrast ratio between two colors, from 1.0 (identical luminance) to 21.0 (black and white)."""
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def with_min_contrast(color: QColor, background: QColor, min_ratio: float) -> QColor:
    """Returns an opaque copy of a color, lightened or darkened until it reaches a contrast ratio against a background.

    Hue and saturation are kept. The color moves away from the background's luminance: lighter on dark backgrounds,
    darker on light ones. If the ratio can't be reached, the result is the lightest or darkest color of that hue.
    """
    result = QColor(color)
    result.setAlpha(255)
    lighten = relative_luminance(background) < LUMINANCE_THRESHOLD
    hue, saturation, lightness, _ = result.getHslF()
    while contrast_ratio(result, background) < min_ratio and 0.0 < lightness < 1.0:
        lightness = min(lightness + 0.02, 1.0) if lighten else max(lightness - 0.02, 0.0)
        result.setHslF(hue, saturation, lightness, 1.0)
    return result
