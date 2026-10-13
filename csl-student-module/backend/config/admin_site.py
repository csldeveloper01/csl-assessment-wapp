from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _
from apps.users.models import User, StudentProfile
from apps.courses.models import Course, Batch
from apps.activities.models import Activity, Assessment, Task, Project


class CSLAdminSite(AdminSite):
    site_header = "CSL Skill Matrix Administration"
    site_title = "CSL Admin Portal"
    index_title = "CSL Operational Dashboard"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}

        # Operational metrics
        extra_context["pending_students_count"] = User.objects.filter(
            role=User.Role.STUDENT, status=User.AccountStatus.PENDING
        ).count()
        extra_context["active_students_count"] = User.objects.filter(
            role=User.Role.STUDENT, status=User.AccountStatus.ACTIVE
        ).count()
        extra_context["total_courses_count"] = Course.objects.filter(is_active=True).count()
        extra_context["total_batches_count"] = Batch.objects.filter(is_active=True).count()
        extra_context["draft_activities_count"] = Activity.objects.filter(status=Activity.Status.DRAFT).count()
        extra_context["active_activities_count"] = Activity.objects.filter(status=Activity.Status.ACTIVE).count()

        return super().index(request, extra_context)
