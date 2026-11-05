"""
The mapping between A1111 / Forge parameter fields and the `Cache` keys of the editor's generation settings.

It is the one mapping between saved generation parameters and editor settings: loading an image, Update metadata and
the metadata window all go through it. A field it doesn't cover can still be read and edited in `A1111Parameters`.
"""
import logging
from typing import Any, Callable, NamedTuple, Optional

from PySide6.QtCore import QSize

from src.config.cache import Cache
from src.image.image_metadata import A1111Parameters

logger = logging.getLogger(__name__)

PROMPT_FIELD = 'prompt'
NEGATIVE_PROMPT_FIELD = 'Negative prompt'
STEPS_FIELD = 'Steps'
SAMPLER_FIELD = 'Sampler'
SCHEDULE_TYPE_FIELD = 'Schedule type'
CFG_SCALE_FIELD = 'CFG scale'
SEED_FIELD = 'Seed'
SIZE_FIELD = 'Size'
DENOISING_STRENGTH_FIELD = 'Denoising strength'
CLIP_SKIP_FIELD = 'Clip skip'
MODEL_FIELD = 'Model'

LOAD_APPLIED_FIELDS = (PROMPT_FIELD, NEGATIVE_PROMPT_FIELD, STEPS_FIELD, SAMPLER_FIELD, CFG_SCALE_FIELD, SEED_FIELD)
"""Fields applied to the editor when an image loads. Other mapped fields are applied only on request."""

METADATA_UPDATE_FIELDS = (*LOAD_APPLIED_FIELDS, SIZE_FIELD)
"""Fields Image > Update metadata writes from the editor. Other fields in the text keep their saved values."""


def _parse_size(text: str) -> QSize:
    width, height = text.lower().split('x')
    return QSize(int(width.strip()), int(height.strip()))


def _format_size(size: QSize) -> str:
    return f'{size.width()}x{size.height()}'


class _FieldMapping(NamedTuple):
    """How one parameter field converts to and from its `Cache` value."""
    cache_key: str
    parse: Callable[[str], Any]
    format: Callable[[Any], str]


def cache_field_keys() -> dict[str, str]:
    """Returns the `Cache` key of every mapped field, in A1111 field order.

    A function, since `Cache` key constants exist only once `Cache` is constructed.
    """
    return {field: mapping.cache_key for field, mapping in _field_mappings().items()}


def _field_mappings() -> dict[str, _FieldMapping]:
    return {
        PROMPT_FIELD: _FieldMapping(Cache.PROMPT, str, str),
        NEGATIVE_PROMPT_FIELD: _FieldMapping(Cache.NEGATIVE_PROMPT, str, str),
        STEPS_FIELD: _FieldMapping(Cache.SAMPLING_STEPS, int, str),
        SAMPLER_FIELD: _FieldMapping(Cache.SAMPLING_METHOD, str, str),
        SCHEDULE_TYPE_FIELD: _FieldMapping(Cache.SCHEDULER, str, str),
        CFG_SCALE_FIELD: _FieldMapping(Cache.GUIDANCE_SCALE, float, str),
        SEED_FIELD: _FieldMapping(Cache.SEED, int, str),
        SIZE_FIELD: _FieldMapping(Cache.GENERATION_SIZE, _parse_size, _format_size),
        DENOISING_STRENGTH_FIELD: _FieldMapping(Cache.DENOISING_STRENGTH, float, str),
        CLIP_SKIP_FIELD: _FieldMapping(Cache.CLIP_SKIP, int, str),
        MODEL_FIELD: _FieldMapping(Cache.SD_MODEL, str, str),
    }


def _read_field(params: A1111Parameters, field: str) -> Optional[str]:
    """Returns a field's saved text. A missing negative prompt reads as empty, as A1111 treats it."""
    if field == PROMPT_FIELD:
        return params.prompt
    if field == NEGATIVE_PROMPT_FIELD:
        return '' if params.negative_prompt is None else params.negative_prompt
    return params.get(field)


def _write_field(params: A1111Parameters, field: str, text: str) -> None:
    if field == PROMPT_FIELD:
        params.prompt = text
    elif field == NEGATIVE_PROMPT_FIELD:
        if params.negative_prompt is not None or text != '':
            params.negative_prompt = text
    else:
        params.set(field, text)


class RejectedField(NamedTuple):
    """A saved field the editor couldn't take, such as a sampler the current generator doesn't offer."""
    field: str
    value: str
    reason: str


def apply_to_cache(params: A1111Parameters, fields: tuple[str, ...]) -> list[RejectedField]:
    """Writes saved field values into the editor's `Cache` settings, returning the fields that were rejected.

    Fields missing from `params` are skipped. A value that doesn't parse, or that `Cache` rejects as out of range or
    not among a setting's options, is left unapplied and returned.
    """
    cache = Cache()
    mappings = _field_mappings()
    rejected: list[RejectedField] = []
    for field in fields:
        text = _read_field(params, field)
        if text is None:
            continue
        mapping = mappings[field]
        try:
            cache.set(mapping.cache_key, mapping.parse(text))
        except (TypeError, ValueError) as err:
            logger.error(f'Saved {field} "{text}" was not applied: {err}')
            rejected.append(RejectedField(field, text, str(err)))
    return rejected


def update_from_cache(params: A1111Parameters, fields: tuple[str, ...]) -> None:
    """Writes the editor's `Cache` values into `params`, adding missing fields.

    A field whose saved value already parses to the editor's value keeps its text, so `7` isn't rewritten as `7.0`.
    """
    cache = Cache()
    mappings = _field_mappings()
    for field in fields:
        mapping = mappings[field]
        value = cache.get(mapping.cache_key)
        saved = _read_field(params, field)
        if saved is not None:
            try:
                if mapping.parse(saved) == value:
                    continue
            except (TypeError, ValueError):
                pass
        _write_field(params, field, mapping.format(value))
