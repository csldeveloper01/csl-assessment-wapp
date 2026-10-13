from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages
from .models import User, StudentProfile


@admin.action(description="Approve selected students (Set status to ACTIVE)")
def approve_students(modeladmin, request, queryset):
    # Only apply to students
    student_qs = queryset.filter(role=User.Role.STUDENT)
    count = student_qs.update(status=User.AccountStatus.ACTIVE, is_active=True)
    non_students = queryset.exclude(role=User.Role.STUDENT).count()
    if non_students:
        modeladmin.message_user(
            request,
            f"{count} student(s) approved. {non_students} non-student user(s) were skipped.",
            level=messages.WARNING,
        )
    else:
        modeladmin.message_user(request, f"{count} student(s) approved.", level=messages.SUCCESS)


@admin.action(description="Reject selected students (Set status to REJECTED)")
def reject_students(modeladmin, request, queryset):
    # Only apply to students
    student_qs = queryset.filter(role=User.Role.STUDENT)
    count = student_qs.update(status=User.AccountStatus.REJECTED)
    non_students = queryset.exclude(role=User.Role.STUDENT).count()
    if non_students:
        modeladmin.message_user(
            request,
            f"{count} student(s) rejected. {non_students} non-student user(s) were skipped.",
            level=messages.WARNING,
        )
    else:
        modeladmin.message_user(request, f"{count} student(s) rejected.", level=messages.SUCCESS)


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    list_display = (
        "email",
        "first_name",
        "last_name",
        "role",
        "status",
        "is_active",
        "is_staff",
        "created_at",
    )
    list_filter = (
        "role",
        "status",
        "is_active",
        "is_staff",
        "created_at",
    )
    search_fields = (
        "email",
        "first_name",
        "last_name",
        "username",
    )
    ordering = ("-created_at", "email")
    actions = [approve_students, reject_students]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "username")}),
        (
            "CSL Role & Status",
            {
                "fields": (
                    "role",
                    "status",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "username",
                    "role",
                    "status",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )


from django import forms
from django.core.exceptions import ValidationError


class StudentProfileAdminForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        course = cleaned_data.get("course")
        batch = cleaned_data.get("batch")
        if batch and course and batch.course_id != course.id:
            raise ValidationError(
                {"batch": f"Batch '{batch.name}' does not belong to Course '{course.name}'."}
            )
        return cleaned_data


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    form = StudentProfileAdminForm
    list_display = (
        "registration_number",
        "get_email",
        "first_name",
        "last_name",
        "course",
        "batch",
        "created_at",
    )
    list_filter = (
        "course",
        "batch",
        "created_at",
    )
    search_fields = (
        "registration_number",
        "user__email",
        "first_name",
        "last_name",
    )
    ordering = ("registration_number",)
    autocomplete_fields = ["user", "course", "batch"]

    @admin.display(description="Student Email", ordering="user__email")
    def get_email(self, obj):
        return obj.user.email if obj.user else "-"
