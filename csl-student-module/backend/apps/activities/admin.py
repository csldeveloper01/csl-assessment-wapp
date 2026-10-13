from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.utils import timezone
from .models import (
    Activity,
    Assessment,
    AssessmentSection,
    Question,
    Task,
    Project,
    TaskSkill,
    ProjectSkill,
    Submission,
    Evaluation,
    EvaluationHistory,
)


# --- Custom Forms & Actions ---

class ActivityAdminForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        activity_type = cleaned_data.get("activity_type")
        max_marks = cleaned_data.get("max_marks")
        status = cleaned_data.get("status")
        deadline = cleaned_data.get("deadline")
        course = cleaned_data.get("course")
        batch = cleaned_data.get("batch")

        # Mark limits validation
        if max_marks is not None:
            if activity_type == Activity.ActivityType.ASSESSMENT and max_marks > 200:
                raise ValidationError({"max_marks": "Maximum marks for Assessment cannot exceed 200."})
            elif activity_type in (Activity.ActivityType.TASK, Activity.ActivityType.PROJECT) and max_marks > 100:
                raise ValidationError({"max_marks": f"Maximum marks for {activity_type} cannot exceed 100."})

        # Batch belongs to course validation
        if batch and course and batch.course_id != course.id:
            raise ValidationError({"batch": f"Batch '{batch.name}' does not belong to course '{course.name}'."})

        # Publishing validation
        if status == Activity.Status.ACTIVE and not deadline:
            raise ValidationError({"deadline": "A valid deadline is required to set status to ACTIVE."})

        return cleaned_data


@admin.action(description="Publish / Activate selected activities")
def publish_activities(modeladmin, request, queryset):
    now = timezone.now()
    published_count = 0
    skipped_count = 0
    for act in queryset:
        if not act.deadline:
            skipped_count += 1
            continue
        act.status = Activity.Status.ACTIVE
        act.is_active = True
        act.save(update_fields=["status", "is_active", "updated_at"])
        published_count += 1

    if skipped_count:
        modeladmin.message_user(
            request,
            f"{published_count} activity/activities published. {skipped_count} skipped because deadline is missing.",
            level=messages.WARNING,
        )
    else:
        modeladmin.message_user(
            request,
            f"{published_count} activity/activities published to ACTIVE.",
            level=messages.SUCCESS,
        )


@admin.action(description="Archive selected activities")
def archive_activities(modeladmin, request, queryset):
    count = queryset.update(status=Activity.Status.ARCHIVED, updated_at=timezone.now())
    modeladmin.message_user(request, f"{count} activity/activities archived.", level=messages.SUCCESS)


# --- Inlines ---

class TaskSkillInlineForm(forms.ModelForm):
    class Meta:
        model = TaskSkill
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        skill = cleaned_data.get("skill")
        sub_skill = cleaned_data.get("sub_skill")
        if skill and sub_skill and sub_skill.skill_id != skill.id:
            raise ValidationError(f"SubSkill '{sub_skill.name}' does not belong to Skill '{skill.name}'.")
        return cleaned_data


class TaskSkillInline(admin.TabularInline):
    model = TaskSkill
    form = TaskSkillInlineForm
    extra = 1
    autocomplete_fields = ["skill", "sub_skill"]


class ProjectSkillInlineForm(forms.ModelForm):
    class Meta:
        model = ProjectSkill
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        skill = cleaned_data.get("skill")
        sub_skill = cleaned_data.get("sub_skill")
        if skill and sub_skill and sub_skill.skill_id != skill.id:
            raise ValidationError(f"SubSkill '{sub_skill.name}' does not belong to Skill '{skill.name}'.")
        return cleaned_data


class ProjectSkillInline(admin.TabularInline):
    model = ProjectSkill
    form = ProjectSkillInlineForm
    extra = 1
    autocomplete_fields = ["skill", "sub_skill"]


class QuestionInlineForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        skill = cleaned_data.get("skill")
        sub_skill = cleaned_data.get("sub_skill")
        if skill and sub_skill and sub_skill.skill_id != skill.id:
            raise ValidationError(f"SubSkill '{sub_skill.name}' does not belong to Skill '{skill.name}'.")
        return cleaned_data


class QuestionInline(admin.TabularInline):
    model = Question
    form = QuestionInlineForm
    extra = 1
    fields = ("order", "prompt", "max_marks", "skill", "sub_skill")
    autocomplete_fields = ["skill", "sub_skill"]


class AssessmentSectionInline(admin.TabularInline):
    model = AssessmentSection
    extra = 1
    fields = ("order", "title", "description")
    show_change_link = True


# --- Model Admins ---

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    form = ActivityAdminForm
    list_display = (
        "title",
        "activity_type",
        "course",
        "batch",
        "max_marks",
        "deadline",
        "status",
        "created_by",
        "created_at",
    )
    list_filter = (
        "activity_type",
        "status",
        "course",
        "batch",
        "is_active",
        "created_at",
    )
    search_fields = (
        "title",
        "description",
        "course__name",
        "course__code",
        "batch__name",
        "created_by__email",
    )
    ordering = ("-created_at",)
    actions = [publish_activities, archive_activities]
    autocomplete_fields = ["course", "batch", "created_by"]

    fieldsets = (
        (
            "Activity Information",
            {
                "fields": (
                    "title",
                    "activity_type",
                    "description",
                )
            },
        ),
        (
            "Course & Batch Targeting",
            {
                "description": "Select target course and optional batch (leave empty for course-wide).",
                "fields": (
                    "course",
                    "batch",
                ),
            },
        ),
        (
            "Assessment Configuration",
            {
                "fields": (
                    "max_marks",
                    "deadline",
                    "status",
                    "is_active",
                ),
            },
        ),
        (
            "Metadata",
            {
                "classes": ("collapse",),
                "fields": ("created_by",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    form = ActivityAdminForm
    list_display = (
        "title",
        "course",
        "batch",
        "max_marks",
        "deadline",
        "status",
        "sections_count",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "course", "batch", "is_active", "created_at")
    search_fields = ("title", "description", "course__name", "course__code", "batch__name")
    ordering = ("-created_at",)
    actions = [publish_activities, archive_activities]
    inlines = [AssessmentSectionInline]
    autocomplete_fields = ["course", "batch", "created_by"]

    @admin.display(description="Sections Count")
    def sections_count(self, obj):
        return obj.sections.count()

    def save_model(self, request, obj, form, change):
        obj.activity_type = Activity.ActivityType.ASSESSMENT
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AssessmentSection)
class AssessmentSectionAdmin(admin.ModelAdmin):
    list_display = ("title", "assessment", "order", "questions_count", "created_at")
    list_filter = ("assessment__course", "assessment", "created_at")
    search_fields = ("title", "description", "assessment__title")
    ordering = ("assessment", "order", "id")
    inlines = [QuestionInline]
    autocomplete_fields = ["assessment"]

    @admin.display(description="Questions Count")
    def questions_count(self, obj):
        return obj.questions.count()


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    form = QuestionInlineForm
    list_display = (
        "__str__",
        "question_type",
        "section",
        "get_assessment",
        "max_marks",
        "skill",
        "sub_skill",
    )
    list_filter = (
        "question_type",
        "skill",
        "section__assessment__course",
        "created_at",
    )
    search_fields = (
        "prompt",
        "input_description",
        "output_description",
        "section__title",
        "section__assessment__title",
        "skill__name",
        "sub_skill__name",
    )
    ordering = ("section", "order", "id")
    autocomplete_fields = ["section", "skill", "sub_skill"]

    fieldsets = (
        (
            "Question Identification",
            {
                "fields": (
                    "section",
                    "order",
                    "question_type",
                    "prompt",
                    "max_marks",
                    "skill",
                    "sub_skill",
                )
            },
        ),
        (
            "Coding Problem Specifications",
            {
                "classes": ("collapse",),
                "description": "Configure test constraints and environment parameters for coding problems.",
                "fields": (
                    "input_description",
                    "output_description",
                    "constraints",
                    "sample_input",
                    "sample_output",
                    "allowed_languages",
                    "time_limit_seconds",
                    "memory_limit_mb",
                ),
            },
        ),
    )

    @admin.display(description="Assessment", ordering="section__assessment__title")
    def get_assessment(self, obj):
        return obj.section.assessment.title if obj.section and obj.section.assessment else "-"


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    form = ActivityAdminForm
    list_display = (
        "title",
        "course",
        "batch",
        "max_marks",
        "deadline",
        "status",
        "skills_mapped_count",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "course", "batch", "is_active", "created_at")
    search_fields = ("title", "description", "course__name", "course__code", "batch__name")
    ordering = ("-created_at",)
    actions = [publish_activities, archive_activities]
    inlines = [TaskSkillInline]
    autocomplete_fields = ["course", "batch", "created_by"]

    @admin.display(description="Skills Mapped")
    def skills_mapped_count(self, obj):
        return obj.skill_mappings.count()

    def save_model(self, request, obj, form, change):
        obj.activity_type = Activity.ActivityType.TASK
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    form = ActivityAdminForm
    list_display = (
        "title",
        "course",
        "batch",
        "max_marks",
        "deadline",
        "status",
        "skills_mapped_count",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "course", "batch", "is_active", "created_at")
    search_fields = ("title", "description", "course__name", "course__code", "batch__name")
    ordering = ("-created_at",)
    actions = [publish_activities, archive_activities]
    inlines = [ProjectSkillInline]
    autocomplete_fields = ["course", "batch", "created_by"]

    @admin.display(description="Skills Mapped")
    def skills_mapped_count(self, obj):
        return obj.skill_mappings.count()

    def save_model(self, request, obj, form, change):
        obj.activity_type = Activity.ActivityType.PROJECT
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TaskSkill)
class TaskSkillAdmin(admin.ModelAdmin):
    form = TaskSkillInlineForm
    list_display = ("task", "skill", "sub_skill", "created_at")
    list_filter = ("skill", "task__course", "created_at")
    search_fields = ("task__title", "skill__name", "sub_skill__name")
    ordering = ("task", "skill")
    autocomplete_fields = ["task", "skill", "sub_skill"]


@admin.register(ProjectSkill)
class ProjectSkillAdmin(admin.ModelAdmin):
    form = ProjectSkillInlineForm
    list_display = ("project", "skill", "sub_skill", "created_at")
    list_filter = ("skill", "project__course", "created_at")
    search_fields = ("project__title", "skill__name", "sub_skill__name")
    ordering = ("project", "skill")
    autocomplete_fields = ["project", "skill", "sub_skill"]


# --- Future Submissions / Evaluations (Read-only / Safe display) ---

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("student", "activity", "status", "submitted_at", "created_at")
    list_filter = ("status", "activity__course", "activity__activity_type", "created_at")
    search_fields = ("student__registration_number", "student__user__email", "activity__title")
    ordering = ("-created_at",)
    autocomplete_fields = ["student", "activity"]


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("submission", "evaluator", "obtained_marks", "status", "evaluated_at", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("submission__student__registration_number", "evaluator__email")
    ordering = ("-created_at",)
    autocomplete_fields = ["submission", "evaluator"]


@admin.register(EvaluationHistory)
class EvaluationHistoryAdmin(admin.ModelAdmin):
    list_display = ("evaluation", "evaluator", "obtained_marks", "status", "recorded_at")
    list_filter = ("status", "recorded_at")
    search_fields = ("evaluation__submission__student__registration_number", "evaluator__email")
    ordering = ("-recorded_at",)
    autocomplete_fields = ["evaluation", "evaluator"]
