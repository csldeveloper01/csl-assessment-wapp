import csv
import logging
import time
import io
import random
import re
from collections import defaultdict
from datetime import timedelta
from django.db import transaction, models
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    QuestionBank,
    AssessmentConfig,
    College,
    Assessment,
    Candidate,
    AssessmentAttempt,
    AttemptQuestionSnapshot,
    IntegrityEvent,
    AssessmentAuditLog,
)

logger = logging.getLogger(__name__)

def log_assessment_audit(action: str, entity_type: str, entity_id: str, user=None, details=None):
    """
    Persists an immutable audit log entry for administrative actions.
    """
    user_name = "System"
    if user and getattr(user, "is_authenticated", False):
        user_name = user.get_full_name() or user.username or "Administrator"

    return AssessmentAuditLog.objects.create(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        performed_by=user if (user and getattr(user, "is_authenticated", False)) else None,
        performed_by_name=user_name,
        details=details or {},
    )


def get_or_create_default_config():
    config = AssessmentConfig.objects.filter(is_active=True).first()
    if not config:
        config = AssessmentConfig.objects.create(
            title="CSL Initial Assessment",
            description="50-mark balanced aptitude and coding fundamentals assessment.",
            duration_minutes=60,
            total_marks=50,
            aptitude_count=25,
            coding_count=25,
            max_attempts=1,
            max_tab_switches_warning=2,
            auto_submit_on_tab_limit=True,
            is_active=True,
        )
    return config


def get_or_create_default_assessment():
    assessment = Assessment.objects.filter(code="CSL-INITIAL-01").first()
    if not assessment:
        config = get_or_create_default_config()
        assessment = Assessment.objects.create(
            code="CSL-INITIAL-01",
            title=config.title,
            description=config.description,
            status=Assessment.Status.OPEN,
            duration_minutes=config.duration_minutes,
            total_marks=config.total_marks,
            aptitude_count=config.aptitude_count,
            coding_count=config.coding_count,
            max_attempts=config.max_attempts,
            max_tab_switches_warning=config.max_tab_switches_warning,
            auto_submit_on_tab_limit=config.auto_submit_on_tab_limit,
        )
    colleges = College.objects.filter(is_active=True)
    if colleges.exists():
        assessment.eligible_colleges.add(*colleges)
    return assessment


def validate_question_bank_sufficiency(aptitude_count: int = None, coding_count: int = None, assessment: Assessment = None):
    """
    Checks that the Question Bank or assessment question pool contains enough active questions for each section.
    Supports dynamic section allocations with fallback to legacy aptitude and coding counts.
    """
    scope_name = f"question pool for '{assessment.title}' ({assessment.code})" if (assessment and assessment.questions.exists()) else "bank"
    errors = []

    has_allocations = False
    try:
        if assessment and assessment.section_allocations.exists():
            has_allocations = True
    except Exception:
        has_allocations = False

    if has_allocations:
        for alloc in assessment.section_allocations.select_related("section").all():
            sec = alloc.section
            needed = alloc.question_count
            if needed <= 0:
                continue
            sec_q_filter = (
                models.Q(section=sec)
                | models.Q(section_type__iexact=sec.code)
                | models.Q(section__code__iexact=sec.code)
            )
            if assessment.questions.exists():
                available = assessment.questions.filter(sec_q_filter, is_active=True).distinct().count()
            else:
                available = QuestionBank.objects.filter(sec_q_filter, is_active=True).distinct().count()

            if available < needed:
                shortage = needed - available
                errors.append(
                    f"Insufficient '{sec.name}' ({sec.code}) questions in {scope_name}: found {available}, requires {needed} (shortage of {shortage})."
                )
    else:
        apt_count = aptitude_count if aptitude_count is not None else (assessment.aptitude_count if assessment else 25)
        cod_count = coding_count if coding_count is not None else (assessment.coding_count if assessment else 25)

        apt_filter = (
            models.Q(section_type__iexact=QuestionBank.SectionType.APTITUDE)
            | models.Q(section__code__iexact="APTITUDE")
        )
        cod_filter = (
            models.Q(section_type__iexact=QuestionBank.SectionType.CODING)
            | models.Q(section__code__iexact="CODING")
        )

        if assessment and assessment.questions.exists():
            active_aptitude = assessment.questions.filter(apt_filter, is_active=True).distinct().count()
            active_coding = assessment.questions.filter(cod_filter, is_active=True).distinct().count()
        else:
            active_aptitude = QuestionBank.objects.filter(apt_filter, is_active=True).distinct().count()
            active_coding = QuestionBank.objects.filter(cod_filter, is_active=True).distinct().count()

        if active_aptitude < apt_count:
            shortage = apt_count - active_aptitude
            errors.append(
                f"Insufficient aptitude questions in {scope_name}: found {active_aptitude}, requires {apt_count} (shortage of {shortage})."
            )
        if active_coding < cod_count:
            shortage = cod_count - active_coding
            errors.append(
                f"Insufficient coding questions in {scope_name}: found {active_coding}, requires {cod_count} (shortage of {shortage})."
            )

    if errors:
        raise ValidationError({"bank_error": " ".join(errors)})
    return True


