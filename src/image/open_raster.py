"""Provides compatibility between the OpenRaster file format and ImageStack object data.

Open Raster specification:
https://www.openraster.org/baseline/file-layout-spec.html

XML file spec:
https://invent.kde.org/documentation/openraster-org/-/blob/master/openraster-standard/schema.rnc
"""
import os.path
import shutil
import tempfile
import zipfile
from typing import Optional, Dict, Any, cast
from xml.etree.ElementTree import ElementTree, Element

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QTransform, QPainter, QImage

from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_stack import LayerStack
from src.util.geometry_utils import get_scaled_placement
from src.util.shared_constants import COMPOSITION_MODES

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

# Dict keys used before converting to xml:
DICT_ELEMENT_NAME = 'ELEMENT'
DICT_NESTED_CONTENT_NAME = 'NESTED'

# image XML element tags:
IMAGE_ELEMENT = 'image'
IMAGE_TAG_VERSION = 'version'
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

# IntraPaint extensions to the format:

# Extended transformation support:
# Layer and stack elements may include 'transform' tag, a comma-separated list of floating-point matrix elements. If the
# transform tag is provided, a second src_untransformed image tag should be included, pointing to another copy of the
# layer image where those transformations have not been applied. When loading an image with a transform tag, the usual
# position tags can be ignored.
TRANSFORM_TAG = 'transformation'
TRANSFORM_SRC_TAG = 'src_untransformed'

# Metadata support:
# The top-level 'metadata' tag can be used to store arbitrary additional string-encoded data, usually image generation
# parameters.
METADATA_TAG = 'metadata'


