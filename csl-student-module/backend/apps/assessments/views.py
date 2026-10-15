import logging
import time

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from .models import (
    Candidate,
    College,
    Assessment,
    AssessmentAttempt,
    IntegrityEvent,
    AssessmentConfig,
    QuestionBank,
)
from .serializers import (
    CandidateRegistrationSerializer,
    StudentCollegeOptionSerializer,
    StudentCandidateAssessmentSerializer,
    AssessmentAttemptDetailSerializer,
    AnswerSaveSerializer,
    IntegrityEventSerializer,
    AssessmentResultSerializer,
)
from .services import (
    start_assessment_for_candidate,
    save_candidate_answer,
    finalize_assessment_attempt,
    get_or_create_default_config,
    get_or_create_default_assessment,
)
from .tokens import (
    CandidateAssessmentAuthentication,
    generate_candidate_token,
)

logger = logging.getLogger(__name__)


def get_authorized_candidate(request):
    """
    Returns candidate from authenticated assessment token or None.
    """
    return getattr(request, "candidate", None)


def verify_attempt_ownership(request, attempt: AssessmentAttempt):
    """
    Verifies that the request's authenticated candidate owns the given attempt.
    Also verifies against staff / admin credentials.
    """
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False):
        return True

    candidate = get_authorized_candidate(request)
    if not candidate:
        return False

    return str(attempt.candidate_id) == str(candidate.id)