def select_balanced_questions(
    section_type,
    required_count: int,
    assessment: Assessment = None,
    section_obj=None,
    exclude_question_ids: set = None,
):
    """
    Selects exactly required_count questions distributed evenly across available difficulty levels.
    - Scopes strictly to assessment pool if questions are assigned to that assessment.
    - Fully supports dynamic AssessmentSection instances or section codes.
    - Excludes previously selected question IDs to guarantee global uniqueness.
    - Uses round-robin stratified sampling across available difficulty groups.
    - The presence of additional questions in the pool never causes failure.
    """
    if required_count <= 0:
        return []

    # Resolve section object or code
    sec = section_obj
    sec_code = None
    sec_name = None

    if sec is not None:
        sec_code = getattr(sec, "code", str(sec))
        sec_name = getattr(sec, "name", sec_code)
    elif hasattr(section_type, "code"):
        sec = section_type
        sec_code = sec.code
        sec_name = getattr(sec, "name", sec_code)
    else:
        sec_code = str(section_type)
        sec_name = sec_code

    if sec is not None:
        q_filter = (
            models.Q(section=sec)
            | models.Q(section_type__iexact=sec_code)
            | models.Q(section__code__iexact=sec_code)
        )
    else:
        q_filter = (
            models.Q(section_type__iexact=sec_code)
            | models.Q(section__code__iexact=sec_code)
            | models.Q(section__name__iexact=sec_code)
        )

    base_qs = assessment.questions if (assessment and assessment.questions.exists()) else QuestionBank.objects
    query = base_qs.filter(q_filter, is_active=True)
    if exclude_question_ids:
        query = query.exclude(id__in=exclude_question_ids)

    # Distinct query and unique dictionary map
    raw_qs = list(query.distinct())
    unique_map = {q.id: q for q in raw_qs}
    qs = list(unique_map.values())

    if len(qs) < required_count:
        scope = f"in pool for '{assessment.title}'" if assessment else "in bank"
        shortage = required_count - len(qs)
        raise ValidationError(
            {
                "bank_error": (
                    f"Insufficient '{sec_name}' ({sec_code}) questions {scope}: "
                    f"found {len(qs)}, requires {required_count} (shortage of {shortage})."
                )
            }
        )

    # Stratified sampling across difficulty buckets
    buckets = defaultdict(list)
    for q in qs:
        buckets[q.difficulty].append(q)

    for key in buckets:
        random.shuffle(buckets[key])

    selected = []
    bucket_keys = list(buckets.keys())
    random.shuffle(bucket_keys)

    changed = True
    while len(selected) < required_count and changed:
        changed = False
        for key in bucket_keys:
            if len(selected) >= required_count:
                break
            if buckets[key]:
                selected.append(buckets[key].pop())
                changed = True

    if len(selected) < required_count:
        leftover = []
        for key in bucket_keys:
            leftover.extend(buckets[key])
        random.shuffle(leftover)
        selected.extend(leftover[: required_count - len(selected)])

    random.shuffle(selected)
    return selected[:required_count]


# ==============================================================================
# ASSESSMENT LIFECYCLE MANAGEMENT
# ==============================================================================

