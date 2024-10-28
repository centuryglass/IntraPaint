"""Provides compatibility between the OpenRaster file format and ImageStack object data.

Open Raster specification:
https://www.openraster.org/baseline/file-layout-spec.html

XML file spec:
https://invent.kde.org/documentation/openraster-org/-/blob/master/openraster-standard/schema.rnc
"""
import logging
import os.path
import shutil
import tempfile
import zipfile
from typing import Optional, Any, cast
from xml.etree.ElementTree import ElementTree, Element

from PySide6.QtCore import QSize
from PySide6.QtGui import QTransform, QImage

from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.text_layer import TextLayer
from src.util.visual.geometry_utils import get_scaled_placement

logger = logging.getLogger(__name__)

# Zipped file directory structure:
ORA_FILE_EXTENSION = '.ora'
MIMETYPE_FILE_NAME = 'mimetype'
MIMETYPE_FILE_CONTENT = 'image/openraster'
XML_FILE_NAME = 'stack.xml'
EXTENDED_DATA_XML_FILE_NAME = 'extended_data.xml'
DATA_DIRECTORY_NAME = 'data'
THUMBNAIL_DIRECTORY_NAME = 'Thumbnails'
THUMBNAIL_FILE_NAME = 'thumbnail.png'
MERGED_IMAGE_FILE_NAME = 'mergedimage'

BOOLEAN_TRUE_STR = 'true'
# BOOLEAN_FALSE_STR = 'false'

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
# IMAGE_TAG_XRES = 'xres'  # int, optional (pixels per inch)
# IMAGE_TAG_YRES = 'yres'  # int, optional (pixels per inch)
IMAGE_TAG_NAME = 'name'  # str

# layerCommonAttributes XML tags:
ATTR_TAG_NAME = 'name'  # str, optional
ATTR_TAG_COMPOSITE = 'composite-op'  # str, optional
ATTR_TAG_OPACITY = 'opacity'  # str, optional
ATTR_TAG_VISIBILITY = 'visibility'  # str, optional
ATTR_TAG_EDIT_LOCKED = 'edit-locked'  # str, optional (official format extension)
ATTR_TAG_SELECTED = 'selected'  # str, optional (official format extension)
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

# IntraPaint extensions to the format:

# Extended transformation support:
# Layer and stack elements may include 'transform' tag, a comma-separated list of floating-point matrix elements. If the
# transform tag is provided, a second src_untransformed image tag should be included, pointing to another copy of the
# layer image where those transformations have not been applied. When loading an image with a transform tag, the usual
# position tags can be ignored.
TRANSFORM_TAG = 'transformation'
TRANSFORM_SRC_TAG = 'src_untransformed'
ATTR_TAG_ALPHA_LOCKED = 'alpha-locked'  # str, optional

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
    extended_data: dict[str, dict[str, str]] = {}

    def _get_transform_str(transform: QTransform) -> str:
        return (f'{transform.m11()},{transform.m12()},{transform.m13()},'
                f'{transform.m21()},{transform.m22()},{transform.m23()},'
                f'{transform.m31()},{transform.m32()},{transform.m33()}')

    def encode_image_layer(layer: ImageLayer | TextLayer) -> dict[str, Any]:
        """Encode an ImageLayer as image data."""
        layer_data: dict[str, Any] = {
            DICT_ELEMENT_NAME: LAYER_ELEMENT,
            IMAGE_TAG_NAME: layer.name
        }
        composite_op_type = layer.composition_mode
        if composite_op_type is not None:
            layer_data[ATTR_TAG_COMPOSITE] = composite_op_type.openraster_composite_mode()
        if layer.locked:
            layer_data[ATTR_TAG_EDIT_LOCKED] = BOOLEAN_TRUE_STR
        if layer == image_stack.active_layer:
            layer_data[ATTR_TAG_SELECTED] = BOOLEAN_TRUE_STR
        layer_data[ATTR_TAG_OPACITY] = layer.opacity
        layer_data[ATTR_TAG_VISIBILITY] = ATTR_VISIBLE if layer.get_visible() else ATTR_HIDDEN
        image_path = os.path.join(DATA_DIRECTORY_NAME, f'{layer.name}_{layer.id}.png')
        flattened_image, offset_transform = layer.transformed_image()
        layer_data[ATTR_TAG_X_POS] = round(offset_transform.dx())
        layer_data[ATTR_TAG_Y_POS] = round(offset_transform.dy())
        layer_data[LAYER_TAG_SRC] = image_path
        flattened_image.save(os.path.join(tmpdir, image_path))

        # Store untransformed images and transformations in a separate extended data section:
        layer_transform = layer.transform
        if layer_transform != offset_transform or (isinstance(layer, ImageLayer) and layer.alpha_locked):
            extended_layer_data: dict[str, str] = {}
            if isinstance(layer, ImageLayer) and layer.alpha_locked:
                extended_layer_data[ATTR_TAG_ALPHA_LOCKED] = BOOLEAN_TRUE_STR
            if layer_transform != offset_transform:
                layer_transform_str = _get_transform_str(layer_transform)
                layer_untransformed_path = os.path.join(DATA_DIRECTORY_NAME,
                                                        f'{layer.name}_{layer.id}-untransformed.png')
                full_untransformed_path = os.path.join(tmpdir, layer_untransformed_path)
                assert layer.image.save(full_untransformed_path), f'failed to write to {full_untransformed_path}'
                extended_layer_data[TRANSFORM_SRC_TAG] = layer_untransformed_path
                extended_layer_data[TRANSFORM_TAG] = layer_transform_str
            extended_data[image_path] = extended_layer_data
        return layer_data

    def encode_layer_group(layer: LayerGroup) -> dict[str, Any]:
        """Encode a LayerGroup as stack data."""
        stack_data: dict[str, Any] = {
            DICT_ELEMENT_NAME: STACK_ELEMENT,
            ATTR_TAG_NAME: layer.name
        }
        composite_op_type = layer.composition_mode.openraster_composite_mode()
        if composite_op_type is not None:
            stack_data[ATTR_TAG_COMPOSITE] = composite_op_type
        if layer.locked:
            stack_data[ATTR_TAG_EDIT_LOCKED] = BOOLEAN_TRUE_STR
        if layer == image_stack.active_layer:
            stack_data[ATTR_TAG_SELECTED] = BOOLEAN_TRUE_STR
        stack_data[ATTR_TAG_OPACITY] = layer.opacity
        stack_data[ATTR_TAG_VISIBILITY] = ATTR_VISIBLE if layer.get_visible() else ATTR_HIDDEN
        stack_data[STACK_TAG_ISOLATION] = ISOLATION_ISOLATE if layer.isolate else ISOLATION_AUTO
        stack_data[DICT_NESTED_CONTENT_NAME] = []
        for child_layer in layer.child_layers:
            if isinstance(child_layer, LayerGroup):
                stack_data[DICT_NESTED_CONTENT_NAME].append(encode_layer_group(child_layer))
            else:
                assert isinstance(child_layer, (ImageLayer, TextLayer))
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

    # Convert to XML, write XML file structure:

    def _create_element(data_dict: dict[str, Any]) -> Element:
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

    # Write non-standard layer info (transformations, untransformed layers) to a different xml file:
    xml_root = ElementTree(_create_element(image_data))
    xml_root.write(os.path.join(tmpdir, XML_FILE_NAME))

    extended_xml_root = Element(STACK_ELEMENT)
    for image_file_path, layer_extended_data in extended_data.items():
        extended_layer = Element(LAYER_ELEMENT)
        extended_layer.set(LAYER_TAG_SRC, image_file_path)
        for extension_tag in [TRANSFORM_TAG, TRANSFORM_SRC_TAG, ATTR_TAG_ALPHA_LOCKED]:
            if extension_tag in layer_extended_data:
                extended_layer.set(extension_tag, layer_extended_data[extension_tag])
        extended_xml_root.append(extended_layer)
    if metadata is not None:
        extended_xml_root.set(METADATA_TAG, metadata)
        image_data[METADATA_TAG] = metadata
    extended_xml_tree = ElementTree(extended_xml_root)
    extended_xml_tree.write(os.path.join(tmpdir, EXTENDED_DATA_XML_FILE_NAME))

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
        zip_file.write(os.path.join(tmpdir, EXTENDED_DATA_XML_FILE_NAME), EXTENDED_DATA_XML_FILE_NAME)
        element_data = [image_data]
        while len(element_data) > 0:
            element = element_data.pop()
            if LAYER_TAG_SRC in element:
                img_path = str(element[LAYER_TAG_SRC])
                zip_file.write(os.path.join(tmpdir, img_path), img_path)
            if DICT_NESTED_CONTENT_NAME in element:
                for nested in cast(list, element[DICT_NESTED_CONTENT_NAME]):
                    element_data.append(nested)
        for _, extended_params in extended_data.items():
            if TRANSFORM_SRC_TAG in extended_params:
                untransformed_path = extended_params[TRANSFORM_SRC_TAG]
                zip_file.write(os.path.join(tmpdir, untransformed_path), untransformed_path)
    shutil.move(tmp_save_path, file_path)
    shutil.rmtree(tmpdir)


