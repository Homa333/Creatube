import uuid

from django.conf import settings
from django.db import models


class Video(models.Model):
    class Status(models.TextChoices):
        UPLOADING = "uploading", "Uploading"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="videos",
    )

    title = models.CharField(max_length=255)

    description = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UPLOADING,
    )

    duration = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duration in seconds",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.title


class VideoFile(models.Model):
    class FileType(models.TextChoices):
        ORIGINAL = "original", "Original"
        THUMBNAIL = "thumbnail", "Thumbnail"
        PREVIEW = "preview", "Preview"
        HLS_1080P = "hls_1080p", "HLS 1080p"
        HLS_720P = "hls_720p", "HLS 720p"
        HLS_480P = "hls_480p", "HLS 480p"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name="files",
    )

    file_type = models.CharField(
        max_length=30,
        choices=FileType.choices,
    )

    object_key = models.CharField(
        max_length=1000,
        help_text="Object key in S3/MinIO",
    )

    content_type = models.CharField(
        max_length=100,
        blank=True,
    )

    size = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text="File size in bytes",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["video", "file_type"],
                name="unique_video_file_type",
            ),
        ]

    def __str__(self):
        return f"{self.video.title} - {self.file_type}"


class VideoLike(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name="likes",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="video_likes",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["video", "user"],
                name="unique_video_like",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.video}"


class Comment(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )

    content = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"{self.user} - {self.content[:50]}"


class VideoView(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name="views",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="video_views",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"{self.video} - {self.user}"


class VideoProcessingRequest(models.Model):
    """Durable intent to enqueue processing for a video."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    video = models.OneToOneField(
        Video,
        on_delete=models.CASCADE,
        related_name="processing_request",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    dispatched_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "When task publication succeeded. "
            "Does not indicate processing completion."
        ),
    )

    def __str__(self):
        return f"Processing request for {self.video_id}"
