"""Tests applying A1111 parameter fields to the editor's Cache settings, and updating them from it."""
from PySide6.QtCore import QSize

from src.config.cache import Cache
from src.image.image_metadata import A1111Parameters
from src.image.metadata_cache_fields import cache_field_keys, apply_to_cache, update_from_cache, PROMPT_FIELD, \
    differs_from_editor, read_field, SEED_FIELD, \
    NEGATIVE_PROMPT_FIELD, SAMPLER_FIELD, SCHEDULE_TYPE_FIELD, MODEL_FIELD, STEPS_FIELD
from test.base_test_case import IntraPaintTestCase

TEXT = ('a cat\nNegative prompt: a dog\nSteps: 12, Sampler: DPM++ 2M, Schedule type: karras, CFG scale: 4.5, '
        'Seed: 77, Size: 640x448, Denoising strength: 0.65, Clip skip: 2, Model: sd15, Version: v1')

# The value each mapped field of TEXT applies to the editor:
EXPECTED_VALUES = {
    PROMPT_FIELD: 'a cat',
    NEGATIVE_PROMPT_FIELD: 'a dog',
    STEPS_FIELD: 12,
    SAMPLER_FIELD: 'DPM++ 2M',
    SCHEDULE_TYPE_FIELD: 'karras',
    'CFG scale': 4.5,
    'Seed': 77,
    'Size': QSize(640, 448),
    'Denoising strength': 0.65,
    'Clip skip': 2,
    MODEL_FIELD: 'sd15',
}

# Editor values that differ from TEXT, and the text each one updates its field to:
EDITOR_VALUES = {
    PROMPT_FIELD: ('a fox', 'a fox'),
    NEGATIVE_PROMPT_FIELD: ('a wolf', 'a wolf'),
    STEPS_FIELD: (30, '30'),
    SAMPLER_FIELD: ('Euler a', 'Euler a'),
    SCHEDULE_TYPE_FIELD: ('normal', 'normal'),
    'CFG scale': (7.0, '7.0'),
    'Seed': (5, '5'),
    'Size': (QSize(512, 768), '512x768'),
    'Denoising strength': (0.3, '0.3'),
    'Clip skip': (1, '1'),
    MODEL_FIELD: ('sdxl', 'sdxl'),
}


