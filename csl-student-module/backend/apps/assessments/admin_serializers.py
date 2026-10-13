from rest_framework import serializers
from django.utils import timezone
from .models import (
    Candidate,
    College,
    Assessment,
    AssessmentAttempt,
    AttemptQuestionSnapshot,
    AssessmentConfig,
    IntegrityEvent,
    QuestionBank,
    AssessmentAuditLog,
)


class AdminCollegeListSerializer(serializers.ModelSerializer):
    candidates_count = serializers.SerializerMethodField()
    assigned_assessments_count = serializers.SerializerMethodField()
    active_attempts_count = serializers.SerializerMethodField()

    class Meta:
        model = College
        fields = [
            "id",
            "name",
            "code",
            "address",
            "location",
            "contact_email",
            "contact_phone",
            "admin_contact_name",
            "is_active",
            "created_at",
            "updated_at",
            "candidates_count",
            "assigned_assessments_count",
            "active_attempts_count",
        ]

    def get_candidates_count(self, obj):
        return obj.candidates.count()

    def get_assigned_assessments_count(self, obj):
        return obj.assigned_assessments.count()

    def get_active_attempts_count(self, obj):
        return AssessmentAttempt.objects.filter(
            candidate__college_ref=obj,
            state__in=[AssessmentAttempt.State.CREATED, AssessmentAttempt.State.IN_PROGRESS],
        ).count()


class AdminCollegeCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = College
        fields = [
            "id",
            "name",
            "code",
            "address",
            "location",
            "contact_email",
            "contact_phone",
            "admin_contact_name",
            "is_active",
        ]

    def validate_name(self, value):
        val = value.strip()
        if len(val) < 2:
            raise serializers.ValidationError("Institution name must be at least 2 characters.")
        return val

    def validate_code(self, value):
        val = value.strip().upper()
        if len(val) < 2:
            raise serializers.ValidationError("Institution code must be at least 2 characters.")
        existing = College.objects.filter(code__iexact=val)
        if self.instance:
            existing = existing.exclude(id=self.instance.id)
        if existing.exists():
            raise serializers.ValidationError(f"Institution code '{val}' is already taken.")
        return val


class AdminAssessmentAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentAuditLog
        fields = [
            "id",
            "action",
            "entity_type",
            "entity_id",
            "performed_by_name",
            "timestamp",
            "details",
        ]


class AdminAssessmentListSerializer(serializers.ModelSerializer):
    eligible_colleges = serializers.SerializerMethodField()
    eligible_colleges_count = serializers.SerializerMethodField()
    attempts_count = serializers.SerializerMethodField()
    in_progress_count = serializers.SerializerMethodField()
    submitted_count = serializers.SerializerMethodField()
    is_open = serializers.SerializerMethodField()
    pool_questions_count = serializers.SerializerMethodField()
    pool_aptitude_count = serializers.SerializerMethodField()
    pool_coding_count = serializers.SerializerMethodField()
    pool_sufficient = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            "id",
            "code",
            "title",
            "description",
            "status",
            "assessment_type",
            "is_open",
            "is_results_released",
            "results_released_at",
            "duration_minutes",
            "total_marks",
            "aptitude_count",
            "coding_count",
            "max_attempts",
            "max_tab_switches_warning",
            "auto_submit_on_tab_limit",
            "scheduled_start_time",
            "scheduled_end_time",
            "opened_at",
            "closed_at",
            "close_policy",
            "created_at",
            "updated_at",
            "eligible_colleges",
            "eligible_colleges_count",
            "attempts_count",
            "in_progress_count",
            "submitted_count",
            "pool_questions_count",
            "pool_aptitude_count",
            "pool_coding_count",
            "pool_sufficient",
        ]

    def get_is_open(self, obj):
        return obj.is_currently_open()

    def get_pool_questions_count(self, obj):
        return obj.questions.count()

    def get_pool_aptitude_count(self, obj):
        return obj.questions.filter(section_type=QuestionBank.SectionType.APTITUDE, is_active=True).count()

    def get_pool_coding_count(self, obj):
        return obj.questions.filter(section_type=QuestionBank.SectionType.CODING, is_active=True).count()

    def get_pool_sufficient(self, obj):
        apt = self.get_pool_aptitude_count(obj)
        cod = self.get_pool_coding_count(obj)
        return (apt >= obj.aptitude_count) and (cod >= obj.coding_count)

    def get_eligible_colleges(self, obj):
        return [{"id": c.id, "name": c.name, "code": c.code} for c in obj.eligible_colleges.all()]

    def get_eligible_colleges_count(self, obj):
        return obj.eligible_colleges.count()

    def get_attempts_count(self, obj):
        return obj.attempts.count()

    def get_in_progress_count(self, obj):
        return obj.attempts.filter(
            state__in=[AssessmentAttempt.State.CREATED, AssessmentAttempt.State.IN_PROGRESS]
        ).count()

    def get_submitted_count(self, obj):
        return obj.attempts.filter(state=AssessmentAttempt.State.SUBMITTED).count()


