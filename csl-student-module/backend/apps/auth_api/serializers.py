from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        max_length=254,
        allow_blank=False,
        trim_whitespace=True,
    )

    name = serializers.CharField(
        required=True,
        max_length=50,
        allow_blank=False,
        trim_whitespace=True,
    )

    password = serializers.CharField(
        min_length=8,
        write_only=True,
        required=True,
        allow_blank=False,
        trim_whitespace=False,
    )

    def validate_email(self, value):
        value = value.strip().lower()

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        return value

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError("Full name is required.")

        if len(value) > 50:
            raise serializers.ValidationError(
                "Full name cannot exceed 50 characters."
            )

        import re

        if not re.fullmatch(r"[A-Za-z]+(?:[ '-][A-Za-z]+)*", value):
            raise serializers.ValidationError(
                "Enter a valid name using letters, spaces, hyphens, or apostrophes."
            )

        return value

    def create(self, validated_data):
        email = validated_data["email"]
        name = validated_data["name"]
        password = validated_data["password"]

        # Preserve the existing pending-approval registration flow.
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=name,
            role=User.Role.STUDENT,
            status=User.AccountStatus.PENDING,
        )

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
