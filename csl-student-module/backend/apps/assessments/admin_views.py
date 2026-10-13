import csv
import io
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import (
    Candidate,
    College,
    Assessment,
    AssessmentAttempt,
    QuestionBank,
    AssessmentConfig,
    IntegrityEvent,
    AssessmentAuditLog,
)
from .admin_permissions import IsCSLAdminUser
from .admin_serializers import (
    AdminCollegeListSerializer,
    AdminCollegeDetailSerializer,
    AdminCollegeCreateUpdateSerializer,
    AdminAssessmentListSerializer,
    AdminAssessmentDetailSerializer,
    AdminAssessmentCreateUpdateSerializer,
    AdminAssessmentAuditLogSerializer,
    AdminCandidateSerializer,
    AdminCandidateDetailSerializer,
    AdminQuestionSerializer,
    AdminQuestionBulkUpdateSerializer,
    AdminAssessmentConfigSerializer,
    AdminLiveAttemptSerializer,
    AdminAttemptReviewSerializer,
    AdminResultSerializer,
    AdminIntegrityEventSerializer,
)
from django.http import HttpResponse
from .services import (
    prepare_assessment,
    open_assessment,
    close_assessment,
    archive_assessment,
    assign_colleges_to_assessment,
    assign_questions_to_assessment,
    remove_questions_from_assessment,
    release_assessment_results,
    unrelease_assessment_results,
    import_candidates_from_csv,
    log_assessment_audit,
)


class AdminMeView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request):
        user = request.user
        return Response({
            "email": user.email,
            "name": user.first_name or user.username or "Administrator",
            "role": getattr(user, "role", "ADMIN"),
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
        })


class AdminStatsView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request):
        colleges_count = College.objects.count()
        assessments_count = Assessment.objects.count()
        open_assessments_count = Assessment.objects.filter(status=Assessment.Status.OPEN).count()
        candidates_count = Candidate.objects.count()
        attempts_count = AssessmentAttempt.objects.count()
        in_progress_count = AssessmentAttempt.objects.filter(state=AssessmentAttempt.State.IN_PROGRESS).count()
        submitted_count = AssessmentAttempt.objects.filter(state=AssessmentAttempt.State.SUBMITTED).count()
        timed_out_count = AssessmentAttempt.objects.filter(state=AssessmentAttempt.State.TIMED_OUT).count()
        flagged_count = AssessmentAttempt.objects.filter(
            Q(state=AssessmentAttempt.State.FLAGGED_FOR_REVIEW) | Q(is_flagged=True)
        ).count()
        aptitude_count = QuestionBank.objects.filter(
            section_type=QuestionBank.SectionType.APTITUDE, is_active=True
        ).count()
        coding_count = QuestionBank.objects.filter(
            section_type=QuestionBank.SectionType.CODING, is_active=True
        ).count()
        total_questions = QuestionBank.objects.count()

        return Response({
            "colleges_count": colleges_count,
            "assessments_count": assessments_count,
            "open_assessments_count": open_assessments_count,
            "candidates_count": candidates_count,
            "attempts_count": attempts_count,
            "in_progress_count": in_progress_count,
            "submitted_count": submitted_count,
            "timed_out_count": timed_out_count,
            "flagged_count": flagged_count,
            "aptitude_questions_count": aptitude_count,
            "coding_questions_count": coding_count,
            "total_questions_count": total_questions,
        })


# ==============================================================================
# COLLEGES MODULE
# ==============================================================================

class AdminCollegeListView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request):
        queryset = College.objects.all().order_by("name")
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(code__icontains=search)
                | Q(location__icontains=search)
                | Q(contact_email__icontains=search)
            )

        is_active = request.query_params.get("is_active", "").strip()
        if is_active.lower() in ["true", "1"]:
            queryset = queryset.filter(is_active=True)
        elif is_active.lower() in ["false", "0"]:
            queryset = queryset.filter(is_active=False)

        serializer = AdminCollegeListSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AdminCollegeCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        college = serializer.save()
        log_assessment_audit(
            action=AssessmentAuditLog.Action.COLLEGE_CREATED,
            entity_type="COLLEGE",
            entity_id=str(college.id),
            user=request.user,
            details={"name": college.name, "code": college.code},
        )
        return Response(AdminCollegeListSerializer(college).data, status=status.HTTP_201_CREATED)


