from django.conf import settings
from django.db import models
from django.db.models import Q


class Activity(models.Model):
    class ActivityType(models.TextChoices):
        ASSESSMENT = "ASSESSMENT", "Assessment"
        TASK = "TASK", "Task"
        PROJECT = "PROJECT", "Project"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        ARCHIVED = "ARCHIVED", "Archived"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    activity_type = models.CharField(max_length=20, choices=ActivityType.choices)
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.PROTECT,
        related_name="activities",
    )
    batch = models.ForeignKey(
        "courses.Batch",
        on_delete=models.PROTECT,
        related_name="activities",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_activities",
    )
    max_marks = models.PositiveIntegerField()
    deadline = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["activity_type", "status"]),
            models.Index(fields=["course", "batch"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.activity_type})"


class Assessment(Activity):
    class Meta:
        verbose_name = "assessment"

    def save(self, *args, **kwargs):
        self.activity_type = Activity.ActivityType.ASSESSMENT
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Task(Activity):
    class Meta:
        verbose_name = "task"

    def save(self, *args, **kwargs):
        self.activity_type = Activity.ActivityType.TASK
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Project(Activity):
    class Meta:
        verbose_name = "project"

    def save(self, *args, **kwargs):
        self.activity_type = Activity.ActivityType.PROJECT
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class AssessmentSection(models.Model):
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["assessment", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "title"],
                name="uniq_section_title_per_assessment",
            ),
        ]

    def __str__(self):
        return f"{self.assessment.title} / {self.title}"


class Question(models.Model):
    class QuestionType(models.TextChoices):
        NORMAL = "NORMAL", "Normal / Conceptual"
        CODING = "CODING", "Coding Problem"

    section = models.ForeignKey(
        AssessmentSection,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.NORMAL,
    )
    prompt = models.TextField(help_text="Problem statement or question text")
    input_description = models.TextField(blank=True, help_text="Format and constraints for inputs")
    output_description = models.TextField(blank=True, help_text="Format of expected output")
    constraints = models.TextField(blank=True, help_text="Constraints on time, memory, or variable ranges")
    sample_input = models.TextField(blank=True, help_text="Sample input for test cases")
    sample_output = models.TextField(blank=True, help_text="Expected output for sample input")
    allowed_languages = models.CharField(
        max_length=255,
        blank=True,
        default="Python, JavaScript, Java, C++",
        help_text="Comma-separated list of allowed programming languages",
    )
    time_limit_seconds = models.PositiveIntegerField(
        default=2,
        help_text="Time limit per test execution in seconds",
    )
    memory_limit_mb = models.PositiveIntegerField(
        default=256,
        help_text="Memory limit in megabytes",
    )
    skill = models.ForeignKey(
        "skills.Skill",
        on_delete=models.PROTECT,
        related_name="questions",
    )
    sub_skill = models.ForeignKey(
        "skills.SubSkill",
        on_delete=models.PROTECT,
        related_name="questions",
    )
    max_marks = models.PositiveIntegerField()
    order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["section", "order", "id"]
        indexes = [
            models.Index(fields=["skill", "sub_skill"]),
            models.Index(fields=["question_type"]),
        ]

    def clean(self):
        super().clean()
        if self.skill_id and self.sub_skill_id:
            if self.sub_skill.skill_id != self.skill_id:
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    {"sub_skill": f"SubSkill '{self.sub_skill.name}' does not belong to Skill '{self.skill.name}'."}
                )

    def __str__(self):
        return f"Q{self.order}: {self.prompt[:60]}"


class TaskSkill(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="skill_mappings",
    )
    skill = models.ForeignKey(
        "skills.Skill",
        on_delete=models.PROTECT,
        related_name="task_mappings",
    )
    sub_skill = models.ForeignKey(
        "skills.SubSkill",
        on_delete=models.PROTECT,
        related_name="task_mappings",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["task", "skill", "sub_skill"],
                condition=Q(sub_skill__isnull=False),
                name="uniq_task_skill_subskill",
            ),
            models.UniqueConstraint(
                fields=["task", "skill"],
                condition=Q(sub_skill__isnull=True),
                name="uniq_task_skill_without_subskill",
            ),
        ]

    def __str__(self):
        target = self.sub_skill.name if self.sub_skill_id else self.skill.name
        return f"{self.task.title} → {target}"


class ProjectSkill(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="skill_mappings",
    )
    skill = models.ForeignKey(
        "skills.Skill",
        on_delete=models.PROTECT,
        related_name="project_mappings",
    )
    sub_skill = models.ForeignKey(
        "skills.SubSkill",
        on_delete=models.PROTECT,
        related_name="project_mappings",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "skill", "sub_skill"],
                condition=Q(sub_skill__isnull=False),
                name="uniq_project_skill_subskill",
            ),
            models.UniqueConstraint(
                fields=["project", "skill"],
                condition=Q(sub_skill__isnull=True),
                name="uniq_project_skill_without_subskill",
            ),
        ]

    def __str__(self):
        target = self.sub_skill.name if self.sub_skill_id else self.skill.name
        return f"{self.project.title} → {target}"


class Submission(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"

    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    content = models.TextField(blank=True)
    content_reference = models.CharField(max_length=500, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawal_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "activity"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.student.registration_number} → {self.activity.title}"


class Evaluation(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        RE_EVALUATED = "RE_EVALUATED", "Re-evaluated"

    submission = models.OneToOneField(
        Submission,
        on_delete=models.CASCADE,
        related_name="evaluation",
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="evaluations",
    )
    obtained_marks = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    feedback = models.TextField(blank=True)
    reason = models.TextField(blank=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["evaluator"]),
        ]

    def __str__(self):
        return f"Evaluation of {self.submission}"


class EvaluationHistory(models.Model):
    evaluation = models.ForeignKey(
        Evaluation,
        on_delete=models.CASCADE,
        related_name="history",
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="evaluation_history_entries",
    )
    obtained_marks = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Evaluation.Status.choices)
    feedback = models.TextField(blank=True)
    reason = models.TextField(blank=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "evaluation histories"
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"History for evaluation {self.evaluation_id} at {self.recorded_at}"
