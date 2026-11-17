"""Draws the panel edge lines `InkStyle` adds around docks: main window separators and dock rail inner edges."""
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QStyleOption, QStyleOptionToolBar


def draw_dock_separator(painter: QPainter, option: QStyleOption, color: QColor) -> None:
    """Draws a main window separator as a 1px line down the middle of its gap."""
    rect = option.rect
    if rect.width() < rect.height():
        line = QRect(rect.center().x(), rect.top(), 1, rect.height())
    else:
        line = QRect(rect.left(), rect.center().y(), rect.width(), 1)
    painter.fillRect(line, color)


def draw_rail_edge(painter: QPainter, option: QStyleOptionToolBar, color: QColor) -> None:
    """Draws a 1px line along a main window toolbar's inner edge, over the base style's bevel."""
    rect = option.rect
    area = option.toolBarArea
    if area == Qt.ToolBarArea.TopToolBarArea:
        line = QRect(rect.left(), rect.bottom(), rect.width(), 1)
    elif area == Qt.ToolBarArea.BottomToolBarArea:
        line = QRect(rect.left(), rect.top(), rect.width(), 1)
    elif area == Qt.ToolBarArea.LeftToolBarArea:
        line = QRect(rect.right(), rect.top(), 1, rect.height())
    elif area == Qt.ToolBarArea.RightToolBarArea:
        line = QRect(rect.left(), rect.top(), 1, rect.height())
    else:
        return
    painter.fillRect(line, color)
