import csv
import io
from django.contrib import admin
from django import forms
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from django.utils.html import format_html
from django.db import transaction

from .models import (
    QuestionBank,
    AssessmentConfig,
    Candidate,
    AssessmentAttempt,
    AttemptQuestionSnapshot,
    IntegrityEvent,
)


class CSVImportForm(forms.Form):
    csv_file = forms.FileField(help_text="Upload CSV containing questions (prompt, section_type, category, difficulty, option_a, option_b, option_c, option_d, correct_option, explanation)")


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "section_type",
        "category",
        "difficulty",
        "get_prompt_preview",
        "correct_option",
        "is_active",
        "created_at",
    )
    list_filter = ("section_type", "difficulty", "category", "is_active")
    search_fields = ("prompt", "category", "explanation")
    ordering = ("section_type", "category", "id")
    actions = ["activate_questions", "deactivate_questions"]
    change_list_template = "admin/assessments/questionbank/change_list.html"

    def get_prompt_preview(self, obj):
        return obj.prompt[:80] + ("..." if len(obj.prompt) > 80 else "")
    get_prompt_preview.short_description = "Prompt"

    @admin.action(description="Activate selected questions")
    def activate_questions(self, request, queryset):
        count = queryset.update(is_active=True)
        messages.success(request, f"{count} question(s) marked active.")

    @admin.action(description="Deactivate selected questions")
    def deactivate_questions(self, request, queryset):
        count = queryset.update(is_active=False)
        messages.success(request, f"{count} question(s) marked inactive.")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("import-csv/", self.admin_site.admin_view(self.import_csv_view), name="questionbank_import_csv"),
            path("export-csv/", self.admin_site.admin_view(self.export_csv_view), name="questionbank_export_csv"),
        ]
        return custom_urls + urls

    def import_csv_view(self, request):
        if request.method == "POST":
            form = CSVImportForm(request.POST, request.FILES)
            if form.is_valid():
                file = request.FILES["csv_file"]
                decoded_file = file.read().decode("utf-8-sig", errors="replace")
                reader = csv.DictReader(io.StringIO(decoded_file))
                
                required_cols = {"prompt", "section_type", "option_a", "option_b", "option_c", "option_d", "correct_option"}
                if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
                    missing = required_cols - set(reader.fieldnames or [])
                    messages.error(request, f"CSV is missing required columns: {', '.join(missing)}")
                    return render(request, "admin/assessments/questionbank/import_csv.html", {"form": form})

                questions_to_create = []
                errors = []
                seen_prompts = set(QuestionBank.objects.values_list("prompt", flat=True))

                for idx, row in enumerate(reader, start=2):
                    prompt = row.get("prompt", "").strip()
                    section_type = row.get("section_type", "").strip().upper()
                    category = row.get("category", "").strip()
                    difficulty = row.get("difficulty", "MEDIUM").strip().upper()
                    opt_a = row.get("option_a", "").strip()
                    opt_b = row.get("option_b", "").strip()
                    opt_c = row.get("option_c", "").strip()
                    opt_d = row.get("option_d", "").strip()
                    correct = row.get("correct_option", "").strip().upper()
                    explanation = row.get("explanation", "").strip()

                    if not prompt or not opt_a or not opt_b or not opt_c or not opt_d:
                        errors.append(f"Row {idx}: Missing prompt or options.")
                        continue

                    if section_type not in ("APTITUDE", "CODING"):
                        errors.append(f"Row {idx}: Invalid section_type '{section_type}'. Must be APTITUDE or CODING.")
                        continue

                    if correct not in ("A", "B", "C", "D"):
                        errors.append(f"Row {idx}: Invalid correct_option '{correct}'. Must be A, B, C, or D.")
                        continue

                    if prompt in seen_prompts:
                        errors.append(f"Row {idx}: Duplicate prompt skipped: '{prompt[:50]}...'.")
                        continue

                    seen_prompts.add(prompt)
                    questions_to_create.append(
                        QuestionBank(
                            prompt=prompt,
                            section_type=section_type,
                            category=category or "General",
                            difficulty=difficulty if difficulty in ("EASY", "MEDIUM", "HARD") else "MEDIUM",
                            option_a=opt_a,
                            option_b=opt_b,
                            option_c=opt_c,
                            option_d=opt_d,
                            correct_option=correct,
                            explanation=explanation,
                        )
                    )

                if errors and not questions_to_create:
                    messages.error(request, f"Import failed completely with {len(errors)} errors: " + " | ".join(errors[:5]))
                elif questions_to_create:
                    with transaction.atomic():
                        QuestionBank.objects.bulk_create(questions_to_create)
                    if errors:
                        messages.warning(
                            request,
                            f"Imported {len(questions_to_create)} questions with {len(errors)} row-level notices: " + " | ".join(errors[:5]),
                        )
                    else:
                        messages.success(request, f"Successfully imported all {len(questions_to_create)} questions transactional batch!")
                return redirect("..")
        else:
            form = CSVImportForm()

        return render(request, "admin/assessments/questionbank/import_csv.html", {"form": form})

    def export_csv_view(self, request):
        from django.http import HttpResponse
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="csl_question_bank.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "prompt", "section_type", "category", "difficulty",
            "option_a", "option_b", "option_c", "option_d",
            "correct_option", "explanation"
        ])
        for q in QuestionBank.objects.all():
            writer.writerow([
                q.prompt, q.section_type, q.category, q.difficulty,
                q.option_a, q.option_b, q.option_c, q.option_d,
                q.correct_option, q.explanation
            ])
        return response


