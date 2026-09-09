import logging
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from videos.models import Video
from videos.services.storage import delete_object


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Delete abandoned uploads and their stored objects."

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than-hours",
            type=int,
            default=24,
            help="Upload age threshold in hours (default: 24).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show eligible videos without deleting anything.",
        )

    def handle(self, *args, **options):
        hours = options["older_than_hours"]
        dry_run = options["dry_run"]

        if hours < 1:
            raise CommandError(
                "--older-than-hours must be at least 1."
            )

        cutoff = timezone.now() - timedelta(hours=hours)
        processed = 0
        failed = 0

        candidates = (
            Video.objects
            .filter(
                status=Video.Status.UPLOADING,
                created_at__lt=cutoff,
            )
            .order_by("created_at", "id")
            .values_list("id", flat=True)
        )

        for video_id in candidates.iterator(chunk_size=200):
            try:
                with transaction.atomic():
                    # Recheck eligibility after acquiring the lock.
                    video = (
                        Video.objects
                        .select_for_update(skip_locked=True)
                        .filter(
                            id=video_id,
                            status=Video.Status.UPLOADING,
                            created_at__lt=cutoff,
                        )
                        .first()
                    )

                    if video is None:
                        continue

                    if dry_run:
                        self.stdout.write(
                            f"Would delete abandoned video {video_id}"
                        )
                    else:
                        object_keys = list(
                            video.files.values_list(
                                "object_key",
                                flat=True,
                            )
                        )

                        for object_key in object_keys:
                            delete_object(object_key)

                        video.delete()

                processed += 1

                if not dry_run:
                    self.stdout.write(
                        f"Deleted abandoned video {video_id}"
                    )

            except Exception:
                failed += 1
                logger.exception(
                    "Could not clean up abandoned video %s.",
                    video_id,
                )

        action = "Eligible" if dry_run else "Deleted"
        self.stdout.write(
            f"{action}: {processed}. Failed: {failed}."
        )

        if failed:
            raise CommandError(
                "Some uploads could not be cleaned up; see logs."
            )