from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless

from django.db import connection, transaction
from django.test import TransactionTestCase

from .models import VideoProcessingRequest

from .models import Video, VideoFile


COMMAND_MODULE = (
    "videos.management.commands.cleanup_abandoned_uploads"
)


class CleanupAbandonedUploadsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="cleanup-test-user",
        )

        patcher = patch(f"{COMMAND_MODULE}.delete_object")
        self.delete_object = patcher.start()
        self.addCleanup(patcher.stop)

    def create_video(
        self,
        age_hours=25,
        video_status=Video.Status.UPLOADING,
    ):
        video = Video.objects.create(
            owner=self.user,
            title="Cleanup test",
            status=video_status,
        )

        Video.objects.filter(id=video.id).update(
            created_at=timezone.now() - timedelta(hours=age_hours),
        )

        original = VideoFile.objects.create(
            video=video,
            file_type=VideoFile.FileType.ORIGINAL,
            object_key=f"videos/{video.id}/original.mp4",
            content_type="video/mp4",
        )

        return video, original

    def run_cleanup(self, **options):
        call_command(
            "cleanup_abandoned_uploads",
            stdout=StringIO(),
            **options,
        )

    def test_deletes_abandoned_upload_and_file_record(self):
        video, original = self.create_video()

        self.run_cleanup()

        self.delete_object.assert_called_once_with(
            original.object_key,
        )
        self.assertFalse(
            Video.objects.filter(id=video.id).exists(),
        )
        self.assertFalse(
            VideoFile.objects.filter(id=original.id).exists(),
        )

    def test_preserves_recent_uploads_and_other_statuses(self):
        retained = [self.create_video(age_hours=1)]

        for video_status in (
            Video.Status.PROCESSING,
            Video.Status.READY,
            Video.Status.FAILED,
        ):
            retained.append(
                self.create_video(video_status=video_status),
            )

        self.run_cleanup()

        self.delete_object.assert_not_called()

        for video, original in retained:
            with self.subTest(video_id=video.id):
                self.assertTrue(
                    Video.objects.filter(id=video.id).exists(),
                )
                self.assertTrue(
                    VideoFile.objects.filter(
                        id=original.id,
                    ).exists(),
                )

    def test_dry_run_does_not_delete_anything(self):
        video, original = self.create_video()

        self.run_cleanup(dry_run=True)

        self.delete_object.assert_not_called()
        self.assertTrue(
            Video.objects.filter(id=video.id).exists(),
        )
        self.assertTrue(
            VideoFile.objects.filter(id=original.id).exists(),
        )

    def test_storage_failure_preserves_records_and_continues(self):
        failed_video, failed_file = self.create_video(age_hours=30)
        other_video, other_file = self.create_video(age_hours=25)

        self.delete_object.side_effect = [
            RuntimeError("Simulated storage outage"),
            None,
        ]

        with self.assertLogs(COMMAND_MODULE, level="ERROR"):
            with self.assertRaises(CommandError):
                self.run_cleanup()

        self.assertTrue(
            Video.objects.filter(id=failed_video.id).exists(),
        )
        self.assertTrue(
            VideoFile.objects.filter(id=failed_file.id).exists(),
        )

        self.assertFalse(
            Video.objects.filter(id=other_video.id).exists(),
        )
        self.assertFalse(
            VideoFile.objects.filter(id=other_file.id).exists(),
        )

        self.assertEqual(self.delete_object.call_count, 2)


@skipUnless(
    connection.vendor == "postgresql",
    "This test requires PostgreSQL row locking.",
)
class CleanupConcurrencyTests(TransactionTestCase):
    def test_cleanup_skips_video_locked_by_upload_completion(self):
        user = get_user_model().objects.create_user(
            username="concurrency-test-user",
        )

        video = Video.objects.create(
            owner=user,
            title="Upload being completed",
        )

        Video.objects.filter(id=video.id).update(
            created_at=timezone.now() - timedelta(hours=25),
        )

        original = VideoFile.objects.create(
            video=video,
            file_type=VideoFile.FileType.ORIGINAL,
            object_key=f"videos/{video.id}/original.mp4",
            content_type="video/mp4",
        )

        def run_cleanup_on_separate_connection():
            output = StringIO()

            try:
                # Bound the test if cleanup accidentally waits for a lock.
                with connection.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '5s'")

                call_command(
                    "cleanup_abandoned_uploads",
                    stdout=output,
                )
                return output.getvalue()
            finally:
                connection.close()

        with patch(f"{COMMAND_MODULE}.delete_object") as delete_mock:
            with ThreadPoolExecutor(max_workers=1) as executor:
                with transaction.atomic():
                    locked_video = (
                        Video.objects
                        .select_for_update()
                        .get(id=video.id)
                    )

                    # Cleanup sees an old UPLOADING row, but cannot lock it.
                    future = executor.submit(
                        run_cleanup_on_separate_connection,
                    )
                    output = future.result(timeout=10)

                    self.assertIn(
                        "Deleted: 0. Failed: 0.",
                        output,
                    )
                    delete_mock.assert_not_called()

                    # Simulate completion committing after cleanup skips.
                    locked_video.status = Video.Status.PROCESSING
                    locked_video.save(
                        update_fields=["status", "updated_at"],
                    )
                    VideoProcessingRequest.objects.create(
                        video=locked_video,
                    )

            # A later cleanup pass must also preserve the completed upload.
            call_command(
                "cleanup_abandoned_uploads",
                stdout=StringIO(),
            )
            delete_mock.assert_not_called()

        video.refresh_from_db()
        self.assertEqual(video.status, Video.Status.PROCESSING)
        self.assertTrue(
            VideoFile.objects.filter(id=original.id).exists(),
        )
        self.assertTrue(
            VideoProcessingRequest.objects.filter(video=video).exists(),
        )
