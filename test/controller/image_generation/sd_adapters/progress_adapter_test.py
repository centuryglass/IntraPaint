"""Tests the status text and previews built from sd_backend_client progress snapshots."""
from PIL import Image
from PySide6.QtGui import QImage, QColor
from sd_backend_client import GenerationProgress, GenerationStatus

from src.controller.image_generation.sd_adapters.progress_adapter import progress_status_text, \
    progress_status_update, progress_percentage, progress_preview, STATUS_QUEUED, STATUS_GENERATING, \
    STATUS_BATCH_NUMBER, STATUS_WAITING, PROGRESS_KEY
from test.base_test_case import IntraPaintTestCase


class ProgressAdapterTest(IntraPaintTestCase):
    """Tests the status text and previews built from sd_backend_client progress snapshots."""

    def test_percentage(self) -> None:
        """Batch progress scales into the whole request, and unknown progress counts as the batch's start."""
        active = GenerationStatus.ACTIVE
        self.assertEqual(progress_percentage(GenerationProgress(active, progress=0.5)), 50.0)
        self.assertEqual(progress_percentage(GenerationProgress(active, progress=0.5), 1, 4), 37.5)
        self.assertEqual(progress_percentage(GenerationProgress(active), 1, 4), 25.0)
        self.assertIsNone(progress_percentage(GenerationProgress(active)))

    def test_queued_text(self) -> None:
        """Pending jobs report their queue position when the backend knows it."""
        self.assertEqual(progress_status_text(GenerationProgress(GenerationStatus.PENDING, queue_index=2)),
                         STATUS_QUEUED.format(queue_number=2))
        self.assertEqual(progress_status_text(GenerationProgress(GenerationStatus.PENDING)), STATUS_WAITING)

    def test_generating_text(self) -> None:
        """Running jobs report the batch, the percentage and the ETA when known."""
        progress = GenerationProgress(GenerationStatus.ACTIVE, progress=0.5, eta_seconds=75)
        batch = STATUS_BATCH_NUMBER.format(batch_num=2, num_batches=2)
        self.assertEqual(progress_status_text(progress, 1, 2), f'{batch} {STATUS_GENERATING}\n75.0% ETA: 1:15')
        self.assertEqual(progress_status_text(GenerationProgress(GenerationStatus.ACTIVE, progress=0.1,
                                                                 eta_seconds=9)),
                         f'{STATUS_GENERATING}\n10.0% ETA: 9s')
        self.assertEqual(progress_status_update(GenerationProgress(GenerationStatus.ACTIVE)),
                         {PROGRESS_KEY: STATUS_GENERATING})

    def test_preview(self) -> None:
        """Previews convert to premultiplied QImages."""
        self.assertIsNone(progress_preview(GenerationProgress(GenerationStatus.ACTIVE)))
        preview = progress_preview(GenerationProgress(GenerationStatus.ACTIVE,
                                                      preview=Image.new('RGB', (2, 2), (10, 20, 30))))
        assert preview is not None
        self.assertEqual(preview.format(), QImage.Format.Format_ARGB32_Premultiplied)
        self.assertEqual(preview.pixelColor(1, 1), QColor(10, 20, 30))
