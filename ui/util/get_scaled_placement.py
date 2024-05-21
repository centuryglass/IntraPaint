"""Provides a utility function for handling image or widget placement."""

from PyQt5.QtCore import QRect, QSize


def get_scaled_placement(container_rect: QRect,
                         inner_size: QSize, margin_width: int = 0) -> QRect:
    """
    Calculate the most appropriate placement of a scaled rectangle within a container, without changing aspect ratio.
    Parameters:
    -----------
    container_rect : QRect
        Bounds of the container where the scaled rectangle will be placed.        
    inner_size : QSize
        S of the rectangle to be scaled and placed within the container.
    margin_width : int
        Distance in pixels of the area around the container edges that should remain empty.
    Returns:
    --------
    placement : QRect
        Size and position of the scaled rectangle within container_rect.
    """
    container_size = container_rect.size() - QSize(margin_width * 2, margin_width * 2)
    scale = min(container_size.width() / max(inner_size.width(), 1),
                container_size.height() / max(inner_size.height(), 1))
    x = float(container_rect.x() + margin_width)
    y = float(container_rect.y() + margin_width)
    if (inner_size.width() * scale) < container_size.width():
        x += (container_size.width() - inner_size.width() * scale) / 2
    if (inner_size.height() * scale) < container_size.height():
        y += (container_size.height() - inner_size.height() * scale) / 2
    return QRect(int(x), int(y), int(inner_size.width() * scale), int(inner_size.height() * scale))