def save_ora_image(image_stack: ImageStack, file_path: str,  metadata: str) -> None:
    """Save image layers in an editable state using the Open Raster specification."""
    # Create temporary directory structure
    tmpdir = tempfile.mkdtemp()
    data_dir_path = os.path.join(tmpdir, DATA_DIRECTORY_NAME)
    thumbnail_dir_path = os.path.join(tmpdir, THUMBNAIL_DIRECTORY_NAME)
    os.mkdir(data_dir_path)
    os.mkdir(thumbnail_dir_path)

    # Save layers and build xml data file:

    def _get_composite_op(mode: QPainter.CompositionMode) -> Optional[str]:
        mode_name = None
        for name, mode_type in COMPOSITION_MODES.items():
            if mode_type == mode:
                mode_name = name
                break
        if mode_name is None:
            return None
        for tag_value, display_name in ORA_COMPOSITION_MODES.items():
            if display_name == mode_name:
                return tag_value
        return None

    def _get_transform_str(transform: QTransform) -> str:
        return (f'{transform.m11()},{transform.m12()},{transform.m13()},'
                f'{transform.m21()},{transform.m22()},{transform.m23()},'
                f'{transform.m31()},{transform.m32()},{transform.m33()}')

    def encode_image_layer(layer: ImageLayer) -> Dict[str, Any]:
        """Encode an ImageLayer as image data."""
        layer_data: Dict[str, Any] = {
            DICT_ELEMENT_NAME: LAYER_ELEMENT,
            IMAGE_TAG_NAME: layer.name
        }
        composite_op_type = _get_composite_op(layer.composition_mode)
        if composite_op_type is not None:
            layer_data[ATTR_TAG_COMPOSITE] = composite_op_type
        layer_data[ATTR_TAG_OPACITY] = layer.opacity
        layer_data[ATTR_TAG_VISIBILITY] = ATTR_VISIBLE if layer.visible else ATTR_HIDDEN
        image_path = os.path.join(DATA_DIRECTORY_NAME, f'{layer.name}_{layer.id}.png')
        flattened_image, offset_transform = layer.transformed_image(True)
        layer_data[ATTR_TAG_X_POS] = round(offset_transform.dx())
        layer_data[ATTR_TAG_Y_POS] = round(offset_transform.dy())
        layer_data[LAYER_TAG_SRC] = image_path
        flattened_image.save(os.path.join(tmpdir, image_path))
        layer_transform = layer.transform
        if layer_transform != offset_transform:
            layer_data[TRANSFORM_TAG] = _get_transform_str(layer_transform)
            untransformed_path = os.path.join(DATA_DIRECTORY_NAME, f'{layer.name}_{layer.id}-untransformed.png')
            layer_data[TRANSFORM_SRC_TAG] = untransformed_path
            layer.image.save(os.path.join(tmpdir, untransformed_path))
        return layer_data

    def encode_layer_group(layer: LayerStack) -> Dict[str, Any]:
        """Encode a LayerStack as stack data."""
        stack_data: Dict[str, Any] = {
            DICT_ELEMENT_NAME: STACK_ELEMENT,
            ATTR_TAG_NAME: layer.name
        }
        composite_op_type = _get_composite_op(layer.composition_mode)
        if composite_op_type is not None:
            stack_data[ATTR_TAG_COMPOSITE] = composite_op_type
        stack_data[ATTR_TAG_OPACITY] = layer.opacity
        stack_data[ATTR_TAG_VISIBILITY] = ATTR_VISIBLE if layer.visible else ATTR_HIDDEN
        # TODO: properly support 'isolate' attribute in layer stacks
        stack_data[STACK_TAG_ISOLATION] = ISOLATION_AUTO
        transform = layer.transform
        if not transform.isIdentity():
            stack_data[TRANSFORM_TAG] = _get_transform_str(transform)
        stack_data[DICT_NESTED_CONTENT_NAME] = []
        for child_layer in layer.child_layers:
            if isinstance(child_layer, LayerStack):
                stack_data[DICT_NESTED_CONTENT_NAME].append(encode_layer_group(child_layer))
            else:
                assert isinstance(child_layer, ImageLayer)
                stack_data[DICT_NESTED_CONTENT_NAME].append(encode_image_layer(child_layer))
        return stack_data

    image_name = os.path.basename(file_path)
    if file_path.endswith(ORA_FILE_EXTENSION):
        image_name = image_name[:-len(ORA_FILE_EXTENSION)]
    else:
        file_path += ORA_FILE_EXTENSION

    image_data = {
        DICT_ELEMENT_NAME: IMAGE_ELEMENT,
        IMAGE_TAG_VERSION: ORA_SPEC_VERSION,
        IMAGE_TAG_WIDTH: image_stack.width,
        IMAGE_TAG_HEIGHT: image_stack.height,
        IMAGE_TAG_NAME: image_name,
        DICT_NESTED_CONTENT_NAME: [encode_layer_group(image_stack.layer_stack)]
    }

    if metadata is not None:
        image_data[METADATA_TAG] = metadata

    # Convert to XML:
    def _create_element(data_dict: Dict[str, Any]) -> Element:
        new_element = Element(data_dict[DICT_ELEMENT_NAME])
        for key, value in data_dict.items():
            if key == DICT_ELEMENT_NAME:
                continue
            if key == DICT_NESTED_CONTENT_NAME:
                assert isinstance(value, list)
                for child_dict in value:
                    assert isinstance(child_dict, dict)
                    child = _create_element(child_dict)
                    new_element.append(child)
            else:
                new_element.set(key, str(value))
        return new_element

    xml_root = ElementTree(_create_element(image_data))
    xml_root.write(os.path.join(tmpdir, XML_FILE_NAME))

    # Archive as .ora:
    tmp_save_path = file_path + '.tmp'
    with zipfile.ZipFile(tmp_save_path, 'w', compression=zipfile.ZIP_STORED) as zip_file:
        # Write mandatory MIMETYPE file:
        zip_file.writestr(MIMETYPE_FILE_NAME, MIMETYPE_FILE_CONTENT)

        # Create merged image file:
        merged_image = image_stack.qimage(True)
        tmp_merged_path = os.path.join(tmpdir, 'merged.png')
        merged_image.save(tmp_merged_path)
        zip_file.write(tmp_merged_path, MERGED_IMAGE_FILE_NAME)

        # Create thumbnail:
        thumbnail_size = get_scaled_placement(QSize(256, 256), merged_image.size()).size()
        thumbnail = merged_image.scaled(thumbnail_size)
        tmp_thumbnail_path = os.path.join(tmpdir, THUMBNAIL_FILE_NAME)
        thumbnail.save(tmp_thumbnail_path)
        zip_file.write(tmp_thumbnail_path, os.path.join(THUMBNAIL_DIRECTORY_NAME, THUMBNAIL_FILE_NAME))

        zip_file.write(os.path.join(tmpdir, XML_FILE_NAME), XML_FILE_NAME)
        element_data = [image_data]
        while len(element_data) > 0:
            element = element_data.pop()
            for img_tag in [LAYER_TAG_SRC, TRANSFORM_SRC_TAG]:
                if img_tag in element:
                    img_path = str(element[img_tag])
                    zip_file.write(os.path.join(tmpdir, img_path), img_path)
            if DICT_NESTED_CONTENT_NAME in element:
                for nested in cast(list, element[DICT_NESTED_CONTENT_NAME]):
                    element_data.append(nested)
    shutil.move(tmp_save_path, file_path)
    shutil.rmtree(tmpdir)