@admin.register(AssessmentConfig)
class AssessmentConfigAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "duration_minutes",
        "total_marks",
        "aptitude_count",
        "coding_count",
        "max_attempts",
        "max_tab_switches_warning",
        "auto_submit_on_tab_limit",
        "is_active",
        "created_at",
    )
    list_editable = ("is_active", "duration_minutes", "max_tab_switches_warning", "auto_submit_on_tab_limit")
    fieldsets = (
        ("Assessment Overview", {
            "fields": ("title", "description", "is_active")
        }),
        ("Exam Duration & Question Allocation", {
            "fields": ("duration_minutes", "total_marks", "aptitude_count", "coding_count", "max_attempts")
        }),
        ("Browser Integrity & Tab Monitoring", {
            "fields": ("max_tab_switches_warning", "auto_submit_on_tab_limit")
        }),
    )


class AttemptQuestionSnapshotInline(admin.TabularInline):
    model = AttemptQuestionSnapshot
    extra = 0
    can_delete = False
    readonly_fields = (
        "question_order",
        "section_type",
        "prompt",
        "selected_option",
        "correct_option_key",
        "is_correct",
        "answered_at",
    )
    fields = (
        "question_order",
        "section_type",
        "prompt",
        "selected_option",
        "correct_option_key",
        "is_correct",
        "answered_at",
    )


class IntegrityEventInline(admin.TabularInline):
    model = IntegrityEvent
    extra = 0
    can_delete = False
    readonly_fields = ("event_type", "event_id", "client_timestamp", "server_timestamp", "metadata")
    fields = ("event_type", "event_id", "client_timestamp", "server_timestamp", "metadata")


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "register_number",
        "college",
        "email",
        "department",
        "year_of_study",
        "created_at",
    )
    list_filter = ("college", "department", "year_of_study", "created_at")
    search_fields = ("full_name", "register_number", "college", "email", "phone_number")
    ordering = ("-created_at",)


@admin.register(AssessmentAttempt)
class AssessmentAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "get_candidate_name",
        "get_college",
        "state",
        "total_score",
        "aptitude_score",
        "coding_score",
        "percentage",
        "tab_switch_count",
        "fullscreen_exit_count",
        "is_flagged",
        "get_flag_status",
        "started_at",
        "submitted_at",
    )
    list_filter = ("state", "is_flagged", "config", "candidate__college", "started_at")
    search_fields = (
        "candidate__full_name",
        "candidate__register_number",
        "candidate__email",
        "candidate__college",
        "flag_reason",
    )
    readonly_fields = (
        "candidate",
        "config",
        "state",
        "started_at",
        "deadline",
        "submitted_at",
        "aptitude_score",
        "coding_score",
        "total_score",
        "percentage",
        "tab_switch_count",
        "fullscreen_exit_count",
        "is_flagged",
        "flag_reason",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)
    inlines = [AttemptQuestionSnapshotInline, IntegrityEventInline]

    def get_candidate_name(self, obj):
        return obj.candidate.full_name
    get_candidate_name.short_description = "Candidate"
    get_candidate_name.admin_order_field = "candidate__full_name"

    def get_college(self, obj):
        return obj.candidate.college
    get_college.short_description = "College"
    get_college.admin_order_field = "candidate__college"

    def get_flag_status(self, obj):
        if obj.is_flagged:
            return format_html('<span style="color: #dc2626; font-weight: 600;">⚠ {}</span>', obj.flag_reason or "Flagged")
        return format_html('<span style="color: #16a34a;">✓ Clean</span>')
    get_flag_status.short_description = "Integrity Status"


@admin.register(IntegrityEvent)
class IntegrityEventAdmin(admin.ModelAdmin):
    list_display = ("attempt", "get_candidate_name", "event_type", "event_id", "server_timestamp")
    list_filter = ("event_type", "server_timestamp")
    search_fields = ("attempt__candidate__full_name", "attempt__candidate__register_number", "event_id")
    readonly_fields = ("attempt", "event_type", "event_id", "client_timestamp", "server_timestamp", "metadata")
    ordering = ("-server_timestamp",)

    def get_candidate_name(self, obj):
        return obj.attempt.candidate.full_name
    get_candidate_name.short_description = "Candidate"
