"""Provides constants and utilities for managing ControlNet model use during image generation.

The Stable Diffusion WebUI and ComfyUI APIs both support ControlNet, but the ways they represent ControlNet data are
entirely different.  This module provides a third format for representing ControlNet unit configurations, designed for
easy use within IntraPaint and for conversion to and from either API format."""
