"""Metaclass used to ensure only a single instance of a class object exists."""


class Singleton(type):
    """Metaclass used to ensure only a single instance of a class object exists."""
    _instances: dict[type, type] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
