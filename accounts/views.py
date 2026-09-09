from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from rest_framework.exceptions import ValidationError
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from core.responses import success_response

from .serializers import LoginSerializer, RegisterSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        User = get_user_model()
        username = User.normalize_username(
            serializer.validated_data["username"],
        )

        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError as exc:
            if User.objects.filter(username=username).exists():
                raise ValidationError({
                    "username": [
                        "A user with that username already exists."
                    ],
                }) from exc

            raise

        return success_response(
            data=serializer.data,
            message="Account created successfully.",
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        token, _ = Token.objects.get_or_create(
            user=user,
        )

        return success_response(
            data={
                "token": token.key,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
            },
            message="Login successful.",
            status=status.HTTP_200_OK,
        )


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        return success_response(
            data={
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
            message="User information retrieved successfully.",
        )
