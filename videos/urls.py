from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    VideoUploadCompleteView,
    VideoUploadStatusView,
    VideoUploadURLView,
    VideoViewSet,
)


router = DefaultRouter()
router.register("", VideoViewSet, basename="video")

urlpatterns = [
    path(
        "upload-url/",
        VideoUploadURLView.as_view(),
        name="video-upload-url",
    ),
    path(
        "<uuid:video_id>/upload-complete/",
        VideoUploadCompleteView.as_view(),
        name="video-upload-complete",
    ),
    path(
        "<uuid:video_id>/upload-status/",
        VideoUploadStatusView.as_view(),
        name="video-upload-status",
    ),
    path("", include(router.urls)),
]