@transaction.atomic
def prepare_assessment(assessment: Assessment, user=None):
    """
    Validates question sufficiency and eligible colleges, transitioning DRAFT -> READY.
    """
    validate_question_bank_sufficiency(assessment=assessment)
    if not assessment.eligible_colleges.exists():
        raise ValidationError({"detail": "Assessment must have at least one assigned college before preparation."})

    previous_status = assessment.status
    assessment.status = Assessment.Status.READY
    assessment.save(update_fields=["status", "updated_at"])

    log_assessment_audit(
        action=AssessmentAuditLog.Action.ASSESSMENT_PREPARED,
        entity_type="ASSESSMENT",
        entity_id=str(assessment.id),
        user=user,
        details={"previous_status": previous_status, "new_status": Assessment.Status.READY},
    )
    return assessment


@transaction.atomic
def open_assessment(assessment: Assessment, user=None):
    """
    Opens an assessment for candidate attempts.
    Validates question bank sufficiency and eligible colleges.
    """
    if assessment.status == Assessment.Status.ARCHIVED:
        raise ValidationError({"detail": f"Cannot open archived assessment '{assessment.title}'. Please unarchive it first."})

    validate_question_bank_sufficiency(assessment=assessment)
    if not assessment.eligible_colleges.exists():
        raise ValidationError({"detail": "Assessment must have at least one assigned college before opening."})

    previous_status = assessment.status
    now = timezone.now()

    assessment.status = Assessment.Status.OPEN
    assessment.opened_at = now
    assessment.opened_by = user if (user and getattr(user, "is_authenticated", False)) else None
    assessment.closed_at = None
    assessment.closed_by = None
    assessment.save(update_fields=["status", "opened_at", "opened_by", "closed_at", "closed_by", "updated_at"])

    log_assessment_audit(
        action=AssessmentAuditLog.Action.ASSESSMENT_OPENED,
        entity_type="ASSESSMENT",
        entity_id=str(assessment.id),
        user=user,
        details={
            "previous_status": previous_status,
            "opened_at": now.isoformat(),
            "eligible_colleges_count": assessment.eligible_colleges.count(),
        },
    )
    return assessment


@transaction.atomic
def close_assessment(assessment: Assessment, user=None, close_policy=None):
    """
    Closes an assessment. Enforces close policy:
    - ALLOW_FINISH: In-progress attempts can finish before their individual deadlines.
    - STRICT_CUTOFF: Any active in-progress attempts are immediately finalized.
    """
    if assessment.status != Assessment.Status.OPEN and assessment.status != Assessment.Status.SCHEDULED:
        raise ValidationError({"detail": f"Cannot close assessment in state '{assessment.status}'."})

    policy = close_policy or assessment.close_policy
    now = timezone.now()

    assessment.status = Assessment.Status.CLOSED
    assessment.closed_at = now
    assessment.closed_by = user if (user and getattr(user, "is_authenticated", False)) else None
    if close_policy:
        assessment.close_policy = close_policy
    assessment.save(update_fields=["status", "closed_at", "closed_by", "close_policy", "updated_at"])

    cutoff_attempts_count = 0
    if policy == Assessment.ClosePolicy.STRICT_CUTOFF:
        in_progress_attempts = AssessmentAttempt.objects.filter(
            assessment=assessment,
            state__in=[AssessmentAttempt.State.CREATED, AssessmentAttempt.State.IN_PROGRESS],
        )
        for att in in_progress_attempts:
            finalize_assessment_attempt(att, final_state=AssessmentAttempt.State.TIMED_OUT)
            cutoff_attempts_count += 1

    log_assessment_audit(
        action=AssessmentAuditLog.Action.ASSESSMENT_CLOSED,
        entity_type="ASSESSMENT",
        entity_id=str(assessment.id),
        user=user,
        details={
            "closed_at": now.isoformat(),
            "close_policy": policy,
            "cutoff_attempts_count": cutoff_attempts_count,
        },
    )
    return assessment


@transaction.atomic
def archive_assessment(assessment: Assessment, user=None):
    """
    Archives a closed or draft assessment.
    """
    if assessment.status == Assessment.Status.OPEN:
        raise ValidationError({"detail": "Cannot archive an active OPEN assessment. Please close it first."})

    previous_status = assessment.status
    assessment.status = Assessment.Status.ARCHIVED
    assessment.save(update_fields=["status", "updated_at"])

    log_assessment_audit(
        action=AssessmentAuditLog.Action.ASSESSMENT_ARCHIVED,
        entity_type="ASSESSMENT",
        entity_id=str(assessment.id),
        user=user,
        details={"previous_status": previous_status, "new_status": Assessment.Status.ARCHIVED},
    )
    return assessment