class StudentCollegesListView(APIView):
    """
    Student-facing: returns active colleges for registration dropdown.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        colleges = College.objects.filter(is_active=True).order_by("name")
        return Response(StudentCollegeOptionSerializer(colleges, many=True).data)


class CandidateEligibleAssessmentsView(APIView):
    """
    Student-facing: returns assessments assigned to the authenticated candidate's college.
    """
    authentication_classes = [CandidateAssessmentAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        candidate = get_authorized_candidate(request)
        if not candidate:
            return Response(
                {"detail": "Authentication required. Valid candidate token must be provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        colleges = [candidate.college_ref] if candidate.college_ref else []
        if candidate.college_ref:
            assessments = candidate.college_ref.assigned_assessments.filter(
                status__in=[
                    Assessment.Status.OPEN,
                    Assessment.Status.SCHEDULED,
                    Assessment.Status.READY,
                    Assessment.Status.CLOSED,
                ]
            ).order_by("status", "-created_at")
        else:
            # Fallback to all open assessments
            assessments = Assessment.objects.filter(status=Assessment.Status.OPEN).order_by("-created_at")

        serializer = StudentCandidateAssessmentSerializer(
            assessments,
            many=True,
            context={"candidate": candidate},
        )
        return Response({
            "candidate": {
                "id": str(candidate.id),
                "full_name": candidate.full_name,
                "register_number": candidate.register_number,
                "college": candidate.college,
                "college_id": candidate.college_ref_id,
                "department": candidate.department,
                "year_of_study": candidate.year_of_study,
                "is_active": candidate.is_active,
            },
            "assessments": serializer.data,
        })


class CandidateRegisterView(APIView):
    """
    Step 1: Student opens assessment portal, enters academic & identity details.
    Selects from managed active Colleges. Enforces mandatory mobile phone number.
    Returns secure, signed assessment token for subsequent requests.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CandidateRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        email = data["email"].strip().lower()
        college_id = data.get("college_id")
        college_name = data.get("college", "").strip()
        reg_no = data["register_number"].strip().upper()
        phone_no = data.get("phone_number", "").strip()

        # Resolve College entity
        college_obj = None
        if college_id:
            college_obj = College.objects.filter(id=college_id, is_active=True).first()
            if not college_obj:
                return Response(
                    {"college_id": ["Selected institution is currently inactive or invalid."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            college_name = college_obj.name
        elif college_name:
            # Search by name
            college_obj = College.objects.filter(name__iexact=college_name, is_active=True).first()
            if not college_obj:
                import re
                clean_code = re.sub(r'[^A-Z0-9]', '', college_name.upper())[:10]
                if not clean_code or College.objects.filter(code=clean_code).exists():
                    clean_code = f"COL-{College.objects.count() + 1:03d}"
                college_obj = College.objects.create(
                    name=college_name,
                    code=clean_code,
                    is_active=True,
                )

        if not college_obj:
            return Response(
                {"college": ["Please select a valid institution from the list."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Check existing candidate by email, or by college + register number
            existing_candidate = Candidate.objects.select_for_update().filter(email=email).first()
            if not existing_candidate:
                existing_candidate = Candidate.objects.select_for_update().filter(
                    college_ref=college_obj, register_number=reg_no
                ).first()

            if existing_candidate:
                # Active candidate & institution check
                if not existing_candidate.is_active:
                    return Response(
                        {"detail": "Your candidate profile has been deactivated. Please contact your administrator."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if college_obj and not college_obj.is_active:
                    return Response(
                        {"detail": f"Institutional registration for {college_obj.name} is currently suspended."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                # Keep candidate record updated idempotently
                if not existing_candidate.email:
                    existing_candidate.email = email
                if phone_no:
                    existing_candidate.phone_number = phone_no
                if data.get("department"):
                    existing_candidate.department = data.get("department")
                if data.get("year_of_study"):
                    existing_candidate.year_of_study = data.get("year_of_study")
                if data.get("full_name") and existing_candidate.full_name != data["full_name"]:
                    existing_candidate.full_name = data["full_name"]
                if existing_candidate.college_ref_id != college_obj.id:
                    existing_candidate.college_ref = college_obj
                    existing_candidate.college = college_obj.name
                existing_candidate.save()

                # Determine target assessment if specified or singular
                target_assessment = None
                target_assessment_id = data.get("assessment_id")
                if target_assessment_id:
                    target_assessment = Assessment.objects.filter(id=target_assessment_id).first()
                    if target_assessment and college_obj:
                        if not target_assessment.eligible_colleges.filter(id=college_obj.id).exists():
                            return Response(
                                {"detail": f"Your institution ({college_obj.name}) is not eligible for '{target_assessment.title}'."},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                if not target_assessment and college_obj:
                    open_assigned = college_obj.assigned_assessments.filter(status=Assessment.Status.OPEN)
                    if open_assigned.count() == 1:
                        target_assessment = open_assigned.first()

                # Check for active in-progress attempt
                attempt_qs = existing_candidate.attempts.all()
                if target_assessment:
                    active_attempt = attempt_qs.filter(
                        assessment=target_assessment,
                        state__in=[AssessmentAttempt.State.CREATED, AssessmentAttempt.State.IN_PROGRESS],
                    ).order_by("-created_at").first()
                else:
                    active_attempt = attempt_qs.filter(
                        state__in=[AssessmentAttempt.State.CREATED, AssessmentAttempt.State.IN_PROGRESS],
                    ).order_by("-created_at").first()

                if active_attempt and active_attempt.is_expired():
                    finalize_assessment_attempt(active_attempt, final_state=AssessmentAttempt.State.TIMED_OUT)
                    active_attempt = None

                # Check completed attempts against attempt limit
                if target_assessment:
                    completed_attempts = attempt_qs.filter(
                        assessment=target_assessment,
                        state__in=[
                            AssessmentAttempt.State.SUBMITTED,
                            AssessmentAttempt.State.TIMED_OUT,
                            AssessmentAttempt.State.FLAGGED_FOR_REVIEW,
                        ],
                    )
                    already_completed = completed_attempts.count() >= target_assessment.max_attempts
                    last_completed = completed_attempts.order_by("-created_at").first()
                else:
                    open_assigned = college_obj.assigned_assessments.filter(status=Assessment.Status.OPEN) if college_obj else Assessment.objects.none()
                    if open_assigned.exists():
                        eligible_for_any = False
                        for a in open_assigned:
                            done_count = attempt_qs.filter(
                                assessment=a,
                                state__in=[
                                    AssessmentAttempt.State.SUBMITTED,
                                    AssessmentAttempt.State.TIMED_OUT,
                                    AssessmentAttempt.State.FLAGGED_FOR_REVIEW,
                                ],
                            ).count()
                            if done_count < a.max_attempts:
                                eligible_for_any = True
                                break
                        already_completed = not eligible_for_any
                        last_completed = attempt_qs.filter(
                            state__in=[
                                AssessmentAttempt.State.SUBMITTED,
                                AssessmentAttempt.State.TIMED_OUT,
                                AssessmentAttempt.State.FLAGGED_FOR_REVIEW,
                            ]
                        ).order_by("-created_at").first()
                    else:
                        completed_attempts = attempt_qs.filter(
                            state__in=[
                                AssessmentAttempt.State.SUBMITTED,
                                AssessmentAttempt.State.TIMED_OUT,
                                AssessmentAttempt.State.FLAGGED_FOR_REVIEW,
                            ]
                        )
                        already_completed = completed_attempts.exists()
                        last_completed = completed_attempts.order_by("-created_at").first()

                if active_attempt:
                    registration_status = "IN_PROGRESS"
                elif already_completed:
                    registration_status = "COMPLETED"
                else:
                    registration_status = "NOT_STARTED"

                token = generate_candidate_token(
                    str(existing_candidate.id),
                    str(active_attempt.id if active_attempt else (last_completed.id if (already_completed and last_completed) else None)),
                )

                remaining_secs = 0
                if active_attempt and active_attempt.deadline:
                    remaining_secs = max(0, int((active_attempt.deadline - timezone.now()).total_seconds()))

                return Response(
                    {
                        "candidate_id": str(existing_candidate.id),
                        "assessment_token": token,
                        "full_name": existing_candidate.full_name,
                        "college": existing_candidate.college,
                        "college_id": existing_candidate.college_ref_id,
                        "registration_status": registration_status,
                        "is_active_attempt": bool(active_attempt),
                        "already_completed": already_completed and not bool(active_attempt),
                        "attempt_id": str(active_attempt.id if active_attempt else (last_completed.id if (already_completed and last_completed) else "")),
                        "attempt_state": active_attempt.state if active_attempt else (last_completed.state if (already_completed and last_completed) else ""),
                        "assessment_title": active_attempt.assessment.title if (active_attempt and active_attempt.assessment) else (last_completed.assessment.title if (already_completed and last_completed and last_completed.assessment) else "Assessment"),
                        "assessment_code": active_attempt.assessment.code if (active_attempt and active_attempt.assessment) else (last_completed.assessment.code if (already_completed and last_completed and last_completed.assessment) else "CSL"),
                        "remaining_seconds": remaining_secs,
                        "message": (
                            "Welcome back. Active session found."
                            if active_attempt
                            else ("Assessment already completed." if already_completed else "Registration verified. You may proceed to your assessment.")
                        ),
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                target_assessment_id = data.get("assessment_id")
                if target_assessment_id and college_obj:
                    target_assessment = Assessment.objects.filter(id=target_assessment_id).first()
                    if target_assessment and not target_assessment.eligible_colleges.filter(id=college_obj.id).exists():
                        return Response(
                            {"detail": f"Your institution ({college_obj.name}) is not eligible for '{target_assessment.title}'."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                candidate = Candidate.objects.create(
                    full_name=data["full_name"],
                    register_number=reg_no,
                    email=email,
                    college_ref=college_obj,
                    college=college_name,
                    department=data.get("department", "Engineering"),
                    year_of_study=data.get("year_of_study", "Final Year"),
                    phone_number=phone_no,
                    is_active=True,
                )

        token = generate_candidate_token(str(candidate.id))

        return Response(
            {
                "candidate_id": str(candidate.id),
                "assessment_token": token,
                "full_name": candidate.full_name,
                "college": candidate.college,
                "college_id": candidate.college_ref_id,
                "registration_status": "NEW_REGISTRATION",
                "is_active_attempt": False,
                "already_completed": False,
                "message": "Registration successful. You may proceed to your assessment.",
            },
            status=status.HTTP_201_CREATED,
        )


class StartAssessmentView(APIView):
    """
    Step 2: Start or resume assessment attempt.
    Requires CandidateAssessmentAuthentication token.
    Accepts optional assessment_id to target a specific independent assessment.
    """
    authentication_classes = [CandidateAssessmentAuthentication]
    permission_classes = [AllowAny]

    def post(self, request):
        candidate = get_authorized_candidate(request)
        if not candidate:
            return Response(
                {"detail": "Authentication required. Valid assessment token must be provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        assessment_id = request.data.get("assessment_id")
        assessment = None
        if assessment_id:
            assessment = Assessment.objects.filter(id=assessment_id).first()
            if not assessment:
                return Response(
                    {"detail": f"Assessment '{assessment_id}' not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        config = get_or_create_default_config()
        request_started = time.perf_counter()

        try:

            service_started = time.perf_counter()
            attempt = start_assessment_for_candidate(candidate, assessment=assessment, config=config)
            service_ms = (time.perf_counter() - service_started) * 1000
            logger.info(
                "ASSESSMENT_START_TIMING service_ms=%.1f candidate_id=%s assessment_id=%s",
                service_ms, candidate.id, assessment.id if assessment else None,
            )

            token = generate_candidate_token(str(candidate.id), str(attempt.id))


            serializer_started = time.perf_counter()
            serializer = AssessmentAttemptDetailSerializer(attempt)
            res_data = dict(serializer.data)
            serializer_ms = (time.perf_counter() - serializer_started) * 1000
            total_ms = (time.perf_counter() - request_started) * 1000
            logger.info(
                "ASSESSMENT_START_TIMING serializer_ms=%.1f total_ms=%.1f attempt_id=%s",
                serializer_ms, total_ms, attempt.id,
            )

            res_data = dict(serializer.data)
            res_data["assessment_token"] = token
            return Response(res_data, status=status.HTTP_200_OK)
        except ValidationError as e:
            detail_msg = getattr(e, "detail", str(e))
            if isinstance(detail_msg, dict):
                return Response(detail_msg, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": str(detail_msg)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"Unexpected assessment generation failure for candidate {candidate.id}: {e}")
            detail_msg = getattr(e, "detail", None)
            if detail_msg:
                if isinstance(detail_msg, dict):
                    return Response(detail_msg, status=status.HTTP_400_BAD_REQUEST)
                return Response({"detail": str(detail_msg)}, status=status.HTTP_400_BAD_REQUEST)
            return Response(
                {"detail": "Assessment generation could not be completed. Please contact your administrator."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class AttemptStateView(APIView):
    """
    Step 3: Retrieve current active attempt (for reconnect / page refresh).
    Strict ownership check.
    """
    authentication_classes = [CandidateAssessmentAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, attempt_id):
        attempt = get_object_or_404(
            AssessmentAttempt.objects.select_related(
                "candidate", "candidate__college_ref", "assessment", "config"
            ).prefetch_related(
                "question_snapshots",
                "assessment__section_allocations__section",
            ),
            id=attempt_id,
        )
        if not verify_attempt_ownership(request, attempt):
            return Response({"detail": "Access forbidden: you do not own this attempt."}, status=status.HTTP_403_FORBIDDEN)

        # If attempt was paused, resume it upon reconnection
        if attempt.state == AssessmentAttempt.State.IN_PROGRESS and attempt.is_paused:
            credited = attempt.resume_attempt()
            if credited > 0:
                IntegrityEvent.objects.create(
                    attempt=attempt,
                    event_type=IntegrityEvent.EventType.RECONNECTED,
                    metadata={"credited_seconds": credited, "source": "ATTEMPT_STATE_RECONNECT"},
                )

        # Check timeout server-side
        if attempt.state == AssessmentAttempt.State.IN_PROGRESS and attempt.is_expired():
            attempt = finalize_assessment_attempt(attempt, final_state=AssessmentAttempt.State.TIMED_OUT)

        serializer = AssessmentAttemptDetailSerializer(attempt)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SaveAnswerView(APIView):
    """
    Step 4: Save individual MCQ answer. Validates deadline server-side with strict ownership.
    """
    authentication_classes = [CandidateAssessmentAuthentication]
    permission_classes = [AllowAny]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(AssessmentAttempt, id=attempt_id)
        if not verify_attempt_ownership(request, attempt):
            return Response({"detail": "Access forbidden: you do not own this attempt."}, status=status.HTTP_403_FORBIDDEN)

        serializer = AnswerSaveSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        q_order = serializer.validated_data["question_order"]
        sel_opt = serializer.validated_data.get("selected_option", "")

        snapshot = save_candidate_answer(attempt, q_order, sel_opt)
        return Response(
            {
                "question_order": snapshot.question_order,
                "selected_option": snapshot.selected_option,
                "saved_at": snapshot.answered_at,
                "status": "saved",
            },
            status=status.HTTP_200_OK,
        )


class AttemptHeartbeatView(APIView):
    """
    Heartbeat and connection health monitor for active candidate attempts.
    - Synchronizes authoritative server timer
    - Resumes paused timer upon reconnect
    - Gracefully pauses timer if explicit disconnect reported
    - Enforces timeout server-side
    - Throttled to prevent request storms
    """
    authentication_classes = [CandidateAssessmentAuthentication]
    permission_classes = [AllowAny]

    def post(self, request, attempt_id):
        attempt = (
            AssessmentAttempt.objects.select_for_update()
            .filter(id=attempt_id)
            .first()
        )
        if not attempt:
            return Response({"detail": "Attempt not found."}, status=status.HTTP_404_NOT_FOUND)

        if not verify_attempt_ownership(request, attempt):
            return Response({"detail": "Access forbidden: you do not own this attempt."}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()

        if attempt.state in [
            AssessmentAttempt.State.SUBMITTED,
            AssessmentAttempt.State.TIMED_OUT,
            AssessmentAttempt.State.FLAGGED_FOR_REVIEW,
        ]:
            return Response(
                {
                    "status": "finalized",
                    "state": attempt.state,
                    "remaining_seconds": 0,
                    "server_time": now.isoformat(),
                    "is_paused": False,
                },
                status=status.HTTP_200_OK,
            )

        if attempt.is_expired():
            attempt = finalize_assessment_attempt(attempt, final_state=AssessmentAttempt.State.TIMED_OUT)
            return Response(
                {
                    "status": "expired",
                    "state": attempt.state,
                    "remaining_seconds": 0,
                    "server_time": now.isoformat(),
                    "is_paused": False,
                },
                status=status.HTTP_200_OK,
            )

        action = request.data.get("action", "").lower()
        if action == "pause":
            if not attempt.is_paused:
                attempt.pause_attempt(at_time=now)
                IntegrityEvent.objects.create(
                    attempt=attempt,
                    event_type=IntegrityEvent.EventType.TAB_HIDDEN,
                    metadata={"reason": "CLIENT_OFFLINE_PAUSE", "paused_at": now.isoformat()},
                )
        else:
            if attempt.is_paused:
                credited = attempt.resume_attempt(at_time=now)
                if credited > 0:
                    IntegrityEvent.objects.create(
                        attempt=attempt,
                        event_type=IntegrityEvent.EventType.RECONNECTED,
                        metadata={"credited_seconds": credited, "source": "HEARTBEAT_RESUME"},
                    )
            else:
                attempt.last_heartbeat = now
                attempt.save(update_fields=["last_heartbeat", "updated_at"])

        return Response(
            {
                "status": "ok",
                "attempt_id": str(attempt.id),
                "state": attempt.state,
                "remaining_seconds": attempt.get_remaining_seconds(),
                "server_time": now.isoformat(),
                "is_paused": attempt.is_paused,
                "total_paused_seconds": attempt.total_paused_seconds,
                "max_disconnection_grace_seconds": attempt.max_disconnection_grace_seconds,
                "deadline": attempt.deadline.isoformat() if attempt.deadline else None,
            },
            status=status.HTTP_200_OK,
        )


class SyncAnswersView(APIView):
    """
    Batch answer synchronization for network recovery.
    Applies multiple locally persisted answers idempotently within a single transaction.
    """
    authentication_classes = [CandidateAssessmentAuthentication]
    permission_classes = [AllowAny]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(AssessmentAttempt, id=attempt_id)
        if not verify_attempt_ownership(request, attempt):
            return Response({"detail": "Access forbidden: you do not own this attempt."}, status=status.HTTP_403_FORBIDDEN)

        if attempt.state != AssessmentAttempt.State.IN_PROGRESS:
            return Response({"detail": f"Attempt is not active (state: {attempt.state})."}, status=status.HTTP_400_BAD_REQUEST)

        if attempt.is_expired():
            finalize_assessment_attempt(attempt, final_state=AssessmentAttempt.State.TIMED_OUT)
            return Response({"detail": "Assessment time has expired."}, status=status.HTTP_400_BAD_REQUEST)

        answers = request.data.get("answers", [])
        if not isinstance(answers, list):
            return Response({"detail": "Answers must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        synced_orders = []
        now = timezone.now()

        with transaction.atomic():
            snapshots = {s.question_order: s for s in attempt.question_snapshots.select_for_update().all()}
            for item in answers:
                if not isinstance(item, dict):
                    continue
                q_order = item.get("question_order")
                sel_opt = (item.get("selected_option") or "").strip().upper()
                if q_order in snapshots and sel_opt in ("", "A", "B", "C", "D"):
                    snap = snapshots[q_order]
                    snap.selected_option = sel_opt
                    snap.answered_at = now
                    snap.save(update_fields=["selected_option", "answered_at", "updated_at"])
                    synced_orders.append(q_order)

        return Response(
            {
                "status": "synced",
                "synced_count": len(synced_orders),
                "synced_orders": synced_orders,
            },
            status=status.HTTP_200_OK,
        )


class RecordIntegrityEventView(APIView):
    """
    Step 5: Record tab switch, full-screen toggle, reconnect integrity events.
    Enforces the tab switch limit (default 2 warnings; 3rd switch auto-submits).
    Supports event_id deduplication for network idempotency.
    """
    authentication_classes = [CandidateAssessmentAuthentication]
    permission_classes = [AllowAny]

    def post(self, request, attempt_id):
        serializer = IntegrityEventSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        ev_type = serializer.validated_data["event_type"]
        event_id = serializer.validated_data.get("event_id", "").strip()
        client_ts = serializer.validated_data.get("client_timestamp")
        metadata = serializer.validated_data.get("metadata", {})

        with transaction.atomic():
            attempt = (
                AssessmentAttempt.objects.select_for_update()
                .filter(id=attempt_id)
                .first()
            )
            if not attempt:
                return Response({"detail": "Attempt not found."}, status=status.HTTP_404_NOT_FOUND)

            if not verify_attempt_ownership(request, attempt):
                return Response(
                    {"detail": "Access forbidden: you do not own this attempt."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            allowed = (
                attempt.assessment.max_tab_switches_warning
                if attempt.assessment
                else (attempt.config.max_tab_switches_warning if attempt.config else 2)
            )
            auto_submit = (
                attempt.assessment.auto_submit_on_tab_limit
                if attempt.assessment
                else (attempt.config.auto_submit_on_tab_limit if attempt.config else True)
            )

            # If attempt is already in a terminal state, return current status
            if attempt.state in [
                AssessmentAttempt.State.SUBMITTED,
                AssessmentAttempt.State.TIMED_OUT,
                AssessmentAttempt.State.FLAGGED_FOR_REVIEW,
            ]:
                return Response(
                    {
                        "status": "already_finalized",
                        "event_type": ev_type,
                        "tab_switches": attempt.tab_switch_count,
                        "max_switches": allowed,
                        "remaining_switches": max(0, allowed - attempt.tab_switch_count),
                        "is_finalized": True,
                        "state": attempt.state,
                        "flag_reason": attempt.flag_reason,
                    },
                    status=status.HTTP_200_OK,
                )

            # Deduplication: Check if this event_id was already recorded
            if event_id and IntegrityEvent.objects.filter(attempt=attempt, event_id=event_id).exists():
                return Response(
                    {
                        "status": "duplicate_ignored",
                        "event_type": ev_type,
                        "tab_switches": attempt.tab_switch_count,
                        "max_switches": allowed,
                        "remaining_switches": max(0, allowed - attempt.tab_switch_count),
                        "is_finalized": False,
                        "state": attempt.state,
                        "flag_reason": attempt.flag_reason,
                    },
                    status=status.HTTP_200_OK,
                )

            is_consecutive_hidden = False
            if ev_type == IntegrityEvent.EventType.TAB_HIDDEN:
                last_vis = (
                    IntegrityEvent.objects.filter(
                        attempt=attempt,
                        event_type__in=[
                            IntegrityEvent.EventType.TAB_HIDDEN,
                            IntegrityEvent.EventType.TAB_VISIBLE,
                        ],
                    )
                    .order_by("-server_timestamp", "-id")
                    .first()
                )
                if last_vis and last_vis.event_type == IntegrityEvent.EventType.TAB_HIDDEN:
                    is_consecutive_hidden = True

                if not is_consecutive_hidden:
                    attempt.tab_switch_count += 1

                    if auto_submit and attempt.tab_switch_count > allowed:
                        attempt.is_flagged = True
                        attempt.flag_reason = (
                            f"TAB_SWITCH_LIMIT_EXCEEDED: Exceeded permitted tab switches "
                            f"({attempt.tab_switch_count} switches recorded, limit is {allowed})"
                        )

                    attempt.save(
                        update_fields=[
                            "tab_switch_count",
                            "is_flagged",
                            "flag_reason",
                            "updated_at",
                        ]
                    )

                    if auto_submit and attempt.tab_switch_count > allowed:
                        attempt = finalize_assessment_attempt(
                            attempt, final_state=AssessmentAttempt.State.FLAGGED_FOR_REVIEW
                        )

            elif ev_type == IntegrityEvent.EventType.FULLSCREEN_EXIT:
                attempt.fullscreen_exit_count += 1
                attempt.save(update_fields=["fullscreen_exit_count", "updated_at"])

            IntegrityEvent.objects.create(
                attempt=attempt,
                event_type=ev_type,
                event_id=event_id,
                client_timestamp=client_ts,
                metadata=metadata,
            )

            is_final = attempt.state in [
                AssessmentAttempt.State.SUBMITTED,
                AssessmentAttempt.State.TIMED_OUT,
                AssessmentAttempt.State.FLAGGED_FOR_REVIEW,
            ]

            return Response(
                {
                    "status": "recorded",
                    "event_type": ev_type,
                    "tab_switches": attempt.tab_switch_count,
                    "max_switches": allowed,
                    "remaining_switches": max(0, allowed - attempt.tab_switch_count),
                    "is_finalized": is_final,
                    "state": attempt.state,
                    "flag_reason": attempt.flag_reason,
                },
                status=status.HTTP_200_OK,
            )


class FinalizeAssessmentView(APIView):
    """
    Step 6: Finalize assessment and calculate scores. Strict ownership check.
    """
    authentication_classes = [CandidateAssessmentAuthentication, SessionAuthentication, BasicAuthentication]
    permission_classes = [AllowAny]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(AssessmentAttempt, id=attempt_id)
        if not verify_attempt_ownership(request, attempt):
            return Response({"detail": "Access forbidden: you do not own this attempt."}, status=status.HTTP_403_FORBIDDEN)

        final_state = AssessmentAttempt.State.SUBMITTED
        if attempt.is_expired():
            final_state = AssessmentAttempt.State.TIMED_OUT

        finalized_attempt = finalize_assessment_attempt(attempt, final_state=final_state)
        serializer = AssessmentResultSerializer(finalized_attempt, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class AssessmentResultView(APIView):
    """
    Step 7: View finalized result. Strict ownership check.
    """
    authentication_classes = [CandidateAssessmentAuthentication, SessionAuthentication, BasicAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, attempt_id):
        attempt = get_object_or_404(AssessmentAttempt, id=attempt_id)
        if not verify_attempt_ownership(request, attempt):
            return Response({"detail": "Access forbidden: you do not own this attempt."}, status=status.HTTP_403_FORBIDDEN)

        if attempt.state in [AssessmentAttempt.State.CREATED, AssessmentAttempt.State.IN_PROGRESS]:
            if attempt.is_expired():
                finalize_assessment_attempt(attempt, final_state=AssessmentAttempt.State.TIMED_OUT)
            else:
                return Response(
                    {"detail": "Assessment attempt is still in progress."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = AssessmentResultSerializer(attempt, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class QuestionBankSummaryView(APIView):
    """
    Admin-only operational view for Question Bank metrics.
    Provides accurate counts of active, inactive, aptitude, coding, and category breakdowns.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        total = QuestionBank.objects.count()
        active = QuestionBank.objects.filter(is_active=True).count()
        inactive = total - active
        aptitude_active = QuestionBank.objects.filter(section_type=QuestionBank.SectionType.APTITUDE, is_active=True).count()
        coding_active = QuestionBank.objects.filter(section_type=QuestionBank.SectionType.CODING, is_active=True).count()

        config = get_or_create_default_config()

        return Response({
            "total_questions": total,
            "active_questions": active,
            "inactive_questions": inactive,
            "aptitude_active": aptitude_active,
            "coding_active": coding_active,
            "aptitude_required": config.aptitude_count,
            "coding_required": config.coding_count,
            "is_sufficient": (aptitude_active >= config.aptitude_count and coding_active >= config.coding_count),
        })
