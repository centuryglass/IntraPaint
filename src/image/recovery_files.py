"""Reads and writes the crash recovery copies that `AutosaveController` keeps of the open document.

Each running instance owns one session folder under `recovery_root()`:

- `lock` holds the owning process ID. A folder whose process isn't running belongs to a session that crashed.
- `files/` holds one PNG per layer image, named by layer id, role and the generation that wrote it, plus
  content-addressed copies of extension and foreign files and the thumbnail.
- `manifest.json` holds everything else: the `stack.xml` and `extended_data.xml` that `open_raster` would write, the
  generation area, the original file path, and which file holds each archive path. Metadata is in the XML and
  archive files, as in an .ora save. Manifests from older versions also hold EXIF data under `KEY_EXIF`.

The manifest is the commit point. `write_recovery` writes every new file first, then replaces the manifest through a
temporary file and `os.replace`, then deletes files the new manifest doesn't name. A crash at any point leaves the
previous manifest and every file it names readable. Restoring rebuilds an .ora archive from the folder and loads it
with `read_ora_image`, so recovery supports exactly what .ora saves support.
"""
import base64
import hashlib
import json
import logging
import os
import shutil
import sys
import tempfile
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from typing import Any, Optional

from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QImage

from src.image.image_metadata import ImageMetadata
from src.image.layers.image_stack import ImageStack
from src.image.open_raster import (OraSnapshot, ora_xml_files, read_ora_image, MIMETYPE_FILE_NAME,
                                   MIMETYPE_FILE_CONTENT, IMAGE_TAG_WIDTH, IMAGE_TAG_HEIGHT)
from src.image.ora_metadata import load_exif
from src.util.shared_constants import DATA_DIR
from src.util.visual.image_utils import read_qimage

logger = logging.getLogger(__name__)

RECOVERY_DIR_NAME = 'recovery'
LOCK_FILE_NAME = 'lock'
MANIFEST_FILE_NAME = 'manifest.json'
MANIFEST_TMP_FILE_NAME = 'manifest.json.tmp'
FILES_DIR_NAME = 'files'

# Bump when the manifest changes incompatibly. A manifest with another version is never offered or deleted.
MANIFEST_VERSION = 1

# Qt maps PNG quality 100 to no compression, which encodes several times faster than the default.
RECOVERY_PNG_QUALITY = 100

# Manifest keys:
KEY_VERSION = 'version'
KEY_GENERATION = 'generation'
KEY_SAVED_AT = 'saved_at'
KEY_ORIGINAL_PATH = 'original_path'
KEY_IMAGE_SIZE = 'image_size'
KEY_GENERATION_AREA = 'generation_area'
KEY_EXIF = 'exif'  # Read only, from manifests written before EXIF data was stored in the archive files.
KEY_XML_FILES = 'xml_files'
KEY_ARCHIVE_FILES = 'archive_files'
KEY_FOREIGN_FILES = 'foreign_files'
KEY_THUMBNAIL = 'thumbnail'
KEY_FILE = 'file'
KEY_COMPRESS_TYPE = 'compress_type'
KEY_DATE_TIME = 'date_time'


def recovery_root() -> str:
    """Returns the directory that holds every instance's session folder."""
    return os.path.join(DATA_DIR, RECOVERY_DIR_NAME)


def process_is_running(pid: int) -> bool:
    """Returns whether a process with this ID exists. A process this one can't inspect counts as running."""
    if pid <= 0:
        return False
    if sys.platform == 'win32':
        # os.kill(pid, 0) terminates the process on Windows, so ask the kernel instead.
        import ctypes  # pylint: disable=import-outside-toplevel
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        process_query_limited_information = 0x1000
        still_active = 259
        error_access_denied = 5
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return kernel32.GetLastError() == error_access_denied
        try:
            exit_code = ctypes.c_ulong(0)
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def create_session_dir(root: Optional[str] = None) -> str:
    """Creates a session folder owned by this process, and returns its path."""
    root = recovery_root() if root is None else root
    session_dir = os.path.join(root, f'{os.getpid()}-{uuid.uuid4().hex[:8]}')
    os.makedirs(os.path.join(session_dir, FILES_DIR_NAME))
    with open(os.path.join(session_dir, LOCK_FILE_NAME), 'w', encoding='utf-8') as lock_file:
        lock_file.write(str(os.getpid()))
    return session_dir


