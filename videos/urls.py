from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import VideoUploadCompleteView, VideoUploadURLView, VideoViewSet


router = DefaultRouter()
router.register("videos", VideoViewSet, basename="video")

urlpatterns = [
    path(
        "upload-url/",
        VideoUploadURLView.as_view(),
        name="video-upload-url",
    ),
    path("", include(router.urls)),
    path(
    "<int:video_id>/upload-complete/",
    VideoUploadCompleteView.as_view(),
    name="video-upload-complete",
),
]