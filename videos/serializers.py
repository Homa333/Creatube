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
            "owner",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "owner",
            "created_at",
            "updated_at",
        ]