class AdminCollegeDetailView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request, pk):
        college = get_object_or_404(College, pk=pk)
        return Response(AdminCollegeDetailSerializer(college).data)

    def patch(self, request, pk):
        college = get_object_or_404(College, pk=pk)
        serializer = AdminCollegeCreateUpdateSerializer(college, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        updated_college = serializer.save()
        log_assessment_audit(
            action=AssessmentAuditLog.Action.COLLEGE_UPDATED,
            entity_type="COLLEGE",
            entity_id=str(college.id),
            user=request.user,
            details={"updated_fields": list(request.data.keys())},
        )
        return Response(AdminCollegeDetailSerializer(updated_college).data)


class AdminCollegeToggleStatusView(APIView):
    permission_classes = [IsCSLAdminUser]

    def post(self, request, pk):
        college = get_object_or_404(College, pk=pk)
        college.is_active = not college.is_active
        college.save(update_fields=["is_active", "updated_at"])

        log_assessment_audit(
            action=AssessmentAuditLog.Action.COLLEGE_STATUS_TOGGLED,
            entity_type="COLLEGE",
            entity_id=str(college.id),
            user=request.user,
            details={"is_active": college.is_active},
        )
        return Response({
            "id": college.id,
            "is_active": college.is_active,
            "message": f"College '{college.name}' is now {'active' if college.is_active else 'inactive'}.",
        })


class AdminCollegeImportCandidatesView(APIView):
    permission_classes = [IsCSLAdminUser]

    def post(self, request, pk):
        college = get_object_or_404(College, pk=pk)

        file_obj = request.FILES.get("file")
        csv_text = request.data.get("csv_content", "")

        if file_obj:
            try:
                decoded = file_obj.read().decode("utf-8")
                csv_data = decoded
            except Exception as e:
                return Response({"detail": f"Failed to read CSV file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        elif csv_text:
            csv_data = csv_text
        else:
            return Response({"detail": "Please provide a CSV file or csv_content string."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = import_candidates_from_csv(college, csv_data, user=request.user)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            detail = getattr(e, "detail", str(e))
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


# ==============================================================================
# ASSESSMENTS MODULE
# ==============================================================================

class AdminAssessmentListView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request):
        queryset = Assessment.objects.prefetch_related("eligible_colleges", "attempts").all().order_by("-created_at")
        status_param = request.query_params.get("status", "").strip().upper()
        if status_param in Assessment.Status.values:
            queryset = queryset.filter(status=status_param)

        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) | Q(title__icontains=search) | Q(description__icontains=search)
            )

        serializer = AdminAssessmentListSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AdminAssessmentCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        college_ids = serializer.validated_data.pop("eligible_college_ids", [])

        with transaction.atomic():
            assessment = Assessment.objects.create(
                **serializer.validated_data,
                status=Assessment.Status.DRAFT,
                created_by=request.user,
            )
            if college_ids:
                colleges = College.objects.filter(id__in=college_ids)
                assessment.eligible_colleges.set(colleges)

            log_assessment_audit(
                action=AssessmentAuditLog.Action.ASSESSMENT_CREATED,
                entity_type="ASSESSMENT",
                entity_id=str(assessment.id),
                user=request.user,
                details={"code": assessment.code, "title": assessment.title},
            )

        return Response(AdminAssessmentDetailSerializer(assessment).data, status=status.HTTP_201_CREATED)


class AdminAssessmentDetailView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request, pk):
        assessment = get_object_or_404(
            Assessment.objects.prefetch_related("eligible_colleges", "attempts"),
            pk=pk,
        )
        return Response(AdminAssessmentDetailSerializer(assessment).data)

    def patch(self, request, pk):
        assessment = get_object_or_404(Assessment, pk=pk)
        serializer = AdminAssessmentCreateUpdateSerializer(assessment, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        college_ids = serializer.validated_data.pop("eligible_college_ids", None)

        with transaction.atomic():
            updated = serializer.save()
            if college_ids is not None:
                colleges = College.objects.filter(id__in=college_ids)
                updated.eligible_colleges.set(colleges)

            log_assessment_audit(
                action=AssessmentAuditLog.Action.ASSESSMENT_UPDATED,
                entity_type="ASSESSMENT",
                entity_id=str(assessment.id),
                user=request.user,
                details={"updated_fields": list(request.data.keys())},
            )

        return Response(AdminAssessmentDetailSerializer(updated).data)


class AdminAssessmentPrepareView(APIView):
    permission_classes = [IsCSLAdminUser]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, pk=pk)
        try:
            assessment = prepare_assessment(assessment, user=request.user)
            return Response({
                "message": f"Assessment '{assessment.title}' verified and marked READY.",
                "status": assessment.status,
            })
        except Exception as e:
            detail = getattr(e, "detail", str(e))
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


class AdminAssessmentOpenView(APIView):
    permission_classes = [IsCSLAdminUser]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, pk=pk)
        try:
            assessment = open_assessment(assessment, user=request.user)
            return Response({
                "message": f"Assessment '{assessment.title}' is now OPEN and accepting candidate attempts.",
                "status": assessment.status,
                "opened_at": assessment.opened_at,
            })
        except Exception as e:
            detail = getattr(e, "detail", str(e))
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


