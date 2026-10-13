import re
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
)


class StudentCollegeOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = College
        fields = ["id", "name", "code", "location"]


class CandidateRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    college_id = serializers.IntegerField(required=False, allow_null=True)
    phone_number = serializers.CharField(required=True, allow_blank=False)

    class Meta:
        model = Candidate
        fields = [
            "id",
            "full_name",
            "register_number",
            "college",
            "college_id",
            "email",
            "department",
            "year_of_study",
            "phone_number",
        ]

    def validate_full_name(self, value):
        val = value.strip()
        if len(val) < 2:
            raise serializers.ValidationError("Full name must be at least 2 characters.")
        return val

    def validate_email(self, value):
        return value.strip().lower()

    def validate_register_number(self, value):
        val = value.strip().upper()
        if len(val) < 2:
            raise serializers.ValidationError("Register number must be at least 2 characters.")
        return val

    def validate_phone_number(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Mobile phone number is mandatory.")
        digits = re.sub(r"\D", "", val)
        if len(digits) < 7 or len(digits) > 15:
            raise serializers.ValidationError("Please provide a valid mobile phone number (7-15 digits).")
        return val

    def validate_college(self, value):
        return value.strip() if value else ""


class QuestionSnapshotStudentSerializer(serializers.ModelSerializer):
    """
    Student-facing question serializer.
    STRICT SECURITY: correct_option_key is NEVER included.
    """
    options = serializers.SerializerMethodField()
    category = serializers.CharField(source="question.category", read_only=True)

    class Meta:
        model = AttemptQuestionSnapshot
        fields = [
            "question_order",
            "section_type",
            "category",
            "prompt",
            "options",
            "selected_option",
        ]

    def get_options(self, obj):
        return [
            {"key": "A", "text": obj.option_a_text},
            {"key": "B", "text": obj.option_b_text},
            {"key": "C", "text": obj.option_c_text},
            {"key": "D", "text": obj.option_d_text},
        ]


class AssessmentAttemptDetailSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    remaining_seconds = serializers.SerializerMethodField()
    candidate_name = serializers.CharField(source="candidate.full_name", read_only=True)
    college = serializers.CharField(source="candidate.college", read_only=True)
    assessment_id = serializers.UUIDField(source="assessment.id", read_only=True, allow_null=True)
    assessment_title = serializers.SerializerMethodField()
    assessment_code = serializers.SerializerMethodField()
    total_questions = serializers.SerializerMethodField()
    max_tab_switches = serializers.SerializerMethodField()
    remaining_tab_switches = serializers.SerializerMethodField()
    server_time = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentAttempt
        fields = [
            "id",
            "assessment_id",
            "assessment_title",
            "assessment_code",
            "state",
            "started_at",
            "deadline",
            "remaining_seconds",
            "server_time",
            "candidate_name",
            "college",
            "total_questions",
            "tab_switch_count",
            "fullscreen_exit_count",
            "max_tab_switches",
            "remaining_tab_switches",
            "is_flagged",
            "flag_reason",
            "questions",
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
        if obj.config:
            return obj.config.total_marks
        return obj.question_snapshots.count() or 50

    def get_remaining_seconds(self, obj):
        if not obj.deadline:
            return 0
        diff = (obj.deadline - timezone.now()).total_seconds()
        return max(0, int(diff))

    def get_server_time(self, obj):
        return timezone.now().isoformat()

    def get_max_tab_switches(self, obj):
        if obj.assessment:
            return obj.assessment.max_tab_switches_warning
        return obj.config.max_tab_switches_warning if obj.config else 2

    def get_remaining_tab_switches(self, obj):
        max_switches = self.get_max_tab_switches(obj)
        return max(0, max_switches - obj.tab_switch_count)

    def get_questions(self, obj):
        snapshots = obj.question_snapshots.all().order_by("question_order")
        return QuestionSnapshotStudentSerializer(snapshots, many=True).data


class AnswerSaveSerializer(serializers.Serializer):
    question_order = serializers.IntegerField(min_value=1, max_value=200)
    selected_option = serializers.CharField(required=False, allow_blank=True)


class IntegrityEventSerializer(serializers.Serializer):
    event_type = serializers.ChoiceField(choices=IntegrityEvent.EventType.choices)
    event_id = serializers.CharField(required=False, allow_blank=True, default="")
    client_timestamp = serializers.DateTimeField(required=False, allow_null=True)
    metadata = serializers.DictField(required=False, default=dict)


class AssessmentResultSerializer(serializers.ModelSerializer):
    candidate_name = serializers.CharField(source="candidate.full_name", read_only=True)
    register_number = serializers.CharField(source="candidate.register_number", read_only=True)
    college = serializers.CharField(source="candidate.college", read_only=True)
    department = serializers.CharField(source="candidate.department", read_only=True)
    year_of_study = serializers.CharField(source="candidate.year_of_study", read_only=True)
    assessment_id = serializers.UUIDField(source="assessment.id", read_only=True, allow_null=True)
    assessment_title = serializers.SerializerMethodField()
    assessment_code = serializers.SerializerMethodField()
    duration_minutes = serializers.SerializerMethodField()
    max_marks = serializers.SerializerMethodField()
    total_questions = serializers.SerializerMethodField()
    breakdown = serializers.SerializerMethodField()
    is_results_released = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentAttempt
        fields = [
            "id",
            "assessment_id",
            "assessment_title",
            "assessment_code",
            "candidate_name",
            "register_number",
            "college",
            "department",
            "year_of_study",
            "state",
            "aptitude_score",
            "coding_score",
            "total_score",
            "percentage",
            "duration_minutes",
            "max_marks",
            "total_questions",
            "tab_switch_count",
            "fullscreen_exit_count",
            "is_flagged",
            "flag_reason",
            "is_results_released",
            "started_at",
            "submitted_at",
            "breakdown",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        is_staff = False
        if request and hasattr(request, "user"):
            user = request.user
            is_auth = getattr(user, "is_authenticated", False)
            if callable(is_auth):
                is_auth = is_auth()
            if is_auth and (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)):
                is_staff = True

        is_released = False
        if instance.assessment:
            is_released = bool(instance.assessment.is_results_released)
        elif instance.config:
            is_released = True

        data["is_results_released"] = is_released

        if not is_staff and not is_released:
            for sensitive_key in [
                "aptitude_score",
                "coding_score",
                "total_score",
                "percentage",
                "breakdown",
            ]:
                data.pop(sensitive_key, None)
            data["message"] = "Assessment Completed"
        return data

    def get_is_results_released(self, obj):
        if obj.assessment:
            return bool(obj.assessment.is_results_released)
        return True

    def get_assessment_title(self, obj):
        if obj.assessment:
            return obj.assessment.title
        return obj.config.title if obj.config else "CSL Assessment"

    def get_assessment_code(self, obj):
        if obj.assessment:
            return obj.assessment.code
        return "CSL-INITIAL-01"

    def get_duration_minutes(self, obj):
        if obj.assessment:
            return obj.assessment.duration_minutes
        return obj.config.duration_minutes if obj.config else 60

    def get_max_marks(self, obj):
        if obj.assessment:
            return obj.assessment.total_marks
        return obj.config.total_marks if obj.config else 50

    def get_total_questions(self, obj):
        return obj.question_snapshots.count() or self.get_max_marks(obj)

    def get_breakdown(self, obj):
        snapshots = list(obj.question_snapshots.all())
        total_q = len(snapshots) or self.get_max_marks(obj)

        apt_snapshots = [s for s in snapshots if s.section_type == QuestionBank.SectionType.APTITUDE]
        cod_snapshots = [s for s in snapshots if s.section_type == QuestionBank.SectionType.CODING]

        apt_correct = sum(1 for s in apt_snapshots if s.is_correct is True)
        apt_unattempted = sum(1 for s in apt_snapshots if not (s.selected_option and s.selected_option.strip()))
        apt_incorrect = max(0, len(apt_snapshots) - apt_correct - apt_unattempted)
        apt_total = len(apt_snapshots) or 25
        apt_pct = round((apt_correct / float(apt_total)) * 100.0, 1) if apt_total else 0.0

        cod_correct = sum(1 for s in cod_snapshots if s.is_correct is True)
        cod_unattempted = sum(1 for s in cod_snapshots if not (s.selected_option and s.selected_option.strip()))
        cod_incorrect = max(0, len(cod_snapshots) - cod_correct - cod_unattempted)
        cod_total = len(cod_snapshots) or 25
        cod_pct = round((cod_correct / float(cod_total)) * 100.0, 1) if cod_total else 0.0

        time_taken_seconds = 0
        time_taken_display = "N/A"
        if obj.started_at and obj.submitted_at:
            time_taken_seconds = max(0, int((obj.submitted_at - obj.started_at).total_seconds()))
            mins = time_taken_seconds // 60
            secs = time_taken_seconds % 60
            if mins > 0 and secs > 0:
                time_taken_display = f"{mins} Minutes {secs} Seconds"
            elif mins > 0:
                time_taken_display = f"{mins} Minutes"
            else:
                time_taken_display = f"{secs} Seconds"

        return {
            "total_questions": total_q,
            "time_taken_seconds": time_taken_seconds,
            "time_taken_display": time_taken_display,
            "aptitude": {
                "score": obj.aptitude_score,
                "total": apt_total,
                "percentage": apt_pct,
                "correct": apt_correct,
                "incorrect": apt_incorrect,
                "unattempted": apt_unattempted,
            },
            "coding": {
                "score": obj.coding_score,
                "total": cod_total,
                "percentage": cod_pct,
                "correct": cod_correct,
                "incorrect": cod_incorrect,
                "unattempted": cod_unattempted,
            },
        }


class StudentCandidateAssessmentSerializer(serializers.ModelSerializer):
    """
    List of assessments visible to a registered candidate based on their college.
    """
    is_open = serializers.SerializerMethodField()
    attempts_count = serializers.SerializerMethodField()
    user_can_attempt = serializers.SerializerMethodField()
    latest_attempt_id = serializers.SerializerMethodField()
    latest_attempt_state = serializers.SerializerMethodField()
    latest_attempt_score = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            "id",
            "code",
            "title",
            "description",
            "duration_minutes",
            "total_marks",
            "aptitude_count",
            "coding_count",
            "max_attempts",
            "status",
            "is_open",
            "scheduled_start_time",
            "scheduled_end_time",
            "attempts_count",
            "user_can_attempt",
            "is_results_released",
            "latest_attempt_id",
            "latest_attempt_state",
            "latest_attempt_score",
        ]

    def get_is_open(self, obj):
        return obj.is_currently_open()

    def _get_candidate(self):
        return self.context.get("candidate")

    def get_attempts_count(self, obj):
        cand = self._get_candidate()
        if not cand:
            return 0
        return obj.attempts.filter(candidate=cand).count()

    def get_user_can_attempt(self, obj):
        cand = self._get_candidate()
        if not cand or not cand.is_active:
            return False
        if not obj.is_currently_open():
            return False
        attempts = obj.attempts.filter(candidate=cand)
        completed = attempts.filter(
            state__in=[
                AssessmentAttempt.State.SUBMITTED,
                AssessmentAttempt.State.TIMED_OUT,
                AssessmentAttempt.State.FLAGGED_FOR_REVIEW,
            ]
        ).count()
        return completed < obj.max_attempts

    def get_latest_attempt_id(self, obj):
        cand = self._get_candidate()
        if not cand:
            return None
        att = obj.attempts.filter(candidate=cand).order_by("-created_at").first()
        return str(att.id) if att else None

    def get_latest_attempt_state(self, obj):
        cand = self._get_candidate()
        if not cand:
            return None
        att = obj.attempts.filter(candidate=cand).order_by("-created_at").first()
        return att.state if att else None

    def get_latest_attempt_score(self, obj):
        cand = self._get_candidate()
        if not cand or not obj.is_results_released:
            return None
        att = obj.attempts.filter(candidate=cand).order_by("-created_at").first()
        return att.total_score if att and att.state == AssessmentAttempt.State.SUBMITTED else None
