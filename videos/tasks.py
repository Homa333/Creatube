from celery import shared_task
from django.db import transaction

from .models import Video


@shared_task
def process_video(video_id):
    try:
        video = Video.objects.get(id=video_id)
    except Video.DoesNotExist:
        return

    try:
        print(f"Starting processing for video {video.id}")

        # FFmpeg processing will go here later.

        video.status = Video.Status.READY
        video.save(update_fields=["status", "updated_at"])

        print(f"Finished processing video {video.id}")

    except Exception:
        video.status = Video.Status.FAILED
        video.save(update_fields=["status", "updated_at"])

        raise