from rest_framework import serializers
from .models import StudentProfile, User


class StudentProfileSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)
    student_id = serializers.CharField(source="registration_number", read_only=True)
    course = serializers.SerializerMethodField()
    batch = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            "name",
            "email",
            "student_id",
            "course",
            "batch",
        ]

    def get_name(self, obj) -> str:
        # Check profile first_name/last_name, fallback to user
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        if full_name:
            return full_name
        user_name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        if user_name:
            return user_name
        return obj.user.username or obj.user.email

    def get_course(self, obj) -> str | None:
        if obj.course:
            return obj.course.name or obj.course.code
        return None

    def get_batch(self, obj) -> str | None:
        if obj.batch:
            return obj.batch.name
        return None
