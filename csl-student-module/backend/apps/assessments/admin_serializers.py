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
    AssessmentSection,
    AssessmentSectionAllocation,
)


class AdminAssessmentSectionSerializer(serializers.ModelSerializer):
    questions_count = serializers.SerializerMethodField()
    assessments_count = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentSection
        fields = [
            "id",
            "name",
            "code",
            "description",
            "is_active",
            "order",
            "questions_count",
            "assessments_count",
            "created_at",
            "updated_at",
        ]

    def get_questions_count(self, obj):
        return QuestionBank.objects.filter(section_type=obj.code).count()

    def get_assessments_count(self, obj):
        return obj.assessment_allocations.count()

    def validate_name(self, value):
        val = value.strip()
        if len(val) < 2:
            raise serializers.ValidationError("Section name must be at least 2 characters.")
        existing = AssessmentSection.objects.filter(name__iexact=val)
        if self.instance:
            existing = existing.exclude(id=self.instance.id)
        if existing.exists():
            raise serializers.ValidationError(f"A section named '{val}' already exists.")
        return val

    def validate_code(self, value):
        val = value.strip().upper()
        if len(val) < 2:
            raise serializers.ValidationError("Section code must be at least 2 characters.")
        existing = AssessmentSection.objects.filter(code__iexact=val)
        if self.instance:
            existing = existing.exclude(id=self.instance.id)
        if existing.exists():
            raise serializers.ValidationError(f"Section code '{val}' is already taken.")
        return val