def delete_session(session_dir: str) -> None:
    """Deletes a session folder and everything in it."""
    shutil.rmtree(session_dir, ignore_errors=True)


def clear_manifest(session_dir: str) -> None:
    """Removes a session's manifest, so it offers nothing for recovery, and keeps its files for the next write."""
    for name in (MANIFEST_FILE_NAME, MANIFEST_TMP_FILE_NAME):
        try:
            os.remove(os.path.join(session_dir, name))
        except FileNotFoundError:
            pass


def _read_lock_pid(session_dir: str) -> Optional[int]:
    try:
        with open(os.path.join(session_dir, LOCK_FILE_NAME), encoding='utf-8') as lock_file:
            return int(lock_file.read().strip())
    except (OSError, ValueError):
        return None


@dataclass
class RecoveryWrite:
    """One autosave, ready for `write_recovery` to write on a worker thread.

    `plan_recovery_write` builds it on the GUI thread. It holds only plain data and unshared `QImage` copies.
    """
    session_dir: str
    manifest: dict[str, Any]
    images: dict[str, QImage]
    """New layer images by file name, each written once."""
    blobs: dict[str, bytes]
    """Extension and foreign files by file name. The name comes from the content, so an existing file is kept."""
    thumbnail: Optional[QImage]
    layer_files: dict[tuple[int, str], str] = field(default_factory=dict)
    """The file holding each (layer id, role) image after this write, for the next write to reuse."""


def plan_recovery_write(snapshot: OraSnapshot, session_dir: str, generation: int,
                        previous_layer_files: dict[tuple[int, str], str], original_path: str,
                        generation_area: QRect, thumbnail: Optional[QImage]) -> tuple[RecoveryWrite, set[int]]:
    """Builds an autosave from a snapshot, reusing `previous_layer_files` for layers the snapshot skipped.

    Returns the write and the ids of skipped layers with no previous file. When that set isn't empty, the write is
    incomplete: capture those layers' pixels and plan again.
    """
    images: dict[str, QImage] = {}
    archive_files: dict[str, str] = {}
    layer_files: dict[tuple[int, str], str] = {}
    missing: set[int] = set()
    for archive_path, owner in snapshot.layer_image_owners.items():
        layer_id, role = owner
        if archive_path in snapshot.layer_images:
            file_name = f'{layer_id}-{role}-{generation}.png'
            images[file_name] = snapshot.layer_images[archive_path]
        elif owner in previous_layer_files:
            file_name = previous_layer_files[owner]
        else:
            missing.add(layer_id)
            continue
        archive_files[archive_path] = file_name
        layer_files[owner] = file_name
    blobs: dict[str, bytes] = {}
    for archive_path, data in snapshot.extension_files.items():
        archive_files[archive_path] = _blob_name(data)
        blobs[archive_files[archive_path]] = data
    foreign_files: dict[str, dict[str, Any]] = {}
    for archive_path, foreign_file in snapshot.foreign_files.items():
        file_name = _blob_name(foreign_file.data)
        blobs[file_name] = foreign_file.data
        foreign_files[archive_path] = {KEY_FILE: file_name, KEY_COMPRESS_TYPE: foreign_file.compress_type,
                                       KEY_DATE_TIME: list(foreign_file.date_time)}
    xml_files = {path: data.decode('ascii') for path, data in ora_xml_files(snapshot).items()}
    size = QSize(int(snapshot.image_data[IMAGE_TAG_WIDTH]), int(snapshot.image_data[IMAGE_TAG_HEIGHT]))
    manifest: dict[str, Any] = {
        KEY_VERSION: MANIFEST_VERSION,
        KEY_GENERATION: generation,
        KEY_SAVED_AT: time.time(),
        KEY_ORIGINAL_PATH: original_path,
        KEY_IMAGE_SIZE: [size.width(), size.height()],
        KEY_GENERATION_AREA: [generation_area.x(), generation_area.y(), generation_area.width(),
                              generation_area.height()],
        KEY_XML_FILES: xml_files,
        KEY_ARCHIVE_FILES: archive_files,
        KEY_FOREIGN_FILES: foreign_files,
        KEY_THUMBNAIL: None if thumbnail is None else f'thumbnail-{generation}.png'
    }
    write = RecoveryWrite(session_dir, manifest, images, blobs, thumbnail, layer_files)
    return write, missing