class AdminAssessmentCreateUpdateSerializer(serializers.ModelSerializer):
    eligible_college_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = Assessment
        fields = [
            "id",
            "code",
            "title",
            "description",
            "assessment_type",
            "duration_minutes",
            "total_marks",
            "aptitude_count",
            "coding_count",
            "max_attempts",
            "max_tab_switches_warning",
            "auto_submit_on_tab_limit",
            "scheduled_start_time",
            "scheduled_end_time",
            "close_policy",
            "eligible_college_ids",
        ]

    def validate_code(self, value):
        val = value.strip().upper()
        if len(val) < 2:
            raise serializers.ValidationError("Assessment code must be at least 2 characters.")
        existing = Assessment.objects.filter(code__iexact=val)
        if self.instance:
            existing = existing.exclude(id=self.instance.id)
        if existing.exists():
            raise serializers.ValidationError(f"Assessment code '{val}' is already taken.")
        return val

    def validate_title(self, value):
        val = value.strip()
        if len(val) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters.")
        return val

    def validate(self, data):
        duration = data.get("duration_minutes", getattr(self.instance, "duration_minutes", 60))
        aptitude = data.get("aptitude_count", getattr(self.instance, "aptitude_count", 25))
        coding = data.get("coding_count", getattr(self.instance, "coding_count", 25))
        total = data.get("total_marks", getattr(self.instance, "total_marks", 50))
        max_attempts = data.get("max_attempts", getattr(self.instance, "max_attempts", 1))

        errors = {}
        if duration < 1:
            errors["duration_minutes"] = "Duration must be at least 1 minute."
        if aptitude < 1 and coding < 1:
            errors["aptitude_count"] = "Must have at least one question configured."
        if total != (aptitude + coding):
            errors["total_marks"] = f"Total marks ({total}) must equal aptitude ({aptitude}) + coding ({coding})."
        if max_attempts < 1:
            errors["max_attempts"] = "Max attempts must be at least 1."

        if errors:
            raise serializers.ValidationError(errors)
        return data


class AdminAssessmentDetailSerializer(AdminAssessmentListSerializer):
    audit_logs = serializers.SerializerMethodField()

    class Meta(AdminAssessmentListSerializer.Meta):
        fields = AdminAssessmentListSerializer.Meta.fields + ["audit_logs"]

    def get_audit_logs(self, obj):
        logs = AssessmentAuditLog.objects.filter(
            entity_type="ASSESSMENT", entity_id=str(obj.id)
        ).order_by("-timestamp")[:20]
        return AdminAssessmentAuditLogSerializer(logs, many=True).data


class AdminCollegeDetailSerializer(AdminCollegeListSerializer):
    candidates = serializers.SerializerMethodField()
    assigned_assessments = serializers.SerializerMethodField()

    class Meta(AdminCollegeListSerializer.Meta):
        fields = AdminCollegeListSerializer.Meta.fields + ["candidates", "assigned_assessments"]

    def get_candidates(self, obj):
        cands = obj.candidates.all().order_by("-created_at")[:50]
        return AdminCandidateSerializer(cands, many=True).data

    def get_assigned_assessments(self, obj):
        assessments = obj.assigned_assessments.all().order_by("-created_at")
        return [
            {
                "id": str(a.id),
                "code": a.code,
                "title": a.title,
                "status": a.status,
                "is_open": a.is_currently_open(),
                "duration_minutes": a.duration_minutes,
                "total_marks": a.total_marks,
            }
            for a in assessments
        ]