class AdminAssessmentSectionAllocationSerializer(serializers.ModelSerializer):
    section_id = serializers.IntegerField(source="section.id", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    section_code = serializers.CharField(source="section.code", read_only=True)
    available_questions_count = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentSectionAllocation
        fields = [
            "id",
            "section_id",
            "section_name",
            "section_code",
            "question_count",
            "marks_per_question",
            "order",
            "available_questions_count",
        ]

    def get_available_questions_count(self, obj):
        assessment = obj.assessment
        if assessment and assessment.questions.exists():
            return assessment.questions.filter(section_type=obj.section.code, is_active=True).count()
        return QuestionBank.objects.filter(section_type=obj.section.code, is_active=True).count()



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
    sections = serializers.SerializerMethodField()

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
            "sections",
        ]

    def get_sections(self, obj):
        try:
            allocs = obj.section_allocations.select_related("section").order_by("order", "id")
            return AdminAssessmentSectionAllocationSerializer(allocs, many=True).data
        except Exception:
            return []

    def get_is_open(self, obj):
        return obj.is_currently_open()

    def get_pool_questions_count(self, obj):
        return obj.questions.count()

    def get_pool_aptitude_count(self, obj):
        return obj.questions.filter(section_type=QuestionBank.SectionType.APTITUDE, is_active=True).count()

    def get_pool_coding_count(self, obj):
        return obj.questions.filter(section_type=QuestionBank.SectionType.CODING, is_active=True).count()

    def get_pool_sufficient(self, obj):
        from django.db.models import Q
        try:
            allocs = obj.section_allocations.select_related("section").all()
            if allocs.exists():
                for alloc in allocs:
                    sec = alloc.section
                    sec_filter = (
                        Q(section=sec)
                        | Q(section_type__iexact=sec.code)
                        | Q(section_type__iexact=sec.name)
                        | Q(section__code__iexact=sec.code)
                        | Q(section__name__iexact=sec.name)
                    )
                    if obj.questions.exists():
                        cnt = obj.questions.filter(sec_filter, is_active=True).distinct().count()
                    else:
                        cnt = QuestionBank.objects.filter(sec_filter, is_active=True).distinct().count()
                    if cnt < alloc.question_count:
                        return False
                return True
        except Exception:
            pass
        apt_req = obj.aptitude_count or 0
        cod_req = obj.coding_count or 0
        if apt_req == 0 and cod_req == 0:
            return False
        apt = self.get_pool_aptitude_count(obj)
        cod = self.get_pool_coding_count(obj)
        return (apt >= apt_req) and (cod >= cod_req)

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
    sections = serializers.ListField(
        child=serializers.DictField(),
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
            "sections",
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
        total = data.get("total_marks", getattr(self.instance, "total_marks", 50))
        max_attempts = data.get("max_attempts", getattr(self.instance, "max_attempts", 1))

        errors = {}
        if duration < 1:
            errors["duration_minutes"] = "Duration must be at least 1 minute."
        if max_attempts < 1:
            errors["max_attempts"] = "Max attempts must be at least 1."

        sections_data = self.initial_data.get("sections")
        if sections_data is not None:
            if not isinstance(sections_data, list) or len(sections_data) == 0:
                errors["sections"] = "At least one section must be configured for the assessment."
            else:
                calculated_total = 0
                for idx, sec in enumerate(sections_data):
                    sec_id = sec.get("section_id")
                    q_count = int(sec.get("question_count", 0))
                    marks_q = int(sec.get("marks_per_question", 1))
                    if not sec_id:
                        errors["sections"] = f"Section at index {idx} must specify a valid section_id."
                        break
                    if q_count < 1:
                        errors["sections"] = "Question count for each section must be at least 1."
                        break
                    if marks_q < 1:
                        errors["sections"] = "Marks per question must be at least 1."
                        break
                    calculated_total += q_count * marks_q
                if "sections" not in errors and total != calculated_total:
                    errors["total_marks"] = f"Total marks ({total}) must equal sum of section marks ({calculated_total})."
        else:
            aptitude = data.get("aptitude_count", getattr(self.instance, "aptitude_count", 25))
            coding = data.get("coding_count", getattr(self.instance, "coding_count", 25))
            if aptitude < 1 and coding < 1:
                errors["aptitude_count"] = "Must have at least one question configured."
            if total != (aptitude + coding):
                errors["total_marks"] = f"Total marks ({total}) must equal aptitude ({aptitude}) + coding ({coding})."

        if errors:
            raise serializers.ValidationError(errors)
        return data

    def create(self, validated_data):
        college_ids = validated_data.pop("eligible_college_ids", None)
        sections_data = self.initial_data.get("sections", None)
        validated_data.pop("sections", None)
        assessment = super().create(validated_data)
        if college_ids is not None:
            colleges = College.objects.filter(id__in=college_ids)
            assessment.eligible_colleges.set(colleges)
        if sections_data:
            self._sync_sections(assessment, sections_data)
        return assessment

    def update(self, instance, validated_data):
        college_ids = validated_data.pop("eligible_college_ids", None)
        sections_data = self.initial_data.get("sections", None)
        validated_data.pop("sections", None)
        assessment = super().update(instance, validated_data)
        if college_ids is not None:
            colleges = College.objects.filter(id__in=college_ids)
            assessment.eligible_colleges.set(colleges)
        if sections_data is not None:
            self._sync_sections(assessment, sections_data)
        return assessment

    def _sync_sections(self, assessment, sections_data):
        from .models import AssessmentSection, AssessmentSectionAllocation
        existing_allocations = {a.section_id: a for a in assessment.section_allocations.all()}
        seen_section_ids = set()

        apt_count = 0
        cod_count = 0

        for idx, sec in enumerate(sections_data):
            sec_id = sec.get("section_id")
            if not sec_id:
                continue
            section = AssessmentSection.objects.filter(id=sec_id).first()
            if not section:
                continue
            q_count = int(sec.get("question_count", 25))
            marks_q = int(sec.get("marks_per_question", 1))
            order_val = int(sec.get("order", idx + 1))

            seen_section_ids.add(section.id)

            if section.id in existing_allocations:
                alloc = existing_allocations[section.id]
                alloc.question_count = q_count
                alloc.marks_per_question = marks_q
                alloc.order = order_val
                alloc.save()
            else:
                AssessmentSectionAllocation.objects.create(
                    assessment=assessment,
                    section=section,
                    question_count=q_count,
                    marks_per_question=marks_q,
                    order=order_val,
                )

            if section.code == "APTITUDE":
                apt_count = q_count
            elif section.code == "CODING":
                cod_count = q_count

        # Remove associations only (without deleting the reusable section!)
        assessment.section_allocations.exclude(section_id__in=seen_section_ids).delete()

        # Update legacy aptitude_count and coding_count fields to reflect current allocations
        assessment.aptitude_count = apt_count
        assessment.coding_count = cod_count
        assessment.save(update_fields=["aptitude_count", "coding_count"])



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
    section_name = serializers.CharField(source="section.name", read_only=True)

    class Meta:
        model = QuestionBank
        fields = [
            "id",
            "prompt",
            "section_type",
            "section_name",
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

    def _get_assessments(self, obj):
        if not hasattr(obj, "_cached_assigned_assessments"):
            obj._cached_assigned_assessments = list(obj.assigned_assessments.all())
        return obj._cached_assigned_assessments

    def get_assigned_assessments(self, obj):
        return [{"id": str(a.id), "code": a.code, "title": a.title} for a in self._get_assessments(obj)]

    def get_assessment_id(self, obj):
        assessments = self._get_assessments(obj)
        return str(assessments[0].id) if assessments else None

    def get_assessment_title(self, obj):
        assessments = self._get_assessments(obj)
        return assessments[0].title if assessments else ""

    def validate_prompt(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Question prompt cannot be empty.")
        return value.strip()

    category = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_category(self, value):
        return value.strip() if value else ""

    def validate_correct_option(self, value):
        val = value.strip().upper()
        if val not in ["A", "B", "C", "D"]:
            raise serializers.ValidationError("Correct option must be A, B, C, or D.")
        return val

    def create(self, validated_data):
        sec_type = validated_data.get("section_type", "")
        if sec_type and "section" not in validated_data:
            sec = AssessmentSection.objects.filter(code__iexact=sec_type).first()
            if not sec:
                sec = AssessmentSection.objects.filter(name__iexact=sec_type).first()
            if sec:
                validated_data["section"] = sec
                validated_data["section_type"] = sec.code
        return super().create(validated_data)

    def update(self, instance, validated_data):
        sec_type = validated_data.get("section_type", instance.section_type)
        if sec_type:
            sec = AssessmentSection.objects.filter(code__iexact=sec_type).first()
            if not sec:
                sec = AssessmentSection.objects.filter(name__iexact=sec_type).first()
            if sec:
                validated_data["section"] = sec
                validated_data["section_type"] = sec.code
        return super().update(instance, validated_data)


class AdminAssessmentConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentConfig
        fields = [
            "id",
            "title",
            "description",
            "max_attempts",
            "max_tab_switches_warning",
            "auto_submit_on_tab_limit",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        max_attempts = data.get("max_attempts", getattr(self.instance, "max_attempts", 1))
        max_tab_switches = data.get("max_tab_switches_warning", getattr(self.instance, "max_tab_switches_warning", 2))

        errors = {}
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
        if hasattr(obj, "_prefetched_objects_cache") and "question_snapshots" in obj._prefetched_objects_cache:
            count = len(obj.question_snapshots.all())
            if count:
                return count
        elif obj.pk:
            count = obj.question_snapshots.count()
            if count:
                return count
        if obj.assessment:
            allocs = obj.assessment.section_allocations.all()
            if allocs.exists():
                return sum(a.question_count for a in allocs)
            return (obj.assessment.aptitude_count or 0) + (obj.assessment.coding_count or 0)
        return 50

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
            "client_timestamp",
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
    section_type = serializers.CharField(
        max_length=50,
        required=False,
    )
    category = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
    )
    difficulty = serializers.ChoiceField(
        choices=QuestionBank.Difficulty.choices,
        required=False,
    )
    is_active = serializers.BooleanField(
        required=False,
    )

    def validate(self, data):
        update_fields = [k for k in ["section_type", "difficulty", "is_active", "category"] if k in data]
        if not update_fields:
            raise serializers.ValidationError(
                "At least one update field (section_type, difficulty, is_active, or category) must be specified."
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
        if hasattr(obj, "_prefetched_objects_cache") and "question_snapshots" in obj._prefetched_objects_cache:
            count = len(obj.question_snapshots.all())
            if count:
                return count
        elif obj.pk:
            count = obj.question_snapshots.count()
            if count:
                return count
        if obj.assessment:
            allocs = obj.assessment.section_allocations.all()
            if allocs.exists():
                return sum(a.question_count for a in allocs)
            return (obj.assessment.aptitude_count or 0) + (obj.assessment.coding_count or 0)
        return 0

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
            "assessment_total_marks",
            "assessment_aptitude_count",
            "assessment_coding_count",
        ]

    assessment_total_marks = serializers.SerializerMethodField()
    assessment_aptitude_count = serializers.SerializerMethodField()
    assessment_coding_count = serializers.SerializerMethodField()

    def get_assessment_title(self, obj):
        if obj.assessment:
            return obj.assessment.title
        return obj.config.title if obj.config else "CSL Assessment"

    def get_assessment_code(self, obj):
        if obj.assessment:
            return obj.assessment.code
        return "CSL-INITIAL-01"

    def get_assessment_total_marks(self, obj):
        if obj.assessment:
            return obj.assessment.total_marks
        return obj.config.total_marks if obj.config else 50

    def get_assessment_aptitude_count(self, obj):
        if obj.assessment:
            return obj.assessment.aptitude_count
        return obj.config.aptitude_count if obj.config else 25

    def get_assessment_coding_count(self, obj):
        if obj.assessment:
            return obj.assessment.coding_count
        return obj.config.coding_count if obj.config else 25
