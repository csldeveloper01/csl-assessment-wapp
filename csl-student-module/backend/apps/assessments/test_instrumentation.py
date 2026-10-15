import logging
import re
import uuid
from django.test import TestCase, Client
from django.utils import timezone
from apps.users.models import User
from apps.assessments.models import (
    QuestionBank,
    AssessmentConfig,
    College,
    Assessment,
    Candidate,
    AssessmentAttempt,
    AttemptQuestionSnapshot,
    AssessmentSection,
)
from apps.assessments.tokens import generate_candidate_token
from apps.assessments.services import (
    save_candidate_answer,
    finalize_assessment_attempt,
)


class ApiPerformanceMiddlewareTests(TestCase):
    """
    Verifies that ApiPerformanceMiddleware accurately measures request duration,
    counts database queries, forwards/generates correlation IDs, logs route patterns
    without sensitive data, and ignores non-API endpoints.
    """

    def setUp(self):
        self.client = Client()
        self.college = College.objects.create(
            name="Testing Institute",
            code="TEST-INST",
            is_active=True,
        )
        self.candidate = Candidate.objects.create(
            full_name="Candidate Observability",
            register_number="OBS-001",
            email="candidate.obs@example.com",
            phone_number="9876543210",
            college_ref=self.college,
            is_active=True,
        )
        self.token = generate_candidate_token(str(self.candidate.id))

    def test_api_request_logs_api_perf_format(self):
        """Verifies API_PERF log format, query count, and duration fields."""
        with self.assertLogs("api.perf", level="INFO") as captured:
            response = self.client.get(
                "/api/assessment/candidate-assessments/",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
            self.assertEqual(response.status_code, 200)

        perf_logs = [record for record in captured.output if "API_PERF" in record]
        self.assertEqual(len(perf_logs), 1)
        log_line = perf_logs[0]

        # Expected format: API_PERF req_id=... method=GET route=... status=200 total_ms=... db_queries=... db_time_ms=...
        self.assertIn("method=GET", log_line)
        self.assertIn("status=200", log_line)
        self.assertIn("route=/api/assessment/candidate-assessments/", log_line)
        self.assertRegex(log_line, r"req_id=\w+")
        self.assertRegex(log_line, r"total_ms=\d+\.\d+")
        self.assertRegex(log_line, r"db_queries=\d+")
        self.assertRegex(log_line, r"db_time_ms=\d+\.\d+")

    def test_correlation_id_forwarded_from_header(self):
        """Verifies custom X-Request-ID is honored in logs and returned in response."""
        custom_id = "test-corr-id-9999"
        with self.assertLogs("api.perf", level="INFO") as captured:
            response = self.client.get(
                "/api/assessment/candidate-assessments/",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
                HTTP_X_REQUEST_ID=custom_id,
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers.get("X-Request-ID"), custom_id)

        perf_logs = [record for record in captured.output if "API_PERF" in record]
        self.assertEqual(len(perf_logs), 1)
        self.assertIn(f"req_id={custom_id}", perf_logs[0])

    def test_correlation_id_fallback_generated_when_missing(self):
        """Verifies generated correlation ID is set in response when no header provided."""
        response = self.client.get(
            "/api/assessment/candidate-assessments/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        generated_id = response.headers.get("X-Request-ID")
        self.assertTrue(generated_id)
        self.assertGreaterEqual(len(generated_id), 8)

    def test_non_api_paths_bypass_instrumentation(self):
        """Verifies /health/ does not trigger API_PERF logs."""
        logger = logging.getLogger("api.perf")
        with self.assertLogs(logger, level="INFO") as captured:
            # First trigger one API call so assertLogs has at least one record
            self.client.get(
                "/api/assessment/candidate-assessments/",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
            # Now call /health/
            health_resp = self.client.get("/health/")
            self.assertEqual(health_resp.status_code, 200)

        # Confirm no log was recorded for /health/
        health_logs = [record for record in captured.output if "/health/" in record]
        self.assertEqual(len(health_logs), 0)

    def test_route_pattern_sanitization_for_parameterized_urls(self):
        """Verifies raw UUIDs in route paths are parameterized and not leaked."""
        dummy_uuid = "11111111-2222-3333-4444-555555555555"
        with self.assertLogs("api.perf", level="INFO") as captured:
            self.client.get(
                f"/api/assessment/attempts/{dummy_uuid}/",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )

        perf_logs = [record for record in captured.output if "API_PERF" in record]
        self.assertEqual(len(perf_logs), 1)
        log_line = perf_logs[0]

        # The route pattern should be parameterized (e.g. containing <uuid:attempt_id>)
        self.assertIn("<uuid:attempt_id>", log_line)
        self.assertNotIn(dummy_uuid, log_line)

    def test_route_pattern_scrubbing_on_unmatched_404_urls(self):
        """Verifies unrouted URLs scrub raw UUIDs in fallback path."""
        dummy_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        with self.assertLogs("api.perf", level="INFO") as captured:
            response = self.client.get(f"/api/nonexistent/{dummy_uuid}/unmatched/")
            self.assertEqual(response.status_code, 404)

        perf_logs = [record for record in captured.output if "API_PERF" in record]
        self.assertEqual(len(perf_logs), 1)
        log_line = perf_logs[0]

        self.assertNotIn(dummy_uuid, log_line)
        self.assertIn("/:id", log_line)
        self.assertIn("status=404", log_line)

    def test_query_count_matches_actual_queries_executed(self):
        """Verifies db_queries in API_PERF accurately reflects the number of queries executed."""
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with self.assertLogs("api.perf", level="INFO") as captured:
            with CaptureQueriesContext(connection) as expected_queries:
                response = self.client.get(
                    "/api/assessment/candidate-assessments/",
                    HTTP_AUTHORIZATION=f"Bearer {self.token}",
                )
                self.assertEqual(response.status_code, 200)

        perf_logs = [record for record in captured.output if "API_PERF" in record]
        self.assertEqual(len(perf_logs), 1)
        match = re.search(r"db_queries=(\d+)", perf_logs[0])
        self.assertTrue(match)
        logged_queries = int(match.group(1))
        self.assertEqual(logged_queries, len(expected_queries))

    def test_bad_request_status_logged_accurately(self):
        """Verifies 400 error status is recorded in API_PERF without modifying response."""
        with self.assertLogs("api.perf", level="INFO") as captured:
            response = self.client.post(
                "/api/assessment/register/",
                data={},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)

        perf_logs = [record for record in captured.output if "API_PERF" in record]
        self.assertEqual(len(perf_logs), 1)
        self.assertIn("status=400", perf_logs[0])


class ServiceTimingInstrumentationTests(TestCase):
    """
    Verifies that ANSWER_SAVE_TIMING and ASSESSMENT_FINALIZE_TIMING log
    accurate execution metrics without exposing sensitive data.
    """

    def setUp(self):
        self.college = College.objects.create(
            name="Metrics Institute",
            code="METRICS-INST",
            is_active=True,
        )
        self.candidate = Candidate.objects.create(
            full_name="Metrics Candidate",
            register_number="MET-001",
            email="metrics@example.com",
            phone_number="9876543211",
            college_ref=self.college,
            is_active=True,
        )
        self.config = AssessmentConfig.objects.create(
            title="Timing Test Config",
            duration_minutes=30,
            total_marks=50,
            aptitude_count=25,
            coding_count=25,
            is_active=True,
        )
        self.assessment = Assessment.objects.create(
            code="TIME-01",
            title="Timing Assessment",
            duration_minutes=30,
            total_marks=50,
            aptitude_count=25,
            coding_count=25,
            status=Assessment.Status.OPEN,
        )
        self.assessment.eligible_colleges.add(self.college)

        self.sec_coding, _ = AssessmentSection.objects.get_or_create(
            code="CODING",
            defaults={"name": "Coding Fundamentals", "is_active": True},
        )

        self.question = QuestionBank.objects.create(
            section=self.sec_coding,
            section_type="CODING",
            prompt="What is Big-O of binary search?",
            option_a="O(1)",
            option_b="O(log n)",
            option_c="O(n)",
            option_d="O(n^2)",
            correct_option="B",
            is_active=True,
        )

        now = timezone.now()
        self.attempt = AssessmentAttempt.objects.create(
            candidate=self.candidate,
            assessment=self.assessment,
            config=self.config,
            state=AssessmentAttempt.State.IN_PROGRESS,
            started_at=now,
            deadline=now + timezone.timedelta(minutes=30),
        )

        self.snapshot = AttemptQuestionSnapshot.objects.create(
            attempt=self.attempt,
            question=self.question,
            question_order=1,
            section_type=QuestionBank.SectionType.CODING,
            prompt=self.question.prompt,
            option_a_text=self.question.option_a,
            option_b_text=self.question.option_b,
            option_c_text=self.question.option_c,
            option_d_text=self.question.option_d,
            correct_option_key="B",
        )

    def test_answer_save_timing_logged(self):
        """Verifies ANSWER_SAVE_TIMING log includes lock_ms, update_ms, and service_ms."""
        with self.assertLogs("apps.assessments.services", level="INFO") as captured:
            snapshot = save_candidate_answer(self.attempt.id, question_order=1, selected_option="B")
            self.assertEqual(snapshot.selected_option, "B")

        timing_logs = [record for record in captured.output if "ANSWER_SAVE_TIMING" in record]
        self.assertEqual(len(timing_logs), 1)
        log_line = timing_logs[0]

        self.assertRegex(log_line, r"lock_ms=\d+\.\d+")
        self.assertRegex(log_line, r"update_ms=\d+\.\d+")
        self.assertRegex(log_line, r"service_ms=\d+\.\d+")

        # Privacy check: ensure attempt UUID, candidate details, or question details are not in log
        self.assertNotIn(str(self.attempt.id), log_line)
        self.assertNotIn(self.candidate.email, log_line)
        self.assertNotIn(self.question.prompt, log_line)

    def test_assessment_finalize_timing_logged(self):
        """Verifies ASSESSMENT_FINALIZE_TIMING log includes service_ms and final_state."""
        with self.assertLogs("apps.assessments.services", level="INFO") as captured:
            finalized = finalize_assessment_attempt(self.attempt, final_state=AssessmentAttempt.State.SUBMITTED)
            self.assertEqual(finalized.state, AssessmentAttempt.State.SUBMITTED)

        timing_logs = [record for record in captured.output if "ASSESSMENT_FINALIZE_TIMING" in record]
        self.assertEqual(len(timing_logs), 1)
        log_line = timing_logs[0]

        self.assertRegex(log_line, r"lock_ms=\d+\.\d+")
        self.assertRegex(log_line, r"scoring_ms=\d+\.\d+")
        self.assertRegex(log_line, r"write_ms=\d+\.\d+")
        self.assertRegex(log_line, r"service_ms=\d+\.\d+")
        self.assertIn("final_state=SUBMITTED", log_line)

        # Calling again on already finalized attempt should also log timing
        with self.assertLogs("apps.assessments.services", level="INFO") as captured_again:
            finalize_assessment_attempt(self.attempt)

        second_logs = [record for record in captured_again.output if "ASSESSMENT_FINALIZE_TIMING" in record]
        self.assertEqual(len(second_logs), 1)
        self.assertRegex(second_logs[0], r"lock_ms=\d+\.\d+")
        self.assertRegex(second_logs[0], r"service_ms=\d+\.\d+")
        self.assertIn("final_state=SUBMITTED", second_logs[0])

    def test_assessment_start_timing_logged(self):
        """Verifies ASSESSMENT_START_TIMING log includes lookup_ms, service_ms, prep_ms, serializer_ms, and total_ms."""
        self.assessment.aptitude_count = 0
        self.assessment.coding_count = 1
        self.assessment.total_marks = 1
        self.assessment.save()

        cand = Candidate.objects.create(
            full_name="Start Timing Candidate",
            register_number="STC-001",
            email="stc001@example.com",
            phone_number="9876543219",
            college_ref=self.college,
            is_active=True,
        )
        token = generate_candidate_token(str(cand.id))

        with self.assertLogs("apps.assessments.views", level="INFO") as captured:
            res = self.client.post(
                "/api/assessment/start/",
                {"assessment_id": str(self.assessment.id)},
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(res.status_code, 200)

        timing_logs = [record for record in captured.output if "ASSESSMENT_START_TIMING" in record]
        self.assertEqual(len(timing_logs), 1)
        log_line = timing_logs[0]

        self.assertRegex(log_line, r"lookup_ms=\d+\.\d+")
        self.assertRegex(log_line, r"service_ms=\d+\.\d+")
        self.assertRegex(log_line, r"prep_ms=\d+\.\d+")
        self.assertRegex(log_line, r"serializer_ms=\d+\.\d+")
        self.assertRegex(log_line, r"total_ms=\d+\.\d+")
        self.assertIn(f"attempt_id={res.data['id']}", log_line)
