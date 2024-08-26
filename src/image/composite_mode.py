"""Image composition mode management: Handles conversion between QPainter CompositionModes, open raster composite
 operations, and equivalent display text, and provides implementations for composite modes not supported by QPainter."""

from typing import Optional, Callable, TypeAlias, Any

import cv2
import numpy as np

try:
    from enum import StrEnum
except ImportError:  # Use third-party StrEnum if python version < 3.11
    # noinspection PyPackageRequirements
    from strenum import StrEnum  # type: ignore

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QPainter, QImage, QTransform
from PySide6.QtWidgets import QApplication

from src.util.image_utils import image_data_as_numpy_8bit, create_transparent_image, is_fully_transparent

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'image.composite_mode'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


NpInt8Arr: TypeAlias = np.ndarray[Any, np.dtype[np.int8]]


class CompositeMode(StrEnum):
    """Image/Layer composition modes:"""
    NORMAL = _tr('Normal')
    MULTIPLY = _tr('Multiply')
    SCREEN = _tr('Screen')
    OVERLAY = _tr('Overlay')
    DARKEN = _tr('Darken')
    LIGHTEN = _tr('Lighten')
    COLOR_DODGE = _tr('Color Dodge')
    COLOR_BURN = _tr('Color Burn')
    HARD_LIGHT = _tr('Hard Light')
    SOFT_LIGHT = _tr('Soft Light')
    DIFFERENCE = _tr('Difference')
    COLOR = _tr('Color')
    LUMINOSITY = _tr('Luminosity')
    HUE = _tr('Hue')
    SATURATION = _tr('Saturation')
    PLUS = _tr('Plus')
    DESTINATION_IN = _tr('Destination In')
    DESTINATION_OUT = _tr('Destination Out')
    SOURCE_ATOP = _tr('Source Atop')
    DESTINATION_ATOP = _tr('Destination Atop')

    def qt_composite_mode(self) -> Optional[QPainter.CompositionMode]:
        """Get the mode's QPainter CompositionMode equivalent, or None if it's one of the unsupported modes."""
        mode: Optional[QPainter.CompositionMode] = None
        match self:
            case CompositeMode.NORMAL:
                mode = QPainter.CompositionMode.CompositionMode_SourceOver
            case CompositeMode.MULTIPLY:
                mode = QPainter.CompositionMode.CompositionMode_Multiply
            case CompositeMode.SCREEN:
                mode = QPainter.CompositionMode.CompositionMode_Screen
            case CompositeMode.OVERLAY:
                mode = QPainter.CompositionMode.CompositionMode_Overlay
            case CompositeMode.DARKEN:
                mode = QPainter.CompositionMode.CompositionMode_Darken
            case CompositeMode.LIGHTEN:
                mode = QPainter.CompositionMode.CompositionMode_Lighten
            case CompositeMode.COLOR_DODGE:
                mode = QPainter.CompositionMode.CompositionMode_ColorDodge
            case CompositeMode.COLOR_BURN:
                mode = QPainter.CompositionMode.CompositionMode_ColorBurn
            case CompositeMode.HARD_LIGHT:
                mode = QPainter.CompositionMode.CompositionMode_HardLight
            case CompositeMode.SOFT_LIGHT:
                mode = QPainter.CompositionMode.CompositionMode_SoftLight
            case CompositeMode.DIFFERENCE:
                mode = QPainter.CompositionMode.CompositionMode_Difference
            case CompositeMode.PLUS:
                mode = QPainter.CompositionMode.CompositionMode_Plus
            case CompositeMode.DESTINATION_IN:
                mode = QPainter.CompositionMode.CompositionMode_DestinationIn
            case CompositeMode.DESTINATION_OUT:
                mode = QPainter.CompositionMode.CompositionMode_DestinationOut
            case CompositeMode.SOURCE_ATOP:
                mode = QPainter.CompositionMode.CompositionMode_SourceAtop
            case CompositeMode.DESTINATION_ATOP:
                mode = QPainter.CompositionMode.CompositionMode_DestinationAtop
        return mode

    def openraster_composite_mode(self) -> str:
        """Get the mode's equivalent name in the Open Raster image format."""
        match self:
            case CompositeMode.NORMAL:
                mode = 'svg:src-over'
            case CompositeMode.MULTIPLY:
                mode = 'svg:multiply'
            case CompositeMode.SCREEN:
                mode = 'svg:screen'
            case CompositeMode.OVERLAY:
                mode = 'svg:overlay'
            case CompositeMode.DARKEN:
                mode = 'svg:darken'
            case CompositeMode.LIGHTEN:
                mode = 'svg:lighten'
            case CompositeMode.COLOR_DODGE:
                mode = 'svg:color-dodge'
            case CompositeMode.COLOR_BURN:
                mode = 'svg:color-burn'
            case CompositeMode.HARD_LIGHT:
                mode = 'svg:hard-light'
            case CompositeMode.SOFT_LIGHT:
                mode = 'svg:soft-light'
            case CompositeMode.DIFFERENCE:
                mode = 'svg:difference'
            case CompositeMode.COLOR:
                mode = 'svg:color'
            case CompositeMode.LUMINOSITY:
                mode = 'svg:luminosity'
            case CompositeMode.HUE:
                mode = 'svg:hue'
            case CompositeMode.SATURATION:
                mode = 'svg:saturation'
            case CompositeMode.PLUS:
                mode = 'svg:plus'
            case CompositeMode.DESTINATION_IN:
                mode = 'svg:dst-in'
            case CompositeMode.DESTINATION_OUT:
                mode = 'svg:dst-out'
            case CompositeMode.SOURCE_ATOP:
                mode = 'svg:src-atop'
            case _:
                assert self == CompositeMode.DESTINATION_ATOP
                mode = 'svg:dst-atop'
        return mode

    def custom_composite_op(self) -> Callable[[QImage, QImage, QRect, QRect, Optional[QTransform]], None]:
        """Gets the custom composite method for a CompositeMode. Throws ValueError if called on a CompositeMode that
        uses a QPainter CompositionMode."""
        match self:
            case CompositeMode.COLOR:
                return CompositeMode.color_composite_render
            case CompositeMode.LUMINOSITY:
                return CompositeMode.luminosity_composite_render
            case CompositeMode.HUE:
                return CompositeMode.hue_composite_render
            case CompositeMode.SATURATION:
                return CompositeMode.saturation_composite_render
        raise ValueError(f'CompositeMode {self.value} has no custom compositing function.')

    @staticmethod
    def from_qt_mode(mode: QPainter.CompositionMode) -> 'CompositeMode':
        """Returns the CompositeMode for a given QPainter.CompositionMode, or raises ValueError if the mode isn't
           supported."""
        for mode_name in CompositeMode:
            composite_mode = CompositeMode(mode_name)
            if composite_mode.qt_composite_mode() == mode:
                return composite_mode
        raise ValueError(f'Unsupported mode {mode}')

    @staticmethod
    def from_ora_name(ora_mode: str) -> 'CompositeMode':
        """Returns the CompositeMode for a given Open Raster composite operation, or raises ValueError if the mode isn't
           recognized."""
        for mode_name in CompositeMode:
            composite_mode = CompositeMode(mode_name)
            if composite_mode.openraster_composite_mode() == ora_mode:
                return composite_mode
        raise ValueError(f'Unrecognized mode {ora_mode}')

    @staticmethod
    def _hsl_composite_render(top_image: QImage, base_image: QImage,
                              composite_op: Callable[[NpInt8Arr, NpInt8Arr], NpInt8Arr],
                              top_bounds: QRect, base_bounds: QRect, top_transform: Optional[QTransform] = None):
        assert top_image.format() == QImage.Format.Format_ARGB32_Premultiplied
        assert base_image.format() == QImage.Format.Format_ARGB32_Premultiplied
        top_size = top_image.size() if top_bounds.isNull() else top_bounds.size()
        base_size = base_image.size() if base_bounds.isNull() else base_bounds.size()
        assert top_size == base_size
        if top_transform is not None and not top_transform.isIdentity():
            transformed_base = create_transparent_image(base_size)
            base_painter = QPainter(transformed_base)
            base_painter.setTransform(top_transform.inverted()[0])
            base_painter.drawImage(QPoint(), base_image)
            base_painter.end()
            base_image = transformed_base
        np_top = image_data_as_numpy_8bit(top_image)
        np_base = image_data_as_numpy_8bit(base_image)
        if not top_bounds.isNull():
            right = top_bounds.x() + top_bounds.width()
            bottom = top_bounds.y() + top_bounds.height()
            assert top_bounds.x() >= 0 and right <= top_image.width() and top_bounds.y() >= 0 \
                   and bottom <= top_image.height()
            np_top = np_top[top_bounds.y():bottom, top_bounds.x():right]
        if not base_bounds.isNull():
            right = base_bounds.x() + base_bounds.width()
            bottom = base_bounds.y() + base_bounds.height()
            assert base_bounds.x() >= 0 and right <= base_image.width() and base_bounds.y() >= 0 \
                   and bottom <= base_image.height()
            np_base = np_base[base_bounds.y():bottom, base_bounds.x():right]
        if is_fully_transparent(np_top) or is_fully_transparent(np_base):
            return

        top_hls = cv2.cvtColor(np_top[:, :, :3], cv2.COLOR_BGR2HLS)
        base_hls = cv2.cvtColor(np_base[:, :, :3], cv2.COLOR_BGR2HLS)
        final_hls = composite_op(top_hls, base_hls)
        final_rgb = cv2.cvtColor(final_hls, cv2.COLOR_HLS2BGR)
        alpha_mask = (np_top[:, :, 3] > 50) & (np_base[:, :, 3] > 50)
        np_top[alpha_mask, :3] = final_rgb[alpha_mask]
        # np_top[:, :, :3] = final_hls[:, :, :3]

    @staticmethod
    def color_composite_render(top_image: QImage, base_image: QImage, top_bounds: QRect, base_bounds: QRect,
                               top_transform: Optional[QTransform] = None):
        """Composite mode combining top image hue and saturation with base image lightness."""

        def _color_blend(top_hls: NpInt8Arr, base_hls: NpInt8Arr) -> NpInt8Arr:
            top_hls[:, :, 1] = base_hls[:, :, 1]
            return top_hls
        CompositeMode._hsl_composite_render(top_image, base_image, _color_blend, top_bounds, base_bounds, top_transform)

    @staticmethod
    def luminosity_composite_render(top_image: QImage, base_image: QImage, top_bounds: QRect, base_bounds: QRect,
                                    top_transform: Optional[QTransform] = None):
        """Composite mode combining top image lightness with base image hue and saturation."""

        def _luminosity_blend(top_hls: NpInt8Arr, base_hls: NpInt8Arr) -> NpInt8Arr:
            base_hls[:, :, 1] = top_hls[:, :, 1]
            return base_hls
        CompositeMode._hsl_composite_render(top_image, base_image, _luminosity_blend, top_bounds, base_bounds,
                                            top_transform)

    @staticmethod
    def hue_composite_render(top_image: QImage, base_image: QImage, top_bounds: QRect, base_bounds: QRect,
                             top_transform: Optional[QTransform] = None):
        """Composite mode combining top image hue with base image saturation and lightness"""

        def _hue_blend(top_hls: NpInt8Arr, base_hls: NpInt8Arr) -> NpInt8Arr:
            base_hls[:, :, 0] = top_hls[:, :, 0]
            return base_hls
        CompositeMode._hsl_composite_render(top_image, base_image, _hue_blend, top_bounds, base_bounds, top_transform)

    @staticmethod
    def saturation_composite_render(top_image: QImage, base_image: QImage, top_bounds: QRect, base_bounds: QRect,
                                    top_transform: Optional[QTransform] = None):
        """Composite mode combining top image saturation with base image hue and lightness"""

        def _saturation_blend(top_hls: NpInt8Arr, base_hls: NpInt8Arr) -> NpInt8Arr:
            base_hls[:, :, 2] = top_hls[:, :, 2]
            return base_hls
        CompositeMode._hsl_composite_render(top_image, base_image, _saturation_blend, top_bounds, base_bounds,
                                            top_transform)