@transaction.atomic
def assign_colleges_to_assessment(assessment: Assessment, college_ids: list, user=None):
    """
    Updates the list of colleges eligible for this assessment.
    Enforces lifecycle rules:
    - ARCHIVED assessments cannot have college assignments modified.
    - READY, SCHEDULED, and OPEN assessments must have at least one eligible college assigned.
    """
    if assessment.status == Assessment.Status.ARCHIVED:
        raise ValidationError({"detail": f"Cannot modify college assignments for archived assessment '{assessment.title}'. Please unarchive it first."})

    colleges = list(College.objects.filter(id__in=college_ids, is_active=True))
    if len(colleges) == 0 and assessment.status in [Assessment.Status.READY, Assessment.Status.SCHEDULED, Assessment.Status.OPEN]:
        raise ValidationError({"detail": f"Assessment in {assessment.status} status must have at least one eligible college assigned."})

    previous_ids = list(assessment.eligible_colleges.values_list("id", flat=True))
    new_ids = [c.id for c in colleges]
    added_ids = [cid for cid in new_ids if cid not in previous_ids]
    removed_ids = [cid for cid in previous_ids if cid not in new_ids]

    assessment.eligible_colleges.set(colleges)
    assessment.save(update_fields=["updated_at"])

    log_assessment_audit(
        action=AssessmentAuditLog.Action.COLLEGE_ASSIGNED,
        entity_type="ASSESSMENT",
        entity_id=str(assessment.id),
        user=user,
        details={
            "assigned_college_ids": new_ids,
            "assigned_college_codes": [c.code for c in colleges],
            "added_college_ids": added_ids,
            "removed_college_ids": removed_ids,
        },
    )
    return assessment


@transaction.atomic
def assign_questions_to_assessment(assessment: Assessment, question_ids: list, user=None):
    """
    Assigns specific QuestionBank items to this assessment's scoped pool.
    """
    questions = list(QuestionBank.objects.filter(id__in=question_ids))
    assessment.questions.add(*questions)
    assessment.save(update_fields=["updated_at"])

    log_assessment_audit(
        action=AssessmentAuditLog.Action.QUESTIONS_ASSIGNED,
        entity_type="ASSESSMENT",
        entity_id=str(assessment.id),
        user=user,
        details={
            "added_count": len(questions),
            "total_pool_count": assessment.questions.count(),
        },
    )
    return assessment


@transaction.atomic
def remove_questions_from_assessment(assessment: Assessment, question_ids: list, user=None):
    """
    Removes specific QuestionBank items from this assessment's scoped pool.
    """
    questions = list(QuestionBank.objects.filter(id__in=question_ids))
    assessment.questions.remove(*questions)
    assessment.save(update_fields=["updated_at"])

    log_assessment_audit(
        action=AssessmentAuditLog.Action.QUESTIONS_ASSIGNED,
        entity_type="ASSESSMENT",
        entity_id=str(assessment.id),
        user=user,
        details={
            "removed_count": len(questions),
            "total_pool_count": assessment.questions.count(),
        },
    )
    return assessment


@transaction.atomic
def release_assessment_results(assessment: Assessment, user=None):
    """
    Officially releases assessment results, allowing candidates to view their verified scorecards.
    """
    now = timezone.now()
    assessment.is_results_released = True
    assessment.results_released_at = now
    assessment.results_released_by = user if (user and getattr(user, "is_authenticated", False)) else None
    assessment.save(update_fields=["is_results_released", "results_released_at", "results_released_by", "updated_at"])

    log_assessment_audit(
        action=AssessmentAuditLog.Action.RESULTS_RELEASED,
        entity_type="ASSESSMENT",
        entity_id=str(assessment.id),
        user=user,
        details={"released_at": now.isoformat()},
    )
    return assessment