class AdminCandidateSerializer(serializers.ModelSerializer):
    attempts_count = serializers.SerializerMethodField()
    latest_state = serializers.SerializerMethodField()
    latest_score = serializers.SerializerMethodField()
    college_code = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = [
            "id",
            "full_name",
            "register_number",
            "college",
            "college_ref_id",
            "college_code",
            "email",
            "department",
            "year_of_study",
            "phone_number",
            "is_active",
            "created_at",
            "attempts_count",
            "latest_state",
            "latest_score",
        ]

    def get_college_code(self, obj):
        return obj.college_ref.code if obj.college_ref else ""

    def get_attempts_count(self, obj):
        return obj.attempts.count()

    def get_latest_state(self, obj):
        latest = obj.attempts.first()
        return latest.state if latest else None

    def get_latest_score(self, obj):
        latest = obj.attempts.first()
        return latest.total_score if latest else None


class AdminCandidateAttemptItemSerializer(serializers.ModelSerializer):
    assessment_title = serializers.SerializerMethodField()
    assessment_code = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentAttempt
        fields = [
            "id",
            "assessment_id",
            "assessment_title",
            "assessment_code",
            "state",
            "started_at",
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
        ]

    def get_assessment_title(self, obj):
        if obj.assessment:
            return obj.assessment.title
        return obj.config.title if obj.config else "CSL Assessment"

    def get_assessment_code(self, obj):
        if obj.assessment:
            return obj.assessment.code
        return "CSL-INITIAL-01"


class AdminCandidateDetailSerializer(serializers.ModelSerializer):
    attempts = AdminCandidateAttemptItemSerializer(many=True, read_only=True)
    college_code = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = [
            "id",
            "full_name",
            "register_number",
            "college",
            "college_ref_id",
            "college_code",
            "email",
            "department",
            "year_of_study",
            "phone_number",
            "is_active",
            "is_email_verified",
            "created_at",
            "updated_at",
            "attempts",
        ]

    def get_college_code(self, obj):
        return obj.college_ref.code if obj.college_ref else ""


