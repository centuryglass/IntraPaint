"""Keeps the File > Open Recent list in `Cache.RECENT_FILES`: newest first, without duplicates, capped in length."""
import os

from src.config.cache import Cache

MAX_RECENT_FILES = 10


def recent_files() -> list[str]:
    """Returns the remembered file paths, newest first."""
    return [str(path) for path in Cache().get(Cache.RECENT_FILES)]


def add_recent_file(file_path: str) -> None:
    """Moves a file to the front of the recent list, dropping the oldest entries past `MAX_RECENT_FILES`."""
    file_path = os.path.abspath(file_path)
    paths = [file_path] + [path for path in recent_files() if path != file_path]
    Cache().set(Cache.RECENT_FILES, paths[:MAX_RECENT_FILES])


def clear_recent_files() -> None:
    """Empties the recent list."""
    Cache().set(Cache.RECENT_FILES, [])