class MetadataCacheFieldsTest(IntraPaintTestCase):
    """Tests the mapping between A1111 fields and Cache keys."""

    def setUp(self) -> None:
        super().setUp()
        cache = Cache()
        option_values = {Cache.SAMPLING_METHOD: ['DPM++ 2M', 'Euler a'], Cache.SCHEDULER: ['karras', 'normal'],
                         Cache.SD_MODEL: ['sd15', 'sdxl']}
        for key, options in option_values.items():
            cache.update_options(key, options)
            self.addCleanup(cache.restore_default_options, key)

    def test_every_field_is_mapped(self) -> None:
        self.assertEqual(set(EXPECTED_VALUES), set(cache_field_keys()))

    def test_apply_each_field(self) -> None:
        cache = Cache()
        keys = cache_field_keys()
        params = A1111Parameters.parse(TEXT)
        for field, expected in EXPECTED_VALUES.items():
            with self.subTest(field=field):
                self.assertEqual([], apply_to_cache(params, (field,)))
                self.assertEqual(expected, cache.get(keys[field]))

    def test_update_each_field(self) -> None:
        """Updating one field rewrites only that field's text."""
        cache = Cache()
        keys = cache_field_keys()
        for field, (value, expected_text) in EDITOR_VALUES.items():
            with self.subTest(field=field):
                params = A1111Parameters.parse(TEXT)
                apply_to_cache(params, tuple(EXPECTED_VALUES))
                cache.set(keys[field], value)
                update_from_cache(params, tuple(EXPECTED_VALUES))
                expected = A1111Parameters.parse(TEXT)
                if field == PROMPT_FIELD:
                    expected.prompt = expected_text
                elif field == NEGATIVE_PROMPT_FIELD:
                    expected.negative_prompt = expected_text
                else:
                    expected.set(field, expected_text)
                self.assertEqual(expected.serialize(), params.serialize())

    def test_update_unchanged_values_keep_text(self) -> None:
        """A saved value that parses to the editor's value keeps its text."""
        params = A1111Parameters.parse('p\nSteps: 20, Sampler: Euler a, CFG scale: 7')
        Cache().set(Cache.GUIDANCE_SCALE, 7.0)
        update_from_cache(params, ('CFG scale',))
        self.assertEqual('p\nSteps: 20, Sampler: Euler a, CFG scale: 7', params.serialize())

    def test_large_seed_applies_and_updates(self) -> None:
        """A saved seed a C integer can't hold applies to the editor as an int, and writes back as the same text."""
        cache = Cache()
        seed = 2 ** 64 - 1
        params = A1111Parameters.parse(f'p\nSteps: 20, Sampler: Euler a, Seed: {seed}')
        self.assertEqual([], apply_to_cache(params, (SEED_FIELD,)))
        self.assertEqual(seed, cache.get(Cache.SEED))
        self.assertIs(type(cache.get(Cache.SEED)), int)
        self.assertFalse(differs_from_editor(params, SEED_FIELD))
        cache.set(Cache.SEED, str(seed - 1))
        self.assertTrue(differs_from_editor(params, SEED_FIELD))
        update_from_cache(params, (SEED_FIELD,))
        self.assertEqual(str(seed - 1), read_field(params, SEED_FIELD))

    def test_out_of_range_seed_is_rejected(self) -> None:
        """A saved seed past the largest the seed field accepts is rejected, leaving the editor's seed unchanged."""
        params = A1111Parameters.parse(f'p\nSteps: 20, Sampler: Euler a, Seed: {2 ** 64}')
        self.assertEqual([SEED_FIELD], [rejected.field for rejected in apply_to_cache(params, (SEED_FIELD,))])
        self.assertEqual(-1, Cache().get(Cache.SEED))

    def test_string_seed_matches_saved_seed(self) -> None:
        """A seed the spinbox sets as text compares equal to the same saved seed."""
        Cache().set(Cache.SEED, '-1')
        params = A1111Parameters.parse('p\nSteps: 20, Sampler: Euler a, Seed: -1')
        self.assertFalse(differs_from_editor(params, SEED_FIELD))
        Cache().set(Cache.SEED, '5')
        self.assertTrue(differs_from_editor(params, SEED_FIELD))

    def test_update_empty_negative_prompt_adds_no_line(self) -> None:
        params = A1111Parameters.parse('p\nSteps: 20, Sampler: Euler a, CFG scale: 7')
        Cache().set(Cache.NEGATIVE_PROMPT, '')
        update_from_cache(params, (NEGATIVE_PROMPT_FIELD,))
        self.assertIsNone(params.negative_prompt)

    def test_unsupported_sampler_is_rejected(self) -> None:
        """A sampler the generator doesn't offer is returned unapplied, and the other fields still apply."""
        cache = Cache()
        cache.set(Cache.SAMPLING_METHOD, 'Euler a')
        params = A1111Parameters.parse(TEXT.replace('DPM++ 2M', 'Unknown sampler'))
        rejected = apply_to_cache(params, (SAMPLER_FIELD, STEPS_FIELD))
        self.assertEqual([(SAMPLER_FIELD, 'Unknown sampler')], [(entry.field, entry.value) for entry in rejected])
        self.assertEqual('Euler a', cache.get(Cache.SAMPLING_METHOD))
        self.assertEqual(12, cache.get(Cache.SAMPLING_STEPS))

    def test_unparsable_value_is_rejected(self) -> None:
        params = A1111Parameters.parse('p\nSteps: many, Sampler: Euler a, CFG scale: 7, Size: big')
        rejected = apply_to_cache(params, (STEPS_FIELD, 'Size'))
        self.assertEqual([STEPS_FIELD, 'Size'], [entry.field for entry in rejected])