class AdminQuestionSerializer(serializers.ModelSerializer):
    assigned_assessments = serializers.SerializerMethodField()
    assessment_id = serializers.SerializerMethodField()
    assessment_title = serializers.SerializerMethodField()

    class Meta:
        model = QuestionBank
        fields = [
            "id",
            "prompt",
            "section_type",
            "category",
            "difficulty",
            "assessment_type",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_option",
            "explanation",
            "is_active",
            "created_at",
            "updated_at",
            "assigned_assessments",
            "assessment_id",
            "assessment_title",
        ]

    def get_assigned_assessments(self, obj):
        return [{"id": str(a.id), "code": a.code, "title": a.title} for a in obj.assigned_assessments.all()]

    def get_assessment_id(self, obj):
        first_a = obj.assigned_assessments.first()
        return str(first_a.id) if first_a else None

    def get_assessment_title(self, obj):
        first_a = obj.assigned_assessments.first()
        return first_a.title if first_a else ""

    def validate_prompt(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Question prompt cannot be empty.")
        return value.strip()

    def validate_category(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Category cannot be empty.")
        return value.strip()

    def validate_correct_option(self, value):
        val = value.strip().upper()
        if val not in ["A", "B", "C", "D"]:
            raise serializers.ValidationError("Correct option must be A, B, C, or D.")
        return val


class AdminAssessmentConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentConfig
        fields = [
            "id",
            "title",
            "description",
            "duration_minutes",
            "total_marks",
            "aptitude_count",
            "coding_count",
            "max_attempts",
            "max_tab_switches_warning",
            "auto_submit_on_tab_limit",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        duration = data.get("duration_minutes", getattr(self.instance, "duration_minutes", 60))
        aptitude = data.get("aptitude_count", getattr(self.instance, "aptitude_count", 25))
        coding = data.get("coding_count", getattr(self.instance, "coding_count", 25))
        total = data.get("total_marks", getattr(self.instance, "total_marks", 50))
        max_attempts = data.get("max_attempts", getattr(self.instance, "max_attempts", 1))
        max_tab_switches = data.get("max_tab_switches_warning", getattr(self.instance, "max_tab_switches_warning", 2))

        errors = {}
        if duration < 1:
            errors["duration_minutes"] = "Duration must be at least 1 minute."
        if aptitude < 1:
            errors["aptitude_count"] = "Aptitude question count must be at least 1."
        if coding < 1:
            errors["coding_count"] = "Coding question count must be at least 1."
        if total != (aptitude + coding):
            errors["total_marks"] = f"Total marks ({total}) must equal aptitude ({aptitude}) + coding ({coding})."
        if max_attempts < 1:
            errors["max_attempts"] = "Max attempts must be at least 1."
        if max_tab_switches < 1:
            errors["max_tab_switches_warning"] = "Permitted tab-switch warnings must be at least 1."

        if errors:
            raise serializers.ValidationError(errors)
        return data


class AdminLiveAttemptSerializer(serializers.ModelSerializer):
    candidate_id = serializers.UUIDField(source="candidate.id", read_only=True)
    candidate_name = serializers.CharField(source="candidate.full_name", read_only=True)
    register_number = serializers.CharField(source="candidate.register_number", read_only=True)
    college = serializers.CharField(source="candidate.college", read_only=True)
    college_id = serializers.IntegerField(source="candidate.college_ref_id", read_only=True)
    assessment_title = serializers.SerializerMethodField()
    assessment_code = serializers.SerializerMethodField()
    remaining_seconds = serializers.SerializerMethodField()
    answered_count = serializers.SerializerMethodField()
    total_questions = serializers.SerializerMethodField()
    integrity_events_count = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentAttempt
        fields = [
            "id",
            "candidate_id",
            "candidate_name",
            "register_number",
            "college",
            "college_id",
            "assessment_id",
            "assessment_title",
            "assessment_code",
            "state",
            "started_at",
            "deadline",
            "remaining_seconds",
            "answered_count",
            "total_questions",
            "tab_switch_count",
            "fullscreen_exit_count",
            "integrity_events_count",
            "is_flagged",
            "flag_reason",
            "total_score",
        ]

    def get_assessment_title(self, obj):
        if obj.assessment:
            return obj.assessment.title
        return obj.config.title if obj.config else "CSL Assessment"

    def get_assessment_code(self, obj):
        if obj.assessment:
            return obj.assessment.code
        return "CSL-INITIAL-01"

    def get_remaining_seconds(self, obj):
        if not obj.deadline:
            return 0
        rem = (obj.deadline - timezone.now()).total_seconds()
        return max(0, int(rem))

    def get_answered_count(self, obj):
        return obj.question_snapshots.exclude(selected_option="").count()

    def get_total_questions(self, obj):
        if obj.assessment:
            return obj.assessment.total_marks
        return obj.question_snapshots.count() or 50

    def get_integrity_events_count(self, obj):
        return obj.integrity_events.count()


class AdminQuestionSnapshotReviewSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="question.category", read_only=True)
    explanation = serializers.CharField(source="question.explanation", read_only=True)
    correct_option_key = serializers.SerializerMethodField()
    marks_awarded = serializers.SerializerMethodField()

    class Meta:
        model = AttemptQuestionSnapshot
        fields = [
            "id",
            "question_order",
            "section_type",
            "category",
            "prompt",
            "option_a_text",
            "option_b_text",
            "option_c_text",
            "option_d_text",
            "correct_option_key",
            "selected_option",
            "is_correct",
            "explanation",
            "marks_awarded",
            "answered_at",
        ]

    def get_correct_option_key(self, obj):
        if obj.attempt.state in [
            AssessmentAttempt.State.SUBMITTED,
            AssessmentAttempt.State.TIMED_OUT,
            AssessmentAttempt.State.FLAGGED_FOR_REVIEW,
        ]:
            return obj.correct_option_key
        return None

    def get_marks_awarded(self, obj):
        return 1 if obj.is_correct is True else 0


class AdminIntegrityEventSerializer(serializers.ModelSerializer):
    candidate_name = serializers.CharField(source="attempt.candidate.full_name", read_only=True)
    register_number = serializers.CharField(source="attempt.candidate.register_number", read_only=True)
    college = serializers.CharField(source="attempt.candidate.college", read_only=True)
    assessment_id = serializers.UUIDField(source="attempt.assessment_id", read_only=True)
    timestamp = serializers.DateTimeField(source="server_timestamp", read_only=True)
    created_at = serializers.DateTimeField(source="server_timestamp", read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = IntegrityEvent
        fields = [
            "id",
            "event_id",
            "attempt_id",
            "assessment_id",
            "candidate_name",
            "register_number",
            "college",
            "event_type",
            "metadata",
            "server_timestamp",
            "timestamp",
            "created_at",
            "is_reviewed",
            "review_notes",
            "reviewed_by_name",
            "reviewed_at",
        ]

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.first_name or obj.reviewed_by.username or obj.reviewed_by.email
        return ""


class AdminQuestionBulkUpdateSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        help_text="List of question IDs to update",
    )
    section_type = serializers.ChoiceField(
        choices=QuestionBank.SectionType.choices,
        required=False,
    )
    category = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=False,
    )
    difficulty = serializers.ChoiceField(
        choices=QuestionBank.Difficulty.choices,
        required=False,
    )
    is_active = serializers.BooleanField(
        required=False,
    )

    def validate(self, data):
        update_fields = [k for k in ["section_type", "category", "difficulty", "is_active"] if k in data]
        if not update_fields:
            raise serializers.ValidationError(
                "At least one update field (section_type, category, difficulty, or is_active) must be specified."
            )
        return data


class AdminAttemptReviewSerializer(serializers.ModelSerializer):
    candidate = AdminCandidateSerializer(read_only=True)
    questions = AdminQuestionSnapshotReviewSerializer(source="question_snapshots", many=True, read_only=True)
    integrity_events = AdminIntegrityEventSerializer(many=True, read_only=True)
    assessment_title = serializers.SerializerMethodField()
    assessment_code = serializers.SerializerMethodField()
    total_questions = serializers.SerializerMethodField()
    answered_count = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentAttempt
        fields = [
            "id",
            "candidate",
            "assessment_id",
            "assessment_title",
            "assessment_code",
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
            "total_questions",
            "answered_count",
            "questions",
            "integrity_events",
        ]

    def get_assessment_title(self, obj):
        if obj.assessment:
            return obj.assessment.title
        return obj.config.title if obj.config else "CSL Assessment"

    def get_assessment_code(self, obj):
        if obj.assessment:
            return obj.assessment.code
        return "CSL-INITIAL-01"

    def get_total_questions(self, obj):
        if obj.assessment:
            return obj.assessment.total_marks
        return obj.question_snapshots.count()

    def get_answered_count(self, obj):
        return obj.question_snapshots.exclude(selected_option="").count()


class AdminResultSerializer(serializers.ModelSerializer):
    candidate_id = serializers.UUIDField(source="candidate.id", read_only=True)
    candidate_name = serializers.CharField(source="candidate.full_name", read_only=True)
    register_number = serializers.CharField(source="candidate.register_number", read_only=True)
    college = serializers.CharField(source="candidate.college", read_only=True)
    college_id = serializers.IntegerField(source="candidate.college_ref_id", read_only=True)
    department = serializers.CharField(source="candidate.department", read_only=True)
    year_of_study = serializers.CharField(source="candidate.year_of_study", read_only=True)
    assessment_title = serializers.SerializerMethodField()
    assessment_code = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentAttempt
        fields = [
            "id",
            "candidate_id",
            "candidate_name",
            "register_number",
            "college",
            "college_id",
            "assessment_id",
            "assessment_title",
            "assessment_code",
            "department",
            "year_of_study",
            "state",
            "aptitude_score",
            "coding_score",
            "total_score",
            "percentage",
            "started_at",
            "submitted_at",
            "tab_switch_count",
            "fullscreen_exit_count",
            "is_flagged",
            "flag_reason",
        ]

    def get_assessment_title(self, obj):
        if obj.assessment:
            return obj.assessment.title
        return obj.config.title if obj.config else "CSL Assessment"

    def get_assessment_code(self, obj):
        if obj.assessment:
            return obj.assessment.code
        return "CSL-INITIAL-01"