class AdminAssessmentCloseView(APIView):
    permission_classes = [IsCSLAdminUser]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, pk=pk)
        close_policy = request.data.get("close_policy")
        try:
            assessment = close_assessment(assessment, user=request.user, close_policy=close_policy)
            return Response({
                "message": f"Assessment '{assessment.title}' is now CLOSED.",
                "status": assessment.status,
                "closed_at": assessment.closed_at,
                "close_policy": assessment.close_policy,
            })
        except Exception as e:
            detail = getattr(e, "detail", str(e))
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


class AdminAssessmentArchiveView(APIView):
    permission_classes = [IsCSLAdminUser]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, pk=pk)
        try:
            assessment = archive_assessment(assessment, user=request.user)
            return Response({
                "message": f"Assessment '{assessment.title}' is now ARCHIVED.",
                "status": assessment.status,
            })
        except Exception as e:
            detail = getattr(e, "detail", str(e))
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


class AdminAssessmentAssignCollegesView(APIView):
    permission_classes = [IsCSLAdminUser]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, pk=pk)
        college_ids = request.data.get("college_ids", [])
        if not isinstance(college_ids, list):
            return Response({"detail": "college_ids must be a list of IDs."}, status=status.HTTP_400_BAD_REQUEST)

        updated = assign_colleges_to_assessment(assessment, college_ids, user=request.user)
        return Response({
            "message": f"Assigned {updated.eligible_colleges.count()} institution(s) to '{assessment.title}'.",
            "eligible_colleges": [{"id": c.id, "name": c.name, "code": c.code} for c in updated.eligible_colleges.all()],
        })


class AdminAssessmentAuditLogsView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request, pk):
        logs = AssessmentAuditLog.objects.filter(
            entity_type="ASSESSMENT", entity_id=str(pk)
        ).order_by("-timestamp")[:100]
        return Response(AdminAssessmentAuditLogSerializer(logs, many=True).data)


class AdminAssessmentAssignQuestionsView(APIView):
    permission_classes = [IsCSLAdminUser]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, pk=pk)
        action = request.data.get("action", "add")  # 'add', 'remove', 'set', 'add_all'
        question_ids = request.data.get("question_ids", [])

        if action == "add_all":
            section = request.data.get("section_type")
            category = request.data.get("category")
            assessment_type = request.data.get("assessment_type")
            qs = QuestionBank.objects.filter(is_active=True)
            if section:
                qs = qs.filter(section_type=section)
            if category:
                qs = qs.filter(category=category)
            if assessment_type:
                qs = qs.filter(assessment_type=assessment_type)
            assessment.questions.add(*qs)
        elif action == "remove":
            remove_questions_from_assessment(assessment, question_ids, user=request.user)
        elif action == "set":
            questions = list(QuestionBank.objects.filter(id__in=question_ids))
            assessment.questions.set(questions)
        else:  # add
            assign_questions_to_assessment(assessment, question_ids, user=request.user)

        apt_count = assessment.questions.filter(section_type=QuestionBank.SectionType.APTITUDE, is_active=True).count()
        cod_count = assessment.questions.filter(section_type=QuestionBank.SectionType.CODING, is_active=True).count()
        return Response({
            "message": f"Updated question pool for '{assessment.title}'.",
            "total_questions": assessment.questions.count(),
            "aptitude_count": apt_count,
            "coding_count": cod_count,
            "is_sufficient": (apt_count >= assessment.aptitude_count and cod_count >= assessment.coding_count),
        })


