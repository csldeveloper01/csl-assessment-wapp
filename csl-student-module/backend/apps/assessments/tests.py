import uuid
from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from apps.users.models import User

from apps.assessments.models import (
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
from apps.assessments.services import (
    start_assessment_for_candidate,
    save_candidate_answer,
    finalize_assessment_attempt,
)
from apps.assessments.tokens import (
    generate_candidate_token,
    decode_candidate_token,
)


class ComprehensiveAssessmentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.config = AssessmentConfig.objects.create(
            title="CSL Initial Assessment",
            duration_minutes=60,
            total_marks=50,
            aptitude_count=25,
            coding_count=25,
            max_attempts=1,
            is_active=True,
        )

        categories_apt = ["Quantitative", "Logical", "Verbal"]
        diffs = ["EASY", "MEDIUM", "HARD"]
        apt_list = []
        for i in range(30):
            apt_list.append(
                QuestionBank(
                    prompt=f"Aptitude Question {i+1}",
                    section_type=QuestionBank.SectionType.APTITUDE,
                    category=categories_apt[i % len(categories_apt)],
                    difficulty=diffs[i % len(diffs)],
                    option_a=f"Opt A {i+1}",
                    option_b=f"Opt B {i+1}",
                    option_c=f"Opt C {i+1}",
                    option_d=f"Opt D {i+1}",
                    correct_option="A",
                    is_active=True,
                )
            )
        QuestionBank.objects.bulk_create(apt_list)

        categories_cod = ["Python", "OOP", "Data Structures"]
        cod_list = []
        for i in range(30):
            cod_list.append(
                QuestionBank(
                    prompt=f"Coding Question {i+1}",
                    section_type=QuestionBank.SectionType.CODING,
                    category=categories_cod[i % len(categories_cod)],
                    difficulty=diffs[i % len(diffs)],
                    option_a=f"Opt A {i+1}",
                    option_b=f"Opt B {i+1}",
                    option_c=f"Opt C {i+1}",
                    option_d=f"Opt D {i+1}",
                    correct_option="B",
                    is_active=True,
                )
            )
        QuestionBank.objects.bulk_create(cod_list)

    def test_candidate_registration_and_token_generation(self):
        payload = {
            "full_name": "Rathinam Student",
            "register_number": "721721U101",
            "college": "Rathinam College of Arts and Science",
            "email": "Student01@Rathinam.IN ",
            "department": "B.Sc Computer Science",
            "year_of_study": "Final Year",
            "phone_number": "9876543210",
        }
        res = self.client.post("/api/assessment/register/", payload, content_type="application/json")
        self.assertEqual(res.status_code, 201)
        self.assertIn("candidate_id", res.data)
        self.assertIn("assessment_token", res.data)
        self.assertEqual(res.data["full_name"], "Rathinam Student")

        # Verify normalized email stored in DB
        candidate = Candidate.objects.get(id=res.data["candidate_id"])
        self.assertEqual(candidate.email, "student01@rathinam.in")
        self.assertEqual(candidate.register_number, "721721U101")

        # Duplicate register number for same college should fail
        clash_payload = payload.copy()
        clash_payload["email"] = "different@example.com"
        res2 = self.client.post("/api/assessment/register/", clash_payload, content_type="application/json")
        self.assertEqual(res2.status_code, 400)

    def test_full_assessment_lifecycle_with_authentication(self):
        # 1. Register candidate
        reg_res = self.client.post(
            "/api/assessment/register/",
            {
                "full_name": "Karthik R",
                "register_number": "CSL-2026-01",
                "college": "CIT Coimbatore",
                "email": "karthik@example.com",
                "department": "CSE",
                "year_of_study": "3rd Year",
                "phone_number": "9876543210",
            },
            content_type="application/json",
        )
        self.assertEqual(reg_res.status_code, 201)
        token = reg_res.data["assessment_token"]
        candidate_id = reg_res.data["candidate_id"]

        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        # 2. Start Assessment with Token
        start_res = self.client.post("/api/assessment/start/", {}, content_type="application/json", **headers)
        self.assertEqual(start_res.status_code, 200)
        attempt_id = start_res.data["id"]
        attempt_token = start_res.data["assessment_token"]
        attempt_headers = {"HTTP_AUTHORIZATION": f"Bearer {attempt_token}"}

        # Verify 50 questions with 25 Aptitude and 25 Coding
        questions = start_res.data["questions"]
        self.assertEqual(len(questions), 50)
        self.assertEqual(start_res.data["total_questions"], 50)
        self.assertEqual(questions[0]["section_type"], "APTITUDE")
        self.assertEqual(questions[24]["section_type"], "APTITUDE")
        self.assertEqual(questions[25]["section_type"], "CODING")
        self.assertEqual(questions[49]["section_type"], "CODING")

        # SECURITY: Ensure correct_option is never in student payload
        for q in questions:
            self.assertNotIn("correct_option", q)
            self.assertNotIn("correct_option_key", q)

        # 3. Retrieve Attempt State (Refresh / Reconnect)
        state_res = self.client.get(f"/api/assessment/attempts/{attempt_id}/", **attempt_headers)
        self.assertEqual(state_res.status_code, 200)
        self.assertEqual(state_res.data["id"], attempt_id)

        # 4. Save Answer
        save_res = self.client.post(
            f"/api/assessment/attempts/{attempt_id}/answer/",
            {"question_order": 1, "selected_option": "A"},
            content_type="application/json",
            **attempt_headers,
        )
        self.assertEqual(save_res.status_code, 200)
        self.assertEqual(save_res.data["status"], "saved")

        # 5. Integrity Event Logging
        event_res = self.client.post(
            f"/api/assessment/attempts/{attempt_id}/integrity-event/",
            {"event_type": "TAB_HIDDEN", "client_timestamp": timezone.now().isoformat()},
            content_type="application/json",
            **attempt_headers,
        )
        self.assertEqual(event_res.status_code, 200)
        self.assertEqual(event_res.data["tab_switches"], 1)

        # 6. Finalize Attempt
        fin_res = self.client.post(f"/api/assessment/attempts/{attempt_id}/finalize/", **attempt_headers)
        self.assertEqual(fin_res.status_code, 200)
        self.assertEqual(fin_res.data["state"], AssessmentAttempt.State.SUBMITTED)
        self.assertFalse(fin_res.data.get("is_results_released", True))
        self.assertNotIn("total_score", fin_res.data)
        self.assertIn("message", fin_res.data)

        # 7. Check Results View before release: withheld
        res_view_pending = self.client.get(f"/api/assessment/attempts/{attempt_id}/result/", **attempt_headers)
        self.assertEqual(res_view_pending.status_code, 200)
        self.assertFalse(res_view_pending.data["is_results_released"])
        self.assertNotIn("total_score", res_view_pending.data)
        self.assertNotIn("breakdown", res_view_pending.data)

        # 8. Release results via assessment
        attempt = AssessmentAttempt.objects.get(id=attempt_id)
        if attempt.assessment:
            attempt.assessment.is_results_released = True
            attempt.assessment.save()

        # 9. Check Results View after release: scores and breakdown now present
        res_view = self.client.get(f"/api/assessment/attempts/{attempt_id}/result/", **attempt_headers)
        self.assertEqual(res_view.status_code, 200)
        self.assertTrue(res_view.data["is_results_released"])
        self.assertEqual(res_view.data["candidate_name"], "Karthik R")
        self.assertIn("total_score", res_view.data)
        self.assertEqual(res_view.data["year_of_study"], "3rd Year")
        self.assertIn("breakdown", res_view.data)

        breakdown = res_view.data["breakdown"]
        apt = breakdown["aptitude"]
        cod = breakdown["coding"]
        self.assertEqual(apt["total"], 25)
        self.assertEqual(cod["total"], 25)
        self.assertEqual(apt["correct"] + apt["incorrect"] + apt["unattempted"], 25)
        self.assertEqual(cod["correct"] + cod["incorrect"] + cod["unattempted"], 25)
        self.assertEqual(apt["correct"] + cod["correct"], res_view.data["total_score"])
        self.assertIn("time_taken_display", breakdown)

    def test_cross_candidate_tampering_forbidden(self):
        # Create Candidate 1 and Attempt 1
        c1 = Candidate.objects.create(
            full_name="User One",
            register_number="REG-01",
            college="College A",
            email="u1@example.com",
            department="CSE",
            year_of_study="1st Year",
        )
        attempt1 = start_assessment_for_candidate(c1, self.config)

        # Create Candidate 2 and Token 2
        c2 = Candidate.objects.create(
            full_name="User Two",
            register_number="REG-02",
            college="College A",
            email="u2@example.com",
            department="CSE",
            year_of_study="1st Year",
        )
        token2 = generate_candidate_token(str(c2.id))
        headers_c2 = {"HTTP_AUTHORIZATION": f"Bearer {token2}"}

        # Attempt to access or modify Candidate 1's attempt using Candidate 2's token
        res_get = self.client.get(f"/api/assessment/attempts/{attempt1.id}/", **headers_c2)
        self.assertEqual(res_get.status_code, 403)

        res_ans = self.client.post(
            f"/api/assessment/attempts/{attempt1.id}/answer/",
            {"question_order": 1, "selected_option": "B"},
            content_type="application/json",
            **headers_c2,
        )
        self.assertEqual(res_ans.status_code, 403)

        res_fin = self.client.post(f"/api/assessment/attempts/{attempt1.id}/finalize/", **headers_c2)
        self.assertEqual(res_fin.status_code, 403)

        res_result = self.client.get(f"/api/assessment/attempts/{attempt1.id}/result/", **headers_c2)
        self.assertEqual(res_result.status_code, 403)

    def test_unauthorized_missing_token_rejected(self):
        fake_id = uuid.uuid4()
        res = self.client.get(f"/api/assessment/attempts/{fake_id}/")
        self.assertIn(res.status_code, [401, 403, 404])

        res_start = self.client.post("/api/assessment/start/", {})
        self.assertEqual(res_start.status_code, 401)

    def test_post_submission_answers_locked_and_idempotent_finalization(self):
        c = Candidate.objects.create(
            full_name="Lock Test Student",
            register_number="LOCK-01",
            college="College B",
            email="lock@example.com",
            department="IT",
            year_of_study="2nd Year",
        )
        attempt = start_assessment_for_candidate(c, self.config)
        token = generate_candidate_token(str(c.id), str(attempt.id))
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        # Save an answer
        save_candidate_answer(attempt, 1, "A")

        # Finalize attempt
        fin1 = finalize_assessment_attempt(attempt)
        score1 = fin1.total_score

        # Repeated finalization should be idempotent and return identical score
        fin2 = finalize_assessment_attempt(attempt)
        self.assertEqual(fin2.total_score, score1)
        self.assertEqual(fin2.state, AssessmentAttempt.State.SUBMITTED)

        # Attempting to modify answers post-submission should fail
        ans_res = self.client.post(
            f"/api/assessment/attempts/{attempt.id}/answer/",
            {"question_order": 1, "selected_option": "C"},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(ans_res.status_code, 400)

    def test_expired_attempt_auto_finalizes_as_timed_out(self):
        c = Candidate.objects.create(
            full_name="Timeout Student",
            register_number="TIME-01",
            college="College C",
            email="time@example.com",
            department="ECE",
            year_of_study="4th Year",
        )
        attempt = start_assessment_for_candidate(c, self.config)
        # Manually backdate deadline to simulate timeout
        attempt.deadline = timezone.now() - timedelta(minutes=5)
        attempt.save()

        token = generate_candidate_token(str(c.id), str(attempt.id))
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        # Accessing state should trigger timeout finalization
        res = self.client.get(f"/api/assessment/attempts/{attempt.id}/", **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["state"], AssessmentAttempt.State.TIMED_OUT)

        # Further answers must be rejected
        ans_res = self.client.post(
            f"/api/assessment/attempts/{attempt.id}/answer/",
            {"question_order": 2, "selected_option": "D"},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(ans_res.status_code, 400)

    def test_max_attempts_limit_enforced(self):
        c = Candidate.objects.create(
            full_name="Limit Student",
            register_number="LIMIT-01",
            college="College D",
            email="limit@example.com",
            department="CSE",
            year_of_study="3rd Year",
        )
        attempt = start_assessment_for_candidate(c, self.config)
        finalize_assessment_attempt(attempt)

        token = generate_candidate_token(str(c.id))
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        # Attempt to start a second attempt when max_attempts=1
        with self.assertRaises(Exception):
            start_assessment_for_candidate(c, self.config)

        res = self.client.post("/api/assessment/start/", {}, **headers)
        self.assertEqual(res.status_code, 400)

    def test_health_check_endpoint(self):
        res = self.client.get("/health/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

    def test_two_tab_switches_permitted_and_third_auto_finalizes(self):
        c = Candidate.objects.create(
            full_name="Tab Limit Student",
            register_number="TAB-01",
            college="College E",
            email="tablimit@example.com",
            department="CSE",
            year_of_study="2nd Year",
        )
        attempt = start_assessment_for_candidate(c, self.config)
        token = generate_candidate_token(str(c.id), str(attempt.id))
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        # 1st tab switch: permitted warning, attempt remains IN_PROGRESS
        r1 = self.client.post(
            f"/api/assessment/attempts/{attempt.id}/integrity-event/",
            {"event_type": "TAB_HIDDEN", "event_id": "ev-1"},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.data["tab_switches"], 1)
        self.assertFalse(r1.data["is_finalized"])
        self.assertEqual(r1.data["state"], AssessmentAttempt.State.IN_PROGRESS)

        # Tab becomes visible again
        self.client.post(
            f"/api/assessment/attempts/{attempt.id}/integrity-event/",
            {"event_type": "TAB_VISIBLE", "event_id": "ev-1-vis"},
            content_type="application/json",
            **headers,
        )

        # 2nd tab switch: permitted warning, attempt remains IN_PROGRESS
        r2 = self.client.post(
            f"/api/assessment/attempts/{attempt.id}/integrity-event/",
            {"event_type": "TAB_HIDDEN", "event_id": "ev-2"},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data["tab_switches"], 2)
        self.assertFalse(r2.data["is_finalized"])
        self.assertEqual(r2.data["state"], AssessmentAttempt.State.IN_PROGRESS)

        # Tab becomes visible again
        self.client.post(
            f"/api/assessment/attempts/{attempt.id}/integrity-event/",
            {"event_type": "TAB_VISIBLE", "event_id": "ev-2-vis"},
            content_type="application/json",
            **headers,
        )

        # 3rd tab switch: LIMIT EXCEEDED -> atomically finalizes and flags for review
        r3 = self.client.post(
            f"/api/assessment/attempts/{attempt.id}/integrity-event/",
            {"event_type": "TAB_HIDDEN", "event_id": "ev-3"},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r3.data["tab_switches"], 3)
        self.assertTrue(r3.data["is_finalized"])
        self.assertEqual(r3.data["state"], AssessmentAttempt.State.FLAGGED_FOR_REVIEW)
        self.assertIn("TAB_SWITCH_LIMIT_EXCEEDED", r3.data["flag_reason"])

        # Verify DB attempt state and integrity flags
        attempt.refresh_from_db()
        self.assertEqual(attempt.state, AssessmentAttempt.State.FLAGGED_FOR_REVIEW)
        self.assertTrue(attempt.is_flagged)
        self.assertIn("TAB_SWITCH_LIMIT_EXCEEDED", attempt.flag_reason)
        self.assertIsNotNone(attempt.submitted_at)

        # Subsequent answer edits must be strictly rejected
        ans_res = self.client.post(
            f"/api/assessment/attempts/{attempt.id}/answer/",
            {"question_order": 1, "selected_option": "A"},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(ans_res.status_code, 400)

    def test_integrity_event_id_deduplication(self):
        c = Candidate.objects.create(
            full_name="Deduplication Student",
            register_number="DEDUP-01",
            college="College E",
            email="dedup@example.com",
            department="CSE",
            year_of_study="2nd Year",
        )
        attempt = start_assessment_for_candidate(c, self.config)
        token = generate_candidate_token(str(c.id), str(attempt.id))
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        # Send initial event
        res1 = self.client.post(
            f"/api/assessment/attempts/{attempt.id}/integrity-event/",
            {"event_type": "TAB_HIDDEN", "event_id": "unique-tab-999"},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.data["status"], "recorded")
        self.assertEqual(res1.data["tab_switches"], 1)

        # Send duplicate of exact same event_id (simulating network retry)
        res2 = self.client.post(
            f"/api/assessment/attempts/{attempt.id}/integrity-event/",
            {"event_type": "TAB_HIDDEN", "event_id": "unique-tab-999"},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.data["status"], "duplicate_ignored")
        self.assertEqual(res2.data["tab_switches"], 1)  # Did not increment!

        # Check DB only has 1 record for this event_id
        self.assertEqual(
            IntegrityEvent.objects.filter(attempt=attempt, event_id="unique-tab-999").count(),
            1,
        )

    def test_consecutive_tab_hidden_without_tab_visible_does_not_double_count(self):
        c = Candidate.objects.create(
            full_name="Consecutive Student",
            register_number="CONSEC-01",
            college="College E",
            email="consec@example.com",
            department="CSE",
            year_of_study="2nd Year",
        )
        attempt = start_assessment_for_candidate(c, self.config)
        token = generate_candidate_token(str(c.id), str(attempt.id))
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        # First hidden transition
        r1 = self.client.post(
            f"/api/assessment/attempts/{attempt.id}/integrity-event/",
            {"event_type": "TAB_HIDDEN", "event_id": "h-1"},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(r1.data["tab_switches"], 1)

        # Second hidden transition without TAB_VISIBLE in between
        r2 = self.client.post(
            f"/api/assessment/attempts/{attempt.id}/integrity-event/",
            {"event_type": "TAB_HIDDEN", "event_id": "h-2"},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(r2.data["tab_switches"], 1)  # Remains 1

        attempt.refresh_from_db()
        self.assertEqual(attempt.tab_switch_count, 1)

    def test_fullscreen_exit_does_not_consume_tab_switches(self):
        c = Candidate.objects.create(
            full_name="FS Student",
            register_number="FS-01",
            college="College E",
            email="fs@example.com",
            department="CSE",
            year_of_study="2nd Year",
        )
        attempt = start_assessment_for_candidate(c, self.config)
        token = generate_candidate_token(str(c.id), str(attempt.id))
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        res = self.client.post(
            f"/api/assessment/attempts/{attempt.id}/integrity-event/",
            {"event_type": "FULLSCREEN_EXIT", "event_id": "fs-evt-1"},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(res.status_code, 200)

        attempt.refresh_from_db()
        self.assertEqual(attempt.fullscreen_exit_count, 1)
        self.assertEqual(attempt.tab_switch_count, 0)

    def test_admin_dashboard_diagnostic_metrics(self):
        admin = User.objects.create_superuser(
            username="admindiag",
            email="admindiag@example.com",
            password="adminpassword123",
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
        )
        self.client.force_login(admin)

        res = self.client.get("/admin/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("assessment_candidates_count", res.context)
        self.assertIn("assessment_in_progress_count", res.context)
        self.assertIn("assessment_submitted_count", res.context)
        self.assertIn("assessment_timed_out_count", res.context)
        self.assertIn("assessment_flagged_count", res.context)
        self.assertIn("assessment_aptitude_questions_count", res.context)
        self.assertIn("assessment_coding_questions_count", res.context)
        self.assertIn("assessment_total_questions_count", res.context)
        self.assertEqual(res.context["assessment_total_questions_count"], 60)
        self.assertEqual(res.context["assessment_aptitude_questions_count"], 30)
        self.assertEqual(res.context["assessment_coding_questions_count"], 30)

    def test_assessment_config_model_validation(self):
        # Invalid duration
        cfg = AssessmentConfig(
            title="Bad Duration",
            duration_minutes=0,
            total_marks=50,
            aptitude_count=25,
            coding_count=25,
            max_attempts=1,
            max_tab_switches_warning=3,
        )
        with self.assertRaises(ValidationError):
            cfg.clean()

        # Total marks does not equal aptitude + coding
        cfg_marks = AssessmentConfig(
            title="Bad Marks",
            duration_minutes=60,
            total_marks=45,
            aptitude_count=25,
            coding_count=25,
            max_attempts=1,
            max_tab_switches_warning=3,
        )
        with self.assertRaises(ValidationError):
            cfg_marks.clean()

        # Tab switch limit < 1
        cfg_tab = AssessmentConfig(
            title="Bad Tab Limit",
            duration_minutes=60,
            total_marks=50,
            aptitude_count=25,
            coding_count=25,
            max_attempts=1,
            max_tab_switches_warning=0,
        )
        with self.assertRaises(ValidationError):
            cfg_tab.clean()


class CSLAdminPanelAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.config = AssessmentConfig.objects.create(
            title="CSL Initial Assessment",
            duration_minutes=60,
            total_marks=50,
            aptitude_count=25,
            coding_count=25,
            is_active=True,
        )
        self.admin_user = User.objects.create_user(
            username="csladmin",
            email="admin@csl.com",
            password="AdminPassword123!",
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
            is_staff=True,
            is_superuser=True,
        )
        self.student_user = User.objects.create_user(
            username="cslstudent",
            email="student@csl.com",
            password="StudentPassword123!",
            role=User.Role.STUDENT,
            status=User.AccountStatus.ACTIVE,
            is_staff=False,
            is_superuser=False,
        )
        self.candidate = Candidate.objects.create(
            full_name="Pooja Sharma",
            register_number="721721U999",
            college="Rathinam College",
            email="pooja@rathinam.in",
            department="B.Tech AI",
            year_of_study="3rd Year",
        )
        self.attempt = AssessmentAttempt.objects.create(
            candidate=self.candidate,
            config=self.config,
            state=AssessmentAttempt.State.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=45),
            submitted_at=timezone.now(),
            aptitude_score=20,
            coding_score=22,
            total_score=42,
            percentage=84.0,
        )

    def test_anonymous_and_student_denied_admin_apis(self):
        # 1. Anonymous access is denied
        res = self.client.get("/api/csl-admin/stats/")
        self.assertIn(res.status_code, [401, 403])

        # 2. Student login is denied
        self.client.force_login(self.student_user)
        res_student = self.client.get("/api/csl-admin/stats/")
        self.assertEqual(res_student.status_code, 403)

    def test_admin_can_access_stats_and_candidates(self):
        self.client.force_login(self.admin_user)
        res_stats = self.client.get("/api/csl-admin/stats/")
        self.assertEqual(res_stats.status_code, 200)
        self.assertEqual(res_stats.data["candidates_count"], 1)
        self.assertEqual(res_stats.data["submitted_count"], 1)

        res_cand = self.client.get("/api/csl-admin/candidates/")
        self.assertEqual(res_cand.status_code, 200)
        self.assertEqual(len(res_cand.data), 1)
        self.assertEqual(res_cand.data[0]["full_name"], "Pooja Sharma")

    def test_admin_question_crud_and_toggle(self):
        self.client.force_login(self.admin_user)
        # Create
        q_data = {
            "prompt": "What is Python's list comprehension?",
            "section_type": "CODING",
            "category": "Python Basics",
            "difficulty": "EASY",
            "option_a": "A syntactic construct",
            "option_b": "A database query",
            "option_c": "A network protocol",
            "option_d": "A compiler tool",
            "correct_option": "A",
            "explanation": "Concise way to create lists.",
            "is_active": True,
        }
        res_create = self.client.post("/api/csl-admin/questions/", q_data, content_type="application/json")
        self.assertEqual(res_create.status_code, 201)
        q_id = res_create.data["id"]

        # Toggle
        res_toggle = self.client.post(f"/api/csl-admin/questions/{q_id}/toggle/")
        self.assertEqual(res_toggle.status_code, 200)
        self.assertFalse(res_toggle.data["is_active"])

    def test_admin_config_update_validation(self):
        self.client.force_login(self.admin_user)
        # Invalid config (total_marks != apt + cod)
        bad_data = {
            "duration_minutes": 60,
            "total_marks": 60,
            "aptitude_count": 25,
            "coding_count": 25,
        }
        res_bad = self.client.put("/api/csl-admin/config/", bad_data, content_type="application/json")
        self.assertEqual(res_bad.status_code, 400)

        # Valid config
        good_data = {
            "duration_minutes": 75,
            "total_marks": 50,
            "aptitude_count": 25,
            "coding_count": 25,
        }
        res_good = self.client.put("/api/csl-admin/config/", good_data, content_type="application/json")
        self.assertEqual(res_good.status_code, 200)
        self.assertEqual(res_good.data["duration_minutes"], 75)

    def test_admin_results_and_review(self):
        self.client.force_login(self.admin_user)
        res_results = self.client.get("/api/csl-admin/results/")
        self.assertEqual(res_results.status_code, 200)
        self.assertEqual(len(res_results.data), 1)
        self.assertEqual(res_results.data[0]["total_score"], 42)

        res_review = self.client.get(f"/api/csl-admin/attempts/{self.attempt.id}/review/")
        self.assertEqual(res_review.status_code, 200)
        self.assertEqual(res_review.data["candidate"]["full_name"], "Pooja Sharma")

    def test_admin_integrity_events_and_review_workflow(self):
        self.client.force_login(self.admin_user)

        event = IntegrityEvent.objects.create(
            attempt=self.attempt,
            event_type=IntegrityEvent.EventType.TAB_HIDDEN,
            metadata={"count": 1, "action": "WARNING"},
            event_id="evt_test_001",
        )

        # 1. Fetch list
        res_list = self.client.get("/api/csl-admin/integrity-events/")
        self.assertEqual(res_list.status_code, 200)
        self.assertTrue(len(res_list.data) >= 1)
        item = [e for e in res_list.data if e["id"] == event.id][0]
        self.assertEqual(item["event_type"], "TAB_HIDDEN")
        self.assertFalse(item["is_reviewed"])

        # 2. Filter by is_reviewed=false
        res_filtered = self.client.get("/api/csl-admin/integrity-events/?is_reviewed=false")
        self.assertEqual(res_filtered.status_code, 200)
        self.assertTrue(any(e["id"] == event.id for e in res_filtered.data))

        # 3. Mark as reviewed with notes
        review_payload = {
            "is_reviewed": True,
            "review_notes": "Reviewed tab switch. Verified benign momentary blur.",
        }
        res_review = self.client.post(
            f"/api/csl-admin/integrity-events/{event.id}/review/",
            review_payload,
            content_type="application/json",
        )
        self.assertEqual(res_review.status_code, 200)
        self.assertTrue(res_review.data["event"]["is_reviewed"])
        self.assertEqual(res_review.data["event"]["review_notes"], "Reviewed tab switch. Verified benign momentary blur.")
        self.assertEqual(res_review.data["event"]["reviewed_by_name"], self.admin_user.username)

        # 4. Verify attempt review includes integrity event without 500 error
        res_attempt_review = self.client.get(f"/api/csl-admin/attempts/{self.attempt.id}/review/")
        self.assertEqual(res_attempt_review.status_code, 200)
        self.assertEqual(len(res_attempt_review.data["integrity_events"]), 1)
        self.assertEqual(res_attempt_review.data["integrity_events"][0]["id"], event.id)

    def test_admin_question_bulk_update(self):
        self.client.force_login(self.admin_user)

        q1 = QuestionBank.objects.create(
            prompt="Bulk Test Q1",
            section_type=QuestionBank.SectionType.APTITUDE,
            category="Arithmetic",
            difficulty="EASY",
            option_a="1", option_b="2", option_c="3", option_d="4",
            correct_option="A",
            is_active=True,
        )
        q2 = QuestionBank.objects.create(
            prompt="Bulk Test Q2",
            section_type=QuestionBank.SectionType.APTITUDE,
            category="Arithmetic",
            difficulty="EASY",
            option_a="1", option_b="2", option_c="3", option_d="4",
            correct_option="B",
            is_active=True,
        )

        bulk_payload = {
            "ids": [q1.id, q2.id],
            "difficulty": "HARD",
            "category": "Advanced Quantitative",
            "is_active": False,
        }
        res_bulk = self.client.post(
            "/api/csl-admin/questions/bulk-update/",
            bulk_payload,
            content_type="application/json",
        )
        self.assertEqual(res_bulk.status_code, 200)
        self.assertEqual(res_bulk.data["updated_count"], 2)

        q1.refresh_from_db()
        q2.refresh_from_db()
        self.assertEqual(q1.difficulty, "HARD")
        self.assertEqual(q1.category, "Advanced Quantitative")
        self.assertFalse(q1.is_active)
        self.assertEqual(q2.difficulty, "HARD")
        self.assertEqual(q2.category, "Advanced Quantitative")
        self.assertFalse(q2.is_active)


class CollegeAndAssessmentManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            email="superadmin@csl.com",
            username="superadmin",
            password="adminpassword123",
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
            is_staff=True,
            is_superuser=True,
        )

        # Seed 30 Aptitude + 30 Coding questions
        apt_list = [
            QuestionBank(
                prompt=f"Aptitude Test Q{i+1}",
                section_type=QuestionBank.SectionType.APTITUDE,
                category="Quantitative",
                difficulty="MEDIUM",
                option_a=f"Opt A {i+1}", option_b=f"Opt B {i+1}", option_c=f"Opt C {i+1}", option_d=f"Opt D {i+1}",
                correct_option="A",
                is_active=True,
            )
            for i in range(30)
        ]
        QuestionBank.objects.bulk_create(apt_list)

        cod_list = [
            QuestionBank(
                prompt=f"Coding Test Q{i+1}",
                section_type=QuestionBank.SectionType.CODING,
                category="Python",
                difficulty="MEDIUM",
                option_a=f"Opt A {i+1}", option_b=f"Opt B {i+1}", option_c=f"Opt C {i+1}", option_d=f"Opt D {i+1}",
                correct_option="B",
                is_active=True,
            )
            for i in range(30)
        ]
        QuestionBank.objects.bulk_create(cod_list)

    def test_college_crud_and_status_toggle(self):
        self.client.force_login(self.admin_user)

        # Create College
        res = self.client.post(
            "/api/csl-admin/colleges/",
            {
                "name": "PSG College of Technology",
                "code": "PSG TECH",
                "location": "Coimbatore",
                "contact_email": "tpo@psgtech.edu",
                "contact_phone": "9876543210",
                "admin_contact_name": "Dr. Placement Officer",
            },
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201)
        college_id = res.data["id"]
        self.assertEqual(res.data["code"], "PSG TECH")
        self.assertTrue(res.data["is_active"])

        # Check Audit log created
        log = AssessmentAuditLog.objects.filter(entity_type="COLLEGE", entity_id=str(college_id)).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action, AssessmentAuditLog.Action.COLLEGE_CREATED)

        # Toggle Status
        tog_res = self.client.post(f"/api/csl-admin/colleges/{college_id}/toggle-status/")
        self.assertEqual(tog_res.status_code, 200)
        self.assertFalse(tog_res.data["is_active"])

    def test_college_candidate_csv_import(self):
        self.client.force_login(self.admin_user)
        college = College.objects.create(name="Kumaraguru College of Technology", code="KCT", is_active=True)

        csv_content = (
            "full_name,register_number,email,department,year_of_study,phone_number\n"
            "Ananya S,717821L101,ananya@kct.ac.in,ECE,Final Year,9876501234\n"
            "Barath K,717821L102,barath@kct.ac.in,CSE,3rd Year,9876505678\n"
        )
        res = self.client.post(
            f"/api/csl-admin/colleges/{college.id}/import-candidates/",
            {"csv_content": csv_content},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["created_count"], 2)
        self.assertEqual(Candidate.objects.filter(college_ref=college).count(), 2)

    def test_assessment_lifecycle_and_opening_control(self):
        self.client.force_login(self.admin_user)
        college = College.objects.create(name="Amrita Vishwa Vidyapeetham", code="AMRITA", is_active=True)

        # 1. Create Assessment (starts in DRAFT)
        create_res = self.client.post(
            "/api/csl-admin/assessments/",
            {
                "code": "AMRITA-DIAG-01",
                "title": "Amrita Diagnostic Round 1",
                "duration_minutes": 45,
                "total_marks": 20,
                "aptitude_count": 10,
                "coding_count": 10,
                "max_attempts": 1,
                "eligible_college_ids": [college.id],
            },
            content_type="application/json",
        )
        self.assertEqual(create_res.status_code, 201)
        assessment_id = create_res.data["id"]
        self.assertEqual(create_res.data["status"], "DRAFT")

        # Create candidate for this college
        candidate = Candidate.objects.create(
            full_name="Deepak V",
            register_number="CB.EN.U4CSE21001",
            college_ref=college,
            college=college.name,
            email="deepak@cb.amrita.edu",
            phone_number="9876543210",
            is_active=True,
        )
        token = generate_candidate_token(str(candidate.id))
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        # Candidate attempts to start DRAFT assessment -> Must be rejected (400)
        start_res = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": assessment_id},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(start_res.status_code, 400)
        self.assertIn("not accepting new attempts", start_res.data["detail"])

        # 2. Admin prepares assessment -> READY
        prep_res = self.client.post(f"/api/csl-admin/assessments/{assessment_id}/prepare/")
        self.assertEqual(prep_res.status_code, 200)
        self.assertEqual(prep_res.data["status"], "READY")

        # 3. Admin opens assessment -> OPEN
        open_res = self.client.post(f"/api/csl-admin/assessments/{assessment_id}/open/")
        self.assertEqual(open_res.status_code, 200)
        self.assertEqual(open_res.data["status"], "OPEN")

        # 4. Now candidate can start assessment
        start_ok_res = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": assessment_id},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(start_ok_res.status_code, 200)
        self.assertEqual(start_ok_res.data["assessment_code"], "AMRITA-DIAG-01")

        # 5. Non-enrolled college candidate cannot start
        other_college = College.objects.create(name="Other College", code="OTHER", is_active=True)
        other_candidate = Candidate.objects.create(
            full_name="Stranger",
            register_number="STR-001",
            college_ref=other_college,
            college=other_college.name,
            email="stranger@other.edu",
            phone_number="9876543210",
            is_active=True,
        )
        stranger_token = generate_candidate_token(str(other_candidate.id))
        stranger_headers = {"HTTP_AUTHORIZATION": f"Bearer {stranger_token}"}

        stranger_res = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": assessment_id},
            content_type="application/json",
            **stranger_headers,
        )
        self.assertEqual(stranger_res.status_code, 400)
        self.assertIn("not enrolled", stranger_res.data["detail"])

        # 6. Admin closes assessment with STRICT_CUTOFF -> active attempts auto-finalized
        close_res = self.client.post(
            f"/api/csl-admin/assessments/{assessment_id}/close/",
            {"close_policy": "STRICT_CUTOFF"},
            content_type="application/json",
        )
        self.assertEqual(close_res.status_code, 200)
        self.assertEqual(close_res.data["status"], "CLOSED")

        # The candidate's attempt should now be TIMED_OUT / finalized
        attempt = AssessmentAttempt.objects.get(id=start_ok_res.data["id"])
        self.assertEqual(attempt.state, AssessmentAttempt.State.TIMED_OUT)

    def test_question_pool_creation_update_and_filtering(self):
        self.client.force_login(self.admin_user)

        # Create two assessments
        a1 = Assessment.objects.create(
            code="POOL-TEST-01",
            title="Pool Assessment 1",
            duration_minutes=60,
            total_marks=50,
            aptitude_count=25,
            coding_count=25,
        )
        a2 = Assessment.objects.create(
            code="POOL-TEST-02",
            title="Pool Assessment 2",
            duration_minutes=60,
            total_marks=50,
            aptitude_count=25,
            coding_count=25,
        )

        # 1. Create Question with valid assessment_id
        q_payload = {
            "prompt": "What is the output of len([1, 2, 3]) in Python?",
            "section_type": "CODING",
            "category": "Python Basics",
            "difficulty": "EASY",
            "option_a": "3",
            "option_b": "2",
            "option_c": "4",
            "option_d": "Error",
            "correct_option": "A",
            "explanation": "len returns the number of elements in a list.",
            "is_active": True,
            "assessment_id": str(a1.id),
        }
        res_create = self.client.post("/api/csl-admin/questions/", q_payload, content_type="application/json")
        self.assertEqual(res_create.status_code, 201)
        q_id = res_create.data["id"]
        self.assertEqual(res_create.data["assessment_id"], str(a1.id))
        self.assertEqual(res_create.data["assessment_title"], "Pool Assessment 1")
        self.assertTrue(a1.questions.filter(id=q_id).exists())

        # 2. Create Question with invalid assessment_id -> 400
        bad_payload = q_payload.copy()
        bad_payload["assessment_id"] = "00000000-0000-0000-0000-000000000000"
        bad_payload["prompt"] = "Invalid assessment question"
        res_bad = self.client.post("/api/csl-admin/questions/", bad_payload, content_type="application/json")
        self.assertEqual(res_bad.status_code, 400)
        self.assertIn("assessment_id", res_bad.data)

        # 3. Update Question reassigning to a2 -> 200
        res_update = self.client.put(
            f"/api/csl-admin/questions/{q_id}/",
            {"assessment_id": str(a2.id)},
            content_type="application/json",
        )
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(res_update.data["assessment_id"], str(a2.id))
        self.assertEqual(res_update.data["assessment_title"], "Pool Assessment 2")
        self.assertTrue(a2.questions.filter(id=q_id).exists())
        self.assertFalse(a1.questions.filter(id=q_id).exists())

        # 4. Filter by assessment_id
        res_filter_a2 = self.client.get(f"/api/csl-admin/questions/?assessment_id={a2.id}")
        self.assertEqual(res_filter_a2.status_code, 200)
        ids_a2 = [item["id"] for item in res_filter_a2.data]
        self.assertIn(q_id, ids_a2)

        res_filter_a1 = self.client.get(f"/api/csl-admin/questions/?assessment_id={a1.id}")
        self.assertEqual(res_filter_a1.status_code, 200)
        ids_a1 = [item["id"] for item in res_filter_a1.data]
        self.assertNotIn(q_id, ids_a1)




