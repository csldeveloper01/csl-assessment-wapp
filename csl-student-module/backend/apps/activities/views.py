from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from apps.users.models import User, StudentProfile
from .models import Activity
from .serializers import (
    StudentActivityListSerializer,
    StudentActivityDetailSerializer,
    StaffActivityCreateSerializer,
    StaffActivityListSerializer,
)


class StudentActivitiesListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != User.Role.STUDENT:
            return Response(
                {"detail": "Only students can access activities."},
                status=status.HTTP_403_FORBIDDEN,
            )

        profile, _ = StudentProfile.objects.get_or_create(
            user=user,
            defaults={
                "registration_number": f"CSL{user.id:04d}",
                "first_name": user.first_name or "Student",
                "last_name": user.last_name or "",
            },
        )

        if not profile.course:
            return Response({"activities": []}, status=status.HTTP_200_OK)

        # Activities applicable to student:
        # Same course, is_active=True, status!=DRAFT,
        # and batch is either NULL (course-wide) or matches student's batch.
        batch_filter = Q(batch__isnull=True)
        if profile.batch:
            batch_filter = batch_filter | Q(batch=profile.batch)

        activities = (
            Activity.objects.filter(
                course=profile.course,
                is_active=True,
                status=Activity.Status.ACTIVE,
            )
            .filter(batch_filter)
            .select_related("course", "batch")
            .order_by("deadline", "-created_at")
        )

        serializer = StudentActivityListSerializer(
            activities,
            many=True,
            context={"student_profile": profile},
        )
        return Response({"activities": serializer.data}, status=status.HTTP_200_OK)


class StudentActivityDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = request.user
        if user.role != User.Role.STUDENT:
            return Response(
                {"detail": "Only students can access activities."},
                status=status.HTTP_403_FORBIDDEN,
            )

        profile, _ = StudentProfile.objects.get_or_create(
            user=user,
            defaults={
                "registration_number": f"CSL{user.id:04d}",
                "first_name": user.first_name or "Student",
                "last_name": user.last_name or "",
            },
        )

        if not profile.course:
            return Response(
                {"detail": "Activity not found or not accessible."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check accessibility
        batch_filter = Q(batch__isnull=True)
        if profile.batch:
            batch_filter = batch_filter | Q(batch=profile.batch)

        try:
            activity = (
                Activity.objects.filter(
                    id=pk,
                    course=profile.course,
                    is_active=True,
                    status=Activity.Status.ACTIVE,
                )
                .filter(batch_filter)
                .select_related("course", "batch")
                .get()
            )
        except Activity.DoesNotExist:
            return Response(
                {"detail": "Activity not found or not accessible."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = StudentActivityDetailSerializer(
            activity,
            context={"student_profile": profile},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


# ==============================================================================
# Staff Activity Management Views
# ==============================================================================

class StaffActivityListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _check_permission(self, user):
        return user.role in (User.Role.ADMIN, User.Role.TUTOR)

    def get(self, request):
        if not self._check_permission(request.user):
            return Response(
                {"detail": "You do not have permission to manage activities."},
                status=status.HTTP_403_FORBIDDEN,
            )

        activities = (
            Activity.objects.all()
            .select_related("course", "batch", "created_by")
            .order_by("-created_at")
        )
        serializer = StaffActivityListSerializer(activities, many=True)
        return Response({"activities": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        if not self._check_permission(request.user):
            return Response(
                {"detail": "You do not have permission to manage activities."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = StaffActivityCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        activity_type = data["activity_type"]
        course = data["course_obj"]
        batch = data["batch_obj"]

        # Polymorphic creation based on ActivityType
        from .models import Task, Assessment, Project, TaskSkill, ProjectSkill, AssessmentSection, Question
        from apps.skills.models import Skill, SubSkill

        if activity_type == Activity.ActivityType.TASK:
            activity = Task.objects.create(
                title=data["title"],
                description=data.get("description", ""),
                course=course,
                batch=batch,
                created_by=request.user,
                max_marks=data["max_marks"],
                deadline=data.get("deadline"),
                status=data.get("status", Activity.Status.DRAFT),
            )
            # Create TaskSkill mappings
            for sk_item in data.get("skills", []):
                sub_id = sk_item.get("sub_skill_id")
                TaskSkill.objects.create(
                    task=activity,
                    skill_id=sk_item["skill_id"],
                    sub_skill_id=sub_id if sub_id else None,
                )

        elif activity_type == Activity.ActivityType.PROJECT:
            activity = Project.objects.create(
                title=data["title"],
                description=data.get("description", ""),
                course=course,
                batch=batch,
                created_by=request.user,
                max_marks=data["max_marks"],
                deadline=data.get("deadline"),
                status=data.get("status", Activity.Status.DRAFT),
            )
            # Create ProjectSkill mappings
            for sk_item in data.get("skills", []):
                sub_id = sk_item.get("sub_skill_id")
                ProjectSkill.objects.create(
                    project=activity,
                    skill_id=sk_item["skill_id"],
                    sub_skill_id=sub_id if sub_id else None,
                )

        elif activity_type == Activity.ActivityType.ASSESSMENT:
            activity = Assessment.objects.create(
                title=data["title"],
                description=data.get("description", ""),
                course=course,
                batch=batch,
                created_by=request.user,
                max_marks=data["max_marks"],
                deadline=data.get("deadline"),
                status=data.get("status", Activity.Status.DRAFT),
            )
            # Create Sections and Questions
            for s_idx, sec_data in enumerate(data.get("sections", []), start=1):
                section = AssessmentSection.objects.create(
                    assessment=activity,
                    title=sec_data["title"],
                    description=sec_data.get("description", ""),
                    order=sec_data.get("order", s_idx),
                )
                for q_idx, q_data in enumerate(sec_data.get("questions", []), start=1):
                    Question.objects.create(
                        section=section,
                        prompt=q_data["prompt"],
                        skill_id=q_data["skill_id"],
                        sub_skill_id=q_data["sub_skill_id"],
                        max_marks=q_data["max_marks"],
                        order=q_data.get("order", q_idx),
                    )

        detail_serializer = StaffActivityListSerializer(activity)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)


class StaffActivityDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _check_permission(self, user):
        return user.role in (User.Role.ADMIN, User.Role.TUTOR)

    def get(self, request, pk):
        if not self._check_permission(request.user):
            return Response(
                {"detail": "You do not have permission to manage activities."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            activity = Activity.objects.select_related("course", "batch", "created_by").get(id=pk)
        except Activity.DoesNotExist:
            return Response(
                {"detail": "Activity not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = StudentActivityDetailSerializer(activity)
        data = dict(serializer.data)
        data["status"] = activity.status  # Staff gets exact model status
        return Response(data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        if not self._check_permission(request.user):
            return Response(
                {"detail": "You do not have permission to manage activities."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            activity = Activity.objects.get(id=pk)
        except Activity.DoesNotExist:
            return Response(
                {"detail": "Activity not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Handle lifecycle actions / field updates
        allowed_fields = ["title", "description", "status", "deadline", "max_marks"]
        for field in allowed_fields:
            if field in request.data:
                val = request.data[field]
                if field == "status" and val in Activity.Status.values:
                    # If setting to ACTIVE, verify deadline exists
                    target_deadline = request.data.get("deadline", activity.deadline)
                    if val == Activity.Status.ACTIVE and not target_deadline:
                        return Response(
                            {"deadline": "A valid deadline is required to activate an activity."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    setattr(activity, field, val)
                elif field == "max_marks":
                    try:
                        val_num = int(val)
                        if val_num <= 0:
                            raise ValueError()
                        if activity.activity_type == Activity.ActivityType.ASSESSMENT and val_num > 200:
                            return Response(
                                {"max_marks": "Assessment cannot exceed 200 maximum marks."},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        elif activity.activity_type in (Activity.ActivityType.TASK, Activity.ActivityType.PROJECT) and val_num > 100:
                            return Response(
                                {"max_marks": f"{activity.activity_type.capitalize()} cannot exceed 100 maximum marks."},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        setattr(activity, field, val_num)
                    except (ValueError, TypeError):
                        return Response(
                            {"max_marks": "Maximum marks must be a valid positive integer."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                elif field == "deadline":
                    setattr(activity, field, val)
                elif field in ("title", "description"):
                    if field == "title" and not str(val).strip():
                        return Response({"title": "Title is required."}, status=status.HTTP_400_BAD_REQUEST)
                    setattr(activity, field, val)

        activity.save()
        serializer = StaffActivityListSerializer(activity)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        if not self._check_permission(request.user):
            return Response(
                {"detail": "You do not have permission to manage activities."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            activity = Activity.objects.get(id=pk)
        except Activity.DoesNotExist:
            return Response(
                {"detail": "Activity not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        activity.delete()
        return Response({"message": "Activity deleted successfully."}, status=status.HTTP_200_OK)


class CourseBatchOptionsView(APIView):
    """Provides courses, batches, and skills/subskills for activity authoring."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in (User.Role.ADMIN, User.Role.TUTOR):
            return Response(
                {"detail": "Permission denied."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from apps.courses.models import Course, Batch
        from apps.skills.models import SkillCategory, Skill, SubSkill

        courses_data = []
        for c in Course.objects.filter(is_active=True).prefetch_related("batches"):
            batches_data = [
                {"id": b.id, "name": b.name}
                for b in c.batches.filter(is_active=True)
            ]
            courses_data.append({
                "id": c.id,
                "name": c.name,
                "code": c.code,
                "batches": batches_data,
            })

        skills_data = []
        for sk in Skill.objects.filter(is_active=True).prefetch_related("sub_skills").select_related("category"):
            subskills_data = [
                {"id": sub.id, "name": sub.name}
                for sub in sk.sub_skills.filter(is_active=True)
            ]
            skills_data.append({
                "id": sk.id,
                "name": sk.name,
                "category": sk.category.name,
                "subskills": subskills_data,
            })

        return Response(
            {
                "courses": courses_data,
                "skills": skills_data,
            },
            status=status.HTTP_200_OK,
        )

