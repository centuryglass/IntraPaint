"""Tests AnimationSaveModal."""
from unittest.mock import patch

from src.config.cache import Cache
from src.ui.modal.animation_save_modal import AnimationSaveModal
from src.util.visual.image_format_utils import AnimationSaveOptions
from test.base_test_case import IntraPaintTestCase


class AnimationSaveModalTest(IntraPaintTestCase):
    """Tests AnimationSaveModal."""

    def _confirmed_result(self, modal: AnimationSaveModal) -> tuple[bool, AnimationSaveOptions | None]:
        with patch.object(AnimationSaveModal, 'exec', lambda _: modal._confirm()):
            return modal.show_animation_save_modal()

    def test_confirm_returns_remembered_values(self) -> None:
        """Confirming returns the Cache values, with a loop count of 0 when looping forever."""
        Cache().set(Cache.ANIMATION_SAVE_AS_ANIMATION, True)
        Cache().set(Cache.ANIMATION_FRAME_DURATION, 120)
        Cache().set(Cache.ANIMATION_LOOP_FOREVER, False)
        Cache().set(Cache.ANIMATION_LOOP_COUNT, 4)
        modal = AnimationSaveModal()
        self.assertEqual(self._confirmed_result(modal), (True, AnimationSaveOptions(120, 4)))
        Cache().set(Cache.ANIMATION_LOOP_FOREVER, True)
        self.assertEqual(self._confirmed_result(AnimationSaveModal()), (True, AnimationSaveOptions(120, 0)))

    def test_flattened_and_cancel(self) -> None:
        """Unchecking the animation mode returns no options, and canceling reports that it wasn't confirmed."""
        Cache().set(Cache.ANIMATION_SAVE_AS_ANIMATION, False)
        self.assertEqual(self._confirmed_result(AnimationSaveModal()), (True, None))
        with patch.object(AnimationSaveModal, 'exec', lambda _: None):
            self.assertEqual(AnimationSaveModal().show_animation_save_modal(), (False, None))

    def test_flattened_unavailable(self) -> None:
        """A format that only saves animations keeps the animation mode on and locked."""
        Cache().set(Cache.ANIMATION_SAVE_AS_ANIMATION, False)
        modal = AnimationSaveModal(allow_flattened=False)
        self.assertFalse(modal._mode_checkbox.isEnabled())
        self.assertEqual(self._confirmed_result(modal), (True, AnimationSaveOptions(Cache().get(
            Cache.ANIMATION_FRAME_DURATION), 0)))