@transaction.atomic
def unrelease_assessment_results(assessment: Assessment, user=None):
    """
    Withholds assessment results from student view.
    """
    assessment.is_results_released = False
    assessment.save(update_fields=["is_results_released", "updated_at"])

    log_assessment_audit(
        action=AssessmentAuditLog.Action.RESULTS_UNRELEASED,
        entity_type="ASSESSMENT",
        entity_id=str(assessment.id),
        user=user,
        details={"withheld_at": timezone.now().isoformat()},
    )
    return assessment


# ==============================================================================
# CANDIDATE CSV IMPORT PER COLLEGE
# ==============================================================================

def import_candidates_from_csv(college: College, csv_data: str, user=None):
    """
    Bulk imports candidates for a managed College from CSV content.
    Expected CSV columns: full_name, register_number, email, department, year_of_study, phone_number
    """
    f = io.StringIO(csv_data.strip())
    reader = csv.DictReader(f)

    required_headers = ["full_name", "register_number", "email"]
    if not reader.fieldnames:
        raise ValidationError({"detail": "CSV file is empty or missing headers."})

    # Normalize header names
    field_map = {fn.strip().lower(): fn for fn in reader.fieldnames}
    for req in required_headers:
        if req not in field_map:
            raise ValidationError({"detail": f"Missing required column header: '{req}'."})

    total_rows = 0
    created_count = 0
    updated_count = 0
    errors = []

    with transaction.atomic():
        for row_num, raw_row in enumerate(reader, start=2):
            total_rows += 1
            row = {k.strip().lower(): (v or "").strip() for k, v in raw_row.items() if k}

            full_name = row.get("full_name", "")
            reg_no = row.get("register_number", "").upper()
            email = row.get("email", "").lower()
            dept = row.get("department", "Engineering")
            year = row.get("year_of_study", "Final Year")
            phone = row.get("phone_number", row.get("mobile", row.get("phone", "")))

            if not full_name:
                errors.append(f"Row {row_num}: Full name is required.")
                continue
            if not reg_no:
                errors.append(f"Row {row_num}: Register number is required.")
                continue
            if not email or "@" not in email:
                errors.append(f"Row {row_num}: Valid email is required.")
                continue
            if not phone:
                errors.append(f"Row {row_num}: Mobile phone number is required.")
                continue

            existing_by_email = Candidate.objects.filter(email=email).first()
            existing_by_reg = Candidate.objects.filter(college_ref=college, register_number=reg_no).first()

            if existing_by_email:
                # Update existing candidate record
                existing_by_email.full_name = full_name
                existing_by_email.register_number = reg_no
                existing_by_email.college_ref = college
                existing_by_email.college = college.name
                existing_by_email.department = dept
                existing_by_email.year_of_study = year
                existing_by_email.phone_number = phone
                existing_by_email.save()
                updated_count += 1
            elif existing_by_reg:
                existing_by_reg.full_name = full_name
                existing_by_reg.email = email
                existing_by_reg.department = dept
                existing_by_reg.year_of_study = year
                existing_by_reg.phone_number = phone
                existing_by_reg.save()
                updated_count += 1
            else:
                Candidate.objects.create(
                    full_name=full_name,
                    register_number=reg_no,
                    email=email,
                    college_ref=college,
                    college=college.name,
                    department=dept,
                    year_of_study=year,
                    phone_number=phone,
                    is_active=True,
                )
                created_count += 1

        log_assessment_audit(
            action=AssessmentAuditLog.Action.CANDIDATES_IMPORTED,
            entity_type="COLLEGE",
            entity_id=str(college.id),
            user=user,
            details={
                "college_code": college.code,
                "total_rows": total_rows,
                "created_count": created_count,
                "updated_count": updated_count,
                "error_count": len(errors),
            },
        )

    return {
        "total_rows": total_rows,
        "created_count": created_count,
        "updated_count": updated_count,
        "errors": errors[:50],
    }


# ==============================================================================
# STUDENT ASSESSMENT ATTEMPTS
# ==============================================================================

