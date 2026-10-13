from django.db import models
from django.db.models import Q


class ProficiencyLevel(models.TextChoices):
    FOUNDATIONAL = "FOUNDATIONAL", "Foundational"
    DEVELOPING = "DEVELOPING", "Developing"
    PROFICIENT = "PROFICIENT", "Proficient"
    ADVANCED = "ADVANCED", "Advanced"


class RecordStatus(models.TextChoices):
    CURRENT = "CURRENT", "Current"
    SUPERSEDED = "SUPERSEDED", "Superseded"


class SkillEvidence(models.Model):
    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="skill_evidences",
    )
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.CASCADE,
        related_name="skill_evidences",
    )
    evaluation = models.ForeignKey(
        "activities.Evaluation",
        on_delete=models.CASCADE,
        related_name="skill_evidences",
    )
    skill = models.ForeignKey(
        "skills.Skill",
        on_delete=models.PROTECT,
        related_name="evidences",
    )
    sub_skill = models.ForeignKey(
        "skills.SubSkill",
        on_delete=models.PROTECT,
        related_name="evidences",
    )
    result = models.PositiveIntegerField()
    is_valid = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "skill evidences"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "sub_skill"]),
            models.Index(fields=["evaluation"]),
            models.Index(fields=["is_valid"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["evaluation", "sub_skill"],
                name="uniq_evidence_per_evaluation_subskill",
            ),
        ]

    def __str__(self):
        return f"{self.student.registration_number} evidence for {self.sub_skill}"


class SubSkillScore(models.Model):
    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="sub_skill_scores",
    )
    sub_skill = models.ForeignKey(
        "skills.SubSkill",
        on_delete=models.PROTECT,
        related_name="student_scores",
    )
    score = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=RecordStatus.choices,
        default=RecordStatus.CURRENT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student", "sub_skill"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "sub_skill"],
                name="uniq_subskill_score_per_student",
            ),
        ]

    def __str__(self):
        return f"{self.student.registration_number} - {self.sub_skill.name}: {self.score}"


class SkillScore(models.Model):
    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="skill_scores",
    )
    skill = models.ForeignKey(
        "skills.Skill",
        on_delete=models.PROTECT,
        related_name="student_scores",
    )
    score = models.PositiveIntegerField(default=0)
    proficiency_level = models.CharField(
        max_length=20,
        choices=ProficiencyLevel.choices,
        default=ProficiencyLevel.FOUNDATIONAL,
    )
    status = models.CharField(
        max_length=20,
        choices=RecordStatus.choices,
        default=RecordStatus.CURRENT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student", "skill"]
        indexes = [
            models.Index(fields=["proficiency_level"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "skill"],
                name="uniq_skill_score_per_student",
            ),
        ]

    def __str__(self):
        return (
            f"{self.student.registration_number} - {self.skill.name}: "
            f"{self.score} ({self.proficiency_level})"
        )


class OverallPerformance(models.Model):
    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="overall_performances",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.PROTECT,
        related_name="overall_performances",
    )
    batch = models.ForeignKey(
        "courses.Batch",
        on_delete=models.PROTECT,
        related_name="overall_performances",
    )
    overall_score = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=RecordStatus.choices,
        default=RecordStatus.CURRENT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-overall_score", "student"]
        indexes = [
            models.Index(fields=["course", "batch"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course", "batch"],
                name="uniq_overall_performance_per_student_context",
            ),
        ]

    def __str__(self):
        return (
            f"{self.student.registration_number} @ {self.batch}: {self.overall_score}"
        )


class LeaderboardEntry(models.Model):
    class RankingScope(models.TextChoices):
        GLOBAL = "GLOBAL", "Global"
        COURSE = "COURSE", "Course"
        BATCH = "BATCH", "Batch"

    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="leaderboard_entries",
    )
    ranking_scope = models.CharField(
        max_length=20,
        choices=RankingScope.choices,
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.PROTECT,
        related_name="leaderboard_entries",
        null=True,
        blank=True,
    )
    batch = models.ForeignKey(
        "courses.Batch",
        on_delete=models.PROTECT,
        related_name="leaderboard_entries",
        null=True,
        blank=True,
    )
    overall_performance = models.ForeignKey(
        OverallPerformance,
        on_delete=models.CASCADE,
        related_name="leaderboard_entries",
    )
    score = models.PositiveIntegerField(default=0)
    rank = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "leaderboard entries"
        ordering = ["ranking_scope", "rank"]
        indexes = [
            models.Index(fields=["ranking_scope", "rank"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "ranking_scope"],
                condition=Q(course__isnull=True, batch__isnull=True),
                name="uniq_leaderboard_global_entry",
            ),
            models.UniqueConstraint(
                fields=["student", "ranking_scope", "course"],
                condition=Q(course__isnull=False, batch__isnull=True),
                name="uniq_leaderboard_course_entry",
            ),
            models.UniqueConstraint(
                fields=["student", "ranking_scope", "course", "batch"],
                condition=Q(course__isnull=False, batch__isnull=False),
                name="uniq_leaderboard_batch_entry",
            ),
        ]

    def __str__(self):
        return f"#{self.rank} {self.student.registration_number} ({self.ranking_scope})"
