"""Provides compatibility between the OpenRaster file format and ImageStack object data.

Open Raster specification:
https://www.openraster.org/baseline/file-layout-spec.html

XML file spec:
https://invent.kde.org/documentation/openraster-org/-/blob/master/openraster-standard/schema.rnc
"""

# Zipped file directory structure:
ORA_FILE_EXTENSION = '.ora'
MIMETYPE_FILE_NAME = 'mimetype'
MIMETYPE_FILE_CONTENT = 'image/openraster'
XML_FILE_NAME = 'stack.xml'
DATA_DIRECTORY_NAME = 'data'
THUMBNAIL_DIRECTORY_NAME = 'Thumbnails'
THUMBNAIL_FILE_NAME = 'thumbnail.png'
MERGED_IMAGE_FILE_NAME = 'mergedimage'

# XML tags and constants:
ORA_SPEC_VERSION = '0.0.3'

# image XML element tags:
IMAGE_ELEMENT = 'image'
IMAGE_TAG_WIDTH = 'w'  # int
IMAGE_TAG_HEIGHT = 'h'  # int
IMAGE_TAG_XRES = 'xres'  # int, optional (pixels per inch)
IMAGE_TAG_YRES = 'yres'  # int, optional (pixels per inch)
IMAGE_TAG_NAME = 'name'  # str

# layerCommonAttributes XML tags:
ATTR_TAG_NAME = 'name'  # str, optional
ATTR_TAG_COMPOSITE = 'composite-op'  # str, optional
ATTR_TAG_OPACITY = 'opacity'  # str, optional
ATTR_TAG_VISIBILITY = 'visibility'  # str, optional
# valid visibility strings:
ATTR_VISIBLE = 'visible'
ATTR_HIDDEN = 'hidden'

# positionAttributes XML tags:
ATTR_TAG_X_POS = 'x'  # int, optional
ATTR_TAG_Y_POS = 'y'  # int, optional

# stack XML element tags:
STACK_ELEMENT = 'stack'
STACK_TAG_ISOLATION = 'isolation'  # str
# valid isolation strings:
ISOLATION_AUTO = 'auto'
ISOLATION_ISOLATE = 'isolate'
# Also: anything within layerCommonAttributes, positionAttributes

# layer XML element tags
LAYER_ELEMENT = 'layer'
LAYER_TAG_SRC = 'src'  # str
# Also: anything within layerCommonAttributes, positionAttributes

# Composition modes:
# Mapped to the equivalent key string in src.util.shared_constants.COMPOSITION_MODES.
# Some of these are not yet supported, so check before indexing into COMPOSITION_MODES
ORA_COMPOSITION_MODES = {
    'svg:src-over': 'Normal',
    'svg:multiply': 'Multiply',
    'svg:screen': 'Screen',
    'svg:overlay': 'Overlay',
    'svg:darken': 'Darken',
    'svg:lighten': 'Lighten',
    'svg:color-dodge': 'Color Dodge',
    'svg:color-burn': 'Color Burn',
    'svg:hard-light': 'Hard Light',
    'svg:soft-light': 'Soft Light',
    'svg:difference': 'Difference',
    'svg:plus': 'Plus',
    'svg:dst-in': 'Destination In',
    'svg:dst-out': 'Destination Out',
    'svg:src-atop': 'Source Atop',
    'svg:dst-atop': 'Destination Atop',
    # The following have no direct implementation available via QPainter.CompositionMode.
    # TODO: look into alternative ways to implement.
    'svg:color': 'Color',
    'svg:luminosity': 'Luminosity',
    'svg:hue': 'Hue',
    'svg:saturation': 'Saturation'
}
