import logging
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from videos.models import VideoProcessingRequest
from videos.services.dispatch import dispatch_processing_request


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Periodically dispatch pending video processing requests."

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=int,
            default=5,
            help="Seconds to wait between passes (default: 5).",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run one dispatch pass and exit.",
        )

    def handle(self, *args, **options):
        interval = options["interval"]
        once = options["once"]

        if interval <= 0:
            raise CommandError("--interval must be greater than zero.")

        self.stdout.write("Video processing dispatcher started.")

        try:
            while True:
                close_old_connections()

                try:
                    published, failed = self.dispatch_pending()
                except Exception as exc:
                    logger.exception("Dispatch pass failed.")

                    if once:
                        raise CommandError(
                            "Dispatch pass failed; see logs."
                        ) from exc
                else:
                    if published:
                        self.stdout.write(
                            f"Published {published} processing request(s)."
                        )

                    if once:
                        if failed:
                            raise CommandError(
                                f"{failed} request(s) failed; see logs."
                            )
                        return

                time.sleep(interval)

        except KeyboardInterrupt:
            self.stdout.write("Video processing dispatcher stopped.")

        finally:
            close_old_connections()

    def dispatch_pending(self):
        # Snapshot this pass so newly created requests wait until the next.
        request_ids = list(
            VideoProcessingRequest.objects
            .filter(dispatched_at__isnull=True)
            .order_by("created_at", "id")
            .values_list("id", flat=True)
        )

        print(f"Dispatching {len(request_ids)} pending processing request(s).")

        published = 0
        failed = 0

        for request_id in request_ids:
            try:
                if dispatch_processing_request(request_id):
                    published += 1
                elif VideoProcessingRequest.objects.filter(
                    id=request_id,
                    dispatched_at__isnull=True,
                ).exists():
                    failed += 1

            except Exception:
                failed += 1
                logger.exception(
                    "Failed to dispatch processing request %s.",
                    request_id,
                )

        return published, failed