from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from .models import Course, Batch, CourseSkill


class BatchInline(admin.TabularInline):
    model = Batch
    extra = 1
    fields = ("name", "start_date", "end_date", "is_active")
    show_change_link = True


class CourseSkillInlineForm(forms.ModelForm):
    class Meta:
        model = CourseSkill
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        skill = cleaned_data.get("skill")
        sub_skill = cleaned_data.get("sub_skill")
        if skill and sub_skill:
            if sub_skill.skill_id != skill.id:
                raise ValidationError(
                    f"SubSkill '{sub_skill.name}' does not belong to Skill '{skill.name}'."
                )
        return cleaned_data


class CourseSkillInline(admin.TabularInline):
    model = CourseSkill
    form = CourseSkillInlineForm
    extra = 1
    fields = ("skill", "sub_skill")
    autocomplete_fields = ["skill", "sub_skill"]


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "batches_count", "required_skills_count", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "code", "description")
    ordering = ("code",)
    inlines = [BatchInline, CourseSkillInline]

    @admin.display(description="Batches")
    def batches_count(self, obj):
        return obj.batches.count()

    @admin.display(description="Required Skills")
    def required_skills_count(self, obj):
        return obj.course_skills.count()


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ("name", "course", "start_date", "end_date", "students_count", "is_active", "created_at")
    list_filter = ("course", "is_active", "start_date")
    search_fields = ("name", "course__name", "course__code")
    ordering = ("-start_date", "name")
    autocomplete_fields = ["course"]

    @admin.display(description="Students Enrolled")
    def students_count(self, obj):
        return obj.students.count()


@admin.register(CourseSkill)
class CourseSkillAdmin(admin.ModelAdmin):
    form = CourseSkillInlineForm
    list_display = ("course", "skill", "sub_skill", "created_at")
    list_filter = ("course", "skill", "created_at")
    search_fields = ("course__name", "course__code", "skill__name", "sub_skill__name")
    ordering = ("course", "skill", "sub_skill")
    autocomplete_fields = ["course", "skill", "sub_skill"]
