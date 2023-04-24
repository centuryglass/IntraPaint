from PyQt5.QtCore import Qt, QPoint, QRect, QSize

def getScaledPlacement(containerRect, innerSize, marginWidth=0):
    """
    Calculate the most appropriate placement of a scaled rectangle within a container, without changing aspect ratio.
    Parameters:
    -----------
    containerRect : QRect
        Bounds of the container where the scaled rectangle will be placed.        
    innerSize : QSize
        S of the rectangle to be scaled and placed within the container.
    marginWidth : int
        Distance in pixels of the area around the container edges that should remain empty.
    Returns:
    --------
    placement : QRect
        Size and position of the scaled rectangle within containerRect.
    scale : number
        Amount that the inner rectangle's width and height should be scaled.
    """
    containerSize = containerRect.size() - QSize(marginWidth * 2, marginWidth * 2)
    scale = min(containerSize.width()/max(innerSize.width(), 1), containerSize.height()/max(innerSize.height(), 1))
    x = containerRect.x() + marginWidth
    y = containerRect.y() + marginWidth
    if (innerSize.width() * scale) < containerSize.width():
        x += (containerSize.width() - innerSize.width() * scale) / 2
    if (innerSize.height() * scale) < containerSize.height():
        y += (containerSize.height() - innerSize.height() * scale) / 2
    return QRect(int(x), int(y), int(innerSize.width() * scale), int(innerSize.height() * scale))