def read_ora_image(image_stack: ImageStack, file_path: str) -> Optional[str]:
    """Read a .ora file into the image stack, returning metadata."""
    tmpdir = tempfile.mkdtemp()
    shutil.unpack_archive(file_path, tmpdir, format='zip')

    def _parse_common_attributes(layer: Layer, element: Element):
        layer_name = element.get(ATTR_TAG_NAME, 'layer')
        layer.set_name(layer_name)
        if ATTR_TAG_VISIBILITY in element.keys():
            visible = element.get(ATTR_TAG_VISIBILITY) == ATTR_VISIBLE
            layer.set_visible(visible)
        if ATTR_TAG_OPACITY in element.keys():
            opacity = float(str(element.get(ATTR_TAG_OPACITY)))
            layer.set_opacity(opacity)
        if ATTR_TAG_COMPOSITE in element.keys():
            comp_mode = COMPOSITION_MODES[ORA_COMPOSITION_MODES[str(element.get(ATTR_TAG_COMPOSITE))]]
            layer.set_composition_mode(comp_mode)
        if TRANSFORM_TAG in element.keys():
            matrix_elements = [float(elem) for elem in str(element.get(TRANSFORM_TAG)).split(',')]
            transform = QTransform(*matrix_elements)
            layer.set_transform(transform)
        elif ATTR_TAG_X_POS in element.keys() and ATTR_TAG_Y_POS in element.keys():
            x = float(str(element.get(ATTR_TAG_X_POS)))
            y = float(str(element.get(ATTR_TAG_Y_POS)))
            transform = QTransform.fromTranslate(x, y)
            layer.set_transform(transform)

    def parse_image_element(element: Element) -> ImageLayer:
        """Load an image layer from its saved XML definition"""
        assert element.tag == LAYER_ELEMENT
        if TRANSFORM_SRC_TAG in element.keys():
            img_path = os.path.join(tmpdir, str(element.get(TRANSFORM_SRC_TAG)))
        else:
            img_path = os.path.join(tmpdir, str(element.get(LAYER_TAG_SRC)))
        layer_image = QImage(img_path)
        layer = ImageLayer(layer_image, '')
        _parse_common_attributes(layer, element)
        return layer

    def parse_stack_element(element: Element) -> LayerStack:
        """Load a layer group from its saved XML definition"""
        assert element.tag == STACK_ELEMENT
        layer = LayerStack('')
        _parse_common_attributes(layer, element)
        for child_element in element:
            if child_element.tag == STACK_ELEMENT:
                child_layer = parse_stack_element(child_element)
            elif child_element.tag == LAYER_ELEMENT:
                child_layer = parse_image_element(child_element)
            else:
                continue
            layer.insert_layer(child_layer, layer.count)
        return layer

    xml_path = os.path.join(tmpdir, XML_FILE_NAME)
    xml_root = ElementTree().parse(xml_path)
    assert xml_root.tag == IMAGE_ELEMENT, f'Unexpected tag "{xml_root.tag}"'
    img_size = QSize(int(str(xml_root.get(IMAGE_TAG_WIDTH))), int(str(xml_root.get(IMAGE_TAG_HEIGHT))))
    layer_stack = parse_stack_element(xml_root[0])
    metadata = xml_root.get(METADATA_TAG, None)
    image_stack.load_layer_stack(layer_stack, img_size)
    return metadata

