import re
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.validators import EmailValidator
from django.db import transaction
from apps.users.models import StudentProfile

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.CharField(
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

    registration_number = serializers.CharField(
        required=True,
        max_length=25,
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

        if not value:
            raise serializers.ValidationError("College email is required.")

        if len(value) > 254:
            raise serializers.ValidationError("College email cannot exceed 254 characters.")

        if " " in value:
            raise serializers.ValidationError("Enter a valid college email address without spaces.")

        # Email syntax validation requiring local part, @, domain name and TLD
        email_pattern = r"^[a-zA-Z0-9_\-\.\+]+@[a-zA-Z0-9\-\.]+\.[a-zA-Z0-9\-]+$"
        if not re.fullmatch(email_pattern, value):
            raise serializers.ValidationError("Enter a valid college email address (e.g. student@college.edu).")

        django_email_validator = EmailValidator(message="Enter a valid college email address.")
        django_email_validator(value)

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

        if not re.fullmatch(r"[A-Za-z]+(?:[ '-][A-Za-z]+)*", value):
            raise serializers.ValidationError(
                "Enter a valid name using letters, spaces, hyphens, or apostrophes."
            )

        return value

    def validate_registration_number(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError("Register / roll number is required.")

        if len(value) > 25:
            raise serializers.ValidationError(
                "Register / roll number cannot exceed 25 characters."
            )

        # Accept letters, numbers, and reasonable separators such as hyphens or slashes
        if not re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9\s\-_/]*$", value):
            raise serializers.ValidationError(
                "Register / roll number must contain only letters, numbers, hyphens, slashes, or spaces."
            )

        if StudentProfile.objects.filter(registration_number__iexact=value).exists():
            raise serializers.ValidationError(
                "A student with this register / roll number already exists."
            )

        return value

    def create(self, validated_data):
        email = validated_data["email"]
        name = validated_data["name"]
        registration_number = validated_data["registration_number"]
        password = validated_data["password"]

        with transaction.atomic():
            # Preserve the existing pending-approval registration flow.
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=name,
                role=User.Role.STUDENT,
                status=User.AccountStatus.PENDING,
            )

            # Persist the StudentProfile with the student's registration_number
            StudentProfile.objects.create(
                user=user,
                registration_number=registration_number,
                first_name=name,
            )

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
