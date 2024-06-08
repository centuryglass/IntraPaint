"""Utility class for tracking arbitrary cached data."""
from typing import Any


class CachedData:
    """Holds cached data with a validity flag."""

    def __init__(self, data: Any) -> None:
        """Set initial data, mark it as initially valid."""
        self._data = data
        self._valid = bool(data is not None)

    @property
    def valid(self) -> bool:
        """Returns whether the cached data is valid."""
        return self._valid

    def invalidate(self) -> None:
        """Mark the cached data as invalid."""
        self._valid = False

    @property
    def data(self) -> Any:
        """Return cached data."""
        return self._data

    @data.setter
    def data(self, new_data: Any) -> None:
        """Updates cached data and marks it as valid."""
        self._data = new_data
        self._valid = True
