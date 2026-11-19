"""Writes a file through a temporary file beside it, so a failed write leaves the original unchanged."""
import os
import shutil
import tempfile
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def replacing_file(file_path: str) -> Iterator[str]:
    """Yields a temporary path for the caller to write, which replaces `file_path` once the block exits normally.

    The temporary file is in the same directory and has the same extension, so code that picks a format from the
    extension writes the right one. The replacement keeps an existing file's permissions. If the block raises, the
    temporary file is deleted and `file_path` is left as it was.
    """
    directory = os.path.dirname(os.path.abspath(file_path))
    base_name = os.path.basename(file_path)
    file_descriptor, temp_path = tempfile.mkstemp(dir=directory, prefix=f'.{base_name}.',
                                                  suffix=os.path.splitext(base_name)[1])
    os.close(file_descriptor)
    try:
        yield temp_path
        if os.path.exists(file_path):
            shutil.copymode(file_path, temp_path)
        os.replace(temp_path, file_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