class AdminAssessmentReleaseResultsView(APIView):
    permission_classes = [IsCSLAdminUser]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, pk=pk)
        release = request.data.get("release", True)
        if release:
            assessment = release_assessment_results(assessment, user=request.user)
            msg = f"Results for '{assessment.title}' are now officially RELEASED to candidates."
        else:
            assessment = unrelease_assessment_results(assessment, user=request.user)
            msg = f"Results for '{assessment.title}' are now WITHHELD from candidates."

        return Response({
            "message": msg,
            "is_results_released": assessment.is_results_released,
            "results_released_at": assessment.results_released_at,
        })


# ==============================================================================
# CANDIDATES MODULE
# ==============================================================================

class AdminCandidateListView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request):
        queryset = Candidate.objects.select_related("college_ref").all().order_by("-created_at")

        college_id = request.query_params.get("college_id", "").strip()
        if college_id:
            queryset = queryset.filter(college_ref_id=college_id)

        is_active = request.query_params.get("is_active", "").strip()
        if is_active.lower() in ["true", "1"]:
            queryset = queryset.filter(is_active=True)
        elif is_active.lower() in ["false", "0"]:
            queryset = queryset.filter(is_active=False)

        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(register_number__icontains=search)
                | Q(college__icontains=search)
                | Q(email__icontains=search)
            )

        serializer = AdminCandidateSerializer(queryset[:200], many=True)
        return Response(serializer.data)


class AdminCandidateExportCSVView(APIView):
    """
    Exports filtered candidate records to CSV with formula injection sanitization.
    """
    permission_classes = [IsCSLAdminUser]

    def get(self, request):
        queryset = (
            Candidate.objects.select_related("college_ref")
            .prefetch_related("college_ref__assigned_assessments")
            .all()
            .order_by("-created_at")
        )

        college_id = request.query_params.get("college_id", "").strip()
        if college_id:
            queryset = queryset.filter(college_ref_id=college_id)

        is_active = request.query_params.get("is_active", "").strip()
        if is_active.lower() in ["true", "1"]:
            queryset = queryset.filter(is_active=True)
        elif is_active.lower() in ["false", "0"]:
            queryset = queryset.filter(is_active=False)

        department = request.query_params.get("department", "").strip()
        if department:
            queryset = queryset.filter(department__icontains=department)

        year_of_study = request.query_params.get("year_of_study", "").strip()
        if year_of_study:
            queryset = queryset.filter(year_of_study__iexact=year_of_study)

        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(register_number__icontains=search)
                | Q(college__icontains=search)
                | Q(email__icontains=search)
            )

        timestamp_str = timezone.now().strftime("%Y%m%d_%H%M%S")
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="csl_candidates_{timestamp_str}.csv"'

        def sanitize_cell(val):
            """Protect against spreadsheet formula injection."""
            if val is None:
                return ""
            s = str(val).strip()
            if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
                return f"'{s}"
            return s

        writer = csv.writer(response)
        writer.writerow([
            "Candidate Name",
            "Register Number",
            "College Name",
            "College Code",
            "Email Address",
            "Mobile Phone Number",
            "Department / Course",
            "Year of Study",
            "Status",
            "Registered Timestamp",
            "Assigned Assessments",
        ])

        for cand in queryset.iterator():
            college_code = cand.college_ref.code if cand.college_ref else ""
            college_name = cand.college_ref.name if cand.college_ref else cand.college
            assigned_codes = []
            if cand.college_ref:
                assigned_codes = [a.code for a in cand.college_ref.assigned_assessments.all()]

            writer.writerow([
                sanitize_cell(cand.full_name),
                sanitize_cell(cand.register_number),
                sanitize_cell(college_name),
                sanitize_cell(college_code),
                sanitize_cell(cand.email),
                sanitize_cell(cand.phone_number),
                sanitize_cell(cand.department),
                sanitize_cell(cand.year_of_study),
                "Active" if cand.is_active else "Deactivated",
                cand.created_at.strftime("%Y-%m-%d %H:%M:%S") if cand.created_at else "",
                sanitize_cell(", ".join(assigned_codes)),
            ])

        return response


