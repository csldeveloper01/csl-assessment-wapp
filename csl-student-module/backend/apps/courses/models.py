from django.db import models
from django.db.models import Q


class Course(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Batch(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="batches",
    )
    name = models.CharField(max_length=150)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "name"],
                name="uniq_batch_name_per_course",
            ),
        ]
        indexes = [
            models.Index(fields=["course", "is_active"]),
        ]

    def __str__(self):
        return f"{self.course.code} / {self.name}"


class CourseSkill(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="course_skills",
    )
    skill = models.ForeignKey(
        "skills.Skill",
        on_delete=models.PROTECT,
        related_name="course_skills",
    )
    sub_skill = models.ForeignKey(
        "skills.SubSkill",
        on_delete=models.PROTECT,
        related_name="course_skills",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["course", "skill", "sub_skill"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "skill", "sub_skill"],
                condition=Q(sub_skill__isnull=False),
                name="uniq_course_skill_subskill",
            ),
            models.UniqueConstraint(
                fields=["course", "skill"],
                condition=Q(sub_skill__isnull=True),
                name="uniq_course_skill_without_subskill",
            ),
        ]

    def __str__(self):
        target = self.sub_skill.name if self.sub_skill_id else self.skill.name
        return f"{self.course.code} requires {target}"