@transaction.atomic
def start_assessment_for_candidate(candidate: Candidate, assessment: Assessment = None, config: AssessmentConfig = None):
    """
    Starts an assessment attempt for the candidate with balanced question selection and snapshotting.
    Strictly verifies:
    1. Candidate is active
    2. Candidate's college is active
    3. Assessment is in OPEN state
    4. Candidate's college is in assessment.eligible_colleges
    5. Candidate has not exceeded max_attempts for this assessment
    6. Concurrency lock on candidate row prevents duplicate simultaneous attempts
    """
    # If 2nd argument is an AssessmentConfig (legacy calls)
    if isinstance(assessment, AssessmentConfig):
        config = assessment
        assessment = None

    perf_started = time.perf_counter()
    perf_marks = {}

    def mark(label):
        now = time.perf_counter()
        perf_marks[label] = round((now - perf_started) * 1000, 1)
        logger.info(
            "ASSESSMENT_SERVICE_TIMING stage=%s elapsed_ms=%.1f candidate_id=%s",
            label,
            perf_marks[label],
            candidate.id,
        )

    # Fallback / resolve assessment & config
    if not assessment:
        if candidate.college_ref:
            # Pick first open assessment assigned to candidate's college
            assessment = candidate.college_ref.assigned_assessments.filter(status=Assessment.Status.OPEN).first()
        if not assessment:
            assessment = Assessment.objects.filter(status=Assessment.Status.OPEN).first()
        if not assessment:
            assessment = get_or_create_default_assessment()

    if not config:
        config = get_or_create_default_config()

    # Lock candidate row for concurrency safety in PostgreSQL
    locked_candidate = Candidate.objects.select_for_update().get(id=candidate.id)
    mark("candidate_lock")

    # Backfill college_ref if missing from candidate
    if not locked_candidate.college_ref:
        default_col = College.objects.filter(is_active=True).first()
        if not default_col:
            default_col = College.objects.create(
                name=locked_candidate.college or "General Institution",
                code="DEFAULT",
                is_active=True,
            )
        locked_candidate.college_ref = default_col
        locked_candidate.save(update_fields=["college_ref"])

    # 1. Candidate active check
    if not locked_candidate.is_active:
        raise ValidationError({"detail": "Your candidate profile has been deactivated. Please contact your administrator."})

    # 2. College active check
    if locked_candidate.college_ref and not locked_candidate.college_ref.is_active:
        raise ValidationError({"detail": f"Institutional registration for {locked_candidate.college_ref.name} is currently suspended."})

    # 3. Assessment OPEN check
    if not assessment.is_currently_open():
        raise ValidationError({
            "detail": f"Assessment '{assessment.title}' is currently {assessment.status.lower()} and not accepting new attempts."
        })

    # 4. College eligibility check
    if locked_candidate.college_ref and not assessment.eligible_colleges.filter(id=locked_candidate.college_ref_id).exists():
        if assessment.code == "CSL-INITIAL-01":
            assessment.eligible_colleges.add(locked_candidate.college_ref)
        else:
            raise ValidationError({
                "detail": f"Your institution ({locked_candidate.college_ref.name}) is not enrolled in '{assessment.title}'."
            })

    # 5. Check if there is already an active attempt in progress for this assessment
    existing_in_progress = AssessmentAttempt.objects.filter(
        candidate=locked_candidate,
        assessment=assessment,
        state__in=[AssessmentAttempt.State.CREATED, AssessmentAttempt.State.IN_PROGRESS],
    ).first()

    if existing_in_progress:
        if existing_in_progress.is_expired():
            finalize_assessment_attempt(existing_in_progress, final_state=AssessmentAttempt.State.TIMED_OUT)
            raise ValidationError({"detail": "Your previous assessment attempt has expired."})
        return existing_in_progress

    # 6. Check attempt limit for this assessment
    completed_attempts = AssessmentAttempt.objects.filter(
        candidate=locked_candidate,
        assessment=assessment,
        state__in=[
            AssessmentAttempt.State.SUBMITTED,
            AssessmentAttempt.State.TIMED_OUT,
            AssessmentAttempt.State.FLAGGED_FOR_REVIEW,
        ],
    ).count()
    mark("attempt_checks")    

    max_allowed = assessment.max_attempts if assessment else config.max_attempts
    if completed_attempts >= max_allowed:
        raise ValidationError({"detail": f"Maximum attempts ({max_allowed}) reached for this assessment."})

    # Validate bank sufficiency for this assessment
    validate_question_bank_sufficiency(assessment=assessment)
    mark("bank_validation")

    # Dynamic or legacy question selection
    all_selected = []
    selected_question_ids = set()
    has_allocations = False
    try:
        if assessment and assessment.section_allocations.exists():
            has_allocations = True
    except Exception:
        has_allocations = False

    if has_allocations:
        allocations = list(assessment.section_allocations.select_related("section").order_by("order", "id"))
        total_required = sum(alloc.question_count for alloc in allocations)
        order_counter = 1
        for alloc in allocations:
            sec_questions = select_balanced_questions(
                alloc.section.code,
                alloc.question_count,
                assessment=assessment,
                section_obj=alloc.section,
                exclude_question_ids=selected_question_ids,
            )
            for q in sec_questions:
                all_selected.append((q, order_counter, alloc.section.code))
                selected_question_ids.add(q.id)
                order_counter += 1
    else:
        apt_count = assessment.aptitude_count if assessment else config.aptitude_count
        cod_count = assessment.coding_count if assessment else config.coding_count
        total_required = apt_count + cod_count

        selected_aptitude = select_balanced_questions(
            QuestionBank.SectionType.APTITUDE,
            apt_count,
            assessment=assessment,
            exclude_question_ids=selected_question_ids,
        )
        for q in selected_aptitude:
            selected_question_ids.add(q.id)

        selected_coding = select_balanced_questions(
            QuestionBank.SectionType.CODING,
            cod_count,
            assessment=assessment,
            exclude_question_ids=selected_question_ids,
        )
        for q in selected_coding:
            selected_question_ids.add(q.id)

        for i, q in enumerate(selected_aptitude):
            all_selected.append((q, i + 1, QuestionBank.SectionType.APTITUDE))
        for i, q in enumerate(selected_coding):
            all_selected.append((q, i + apt_count + 1, QuestionBank.SectionType.CODING))
    mark("question_selection")
    if len(all_selected) != total_required:
        raise ValidationError(
            {"detail": f"Failed to generate assessment: expected {total_required} questions, selected {len(all_selected)}."}
        )

    now = timezone.now()
    duration = assessment.duration_minutes if assessment else config.duration_minutes
    deadline = now + timedelta(minutes=duration)

    # Create Attempt
    attempt = AssessmentAttempt.objects.create(
        candidate=locked_candidate,
        config=config,
        assessment=assessment,
        state=AssessmentAttempt.State.IN_PROGRESS,
        started_at=now,
        deadline=deadline,
    )

    # Create Snapshots with option shuffling and strict question uniqueness
    snapshots = []
    seen_q_ids = set()
    snapshot_order = 1
    for q, order, sec_code in all_selected:
        if q.id in seen_q_ids:
            continue
        seen_q_ids.add(q.id)

        orig_options = [
            ("A", q.option_a),
            ("B", q.option_b),
            ("C", q.option_c),
            ("D", q.option_d),
        ]
        shuffled = orig_options.copy()
        random.shuffle(shuffled)

        keys = ["A", "B", "C", "D"]
        correct_key_in_shuffled = "A"
        for idx, (orig_key, text) in enumerate(shuffled):
            if orig_key == q.correct_option:
                correct_key_in_shuffled = keys[idx]

        snapshots.append(
            AttemptQuestionSnapshot(
                attempt=attempt,
                question=q,
                question_order=snapshot_order,
                section_type=sec_code,
                prompt=q.prompt,
                option_a_text=shuffled[0][1],
                option_b_text=shuffled[1][1],
                option_c_text=shuffled[2][1],
                option_d_text=shuffled[3][1],
                correct_option_key=correct_key_in_shuffled,
            )
        )
        snapshot_order += 1

    AttemptQuestionSnapshot.objects.bulk_create(snapshots)
    mark("snapshot_creation")

    IntegrityEvent.objects.create(
        attempt=attempt,
        event_type=IntegrityEvent.EventType.ATTEMPT_STARTED,
        metadata={
            "started_at": now.isoformat(),
            "assessment_id": str(assessment.id) if assessment else None,
            "assessment_code": assessment.code if assessment else "LEGACY",
        },
    )
    mark("integrity_event")
    logger.info(
        "ASSESSMENT_SERVICE_TIMING total_ms=%.1f candidate_id=%s",
        (time.perf_counter() - perf_started) * 1000,
        candidate.id,
    )    

    return attempt