def _blob_name(data: bytes) -> str:
    return f'blob-{hashlib.sha1(data).hexdigest()}'


def write_recovery(write: RecoveryWrite) -> None:
    """Writes an autosave's new files, then commits its manifest, then deletes files the manifest doesn't name.

    Touches no `Layer` or Qt widget objects, so it is safe to run on a worker thread. Raises OSError on failure, which
    leaves the previous manifest in place.
    """
    files_dir = os.path.join(write.session_dir, FILES_DIR_NAME)
    os.makedirs(files_dir, exist_ok=True)
    manifest = write.manifest
    for file_name, image in write.images.items():
        if not image.save(os.path.join(files_dir, file_name), 'PNG', RECOVERY_PNG_QUALITY):
            raise OSError(f'failed to write {file_name}')
    if write.thumbnail is not None:
        assert manifest[KEY_THUMBNAIL] is not None
        if not write.thumbnail.save(os.path.join(files_dir, manifest[KEY_THUMBNAIL]), 'PNG'):
            raise OSError('failed to write the recovery thumbnail')
    for file_name, data in write.blobs.items():
        blob_path = os.path.join(files_dir, file_name)
        if not os.path.isfile(blob_path):
            with open(blob_path, 'wb') as blob_file:
                blob_file.write(data)

    tmp_manifest_path = os.path.join(write.session_dir, MANIFEST_TMP_FILE_NAME)
    with open(tmp_manifest_path, 'w', encoding='utf-8') as manifest_file:
        json.dump(manifest, manifest_file)
    os.replace(tmp_manifest_path, os.path.join(write.session_dir, MANIFEST_FILE_NAME))

    referenced = _referenced_files(manifest)
    for name in os.listdir(files_dir):
        if name not in referenced:
            try:
                os.remove(os.path.join(files_dir, name))
            except OSError as err:
                logger.warning(f'Could not remove old recovery file {name}: {err}')


def _referenced_files(manifest: dict[str, Any]) -> set[str]:
    referenced = set(manifest[KEY_ARCHIVE_FILES].values())
    referenced.update(entry[KEY_FILE] for entry in manifest[KEY_FOREIGN_FILES].values())
    if manifest.get(KEY_THUMBNAIL) is not None:
        referenced.add(manifest[KEY_THUMBNAIL])
    return referenced


@dataclass(frozen=True)
class RecoverableSession:
    """A crashed session's folder and its last complete autosave."""
    session_dir: str
    manifest: dict[str, Any]

    @property
    def original_path(self) -> str:
        """Returns the path the document was opened from or last saved to, or '' if it was never saved."""
        return str(self.manifest[KEY_ORIGINAL_PATH])

    @property
    def saved_at(self) -> float:
        """Returns the time of the last autosave, in seconds since the epoch."""
        return float(self.manifest[KEY_SAVED_AT])

    def thumbnail(self) -> Optional[QImage]:
        """Returns the document's thumbnail as of the last autosave, if it has one."""
        name = self.manifest.get(KEY_THUMBNAIL)
        if name is None:
            return None
        image = read_qimage(os.path.join(self.session_dir, FILES_DIR_NAME, name))
        return None if image.isNull() else image