class AdminCandidateDetailView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request, candidate_id):
        candidate = get_object_or_404(Candidate.objects.select_related("college_ref"), id=candidate_id)
        serializer = AdminCandidateDetailSerializer(candidate)
        return Response(serializer.data)


class AdminCandidateToggleStatusView(APIView):
    permission_classes = [IsCSLAdminUser]

    def post(self, request, candidate_id):
        candidate = get_object_or_404(Candidate, id=candidate_id)
        candidate.is_active = not candidate.is_active
        candidate.save(update_fields=["is_active", "updated_at"])

        return Response({
            "id": str(candidate.id),
            "is_active": candidate.is_active,
            "message": f"Candidate '{candidate.full_name}' is now {'active' if candidate.is_active else 'deactivated'}.",
        })


# ==============================================================================
# QUESTION BANK MODULE
# ==============================================================================

class AdminQuestionListView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request):
        queryset = QuestionBank.objects.all().order_by("-id").prefetch_related("assigned_assessments")
        section = request.query_params.get("section_type", "").strip().upper()
        if section in [QuestionBank.SectionType.APTITUDE, QuestionBank.SectionType.CODING]:
            queryset = queryset.filter(section_type=section)

        category = request.query_params.get("category", "").strip()
        if category:
            queryset = queryset.filter(category__icontains=category)

        difficulty = request.query_params.get("difficulty", "").strip().upper()
        if difficulty in ["EASY", "MEDIUM", "HARD"]:
            queryset = queryset.filter(difficulty=difficulty)

        is_active = request.query_params.get("is_active", "").strip()
        if is_active.lower() in ["true", "1"]:
            queryset = queryset.filter(is_active=True)
        elif is_active.lower() in ["false", "0"]:
            queryset = queryset.filter(is_active=False)

        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(prompt__icontains=search) | Q(category__icontains=search)
            )

        assessment_id = request.query_params.get("assessment_id", "").strip()
        if assessment_id:
            try:
                uuid.UUID(str(assessment_id))
                queryset = queryset.filter(assigned_assessments__id=assessment_id)
            except (ValueError, TypeError):
                queryset = queryset.none()

        assessment_type = request.query_params.get("assessment_type", "").strip()
        if assessment_type:
            queryset = queryset.filter(assessment_type__iexact=assessment_type)

        serializer = AdminQuestionSerializer(queryset[:500], many=True)
        return Response(serializer.data)

    def post(self, request):
        assessment_id = request.data.get("assessment_id")
        target_assessment = None
        if assessment_id:
            try:
                target_assessment = Assessment.objects.get(id=assessment_id)
            except (Assessment.DoesNotExist, ValueError):
                return Response(
                    {"assessment_id": [f"Selected assessment '{assessment_id}' does not exist or is invalid."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif "assessment_id" in request.data:
            return Response(
                {"assessment_id": ["Target assessment pool is required. Please select an assessment."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AdminQuestionSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                question = serializer.save()
                if target_assessment:
                    target_assessment.questions.add(question)
                    log_assessment_audit(
                        action=AssessmentAuditLog.Action.QUESTIONS_ASSIGNED,
                        entity_type="ASSESSMENT",
                        entity_id=str(target_assessment.id),
                        user=request.user,
                        details={
                            "question_id": question.id,
                            "prompt": question.prompt[:80],
                            "source": "MANUAL_CREATE",
                            "total_pool_count": target_assessment.questions.count(),
                        },
                    )
            return Response(AdminQuestionSerializer(question).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminQuestionDetailView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request, pk):
        question = get_object_or_404(QuestionBank.objects.prefetch_related("assigned_assessments"), pk=pk)
        return Response(AdminQuestionSerializer(question).data)

    def put(self, request, pk):
        question = get_object_or_404(QuestionBank.objects.prefetch_related("assigned_assessments"), pk=pk)
        target_assessment = None
        update_assessment = False

        if "assessment_id" in request.data:
            assessment_id = request.data.get("assessment_id")
            if assessment_id:
                try:
                    target_assessment = Assessment.objects.get(id=assessment_id)
                    update_assessment = True
                except (Assessment.DoesNotExist, ValueError):
                    return Response(
                        {"assessment_id": [f"Selected assessment '{assessment_id}' does not exist or is invalid."]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {"assessment_id": ["Target assessment pool cannot be empty."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = AdminQuestionSerializer(question, data=request.data, partial=True)
        if serializer.is_valid():
            with transaction.atomic():
                question = serializer.save()
                if update_assessment and target_assessment:
                    question.assigned_assessments.set([target_assessment])
                    log_assessment_audit(
                        action=AssessmentAuditLog.Action.QUESTIONS_ASSIGNED,
                        entity_type="ASSESSMENT",
                        entity_id=str(target_assessment.id),
                        user=request.user,
                        details={
                            "question_id": question.id,
                            "prompt": question.prompt[:80],
                            "source": "POOL_REASSIGNMENT",
                            "total_pool_count": target_assessment.questions.count(),
                        },
                    )
            return Response(AdminQuestionSerializer(question).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        return self.put(request, pk)

    def delete(self, request, pk):
        question = get_object_or_404(QuestionBank, pk=pk)
        question.is_active = False
        question.save(update_fields=["is_active"])
        return Response({"message": "Question deactivated."})


class AdminQuestionToggleView(APIView):
    permission_classes = [IsCSLAdminUser]

    def post(self, request, pk):
        question = get_object_or_404(QuestionBank, pk=pk)
        question.is_active = not question.is_active
        question.save(update_fields=["is_active"])
        return Response({
            "id": question.id,
            "is_active": question.is_active,
            "message": f"Question {'activated' if question.is_active else 'deactivated'}."
        })


class AdminQuestionImportCSVView(APIView):
    permission_classes = [IsCSLAdminUser]

    def post(self, request):
        assessment_id = request.data.get("assessment_id")
        if not assessment_id:
            return Response(
                {"assessment_id": ["Target assessment is required. Please select an assessment for CSV question import."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            assessment = Assessment.objects.get(id=assessment_id)
        except (Assessment.DoesNotExist, ValueError):
            return Response(
                {"assessment_id": [f"Selected assessment '{assessment_id}' does not exist or is invalid."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        file_obj = request.FILES.get("file")
        csv_text = request.data.get("csv_content", "")

        if file_obj:
            try:
                decoded = file_obj.read().decode("utf-8")
                io_string = io.StringIO(decoded)
            except Exception as e:
                return Response({"detail": f"Failed to read CSV file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        elif csv_text:
            io_string = io.StringIO(csv_text)
        else:
            return Response({"detail": "Please supply a CSV file or csv_content string."}, status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(io_string)
        required_fields = ["prompt", "section_type", "category", "option_a", "option_b", "option_c", "option_d", "correct_option"]

        if not reader.fieldnames:
            return Response({"detail": "CSV file is empty or missing headers."}, status=status.HTTP_400_BAD_REQUEST)

        created_questions = []
        errors = []

        with transaction.atomic():
            for row_idx, row in enumerate(reader, start=2):
                missing = [f for f in required_fields if not row.get(f)]
                if missing:
                    errors.append(f"Row {row_idx}: Missing required fields: {', '.join(missing)}")
                    continue

                sec = row["section_type"].strip().upper()
                if sec not in [QuestionBank.SectionType.APTITUDE, QuestionBank.SectionType.CODING]:
                    errors.append(f"Row {row_idx}: Invalid section_type '{sec}'. Must be APTITUDE or CODING.")
                    continue

                correct = row["correct_option"].strip().upper()
                if correct not in ["A", "B", "C", "D"]:
                    errors.append(f"Row {row_idx}: Invalid correct_option '{correct}'. Must be A, B, C, or D.")
                    continue

                diff = row.get("difficulty", "MEDIUM").strip().upper()
                if diff not in ["EASY", "MEDIUM", "HARD"]:
                    diff = "MEDIUM"

                try:
                    q = QuestionBank.objects.create(
                        prompt=row["prompt"].strip(),
                        section_type=sec,
                        category=row["category"].strip(),
                        difficulty=diff,
                        option_a=row["option_a"].strip(),
                        option_b=row["option_b"].strip(),
                        option_c=row["option_c"].strip(),
                        option_d=row["option_d"].strip(),
                        correct_option=correct,
                        explanation=row.get("explanation", "").strip(),
                        is_active=True,
                    )
                    created_questions.append(q)
                except Exception as e:
                    errors.append(f"Row {row_idx}: Database save error: {str(e)}")

            if created_questions:
                assessment.questions.add(*created_questions)
                log_assessment_audit(
                    action=AssessmentAuditLog.Action.QUESTIONS_ASSIGNED,
                    entity_type="ASSESSMENT",
                    entity_id=str(assessment.id),
                    user=request.user,
                    details={
                        "imported_count": len(created_questions),
                        "source": "CSV_IMPORT",
                        "total_pool_count": assessment.questions.count(),
                    },
                )

        return Response({
            "success_count": len(created_questions),
            "error_count": len(errors),
            "errors": errors[:50],
            "assessment_id": str(assessment.id),
            "assessment_title": assessment.title,
            "total_pool_count": assessment.questions.count(),
        })


class AdminQuestionBulkUpdateView(APIView):
    permission_classes = [IsCSLAdminUser]

    def post(self, request):
        serializer = AdminQuestionBulkUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        ids = serializer.validated_data["ids"]
        updates = {}
        for field in ["section_type", "category", "difficulty", "is_active"]:
            if field in serializer.validated_data:
                updates[field] = serializer.validated_data[field]

        if not updates:
            return Response({"detail": "No valid fields provided for bulk update."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            matched_qs = QuestionBank.objects.filter(id__in=ids)
            updated_count = matched_qs.update(**updates)

        return Response({
            "updated_count": updated_count,
            "message": f"Successfully updated {updated_count} question(s).",
        })


class AdminConfigView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request):
        config = AssessmentConfig.objects.filter(is_active=True).first()
        if not config:
            config = AssessmentConfig.objects.create()
        return Response(AdminAssessmentConfigSerializer(config).data)

    def put(self, request):
        config = AssessmentConfig.objects.filter(is_active=True).first()
        if not config:
            config = AssessmentConfig.objects.create()

        serializer = AdminAssessmentConfigSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==============================================================================
# LIVE ATTEMPTS & SESSIONS
# ==============================================================================

class AdminLiveAttemptsView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request):
        queryset = AssessmentAttempt.objects.select_related("candidate__college_ref", "assessment").prefetch_related(
            "question_snapshots", "integrity_events"
        ).all().order_by("-created_at")

        assessment_id = request.query_params.get("assessment_id", "").strip()
        if assessment_id:
            queryset = queryset.filter(assessment_id=assessment_id)

        college_id = request.query_params.get("college_id", "").strip()
        if college_id:
            queryset = queryset.filter(candidate__college_ref_id=college_id)

        state = request.query_params.get("state", "").strip()
        if state:
            queryset = queryset.filter(state=state)

        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(candidate__full_name__icontains=search)
                | Q(candidate__register_number__icontains=search)
                | Q(candidate__college__icontains=search)
            )

        serializer = AdminLiveAttemptSerializer(queryset[:150], many=True)
        return Response(serializer.data)


class AdminAttemptReviewView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request, attempt_id):
        attempt = get_object_or_404(
            AssessmentAttempt.objects.select_related("candidate__college_ref", "assessment").prefetch_related(
                "question_snapshots__question", "integrity_events"
            ),
            id=attempt_id,
        )
        serializer = AdminAttemptReviewSerializer(attempt)
        return Response(serializer.data)

    def post(self, request, attempt_id):
        attempt = get_object_or_404(AssessmentAttempt, id=attempt_id)
        action = request.data.get("action", "").strip().upper()
        notes = request.data.get("notes", "").strip()

        if action == "CLEAR_FLAG":
            attempt.is_flagged = False
            if notes:
                attempt.flag_reason = f"{attempt.flag_reason}\n[Admin Cleared]: {notes}".strip()
            attempt.save(update_fields=["is_flagged", "flag_reason"])
            return Response({"message": "Attempt flag cleared."})
        elif action == "FLAG":
            attempt.is_flagged = True
            if notes:
                attempt.flag_reason = f"{attempt.flag_reason}\n[Admin Flagged]: {notes}".strip()
            attempt.save(update_fields=["is_flagged", "flag_reason"])
            return Response({"message": "Attempt flagged for review."})

        return Response({"detail": "Invalid action. Use CLEAR_FLAG or FLAG."}, status=status.HTTP_400_BAD_REQUEST)


# ==============================================================================
# RESULTS & INTEGRITY EVENTS
# ==============================================================================

class AdminResultsView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request):
        queryset = AssessmentAttempt.objects.filter(
            state__in=[
                AssessmentAttempt.State.SUBMITTED,
                AssessmentAttempt.State.TIMED_OUT,
                AssessmentAttempt.State.FLAGGED_FOR_REVIEW,
            ]
        ).select_related("candidate__college_ref", "assessment").order_by("-submitted_at", "-created_at")

        assessment_id = request.query_params.get("assessment_id", "").strip()
        if assessment_id:
            queryset = queryset.filter(assessment_id=assessment_id)

        college_id = request.query_params.get("college_id", "").strip()
        if college_id:
            queryset = queryset.filter(candidate__college_ref_id=college_id)

        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(candidate__full_name__icontains=search)
                | Q(candidate__register_number__icontains=search)
                | Q(candidate__college__icontains=search)
            )

        serializer = AdminResultSerializer(queryset[:150], many=True)
        return Response(serializer.data)


class AdminIntegrityEventsView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request):
        queryset = IntegrityEvent.objects.select_related(
            "attempt__candidate__college_ref", "attempt__assessment", "reviewed_by"
        ).all().order_by("-server_timestamp")

        event_type = request.query_params.get("event_type", "").strip()
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        is_reviewed = request.query_params.get("is_reviewed", "").strip()
        if is_reviewed.lower() in ["true", "1"]:
            queryset = queryset.filter(is_reviewed=True)
        elif is_reviewed.lower() in ["false", "0"]:
            queryset = queryset.filter(is_reviewed=False)

        attempt_id = request.query_params.get("attempt_id", "").strip()
        if attempt_id:
            queryset = queryset.filter(attempt_id=attempt_id)

        assessment_id = request.query_params.get("assessment_id", "").strip()
        if assessment_id:
            queryset = queryset.filter(attempt__assessment_id=assessment_id)

        college_id = request.query_params.get("college_id", "").strip()
        if college_id:
            queryset = queryset.filter(attempt__candidate__college_ref_id=college_id)

        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(attempt__candidate__full_name__icontains=search)
                | Q(attempt__candidate__register_number__icontains=search)
                | Q(attempt__candidate__college__icontains=search)
                | Q(event_id__icontains=search)
                | Q(review_notes__icontains=search)
            )

        serializer = AdminIntegrityEventSerializer(queryset[:200], many=True)
        return Response(serializer.data)


class AdminIntegrityEventReviewActionView(APIView):
    permission_classes = [IsCSLAdminUser]

    def post(self, request, pk):
        event = get_object_or_404(
            IntegrityEvent.objects.select_related("attempt__candidate", "reviewed_by"),
            pk=pk,
        )
        is_reviewed = request.data.get("is_reviewed", True)
        if isinstance(is_reviewed, str):
            is_reviewed = is_reviewed.lower() in ["true", "1", "yes"]
        review_notes = str(request.data.get("review_notes", "")).strip()

        event.is_reviewed = bool(is_reviewed)
        event.review_notes = review_notes
        event.reviewed_by = request.user
        event.reviewed_at = timezone.now() if event.is_reviewed else None
        event.save(update_fields=["is_reviewed", "review_notes", "reviewed_by", "reviewed_at"])

        serializer = AdminIntegrityEventSerializer(event)
        return Response({
            "event": serializer.data,
            "message": "Integrity event review status updated successfully.",
        })


class AdminGlobalAuditLogsView(APIView):
    permission_classes = [IsCSLAdminUser]

    def get(self, request):
        logs = AssessmentAuditLog.objects.all().order_by("-timestamp")[:100]
        return Response(AdminAssessmentAuditLogSerializer(logs, many=True).data)