@transaction.atomic
def save_candidate_answer(attempt: AssessmentAttempt, question_order: int, selected_option: str):
    """
    Idempotent single answer save. Validates deadline and attempt state.
    Locks attempt row with select_for_update().
    """
    locked_attempt = (
        AssessmentAttempt.objects.select_for_update()
        .filter(id=attempt.id)
        .first()
    )
    if not locked_attempt:
        raise ValidationError({"detail": "Attempt not found."})

    if locked_attempt.state != AssessmentAttempt.State.IN_PROGRESS:
        raise ValidationError({"detail": f"Attempt is not active (state: {locked_attempt.state})."})

    if locked_attempt.is_expired():
        finalize_assessment_attempt(locked_attempt, final_state=AssessmentAttempt.State.TIMED_OUT)
        raise ValidationError({"detail": "Assessment time has expired."})

    snapshot = (
        AttemptQuestionSnapshot.objects.select_for_update()
        .filter(attempt=locked_attempt, question_order=question_order)
        .first()
    )
    if not snapshot:
        raise ValidationError({"detail": "Invalid question order."})

    selected_clean = selected_option.strip().upper() if selected_option else ""
    if selected_clean and selected_clean not in ("A", "B", "C", "D"):
        raise ValidationError({"detail": "Invalid option selected."})

    snapshot.selected_option = selected_clean
    snapshot.answered_at = timezone.now()
    snapshot.save(update_fields=["selected_option", "answered_at", "updated_at"])

    return snapshot


