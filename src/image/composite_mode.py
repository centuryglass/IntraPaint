"""Image composition mode management: Handles conversion between QPainter CompositionModes, open raster composite
 operations, and equivalent display text, and provides implementations for composite modes not supported by QPainter."""

from typing import Optional, Callable

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

from src.util.image_utils import image_data_as_numpy_8bit, create_transparent_image, NpUInt8Array, \
    numpy_bounds_index, image_is_fully_transparent
from src.util.geometry_utils import map_rect_precise

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'image.composite_mode'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


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

    def custom_composite_op(self) -> Callable[[QImage, QImage, float, Optional[QTransform]], None]:
        """Gets the custom composite method for a CompositeMode. Throws ValueError if called on a CompositeMode that
        uses a QPainter CompositionMode."""
        match self:
            case CompositeMode.COLOR:
                return CompositeMode.color_composite_blend
            case CompositeMode.LUMINOSITY:
                return CompositeMode.luminosity_composite_blend
            case CompositeMode.HUE:
                return CompositeMode.hue_composite_blend
            case CompositeMode.SATURATION:
                return CompositeMode.saturation_composite_blend
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
    def _hsl_composite_blend(source_image: QImage,
                             base_image: QImage,
                             blending_op: Callable[[NpUInt8Array, NpUInt8Array], NpUInt8Array],
                             opacity: float = 1.0,
                             top_transform: Optional[QTransform] = None) -> None:
        assert source_image.format() == base_image.format() == QImage.Format.Format_ARGB32_Premultiplied
        if opacity == 0 or image_is_fully_transparent(source_image):
            return
        if top_transform is None:
            top_transform = QTransform()
        base_bounds = QRect(QPoint(), base_image.size())
        if not top_transform.isIdentity():
            source_bounds = map_rect_precise(QRect(QPoint(), source_image.size()), top_transform).toAlignedRect()
            transformed_source = create_transparent_image(source_bounds.size())
            source_painter = QPainter(transformed_source)
            source_painter.setTransform(top_transform * QTransform.fromTranslate(-source_bounds.x(),
                                                                                 -source_bounds.y()))
            source_painter.drawImage(QPoint(), source_image)
            source_painter.end()
        else:
            source_bounds = QRect(QPoint(), source_image.size())
            transformed_source = source_image
        assert base_bounds.contains(source_bounds)
        np_top = image_data_as_numpy_8bit(transformed_source)
        np_base = numpy_bounds_index(image_data_as_numpy_8bit(base_image), source_bounds)
        assert np_top.shape == np_base.shape

        # calculate final alpha:
        alpha_top = np_top[:, :, 3] / 255.0 * opacity
        alpha_base = np_base[:, :, 3] / 255.0
        alpha_combined = np.clip(alpha_top + alpha_base * (1 - alpha_top), 0, 1)

        # Calculate HSL values (as hls):
        top_hls = cv2.cvtColor(np_top[:, :, :3], cv2.COLOR_BGR2HLS)
        base_hls = cv2.cvtColor(np_base[:, :, :3], cv2.COLOR_BGR2HLS)

        # apply blending operation, convert back to RGB:
        final_hls = blending_op(top_hls, base_hls)
        blended_rgb = cv2.cvtColor(final_hls, cv2.COLOR_HLS2BGR)

        # final compositing onto the base image:
        for c in range(3):
            np_base[:, :, c] = (blended_rgb[:, :, c] * alpha_top + np_base[:, :, c]
                                * alpha_base * (1 - alpha_top) / alpha_combined)
        np_base[:, :, 3] = alpha_combined * 255

    @classmethod
    def color_composite_blend(cls, top_image: QImage, base_image: QImage, opacity: float = 1.0,
                              top_transform: Optional[QTransform] = None) -> None:
        """Composite top_image over base_image, blending top image hue and saturation with base image luminosity.

        Parameters:
        -----------
        top_image: QImage
            The source image for the compositing operation.
        base_image: QImage
            The backdrop image for the compositing operation. This image will be modified in-place to create the final
            composited image.
        opacity: float, default=1.0
            Opacity of the top layer.
        top_transform: QTransform | None
            Optional transformation to apply to the top image before compositing.
        """

        def _color_blend(top_hls: NpUInt8Array, base_hls: NpUInt8Array) -> NpUInt8Array:
            top_hls[:, :, 1] = base_hls[:, :, 1]
            return top_hls

        CompositeMode._hsl_composite_blend(top_image, base_image, _color_blend, opacity, top_transform)

    @classmethod
    def luminosity_composite_blend(cls, top_image: QImage, base_image: QImage, opacity: float = 1.0,
                                   top_transform: Optional[QTransform] = None) -> None:
        """Composite top_image over base_image, blending top image luminosity with base image hue and saturation.

        Parameters:
        -----------
        top_image: QImage
            The source image for the compositing operation.
        base_image: QImage
            The backdrop image for the compositing operation. This image will be modified in-place to create the final
            composited image.
        opacity: float, default=1.0
            Opacity of the top layer.
        top_transform: QTransform | None
            Optional transformation to apply to the top image before compositing.
        """

        def _luminosity_blend(top_hls: NpUInt8Array, base_hls: NpUInt8Array) -> NpUInt8Array:
            base_hls[:, :, 1] = top_hls[:, :, 1]
            return base_hls

        CompositeMode._hsl_composite_blend(top_image, base_image, _luminosity_blend, opacity, top_transform)

    @classmethod
    def hue_composite_blend(cls, top_image: QImage, base_image: QImage, opacity: float = 1.0,
                            top_transform: Optional[QTransform] = None) -> None:
        """Composite top_image over base_image, blending top image hue with base image luminosity and saturation.

        Parameters:
        -----------
        top_image: QImage
            The source image for the compositing operation.
        base_image: QImage
            The backdrop image for the compositing operation. This image will be modified in-place to create the final
            composited image.
        opacity: float, default=1.0
            Opacity of the top layer.
        top_transform: QTransform | None
            Optional transformation to apply to the top image before compositing.
        """

        def _hue_blend(top_hls: NpUInt8Array, base_hls: NpUInt8Array) -> NpUInt8Array:
            base_hls[:, :, 0] = top_hls[:, :, 0]
            return base_hls

        CompositeMode._hsl_composite_blend(top_image, base_image, _hue_blend, opacity, top_transform)

    @classmethod
    def saturation_composite_blend(cls, top_image: QImage, base_image: QImage, opacity: float = 1.0,
                                   top_transform: Optional[QTransform] = None) -> None:
        """Composite top_image over base_image, blending top image saturation with base image hue and luminosity.

        Parameters:
        -----------
        top_image: QImage
            The source image for the compositing operation.
        base_image: QImage
            The backdrop image for the compositing operation. This image will be modified in-place to create the final
            composited image.
        opacity: float, default=1.0
            Opacity of the top layer.
        top_transform: QTransform | None
            Optional transformation to apply to the top image before compositing.
        """

        def _saturation_blend(top_hls: NpUInt8Array, base_hls: NpUInt8Array) -> NpUInt8Array:
            base_hls[:, :, 2] = top_hls[:, :, 2]
            return base_hls

        CompositeMode._hsl_composite_blend(top_image, base_image, _saturation_blend, opacity, top_transform)