def read_ora_image(image_stack: ImageStack, file_path: str) -> Optional[str]:
    """Read a .ora file into the image stack, returning metadata."""
    tmpdir = tempfile.mkdtemp()
    with zipfile.ZipFile(file_path) as zip_file:
        zip_file.extractall(tmpdir)

    extended_xml_path = os.path.join(tmpdir, EXTENDED_DATA_XML_FILE_NAME)
    metadata = None
    extended_data: dict[str, dict[str, Any]] = {}
    if os.path.isfile(extended_xml_path):
        extended_xml_root = ElementTree().parse(extended_xml_path)
        metadata = extended_xml_root.get(METADATA_TAG)
        for extended_layer in extended_xml_root:
            extended_layer_data = {}
            flattened_image_path = extended_layer.get(LAYER_TAG_SRC)
            assert flattened_image_path is not None
            transform_image_path = extended_layer.get(TRANSFORM_SRC_TAG)
            if transform_image_path is not None:
                transform_image_full_path = os.path.join(tmpdir, transform_image_path)
                assert os.path.isfile(transform_image_full_path), f'missing file: {transform_image_full_path}'
                transform_image = QImage(transform_image_full_path)
                assert not transform_image.isNull(), f'loading failed: {transform_image_full_path}'
                extended_layer_data[TRANSFORM_SRC_TAG] = transform_image
                matrix_elements = [float(elem) for elem in str(extended_layer.get(TRANSFORM_TAG)).split(',')]
                transform = QTransform(*matrix_elements)
                extended_layer_data[TRANSFORM_TAG] = transform
                extended_layer_data[ATTR_TAG_ALPHA_LOCKED] = extended_layer.get(ATTR_TAG_ALPHA_LOCKED)
            extended_data[flattened_image_path] = extended_layer_data

    def _parse_common_attributes(layer: Layer, element: Element) -> bool:
        """Parse shared attributes, return whether this layer is selected."""
        layer_name = element.get(ATTR_TAG_NAME, 'layer')
        layer.set_name(layer_name)
        if ATTR_TAG_VISIBILITY in element.keys():
            visible = element.get(ATTR_TAG_VISIBILITY) == ATTR_VISIBLE
            layer.set_visible(visible)
        if element.get(ATTR_TAG_EDIT_LOCKED) == BOOLEAN_TRUE_STR:
            layer.set_locked(True)
        if ATTR_TAG_OPACITY in element.keys():
            opacity = float(str(element.get(ATTR_TAG_OPACITY)))
            layer.set_opacity(opacity)
        if ATTR_TAG_COMPOSITE in element.keys():
            composite_op = str(element.get(ATTR_TAG_COMPOSITE))
            try:
                comp_mode = CompositeMode.from_ora_name(composite_op)
                if comp_mode is None:
                    logger.error(f'Unsupported layer composite mode {composite_op} ignored')
                else:
                    layer.set_composition_mode(comp_mode)
            except ValueError:
                logger.error(f'Unrecognised layer composite mode {composite_op} ignored')
        return element.get(ATTR_TAG_SELECTED) == BOOLEAN_TRUE_STR

    def parse_image_element(element: Element) -> tuple[ImageLayer, bool]:
        """Load an image layer from its saved XML definition, return whether this layer is selected."""
        assert element.tag == LAYER_ELEMENT
        base_image_path = element.get(LAYER_TAG_SRC)
        assert base_image_path is not None
        layer_image = QImage()
        layer_transform = QTransform()
        alpha_locked = None
        if base_image_path in extended_data:
            extended_layer_load_data = extended_data[base_image_path]
            if TRANSFORM_SRC_TAG in extended_layer_load_data:
                layer_image = extended_layer_load_data[TRANSFORM_SRC_TAG]
                layer_transform = extended_layer_load_data[TRANSFORM_TAG]
            if ATTR_TAG_ALPHA_LOCKED in extended_layer_load_data:
                alpha_locked = extended_layer_load_data[ATTR_TAG_ALPHA_LOCKED]
        if layer_image.isNull():
            layer_image = QImage(os.path.join(tmpdir, base_image_path))
        layer = ImageLayer(layer_image, '')
        is_active = _parse_common_attributes(layer, element)
        if alpha_locked == BOOLEAN_TRUE_STR:
            layer.set_alpha_locked(True)
        if not layer_transform.isIdentity():
            layer.set_transform(layer_transform)
        elif ATTR_TAG_X_POS in element.keys() and ATTR_TAG_Y_POS in element.keys():
            x = float(str(element.get(ATTR_TAG_X_POS)))
            y = float(str(element.get(ATTR_TAG_Y_POS)))
            layer_transform = QTransform.fromTranslate(x, y)
            layer.set_transform(layer_transform)
        return layer, is_active

    def parse_stack_element(element: Element) -> tuple[LayerGroup, Optional[Layer]]:
        """Load a layer group from its saved XML definition, return the selected layer (if found)"""
        assert element.tag == STACK_ELEMENT
        layer = LayerGroup('')
        active_layer = None
        if _parse_common_attributes(layer, element):
            active_layer = layer
        if STACK_TAG_ISOLATION in element.keys() and element.get(STACK_TAG_ISOLATION) == ISOLATION_ISOLATE:
            layer.isolate = True
        for child_element in element:
            is_active = False
            if child_element.tag == STACK_ELEMENT:
                child_layer, active_layer = parse_stack_element(child_element)
            elif child_element.tag == LAYER_ELEMENT:
                child_layer, is_active = parse_image_element(child_element)
            else:
                continue
            if is_active:
                active_layer = child_layer
            layer.insert_layer(child_layer, layer.count)
        return layer, active_layer

    xml_path = os.path.join(tmpdir, XML_FILE_NAME)
    xml_root = ElementTree().parse(xml_path)
    assert xml_root.tag == IMAGE_ELEMENT, f'Unexpected tag "{xml_root.tag}"'
    img_size = QSize(int(str(xml_root.get(IMAGE_TAG_WIDTH))), int(str(xml_root.get(IMAGE_TAG_HEIGHT))))
    layer_stack, saved_active_layer = parse_stack_element(xml_root[0])
    image_stack.load_layer_stack(layer_stack, img_size, saved_active_layer)
    return metadata