@transaction.atomic
def finalize_assessment_attempt(attempt: AssessmentAttempt, final_state=AssessmentAttempt.State.SUBMITTED):
    """
    Evaluates MCQs server-side, tallies scores, locks answers, transitions state.
    Uses select_for_update() to prevent concurrent finalization or duplicate scoring.
    """
    locked_attempt = (
        AssessmentAttempt.objects.select_for_update()
        .filter(id=attempt.id)
        .first()
    )
    if not locked_attempt:
        return attempt

    # If already finalized, return immediately without re-scoring or altering state
    if locked_attempt.state in [
        AssessmentAttempt.State.SUBMITTED,
        AssessmentAttempt.State.TIMED_OUT,
        AssessmentAttempt.State.FLAGGED_FOR_REVIEW,
    ]:
        return locked_attempt

    now = timezone.now()
    snapshots = locked_attempt.question_snapshots.select_related("question").all()

    # Dynamic section marks lookup
    marks_map = {}
    try:
        if locked_attempt.assessment and locked_attempt.assessment.section_allocations.exists():
            for alloc in locked_attempt.assessment.section_allocations.select_related("section").all():
                marks_map[alloc.section.code] = alloc.marks_per_question
    except Exception:
        marks_map = {}

    aptitude_score = 0
    coding_score = 0
    total_score = 0

    for s in snapshots:
        if s.selected_option and s.selected_option == s.correct_option_key:
            s.is_correct = True
            q_marks = marks_map.get(s.section_type, 1)
            total_score += q_marks
            if s.section_type == QuestionBank.SectionType.APTITUDE:
                aptitude_score += q_marks
            elif s.section_type == QuestionBank.SectionType.CODING:
                coding_score += q_marks
        else:
            s.is_correct = False
        s.save(update_fields=["is_correct", "updated_at"])

    max_marks = (
        locked_attempt.assessment.total_marks
        if locked_attempt.assessment
        else (locked_attempt.config.total_marks if locked_attempt.config else 50)
    )
    percentage = round((total_score / float(max_marks)) * 100.0, 2) if max_marks else 0.0

    locked_attempt.state = final_state
    locked_attempt.aptitude_score = aptitude_score
    locked_attempt.coding_score = coding_score
    locked_attempt.total_score = total_score
    locked_attempt.percentage = percentage
    locked_attempt.submitted_at = now
    locked_attempt.save(
        update_fields=[
            "state",
            "aptitude_score",
            "coding_score",
            "total_score",
            "percentage",
            "submitted_at",
            "updated_at",
        ]
    )

    IntegrityEvent.objects.create(
        attempt=locked_attempt,
        event_type=(
            IntegrityEvent.EventType.SUBMITTED
            if final_state == AssessmentAttempt.State.SUBMITTED
            else IntegrityEvent.EventType.TIMED_OUT
        ),
        metadata={"total_score": total_score, "final_state": final_state},
    )

    return locked_attempt
