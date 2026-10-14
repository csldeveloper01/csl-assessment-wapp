from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class CustomUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("status", User.AccountStatus.ACTIVE)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        TUTOR = "TUTOR", "Tutor"
        STUDENT = "STUDENT", "Student"

    class AccountStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        REJECTED = "REJECTED", "Rejected"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        if self.is_superuser or self.is_staff:
            if self.role == self.Role.STUDENT:
                self.role = self.Role.ADMIN
            if self.status == self.AccountStatus.PENDING:
                self.status = self.AccountStatus.ACTIVE
        super().save(*args, **kwargs)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ["email"]
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.email} ({self.role})"


class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
        limit_choices_to={"role": User.Role.STUDENT},
    )
    registration_number = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150, blank=True)
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.PROTECT,
        related_name="students",
        null=True,
        blank=True,
    )
    batch = models.ForeignKey(
        "courses.Batch",
        on_delete=models.PROTECT,
        related_name="students",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["registration_number"]
        indexes = [
            models.Index(fields=["course", "batch"]),
        ]

    def clean(self):
        super().clean()
        if self.batch and self.course and self.batch.course_id != self.course.id:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                {"batch": f"Batch '{self.batch.name}' does not belong to course '{self.course.name}'."}
            )

    def __str__(self):
        return f"{self.registration_number} - {self.first_name}"
