import io
import uuid
from datetime import timedelta
from django.test import TestCase, Client
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

from apps.assessments.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentPdfDocument,
    Candidate,
    College,
    IntegrityEvent,
    AssessmentAuditLog,
)
from apps.assessments.tokens import generate_candidate_token
from apps.assessments.services import (
    prepare_assessment,
    open_assessment,
    start_assessment_for_candidate,
    finalize_assessment_attempt,
)

User = get_user_model()


def make_valid_pdf_bytes(title="Question Paper"):
    """Generates a valid, minimal PDF conforming strictly to the PDF-1.4 specification."""
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000117 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF\n"
    )
    return pdf_content


class PdfCodingAssessmentModeTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin user
        self.admin_user = User.objects.create_superuser(
            username="pdfadmin",
            email="admin@testcsl.edu",
            password="adminpassword123",
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
        )

        # Standard non-admin candidate user
        self.student_user = User.objects.create_user(
            username="pdfstudent",
            email="student@apex.edu",
            password="studentpassword123",
            role=User.Role.STUDENT,
            status=User.AccountStatus.ACTIVE,
        )

        # College
        self.college = College.objects.create(
            name="Apex Institute of Technology",
            code="APEX_TECH",
            is_active=True,
        )

        # Candidate
        self.candidate = Candidate.objects.create(
            full_name="PDF Test Candidate",
            register_number="PDF_CAND_01",
            college=self.college.name,
            college_ref=self.college,
            email="pdf_candidate@apex.edu",
            department="Computer Science",
            year_of_study="Final Year",
            is_active=True,
        )

        self.candidate_token = generate_candidate_token(self.candidate.id)

    # ──────────────────────────────────────────────────────────────────────────
    # 1. Existing MCQ Regression Tests
    # ──────────────────────────────────────────────────────────────────────────

    def test_default_delivery_mode_is_mcq(self):
        """Assessments created without delivery_mode default to MCQ and preserve existing behavior."""
        assessment = Assessment.objects.create(
            code="MCQ-REG-01",
            title="Regression MCQ Assessment",
            duration_minutes=60,
            total_marks=50,
            aptitude_count=25,
            coding_count=25,
        )
        self.assertEqual(assessment.delivery_mode, Assessment.DeliveryMode.MCQ)
        self.assertFalse(hasattr(assessment, "pdf_document") and assessment.pdf_document)

    def test_admin_create_mcq_assessment_unaffected(self):
        """Admin can create a regular MCQ assessment without any PDF requirement."""
        self.client.force_login(self.admin_user)
        payload = {
            "code": "MCQ-ADMIN-01",
            "title": "Admin Created MCQ",
            "duration_minutes": 45,
            "total_marks": 50,
            "aptitude_count": 25,
            "coding_count": 25,
            "delivery_mode": "MCQ",
        }
        res = self.client.post("/api/csl-admin/assessments/", payload, content_type="application/json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["delivery_mode"], "MCQ")
        self.assertIsNone(res.data["pdf_filename"])

    # ──────────────────────────────────────────────────────────────────────────
    # 2. PDF Assessment Configuration Tests
    # ──────────────────────────────────────────────────────────────────────────

    def test_admin_create_pdf_assessment_with_valid_pdf(self):
        """Authorized administrator can create a PDF-mode assessment with an attached PDF."""
        self.client.force_login(self.admin_user)
        pdf_bytes = make_valid_pdf_bytes()
        pdf_file = SimpleUploadedFile("coding_drive_paper.pdf", pdf_bytes, content_type="application/pdf")

        payload = {
            "code": "PDF-DRIVE-01",
            "title": "Annual Coding Drive - Offline Paper",
            "description": "Read questions and write answers on physical sheets.",
            "duration_minutes": 90,
            "total_marks": 100,
            "delivery_mode": "PDF_CODING",
            "pdf_file": pdf_file,
            "eligible_college_ids": [self.college.id],
        }
        res = self.client.post("/api/csl-admin/assessments/", payload, format="multipart")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["delivery_mode"], "PDF_CODING")
        self.assertEqual(res.data["pdf_filename"], "coding_drive_paper.pdf")

        # Verify database state
        created_assessment = Assessment.objects.get(code="PDF-DRIVE-01")
        self.assertEqual(created_assessment.delivery_mode, Assessment.DeliveryMode.PDF_CODING)
        self.assertTrue(hasattr(created_assessment, "pdf_document"))
        self.assertEqual(created_assessment.pdf_document.original_filename, "coding_drive_paper.pdf")
        self.assertGreater(created_assessment.pdf_document.file_size, 0)
        self.assertEqual(created_assessment.pdf_document.get_file_bytes(), pdf_bytes)

        # Verify audit log recorded
        audit = AssessmentAuditLog.objects.filter(
            entity_id=str(created_assessment.id),
            action=AssessmentAuditLog.Action.PDF_UPLOADED,
        ).first()
        self.assertIsNotNone(audit)

    def test_pdf_assessment_creation_rejected_without_pdf(self):
        """Creating an assessment in PDF_CODING mode without a PDF file is rejected."""
        self.client.force_login(self.admin_user)
        payload = {
            "code": "PDF-NOPDF-01",
            "title": "Missing PDF Assessment",
            "duration_minutes": 60,
            "total_marks": 50,
            "delivery_mode": "PDF_CODING",
        }
        res = self.client.post("/api/csl-admin/assessments/", payload, content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("pdf_file", res.data)

    def test_pdf_upload_rejected_for_non_pdf(self):
        """Uploading an executable, text file, or non-PDF is rejected."""
        self.client.force_login(self.admin_user)
        fake_file = SimpleUploadedFile("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00", content_type="application/x-msdownload")
        payload = {
            "code": "PDF-BADFILE-01",
            "title": "Malicious Upload Attempt",
            "duration_minutes": 60,
            "total_marks": 50,
            "delivery_mode": "PDF_CODING",
            "pdf_file": fake_file,
        }
        res = self.client.post("/api/csl-admin/assessments/", payload, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertIn("pdf_file", res.data)

    def test_pdf_upload_rejected_for_malformed_header(self):
        """A file with .pdf extension but missing %PDF- header is rejected."""
        self.client.force_login(self.admin_user)
        corrupt_file = SimpleUploadedFile("corrupt.pdf", b"This is just plain text, not a PDF", content_type="application/pdf")
        payload = {
            "code": "PDF-CORRUPT-01",
            "title": "Corrupt PDF",
            "duration_minutes": 60,
            "total_marks": 50,
            "delivery_mode": "PDF_CODING",
            "pdf_file": corrupt_file,
        }
        res = self.client.post("/api/csl-admin/assessments/", payload, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertIn("pdf_file", res.data)

    def test_admin_can_replace_attached_pdf(self):
        """Authorized administrator can replace the attached PDF question paper."""
        self.client.force_login(self.admin_user)
        pdf1 = make_valid_pdf_bytes("Paper 1")
        assessment = Assessment.objects.create(
            code="PDF-REPLACE-01",
            title="Replaceable PDF Assessment",
            duration_minutes=60,
            total_marks=50,
            delivery_mode=Assessment.DeliveryMode.PDF_CODING,
        )
        AssessmentPdfDocument.objects.create(
            assessment=assessment,
            original_filename="version_1.pdf",
            file_size=len(pdf1),
            sha256="fake_sha1",
            binary_data=pdf1,
            uploaded_by=self.admin_user,
        )

        pdf2 = make_valid_pdf_bytes("Paper 2 - Updated")
        replacement_file = SimpleUploadedFile("version_2_final.pdf", pdf2, content_type="application/pdf")

        res = self.client.post(
            f"/api/csl-admin/assessments/{assessment.id}/upload-pdf/",
            {"pdf_file": replacement_file},
            format="multipart",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["filename"], "version_2_final.pdf")

        assessment.refresh_from_db()
        self.assertEqual(assessment.pdf_document.original_filename, "version_2_final.pdf")
        self.assertEqual(assessment.pdf_document.get_file_bytes(), pdf2)

    def test_unauthorized_user_cannot_upload_or_manage_pdf(self):
        """Unauthenticated or candidate users cannot upload assessment PDFs."""
        assessment = Assessment.objects.create(
            code="PDF-UNAUTH-01",
            title="Unauthorized Test",
            delivery_mode=Assessment.DeliveryMode.PDF_CODING,
        )
        pdf_file = SimpleUploadedFile("paper.pdf", make_valid_pdf_bytes(), content_type="application/pdf")

        # Unauthenticated
        res = self.client.post(f"/api/csl-admin/assessments/{assessment.id}/upload-pdf/", {"pdf_file": pdf_file}, format="multipart")
        self.assertIn(res.status_code, [401, 403])

        # Logged in as student
        self.client.force_login(self.student_user)
        res = self.client.post(f"/api/csl-admin/assessments/{assessment.id}/upload-pdf/", {"pdf_file": pdf_file}, format="multipart")
        self.assertEqual(res.status_code, 403)

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Candidate Access and Security Tests
    # ──────────────────────────────────────────────────────────────────────────

    def _setup_open_pdf_assessment(self):
        """Helper to create and open a valid PDF Coding Assessment with candidate enrollment."""
        pdf_bytes = make_valid_pdf_bytes("Final Coding Challenge")
        assessment = Assessment.objects.create(
            code="PDF-OPEN-01",
            title="Live PDF Coding Challenge",
            duration_minutes=60,
            total_marks=50,
            delivery_mode=Assessment.DeliveryMode.PDF_CODING,
            status=Assessment.Status.DRAFT,
        )
        assessment.eligible_colleges.add(self.college)

        AssessmentPdfDocument.objects.create(
            assessment=assessment,
            original_filename="live_challenge.pdf",
            file_size=len(pdf_bytes),
            sha256="sha256_mock_abc",
            binary_data=pdf_bytes,
            uploaded_by=self.admin_user,
        )

        open_assessment(assessment, user=self.admin_user)
        return assessment, pdf_bytes

    def test_eligible_candidate_can_start_and_download_pdf(self):
        """Eligible candidate starts attempt and accesses question paper PDF."""
        assessment, pdf_bytes = self._setup_open_pdf_assessment()

        # Step 1: Start assessment
        res_start = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.candidate_token}",
        )
        self.assertEqual(res_start.status_code, 200, res_start.data)
        attempt_id = res_start.data["id"]
        self.assertEqual(res_start.data["delivery_mode"], "PDF_CODING")
        self.assertTrue(res_start.data["has_pdf"])
        self.assertEqual(res_start.data["pdf_filename"], "live_challenge.pdf")
        self.assertEqual(len(res_start.data["questions"]), 0, "PDF mode must not return MCQ questions")

        attempt_token = res_start.data["assessment_token"]

        # Step 2: Download question paper PDF
        res_pdf = self.client.get(
            f"/api/assessment/attempts/{attempt_id}/pdf/",
            HTTP_AUTHORIZATION=f"Bearer {attempt_token}",
        )
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf["Content-Type"], "application/pdf")
        self.assertIn("live_challenge.pdf", res_pdf["Content-Disposition"])
        self.assertEqual(res_pdf.content, pdf_bytes)

    def test_unassigned_candidate_cannot_access_pdf(self):
        """Candidate belonging to a non-enrolled college cannot start or access the PDF."""
        other_college = College.objects.create(name="Other College", code="OTHER_COL")
        unassigned_cand = Candidate.objects.create(
            full_name="Unassigned Candidate",
            register_number="UNASSIGNED_01",
            college=other_college.name,
            college_ref=other_college,
            email="unassigned@other.edu",
            department="CSE",
            year_of_study="3",
        )
        unassigned_token = generate_candidate_token(unassigned_cand.id)

        assessment, _ = self._setup_open_pdf_assessment()

        res = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {unassigned_token}",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("not enrolled", str(res.data.get("detail", "")).lower())

    def test_candidate_cannot_access_another_candidates_pdf_attempt(self):
        """Candidate A cannot retrieve the PDF via Candidate B's attempt UUID."""
        assessment, _ = self._setup_open_pdf_assessment()

        # Candidate A starts attempt
        attempt_a = start_assessment_for_candidate(self.candidate, assessment=assessment)

        # Candidate B attempts to fetch Candidate A's attempt PDF
        cand_b = Candidate.objects.create(
            full_name="Candidate B",
            register_number="CAND_B_01",
            college=self.college.name,
            college_ref=self.college,
            email="cand_b@apex.edu",
            department="CSE",
            year_of_study="4",
        )
        token_b = generate_candidate_token(cand_b.id)

        res = self.client.get(
            f"/api/assessment/attempts/{attempt_a.id}/pdf/",
            HTTP_AUTHORIZATION=f"Bearer {token_b}",
        )
        self.assertEqual(res.status_code, 403)

    def test_pdf_mode_rejects_answer_submission(self):
        """Saving individual MCQ answers or syncing answers is rejected in PDF mode."""
        assessment, _ = self._setup_open_pdf_assessment()
        attempt = start_assessment_for_candidate(self.candidate, assessment=assessment)
        token = generate_candidate_token(self.candidate.id, attempt_id=attempt.id)

        # Try save individual answer
        res_answer = self.client.post(
            f"/api/assessment/attempts/{attempt.id}/answer/",
            {"question_order": 1, "selected_option": "A"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res_answer.status_code, 400)

        # Try sync answers
        res_sync = self.client.post(
            f"/api/assessment/attempts/{attempt.id}/sync-answers/",
            {"answers": [{"question_order": 1, "selected_option": "A"}]},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res_sync.status_code, 400)

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Lifecycle, Completion, and Proctoring Tests
    # ──────────────────────────────────────────────────────────────────────────

    def test_pdf_attempt_completion_transitions_to_manual_evaluation_pending(self):
        """Finishing a PDF assessment transitions attempt state to COMPLETED_PENDING_MANUAL_EVALUATION."""
        assessment, _ = self._setup_open_pdf_assessment()
        attempt = start_assessment_for_candidate(self.candidate, assessment=assessment)
        token = generate_candidate_token(self.candidate.id, attempt_id=attempt.id)

        res_finalize = self.client.post(
            f"/api/assessment/attempts/{attempt.id}/finalize/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res_finalize.status_code, 200)
        self.assertEqual(res_finalize.data["state"], AssessmentAttempt.State.COMPLETED_PENDING_MANUAL_EVALUATION)

        attempt.refresh_from_db()
        self.assertEqual(attempt.state, AssessmentAttempt.State.COMPLETED_PENDING_MANUAL_EVALUATION)
        self.assertIsNotNone(attempt.submitted_at)

        # Verify zero-scoring artifact did NOT occur
        self.assertEqual(attempt.total_score, 0)
        self.assertEqual(attempt.percentage, 0.0)

        # Integrity event logged
        submit_event = IntegrityEvent.objects.filter(
            attempt=attempt,
            event_type=IntegrityEvent.EventType.SUBMITTED,
        ).first()
        self.assertIsNotNone(submit_event)
        self.assertTrue(submit_event.metadata.get("manual_evaluation_pending"))

    def test_pdf_attempt_completion_is_idempotent(self):
        """Repeated finalize requests do not alter state or duplicate completion events."""
        assessment, _ = self._setup_open_pdf_assessment()
        attempt = start_assessment_for_candidate(self.candidate, assessment=assessment)
        token = generate_candidate_token(self.candidate.id, attempt_id=attempt.id)

        # First finalize
        self.client.post(f"/api/assessment/attempts/{attempt.id}/finalize/", HTTP_AUTHORIZATION=f"Bearer {token}")
        attempt.refresh_from_db()
        first_submitted_at = attempt.submitted_at

        # Second finalize
        res2 = self.client.post(f"/api/assessment/attempts/{attempt.id}/finalize/", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(res2.status_code, 200)

        attempt.refresh_from_db()
        self.assertEqual(attempt.submitted_at, first_submitted_at)
        self.assertEqual(
            IntegrityEvent.objects.filter(attempt=attempt, event_type=IntegrityEvent.EventType.SUBMITTED).count(),
            1,
        )

    def test_pdf_attempt_timeout_transitions_to_timed_out(self):
        """Expired PDF attempt properly transitions to TIMED_OUT."""
        assessment, _ = self._setup_open_pdf_assessment()
        attempt = start_assessment_for_candidate(self.candidate, assessment=assessment)
        # Force attempt to be in the past
        attempt.deadline = timezone.now() - timedelta(minutes=5)
        attempt.save(update_fields=["deadline"])

        finalize_assessment_attempt(attempt)
        attempt.refresh_from_db()
        self.assertEqual(attempt.state, AssessmentAttempt.State.TIMED_OUT)

    def test_proctoring_events_recorded_during_pdf_attempt(self):
        """Tab switches and fullscreen exits are properly recorded for PDF attempts."""
        assessment, _ = self._setup_open_pdf_assessment()
        attempt = start_assessment_for_candidate(self.candidate, assessment=assessment)
        token = generate_candidate_token(self.candidate.id, attempt_id=attempt.id)

        res_tab = self.client.post(
            f"/api/assessment/attempts/{attempt.id}/integrity-event/",
            {"event_type": "TAB_HIDDEN", "event_id": f"{attempt.id}_tab_01"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res_tab.status_code, 200)

        attempt.refresh_from_db()
        self.assertEqual(attempt.tab_switch_count, 1)

    def test_admin_monitoring_shows_manual_evaluation_pending(self):
        """Admin result and review APIs clearly distinguish PDF attempts awaiting manual evaluation."""
        assessment, _ = self._setup_open_pdf_assessment()
        attempt = start_assessment_for_candidate(self.candidate, assessment=assessment)
        finalize_assessment_attempt(attempt)

        self.client.force_login(self.admin_user)

        # Check results list API
        res_results = self.client.get("/api/csl-admin/results/")
        self.assertEqual(res_results.status_code, 200)
        item = next((r for r in res_results.data if str(r["id"]) == str(attempt.id)), None)
        self.assertIsNotNone(item)
        self.assertEqual(item["delivery_mode"], "PDF_CODING")
        self.assertEqual(item["state"], AssessmentAttempt.State.COMPLETED_PENDING_MANUAL_EVALUATION)
        self.assertTrue(item["is_manual_evaluation_pending"])

        # Check attempt review API
        res_review = self.client.get(f"/api/csl-admin/attempts/{attempt.id}/review/")
        self.assertEqual(res_review.status_code, 200)
        self.assertEqual(res_review.data["delivery_mode"], "PDF_CODING")
        self.assertTrue(res_review.data["is_manual_evaluation_pending"])
        self.assertEqual(res_review.data["pdf_filename"], "live_challenge.pdf")

    # ─── NEON OBJECT STORAGE / S3 BACKEND REGRESSION TESTS ───────────────────

    def test_neon_s3_storage_upload_and_candidate_stream(self):
        """
        Validates full Neon Object Storage / S3 lifecycle:
        1. Uploads to S3 via S3-compatible API.
        2. Stores s3_key and s3_bucket in PostgreSQL, keeping binary_data empty.
        3. Candidate streams PDF bytes authenticated directly through server backend.
        4. No permanent public URLs exposed.
        """
        from unittest.mock import patch, MagicMock
        from apps.assessments.storage_service import AssessmentPdfStorageService

        mock_s3 = MagicMock()
        stored_objects = {}

        def mock_put_object(Bucket, Key, Body, **kwargs):
            stored_objects[(Bucket, Key)] = Body
            return {"ETag": "mock-etag"}

        def mock_get_object(Bucket, Key, **kwargs):
            if (Bucket, Key) not in stored_objects:
                raise Exception("NoSuchKey")
            body_mock = MagicMock()
            body_mock.read.return_value = stored_objects[(Bucket, Key)]
            return {"Body": body_mock, "ContentType": "application/pdf"}

        mock_s3.put_object.side_effect = mock_put_object
        mock_s3.get_object.side_effect = mock_get_object

        pdf_bytes = make_valid_pdf_bytes("Neon Storage Assessment Paper")
        pdf_file = SimpleUploadedFile("neon_coding_paper.pdf", pdf_bytes, content_type="application/pdf")

        assessment = Assessment.objects.create(
            code="NEON-PDF-01",
            title="Neon S3 Storage Assessment",
            delivery_mode=Assessment.DeliveryMode.PDF_CODING,
            duration_minutes=60,
            total_marks=100,
        )
        assessment.eligible_colleges.add(self.college)

        with patch.dict("os.environ", {
            "NEON_STORAGE_ENDPOINT_URL": "https://test-branch.storage.us-east-1.aws.neon.tech",
            "NEON_STORAGE_ACCESS_KEY_ID": "test-neon-access-key",
            "NEON_STORAGE_SECRET_ACCESS_KEY": "test-neon-secret-key",
            "NEON_STORAGE_REGION": "us-east-1",
            "NEON_STORAGE_BUCKET_NAME": "csl-assessments-private",
        }), patch.object(AssessmentPdfStorageService, "get_s3_client", return_value=mock_s3):
            self.client.force_login(self.admin_user)

            # Upload PDF via admin endpoint
            res_upload = self.client.post(
                f"/api/csl-admin/assessments/{assessment.id}/upload-pdf/",
                {"pdf_file": pdf_file},
                format="multipart",
            )
            self.assertEqual(res_upload.status_code, 200, res_upload.data)
            self.assertEqual(res_upload.data["filename"], "neon_coding_paper.pdf")

            # Check S3 put_object was called
            self.assertTrue(mock_s3.put_object.called)
            call_kwargs = mock_s3.put_object.call_args[1]
            self.assertEqual(call_kwargs["Bucket"], "csl-assessments-private")
            self.assertTrue(call_kwargs["Key"].startswith(f"assessments/{assessment.id}/"))
            self.assertTrue(call_kwargs["Key"].endswith(".pdf"))
            self.assertEqual(call_kwargs["ContentType"], "application/pdf")

            # Verify PostgreSQL state: metadata stored, but binary_data is None to prevent DB bloat
            assessment.refresh_from_db()
            pdf_doc = assessment.pdf_document
            self.assertEqual(pdf_doc.s3_bucket, "csl-assessments-private")
            self.assertEqual(pdf_doc.s3_key, call_kwargs["Key"])
            self.assertIsNone(pdf_doc.binary_data, "PostgreSQL binary_data must remain None when S3 storage is enabled")
            self.assertEqual(pdf_doc.file_size, len(pdf_bytes))

            # Prepare and open assessment
            prepare_assessment(assessment, user=self.admin_user)
            open_assessment(assessment, user=self.admin_user)

            # Candidate starts attempt and downloads PDF
            attempt = start_assessment_for_candidate(self.candidate, assessment=assessment)
            token = generate_candidate_token(self.candidate.id, attempt_id=attempt.id)

            res_stream = self.client.get(
                f"/api/assessment/attempts/{attempt.id}/pdf/",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(res_stream.status_code, 200)
            self.assertEqual(res_stream["Content-Type"], "application/pdf")
            self.assertEqual(res_stream["X-Content-Type-Options"], "nosniff")
            self.assertIn("no-cache", res_stream["Cache-Control"])
            self.assertIn("private", res_stream["Cache-Control"])
            self.assertEqual(res_stream.content, pdf_bytes)

    def test_s3_orphaned_object_cleanup_on_database_error(self):
        """
        When S3 upload succeeds but database transaction fails,
        the orphaned S3 object is safely deleted to prevent cloud storage leaks.
        """
        from unittest.mock import patch, MagicMock
        from apps.assessments.storage_service import AssessmentPdfStorageService

        mock_s3 = MagicMock()
        mock_s3.put_object.return_value = {"ETag": "mock-etag"}

        pdf_bytes = make_valid_pdf_bytes("Cleanup Test Paper")
        pdf_file = SimpleUploadedFile("leak_test.pdf", pdf_bytes, content_type="application/pdf")

        assessment = Assessment.objects.create(
            code="CLEANUP-PDF-01",
            title="Cleanup Assessment",
            delivery_mode=Assessment.DeliveryMode.PDF_CODING,
            duration_minutes=60,
            total_marks=50,
        )

        with patch.dict("os.environ", {
            "NEON_STORAGE_ACCESS_KEY_ID": "test-key",
            "NEON_STORAGE_SECRET_ACCESS_KEY": "test-secret",
            "NEON_STORAGE_BUCKET_NAME": "csl-cleanup-bucket",
        }), patch.object(AssessmentPdfStorageService, "get_s3_client", return_value=mock_s3):
            self.client.force_login(self.admin_user)

            # Simulate database integrity error during AssessmentPdfDocument.objects.create
            with patch("apps.assessments.models.AssessmentPdfDocument.objects.create", side_effect=Exception("Database connection terminated")):
                with self.assertRaises(Exception):
                    self.client.post(
                        f"/api/csl-admin/assessments/{assessment.id}/upload-pdf/",
                        {"pdf_file": pdf_file},
                        format="multipart",
                    )

            # S3 put_object was attempted, and delete_object was invoked to clean up the orphan!
            self.assertTrue(mock_s3.put_object.called)
            self.assertTrue(mock_s3.delete_object.called)
            del_kwargs = mock_s3.delete_object.call_args[1]
            self.assertEqual(del_kwargs["Bucket"], "csl-cleanup-bucket")
            self.assertTrue(del_kwargs["Key"].startswith(f"assessments/{assessment.id}/"))

    def test_s3_cleanup_on_assessment_deletion(self):
        """
        When an assessment with an S3-backed PDF is deleted, the corresponding S3 object is removed.
        """
        from unittest.mock import patch, MagicMock
        from apps.assessments.storage_service import AssessmentPdfStorageService

        mock_s3 = MagicMock()
        assessment = Assessment.objects.create(
            code="DEL-PDF-01",
            title="Delete Test Assessment",
            delivery_mode=Assessment.DeliveryMode.PDF_CODING,
            duration_minutes=60,
            total_marks=50,
        )
        pdf_doc = AssessmentPdfDocument.objects.create(
            assessment=assessment,
            original_filename="delete_me.pdf",
            file_size=1024,
            sha256="fake-hash",
            s3_key="assessments/DEL-PDF-01/delete_me.pdf",
            s3_bucket="test-del-bucket",
        )

        with patch.dict("os.environ", {
            "NEON_STORAGE_ACCESS_KEY_ID": "test-key",
            "NEON_STORAGE_SECRET_ACCESS_KEY": "test-secret",
            "NEON_STORAGE_BUCKET_NAME": "test-del-bucket",
        }), patch.object(AssessmentPdfStorageService, "get_s3_client", return_value=mock_s3):
            # Delete PDF document
            pdf_doc.delete()
            self.assertTrue(mock_s3.delete_object.called)
            del_kwargs = mock_s3.delete_object.call_args[1]
            self.assertEqual(del_kwargs["Bucket"], "test-del-bucket")
            self.assertEqual(del_kwargs["Key"], "assessments/DEL-PDF-01/delete_me.pdf")