def read_manifest(session_dir: str) -> Optional[dict[str, Any]]:
    """Returns a session's last committed manifest, or None if it has none or it can't be used."""
    try:
        with open(os.path.join(session_dir, MANIFEST_FILE_NAME), encoding='utf-8') as manifest_file:
            manifest = json.load(manifest_file)
        if not isinstance(manifest, dict) or manifest.get(KEY_VERSION) != MANIFEST_VERSION:
            return None
        files_dir = os.path.join(session_dir, FILES_DIR_NAME)
        for name in _referenced_files(manifest):
            if not os.path.isfile(os.path.join(files_dir, name)):
                logger.warning(f'Recovery file {name} is missing from {session_dir}')
                return None
        return manifest
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as err:
        if not isinstance(err, FileNotFoundError):
            logger.warning(f'Unreadable recovery manifest in {session_dir}: {err}')
        return None


def find_recoverable_sessions(root: Optional[str] = None) -> list[RecoverableSession]:
    """Returns crashed sessions with something to restore, newest first.

    Skips folders whose process is running, including this one's. Deletes crashed sessions that have nothing to
    restore. A manifest with another `MANIFEST_VERSION` is left alone.
    """
    root = recovery_root() if root is None else root
    if not os.path.isdir(root):
        return []
    sessions: list[RecoverableSession] = []
    for name in os.listdir(root):
        session_dir = os.path.join(root, name)
        if not os.path.isdir(session_dir):
            continue
        pid = _read_lock_pid(session_dir)
        if pid is not None and (pid == os.getpid() or process_is_running(pid)):
            continue
        manifest = read_manifest(session_dir)
        if manifest is not None:
            sessions.append(RecoverableSession(session_dir, manifest))
        elif not _has_other_version_manifest(session_dir):
            delete_session(session_dir)
    sessions.sort(key=lambda session: session.saved_at, reverse=True)
    return sessions


def _has_other_version_manifest(session_dir: str) -> bool:
    try:
        with open(os.path.join(session_dir, MANIFEST_FILE_NAME), encoding='utf-8') as manifest_file:
            version = json.load(manifest_file).get(KEY_VERSION)
        return isinstance(version, int) and version != MANIFEST_VERSION
    except (OSError, ValueError, AttributeError):
        return False


@dataclass(frozen=True)
class RestoredDocument:
    """What a restore returns besides the layers it loads into the image stack."""
    original_path: str
    metadata: ImageMetadata


def restore_session(image_stack: ImageStack, session: RecoverableSession) -> RestoredDocument:
    """Loads a crashed session's last autosave into the image stack, replacing the open document.

    Raises OSError, ValueError or AssertionError if the files can't be read.
    """
    manifest = session.manifest
    files_dir = os.path.join(session.session_dir, FILES_DIR_NAME)
    tmpdir = tempfile.mkdtemp()
    try:
        archive_path = os.path.join(tmpdir, 'recovered.ora')
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_STORED) as zip_file:
            zip_file.writestr(MIMETYPE_FILE_NAME, MIMETYPE_FILE_CONTENT)
            for xml_path, xml_text in manifest[KEY_XML_FILES].items():
                zip_file.writestr(xml_path, xml_text.encode('ascii'))
            for member_path, file_name in manifest[KEY_ARCHIVE_FILES].items():
                zip_file.write(os.path.join(files_dir, file_name), member_path)
            for member_path, entry in manifest[KEY_FOREIGN_FILES].items():
                file_info = zipfile.ZipInfo(member_path, tuple(entry[KEY_DATE_TIME]))  # type: ignore[arg-type]
                file_info.compress_type = int(entry[KEY_COMPRESS_TYPE])
                with open(os.path.join(files_dir, entry[KEY_FILE]), 'rb') as foreign_file:
                    zip_file.writestr(file_info, foreign_file.read())
        metadata = read_ora_image(image_stack, archive_path)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    x, y, width, height = (int(value) for value in manifest[KEY_GENERATION_AREA])
    image_stack.generation_area = QRect(x, y, width, height)
    legacy_exif = manifest.get(KEY_EXIF)
    if isinstance(legacy_exif, str) and len(metadata.exif_entries()) == 0:
        load_exif(metadata, base64.b64decode(legacy_exif))
    return RestoredDocument(session.original_path, metadata)
