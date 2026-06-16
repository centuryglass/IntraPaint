"""A no-op replacement for numba's njit annotation, to use when numba is not available."""
from functools import wraps


def njit(func):
    """A no-op replacement for numba's njit annotation."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper