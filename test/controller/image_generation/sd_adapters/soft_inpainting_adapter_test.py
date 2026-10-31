"""Tests the saved soft inpainting parameter definitions and values."""
from sd_backend_client import ParameterDef

from src.config.cache import Cache
from src.controller.image_generation.sd_adapters.soft_inpainting_adapter import (load_parameter_defs, load_values,
                                                                                 request_values, save_parameter_defs,
                                                                                 save_value)
from test.base_test_case import IntraPaintTestCase

BIAS = ParameterDef(key='schedule_bias', display_name='Schedule bias', default_value=1.0, min_val=0.0, max_val=8.0,
                    step_val=0.1)
STRENGTH = ParameterDef(key='strength', display_name='Strength', default_value=1.0, min_val=0.05, max_val=1.0,
                        step_val=0.05)


class SoftInpaintingAdapterTest(IntraPaintTestCase):
    """Tests the saved soft inpainting parameter definitions and values."""

    def test_parameter_defs_round_trip(self) -> None:
        """Saved definitions load back unchanged, and invalid cached entries are skipped."""
        save_parameter_defs([BIAS, STRENGTH])
        self.assertEqual(load_parameter_defs(), [BIAS, STRENGTH])
        Cache().set(Cache.SOFT_INPAINTING_PARAMETERS, [BIAS.model_dump_json(), '{"key": 5}', 'not json'])
        self.assertEqual(load_parameter_defs(), [BIAS])

    def test_values_accumulate(self) -> None:
        """Saving one value keeps the others, and invalid saved data reads as empty."""
        save_value('schedule_bias', 2.0)
        save_value('strength', 0.5)
        self.assertEqual(load_values(), {'schedule_bias': 2.0, 'strength': 0.5})
        Cache().set(Cache.SOFT_INPAINTING_VALUES, '[1, 2]')
        self.assertEqual(load_values(), {})
        Cache().set(Cache.SOFT_INPAINTING_VALUES, '{broken')
        self.assertEqual(load_values(), {})

    def test_request_values_keep_only_valid_listed_values(self) -> None:
        """Values for unlisted keys, of the wrong type or out of range are left out, so backend defaults apply."""
        save_value('schedule_bias', 2.0)
        save_value('strength', 0.5)
        save_value('unlisted', 1.0)
        self.assertEqual(request_values([BIAS]), {'schedule_bias': 2.0})
        save_value('schedule_bias', 100.0)
        self.assertEqual(request_values([BIAS]), {})
        save_value('schedule_bias', 'high')
        self.assertEqual(request_values([BIAS]), {})
