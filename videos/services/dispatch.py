import logging

from django.db import transaction
from django.utils import timezone
from kombu.exceptions import OperationalError as BrokerOperationalError

from videos.models import VideoProcessingRequest
from videos.tasks import process_video


logger = logging.getLogger(__name__)


def dispatch_processing_request(request_id):
    """
    Publish one pending processing request.

    Return True after successful publication and database commit.
    Return False if unavailable, already dispatched, or publication fails.
    """
    try:
        with transaction.atomic():
            processing_request = (
                VideoProcessingRequest.objects
                .select_for_update(skip_locked=True)
                .filter(
                    id=request_id,
                    dispatched_at__isnull=True,
                )
                .first()
            )

            if processing_request is None:
                return False

            process_video.apply_async(
                args=[str(processing_request.video_id)],
                retry=False,
            )

            processing_request.dispatched_at = timezone.now()
            processing_request.save(
                update_fields=["dispatched_at"],
            )

    except BrokerOperationalError:
        logger.exception(
            "Could not publish processing request %s; "
            "leaving it pending for retry.",
            request_id,
        )
        return False

    return True