import os

from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from videos.services.storage import generate_upload_url, object_exists


from .models import Video
from .serializers import VideoSerializer
from .tasks import process_video


class VideoViewSet(viewsets.ModelViewSet):
    queryset = Video.objects.all()
    serializer_class = VideoSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class VideoUploadURLView(APIView):

    def post(self, request):
        title = request.data.get("title")
        description = request.data.get("description", "")
        filename = request.data.get("filename")
        content_type = request.data.get("content_type")

        if not title:
            return Response(
                {"detail": "title is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not filename or not content_type:
            return Response(
                {
                    "detail": "filename and content_type are required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        extension = os.path.splitext(filename)[1].lower()

        if not extension:
            return Response(
                {"detail": "File extension is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        video = Video.objects.create(
            owner=request.user,
            title=title,
            description=description,
            status=Video.Status.UPLOADING,
        )

        object_key = f"videos/{video.id}/original{extension}"

        video.original_file = object_key
        video.save(update_fields=["original_file"])

        upload_url = generate_upload_url(
            object_key=object_key,
            content_type=content_type,
        )

        return Response(
            {
                "video_id": video.id,
                "upload_url": upload_url,
                "object_key": object_key,
            },
            status=status.HTTP_201_CREATED,
        )


class VideoUploadCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, video_id):
        video = get_object_or_404(
            Video,
            id=video_id,
            owner=request.user,
        )

        if video.status != Video.Status.UPLOADING:
            return Response(
                {
                    "detail": (
                        f"Video cannot be completed from "
                        f"'{video.status}' status."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not object_exists(video.original_file):
            return Response(
                {
                    "detail": "Uploaded video was not found in storage."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        video.status = Video.Status.PROCESSING
        video.save(update_fields=["status", "updated_at"])

        process_video.delay(video.id)

        return Response(
            {
                "video_id": video.id,
                "status": video.status,
            },
            status=status.HTTP_200_OK,
        )