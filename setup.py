"""Builds the Cython `image_fill` extension in place: `python setup.py build_ext --inplace`."""
from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules = cythonize('src/util/visual/image_fill.py')
)