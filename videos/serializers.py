from rest_framework import serializers

from .models import Video


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = [
            "id",
            "title",
            "description",
            "status",
            "duration",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "status",
            "duration",
            "created_at",
            "updated_at",
        ]


class VideoUploadSerializer(serializers.Serializer):
    title = serializers.CharField(
        max_length=255,
    )

    description = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    content_type = serializers.CharField(
        max_length=100,
    )

    def validate_content_type(self, value):
        allowed_types = {
            "video/mp4",
            "video/webm",
            "video/quicktime",
            "video/x-matroska",
        }

        if value not in allowed_types:
            raise serializers.ValidationError(
                f"Unsupported video type: {value}"
            )

        return value
