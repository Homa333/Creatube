from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import success_response
from videos.services.storage import (
    generate_upload_url,
    get_object_metadata,
)

from .models import Video, VideoFile
from .serializers import VideoSerializer, VideoUploadSerializer
from .tasks import process_video


class VideoViewSet(viewsets.ModelViewSet):
    queryset = Video.objects.all()
    serializer_class = VideoSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class VideoUploadURLView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = VideoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        content_type = validated_data["content_type"]
        extension = self.get_extension(content_type)

        with transaction.atomic():
            video = Video.objects.create(
                owner=request.user,
                title=validated_data["title"],
                description=validated_data.get("description", ""),
            )

            object_key = f"videos/{video.id}/original{extension}"

            VideoFile.objects.create(
                video=video,
                file_type=VideoFile.FileType.ORIGINAL,
                object_key=object_key,
                content_type=content_type,
            )

            upload_url = generate_upload_url(
                object_key=object_key,
                content_type=content_type,
            )

        return success_response(
            data={
                "video_id": str(video.id),
                "upload_url": upload_url,
                "object_key": object_key,
            },
            message="Video upload initialized successfully.",
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def get_extension(content_type):
        extensions = {
            "video/mp4": ".mp4",
            "video/webm": ".webm",
            "video/quicktime": ".mov",
            "video/x-matroska": ".mkv",
        }

        extension = extensions.get(content_type)

        if extension is None:
            raise ValidationError({
                "content_type": [
                    f"Unsupported video type: {content_type}"
                ]
            })

        return extension


class VideoUploadCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, video_id):
        with transaction.atomic():
            video = get_object_or_404(
                Video.objects.select_for_update(),
                id=video_id,
                owner=request.user,
            )

            if video.status in (
                Video.Status.PROCESSING,
                Video.Status.READY,
            ):
                return success_response(
                    data={
                        "video_id": str(video.id),
                        "status": video.status,
                    },
                    message="Upload completion was already recorded.",
                    status=status.HTTP_200_OK,
                )

            if video.status != Video.Status.UPLOADING:
                raise ValidationError(
                    f"Video cannot be completed from "
                    f"'{video.status}' status."
                )

            original_file = video.files.filter(
                file_type=VideoFile.FileType.ORIGINAL,
            ).first()

            if original_file is None:
                raise ValidationError(
                    "No original file record exists for this video."
                )

            metadata = get_object_metadata(
                original_file.object_key,
            )

            if metadata is None:
                raise ValidationError(
                    "Uploaded video was not found in storage."
                )

            if metadata["size"] == 0:
                raise ValidationError(
                    "Uploaded video is empty."
                )

            if metadata["content_type"] != original_file.content_type:
                raise ValidationError(
                    "Uploaded content type does not match "
                    "the initialized upload."
                )

            original_file.size = metadata["size"]
            original_file.content_type = metadata["content_type"]
            original_file.save(
                update_fields=["size", "content_type"],
            )

            video.status = Video.Status.PROCESSING
            video.save(
                update_fields=["status", "updated_at"],
            )

            transaction.on_commit(
                lambda: process_video.delay(str(video.id))
            )

        return success_response(
            data={
                "video_id": str(video.id),
                "status": video.status,
            },
            message="Video processing queued.",
            status=status.HTTP_200_OK,
        )
