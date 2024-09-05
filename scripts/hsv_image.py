"""Generates an HSV color picker image"""
from typing import Any

import numpy as np
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, Qt, QColor

HUE_MAX = 359
SAT_MAX = 255

X_RES = 720
Y_RES = 512

OUT_PATH = 'resources/hsv_square.png'

hsv_image = QImage(QSize(X_RES, Y_RES), QImage.Format.Format_ARGB32_Premultiplied)
hsv_image.fill(Qt.GlobalColor.white)

numpy_image: np.ndarray[Any, np.dtype[np.uint8]] = np.ndarray(shape=(hsv_image.height(), hsv_image.width(), 4),
                                                              dtype=np.uint8, buffer=hsv_image.bits())
for y in range(Y_RES):
    for x in range(X_RES):
        color = QColor.fromHsvF(1.0 - x / X_RES, 1.0 - y / Y_RES, 1.0, 1.0)
        color = color.toRgb()
        numpy_image[y, x, 0] = color.blue()
        numpy_image[y, x, 1] = color.green()
        numpy_image[y, x, 2] = color.red()
hsv_image.save(OUT_PATH)