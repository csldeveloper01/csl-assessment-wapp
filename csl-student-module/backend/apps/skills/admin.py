from django.contrib import admin
from .models import SkillCategory, Skill, SubSkill


class SubSkillInline(admin.TabularInline):
    model = SubSkill
    extra = 1
    fields = ("name", "description", "display_order", "is_active")
    ordering = ("display_order", "id")


class SkillInline(admin.TabularInline):
    model = Skill
    extra = 1
    fields = ("name", "description", "is_active")
    show_change_link = True


@admin.register(SkillCategory)
class SkillCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "skills_count", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "description")
    ordering = ("name",)
    inlines = [SkillInline]

    @admin.display(description="Skills Count")
    def skills_count(self, obj):
        return obj.skills.count()


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "subskills_count", "is_active", "created_at")
    list_filter = ("category", "is_active", "created_at")
    search_fields = ("name", "description", "category__name")
    ordering = ("category__name", "name")
    inlines = [SubSkillInline]

    @admin.display(description="SubSkills Count")
    def subskills_count(self, obj):
        return obj.sub_skills.count()


@admin.register(SubSkill)
class SubSkillAdmin(admin.ModelAdmin):
    list_display = ("name", "skill", "get_category", "display_order", "is_active", "created_at")
    list_filter = ("skill__category", "skill", "is_active", "created_at")
    search_fields = ("name", "description", "skill__name", "skill__category__name")
    ordering = ("skill", "display_order", "id")
    list_editable = ("display_order", "is_active")

    @admin.display(description="Category", ordering="skill__category__name")
    def get_category(self, obj):
        return obj.skill.category.name if obj.skill else "-"
