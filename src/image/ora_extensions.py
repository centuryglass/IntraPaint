"""Extension points for the IntraPaint data `open_raster` stores in .ora files beyond the OpenRaster baseline.

Two kinds of extension exist, both stored in `extended_data.xml`:

- **Layer extensions.** A layer's `<layer src="...">` entry carries extra attributes, written from
  `NonDestructiveLayer.ora_extension_data`. A loader registered with `register_layer_loader` claims entries that have
  its tag and builds the layer. Entries nobody claims load as image layers from their PNG.
- **Document extensions.** Data that isn't a layer (a layer reference held by a ControlNet unit, prompt-region masks,
  guides, foreign data carried through a load and save) goes in `<extension name="...">` children of the root, with a
  text payload and any number of files under `data/extensions/<name>/`. A `DocumentExtension` registered with
  `register_document_extension` writes and reads it.

This module imports no layer classes, so layer modules can use it. `open_raster` owns the archive layout and drives
both registries.
"""
import os
import posixpath
from dataclasses import dataclass
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.image.layers.image_stack import ImageStack
    from src.image.layers.layer import Layer

EXTENSION_ELEMENT = 'extension'
EXTENSION_TAG_NAME = 'name'
LAYER_FILE_DIRECTORY = 'data'
EXTENSION_DIRECTORY = 'data/extensions'


def _safe_relative_path(path: str) -> str:
    """Returns path normalized to '/' separators, raising ValueError unless it stays inside its directory."""
    normalized = posixpath.normpath(path.replace('\\', '/'))
    if normalized in ('', '.') or normalized.startswith(('/', '../')) or normalized == '..' or ':' in normalized:
        raise ValueError(f'Invalid extension file path "{path}"')
    return normalized


class OraWriteContext:
    """Collects the files an extension adds to the archive while saving.

    Layer extensions write under `data/`. Document extensions get a context from `for_extension`."""

    def __init__(self, archive_directory: str = LAYER_FILE_DIRECTORY) -> None:
        self._archive_directory = archive_directory
        self._files: dict[str, bytes] = {}

    def for_extension(self, name: str) -> 'OraWriteContext':
        """Returns a context that shares this one's file collection and writes under the named extension's folder."""
        child = OraWriteContext(posixpath.join(EXTENSION_DIRECTORY, _safe_relative_path(name)))
        child._files = self._files  # pylint: disable=protected-access
        return child

    @property
    def files(self) -> dict[str, bytes]:
        """Returns every file written so far, keyed by archive path."""
        return self._files

    def write_file(self, relative_path: str, data: bytes) -> str:
        """Adds a file to the archive and returns its archive path, which the extension stores to find it on load.

        Raises ValueError if `relative_path` would leave this extension's directory.
        """
        archive_path = posixpath.join(self._archive_directory, _safe_relative_path(relative_path))
        self._files[archive_path] = data
        return archive_path


class OraReadContext:
    """Reads files from the archive being loaded, which `open_raster` has extracted to a directory."""

    def __init__(self, extracted_directory: str) -> None:
        self._directory = extracted_directory

    def read_file(self, archive_path: str) -> Optional[bytes]:
        """Returns a file's content, or None if the archive has no file at that path (or the path is invalid)."""
        try:
            full_path = os.path.join(self._directory, *_safe_relative_path(archive_path).split('/'))
        except ValueError:
            return None
        if not os.path.isfile(full_path):
            return None
        with open(full_path, 'rb') as file:
            return file.read()


LayerLoader = Callable[[dict[str, str], OraReadContext], Optional['Layer']]
"""Builds a layer from an `extended_data.xml` entry's attributes, or returns None to load an image layer instead.
`open_raster` then applies the common layer attributes and transform."""


@dataclass(frozen=True)
class DocumentExtension:
    """Reads and writes one named piece of document-level data."""

    name: str
    """Unique, file-name-safe identifier, stored as the element's `name` attribute."""

    save: Callable[['ImageStack', OraWriteContext], Optional[str]]
    """Returns the text payload to store, or None to store nothing. Files go through the context."""

    load: Callable[['ImageStack', str, OraReadContext], None]
    """Restores the data into the loaded image stack from the stored payload."""


_layer_loaders: dict[str, LayerLoader] = {}
_document_extensions: dict[str, DocumentExtension] = {}


def register_layer_loader(attribute_tag: str, loader: LayerLoader) -> None:
    """Registers a loader for layer entries carrying `attribute_tag`. The first registered tag present wins."""
    _layer_loaders[attribute_tag] = loader


def unregister_layer_loader(attribute_tag: str) -> None:
    """Removes a layer loader, if registered."""
    _layer_loaders.pop(attribute_tag, None)


def layer_loaders() -> dict[str, LayerLoader]:
    """Returns the registered layer loaders in registration order."""
    return dict(_layer_loaders)


def register_document_extension(extension: DocumentExtension) -> None:
    """Registers a document-level extension, replacing any with the same name."""
    _safe_relative_path(extension.name)
    _document_extensions[extension.name] = extension


def unregister_document_extension(name: str) -> None:
    """Removes a document extension, if registered."""
    _document_extensions.pop(name, None)


def document_extensions() -> dict[str, DocumentExtension]:
    """Returns the registered document extensions in registration order."""
    return dict(_document_extensions)
