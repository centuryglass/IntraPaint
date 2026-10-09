"""Converts between IntraPaint's Qt images and saved settings and the `sd_backend_client` library's models.

The Stable Diffusion generators use these to build library requests and read library results. Only names in the
library's root `__all__` are imported here, since deeper module paths may move in any release.
"""
