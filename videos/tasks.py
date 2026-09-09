import logging

from celery import shared_task

from .models import Video


logger = logging.getLogger(__name__)


@shared_task
def process_video(video_id):
    try:
        video = Video.objects.get(id=video_id)
    except Video.DoesNotExist:
        logger.warning(
            "Ignoring processing task: video %s no longer exists.",
            video_id,
        )
        return

    if video.status != Video.Status.PROCESSING:
        logger.info(
            "Ignoring processing task for video %s with status %s.",
            video.id,
            video.status,
        )
        return

    logger.info(
        "Processing task received for video %s. "
        "Awaiting implementation of media processing.",
        video.id,
    )
