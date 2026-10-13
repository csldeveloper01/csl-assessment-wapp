from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(max_length=150)
    password = serializers.CharField(min_length=8, write_only=True)

    def validate_email(self, value):
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        return value

    def create(self, validated_data):
        email = validated_data["email"]
        name = validated_data["name"]
        password = validated_data["password"]

        # username is required by AbstractUser; use email as username
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
