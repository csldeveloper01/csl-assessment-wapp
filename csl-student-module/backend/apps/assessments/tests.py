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
    AssessmentSection,
    AssessmentSectionAllocation,
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
        from apps.users.models import User
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin_comp",
            email="admin_comp@csl.com",
            password="AdminPassword123!",
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
            is_staff=True,
            is_superuser=True,
        )
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

        # 6. Finalize Attempt (scores concealed from student view)
        fin_res = self.client.post(f"/api/assessment/attempts/{attempt_id}/finalize/", **attempt_headers)
        self.assertEqual(fin_res.status_code, 200)
        self.assertEqual(fin_res.data["state"], AssessmentAttempt.State.SUBMITTED)
        self.assertNotIn("total_score", fin_res.data)
        self.assertIn("message", fin_res.data)
        self.assertEqual(fin_res.data["message"], "Assessment Completed")

        # 7. Student Results View: score withheld, completion state confirmed
        res_view_student = self.client.get(f"/api/assessment/attempts/{attempt_id}/result/", **attempt_headers)
        self.assertEqual(res_view_student.status_code, 200)
        self.assertNotIn("total_score", res_view_student.data)
        self.assertNotIn("breakdown", res_view_student.data)
        self.assertEqual(res_view_student.data["message"], "Assessment Completed")

        # 8. Administrative Result Access: authorized staff access to full verified scores and breakdown
        self.client.force_login(self.admin_user)
        admin_res_view = self.client.get(f"/api/assessment/attempts/{attempt_id}/result/")
        self.assertEqual(admin_res_view.status_code, 200)
        self.assertEqual(admin_res_view.data["candidate_name"], "Karthik R")
        self.assertIn("total_score", admin_res_view.data)
        self.assertEqual(admin_res_view.data["year_of_study"], "3rd Year")
        self.assertIn("breakdown", admin_res_view.data)

        breakdown = admin_res_view.data["breakdown"]
        apt = breakdown["aptitude"]
        cod = breakdown["coding"]
        self.assertEqual(apt["total"], 25)
        self.assertEqual(cod["total"], 25)
        self.assertEqual(apt["correct"] + apt["incorrect"] + apt["unattempted"], 25)
        self.assertEqual(cod["correct"] + cod["incorrect"] + cod["unattempted"], 25)
        self.assertEqual(apt["correct"] + cod["correct"], admin_res_view.data["total_score"])
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

        # Legacy Django Admin route /admin/ is retired and returns 404
        res_admin = self.client.get("/admin/")
        self.assertEqual(res_admin.status_code, 404)

        # Active diagnostic metrics are served via the React Admin API endpoint
        res = self.client.get("/api/csl-admin/stats/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("candidates_count", res.data)
        self.assertIn("in_progress_count", res.data)
        self.assertIn("submitted_count", res.data)
        self.assertIn("timed_out_count", res.data)
        self.assertIn("flagged_count", res.data)
        self.assertIn("aptitude_questions_count", res.data)
        self.assertIn("coding_questions_count", res.data)
        self.assertIn("total_questions_count", res.data)
        self.assertEqual(res.data["total_questions_count"], 60)
        self.assertEqual(res.data["aptitude_questions_count"], 30)
        self.assertEqual(res.data["coding_questions_count"], 30)

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

    def test_admin_question_creation_without_category(self):
        """
        Verify creating a question does not require a category field.
        The question is saved, assigned to the selected assessment pool,
        and classified by section without any category validation error.
        """
        self.client.force_login(self.admin_user)
        assessment = Assessment.objects.create(
            code="TST-NO-CAT",
            title="Test No Category Assessment",
            duration_minutes=30,
            total_marks=20,
            status=Assessment.Status.DRAFT,
        )
        sec, _ = AssessmentSection.objects.get_or_create(
            code="LOGICAL",
            defaults={"name": "Logical Reasoning", "order": 3},
        )
        q_data = {
            "assessment_id": str(assessment.id),
            "prompt": "Which shape completes the pattern?",
            "section_type": "LOGICAL",
            "difficulty": "MEDIUM",
            "option_a": "Triangle",
            "option_b": "Circle",
            "option_c": "Square",
            "option_d": "Hexagon",
            "correct_option": "B",
            "explanation": "Circle follows the alternating pattern.",
            "is_active": True,
        }
        res_create = self.client.post("/api/csl-admin/questions/", q_data, content_type="application/json")
        self.assertEqual(res_create.status_code, 201)
        q_id = res_create.data["id"]

        # Confirm question saved in database without requiring category
        q = QuestionBank.objects.get(id=q_id)
        self.assertEqual(q.prompt, "Which shape completes the pattern?")
        self.assertEqual(q.section_type, "LOGICAL")
        self.assertEqual(q.category, "")
        self.assertEqual(q.section, sec)

        # Confirm question is in the target assessment's pool
        self.assertIn(q, assessment.questions.all())

        # Verify querying the assessment questions returns the created question
        res_list = self.client.get(f"/api/csl-admin/questions/?assessment_id={assessment.id}")
        self.assertEqual(res_list.status_code, 200)
        self.assertTrue(any(item["id"] == q_id for item in res_list.data))

    def test_admin_assign_and_update_colleges_on_existing_assessment(self):
        """
        Verify administrators can inspect, add, and remove eligible colleges on an existing assessment.
        """
        self.client.force_login(self.admin_user)
        col_a = College.objects.create(name="Alpha Institute", code="ALPHA")
        col_b = College.objects.create(name="Beta Engineering College", code="BETA")

        assessment = Assessment.objects.create(
            code="TST-COL-01",
            title="Institutional Eligibility Assessment",
            duration_minutes=45,
            total_marks=20,
            status=Assessment.Status.DRAFT,
        )
        assessment.eligible_colleges.add(col_a)

        # 1. GET college assignments endpoint
        url = f"/api/csl-admin/assessments/{assessment.id}/assign-colleges/"
        res_get = self.client.get(url)
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.data["assessment_id"], str(assessment.id))
        self.assertIn(col_a.id, res_get.data["assigned_college_ids"])

        # 2. Add College B (assign A and B)
        payload_add = {"college_ids": [col_a.id, col_b.id]}
        res_post_add = self.client.post(url, payload_add, content_type="application/json")
        self.assertEqual(res_post_add.status_code, 200)
        self.assertEqual(len(res_post_add.data["eligible_colleges"]), 2)

        assessment.refresh_from_db()
        self.assertEqual(assessment.eligible_colleges.count(), 2)
        self.assertTrue(assessment.eligible_colleges.filter(id=col_a.id).exists())
        self.assertTrue(assessment.eligible_colleges.filter(id=col_b.id).exists())

        # 3. Remove College A (keep only College B)
        payload_remove = {"college_ids": [col_b.id]}
        res_post_rem = self.client.post(url, payload_remove, content_type="application/json")
        self.assertEqual(res_post_rem.status_code, 200)
        self.assertEqual(len(res_post_rem.data["eligible_colleges"]), 1)

        assessment.refresh_from_db()
        self.assertEqual(assessment.eligible_colleges.count(), 1)
        self.assertFalse(assessment.eligible_colleges.filter(id=col_a.id).exists())
        self.assertTrue(assessment.eligible_colleges.filter(id=col_b.id).exists())

    def test_college_eligibility_enforcement_for_student_registration_and_start(self):
        """
        Verify student registration and start endpoints strictly enforce updated college assignments:
        - Candidates from newly assigned colleges can register and start.
        - Candidates from unassigned or removed colleges are denied.
        """
        col_enrolled = College.objects.create(name="Enrolled Institute", code="ENROLLED")
        col_removed = College.objects.create(name="Removed Institute", code="REMOVED")

        # Create OPEN assessment with enrolled college and sufficient questions
        assessment = Assessment.objects.create(
            code="TST-ELIG-01",
            title="Active Eligibility Test",
            duration_minutes=30,
            total_marks=2,
            aptitude_count=1,
            coding_count=1,
            status=Assessment.Status.OPEN,
        )
        assessment.eligible_colleges.add(col_enrolled)

        q_apt = QuestionBank.objects.create(
            prompt="Aptitude sample question",
            section_type="APTITUDE",
            difficulty="EASY",
            option_a="1",
            option_b="2",
            option_c="3",
            option_d="4",
            correct_option="A",
            is_active=True,
        )
        q_cod = QuestionBank.objects.create(
            prompt="Coding sample question",
            section_type="CODING",
            difficulty="EASY",
            option_a="1",
            option_b="2",
            option_c="3",
            option_d="4",
            correct_option="B",
            is_active=True,
        )
        assessment.questions.add(q_apt, q_cod)

        # 1. Candidate from removed / unassigned college attempts registration for this assessment
        reg_payload_removed = {
            "full_name": "Student Removed",
            "register_number": "REG-REM-01",
            "email": "student.removed@example.com",
            "college_id": col_removed.id,
            "department": "Computer Science",
            "year_of_study": "3rd Year",
            "phone_number": "9876543210",
            "assessment_id": str(assessment.id),
        }
        res_reg_rem = self.client.post("/api/assessment/register/", reg_payload_removed, content_type="application/json")
        self.assertEqual(res_reg_rem.status_code, 400)
        self.assertIn("not eligible", res_reg_rem.data.get("detail", ""))

        # 2. Candidate from enrolled college registers successfully
        reg_payload_enrolled = {
            "full_name": "Student Enrolled",
            "register_number": "REG-ENR-01",
            "email": "student.enrolled@example.com",
            "college_id": col_enrolled.id,
            "department": "Computer Science",
            "year_of_study": "3rd Year",
            "phone_number": "9876543211",
            "assessment_id": str(assessment.id),
        }
        res_reg_enr = self.client.post("/api/assessment/register/", reg_payload_enrolled, content_type="application/json")
        self.assertEqual(res_reg_enr.status_code, 201)
        token_enr = res_reg_enr.data["assessment_token"]

        # 3. Candidate from enrolled college starts assessment successfully
        res_start = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(assessment.id)},
            content_type="application/json",
            HTTP_X_ASSESSMENT_TOKEN=token_enr,
        )
        self.assertEqual(res_start.status_code, 200)
        self.assertEqual(res_start.data["state"], "IN_PROGRESS")

    def test_college_assignment_preserves_historical_data_and_enforces_lifecycle(self):
        """
        Verify historical attempt data is preserved when college assignments change,
        and lifecycle rules prevent invalid states (e.g. archived assessment, empty open assessment).
        """
        self.client.force_login(self.admin_user)
        col = College.objects.create(name="Heritage College", code="HERITAGE")
        col_new = College.objects.create(name="New College", code="NEWCOL")

        assessment = Assessment.objects.create(
            code="TST-HIST-01",
            title="Historical Data Integrity Assessment",
            duration_minutes=30,
            total_marks=2,
            aptitude_count=1,
            coding_count=1,
            status=Assessment.Status.OPEN,
        )
        assessment.eligible_colleges.add(col)

        cand = Candidate.objects.create(
            full_name="History Candidate",
            register_number="HIST-001",
            email="history@csl.com",
            college_ref=col,
            college=col.name,
        )
        attempt = AssessmentAttempt.objects.create(
            candidate=cand,
            assessment=assessment,
            config=self.config,
            state=AssessmentAttempt.State.SUBMITTED,
            started_at=timezone.now() - timedelta(minutes=20),
            submitted_at=timezone.now(),
            total_score=2,
            percentage=100.0,
        )

        url = f"/api/csl-admin/assessments/{assessment.id}/assign-colleges/"

        # 1. Update colleges to replace col with col_new
        res = self.client.post(url, {"college_ids": [col_new.id]}, content_type="application/json")
        self.assertEqual(res.status_code, 200)

        # Confirm historical data is preserved
        attempt.refresh_from_db()
        self.assertEqual(attempt.state, AssessmentAttempt.State.SUBMITTED)
        self.assertEqual(attempt.total_score, 2)
        self.assertEqual(attempt.candidate.college_ref, col)
        self.assertEqual(AssessmentAttempt.objects.filter(assessment=assessment).count(), 1)

        # 2. Lifecycle: Cannot remove all colleges from an OPEN assessment
        res_empty = self.client.post(url, {"college_ids": []}, content_type="application/json")
        self.assertEqual(res_empty.status_code, 400)
        self.assertIn("must have at least one eligible college", res_empty.data.get("detail", ""))

        # 3. Lifecycle: Cannot modify college assignments on an ARCHIVED assessment
        assessment.status = Assessment.Status.ARCHIVED
        assessment.save(update_fields=["status"])
        res_arch = self.client.post(url, {"college_ids": [col.id]}, content_type="application/json")
        self.assertEqual(res_arch.status_code, 400)
        self.assertIn("archived", res_arch.data.get("detail", "").lower())

    def test_admin_config_update_validation(self):
        self.client.force_login(self.admin_user)
        # Invalid platform-wide config (max_attempts < 1, max_tab_switches < 1)
        bad_data = {
            "max_attempts": 0,
            "max_tab_switches_warning": 0,
        }
        res_bad = self.client.put("/api/csl-admin/config/", bad_data, content_type="application/json")
        self.assertEqual(res_bad.status_code, 400)

        # Valid platform-wide config
        good_data = {
            "title": "CSL Global Platform Configuration",
            "max_attempts": 2,
            "max_tab_switches_warning": 3,
        }
        res_good = self.client.put("/api/csl-admin/config/", good_data, content_type="application/json")
        self.assertEqual(res_good.status_code, 200)
        self.assertEqual(res_good.data["max_attempts"], 2)
        self.assertEqual(res_good.data["max_tab_switches_warning"], 3)

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


class RegressionAndDynamicSectionTests(TestCase):
    def setUp(self):
        from apps.users.models import User
        from apps.assessments.models import AssessmentSection, AssessmentSectionAllocation
        self.admin_user = User.objects.create_user(
            username="regression_admin",
            email="reg_admin@csl.internal",
            password="AdminPassword123!",
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
            is_staff=True,
            is_superuser=True,
        )
        self.college = College.objects.create(
            name="Regression College",
            code="REG_COL",
            is_active=True,
        )

    def test_cors_preflight_allows_custom_token(self):
        """
        Regression: Preflight OPTIONS request with x-assessment-token header
        must be allowed for https://csl-assessment-wapp.vercel.app origin.
        """
        response = self.client.options(
            "/api/assessment/start/",
            HTTP_ORIGIN="https://csl-assessment-wapp.vercel.app",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="x-assessment-token, content-type",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("Access-Control-Allow-Origin"),
            "https://csl-assessment-wapp.vercel.app",
        )
        allow_headers = response.headers.get("Access-Control-Allow-Headers", "").lower()
        self.assertIn("x-assessment-token", allow_headers)

        # Untrusted origin should NOT be reflected
        bad_response = self.client.options(
            "/api/assessment/start/",
            HTTP_ORIGIN="https://malicious-site.example.com",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="x-assessment-token",
        )
        self.assertNotEqual(
            bad_response.headers.get("Access-Control-Allow-Origin"),
            "https://malicious-site.example.com",
        )

    def test_idempotent_registration_lifecycle(self):
        """
        Regression: Candidates re-registering before start, during in-progress,
        and after completion must be handled idempotently according to policy.
        """
        # Create an open assessment for the college
        assessment = Assessment.objects.create(
            code="REG-ASSESS-01",
            title="Regression Assessment",
            status=Assessment.Status.OPEN,
            duration_minutes=30,
            total_marks=2,
            aptitude_count=1,
            coding_count=1,
            max_attempts=1,
        )
        assessment.eligible_colleges.add(self.college)

        # Create 1 aptitude and 1 coding question
        QuestionBank.objects.create(
            prompt="Aptitude Q1",
            section_type="APTITUDE",
            option_a="1", option_b="2", option_c="3", option_d="4",
            correct_option="A",
            is_active=True,
        )
        QuestionBank.objects.create(
            prompt="Coding Q1",
            section_type="CODING",
            option_a="1", option_b="2", option_c="3", option_d="4",
            correct_option="A",
            is_active=True,
        )

        reg_payload = {
            "full_name": "Suresh Kumar",
            "register_number": "REG-2026-001",
            "college_id": self.college.id,
            "email": "suresh@example.com",
            "department": "ECE",
            "year_of_study": "3rd Year",
            "phone_number": "9876543210",
        }

        # 1. Initial registration -> 201 Created, NEW_REGISTRATION
        res1 = self.client.post("/api/assessment/register/", reg_payload, content_type="application/json")
        self.assertEqual(res1.status_code, 201)
        self.assertEqual(res1.data["registration_status"], "NEW_REGISTRATION")
        self.assertFalse(res1.data["is_active_attempt"])
        self.assertFalse(res1.data["already_completed"])
        cand_id = res1.data["candidate_id"]
        token1 = res1.data["assessment_token"]

        # 2. Repeated registration BEFORE starting -> 200 OK, NOT_STARTED, no duplicate candidate
        res2 = self.client.post("/api/assessment/register/", reg_payload, content_type="application/json")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.data["registration_status"], "NOT_STARTED")
        self.assertEqual(res2.data["candidate_id"], cand_id)
        self.assertFalse(res2.data["is_active_attempt"])
        self.assertFalse(res2.data["already_completed"])
        self.assertEqual(Candidate.objects.filter(email="suresh@example.com").count(), 1)

        # 3. Start assessment attempt
        start_res = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token1}",
        )
        self.assertEqual(start_res.status_code, 200)
        attempt_id = start_res.data["id"]

        # 4. Repeated registration WHILE IN-PROGRESS -> 200 OK, IN_PROGRESS, preserves resume
        res3 = self.client.post("/api/assessment/register/", reg_payload, content_type="application/json")
        self.assertEqual(res3.status_code, 200)
        self.assertEqual(res3.data["registration_status"], "IN_PROGRESS")
        self.assertTrue(res3.data["is_active_attempt"])
        self.assertFalse(res3.data["already_completed"])
        self.assertEqual(res3.data["attempt_id"], attempt_id)

        # 5. Finalize assessment attempt
        attempt_token = start_res.data["assessment_token"]
        fin_res = self.client.post(
            f"/api/assessment/attempts/{attempt_id}/finalize/",
            HTTP_AUTHORIZATION=f"Bearer {attempt_token}",
        )
        self.assertEqual(fin_res.status_code, 200)

        # 6. Repeated registration AFTER FINALIZATION -> 200 OK, COMPLETED (max attempts reached)
        res4 = self.client.post("/api/assessment/register/", reg_payload, content_type="application/json")
        self.assertEqual(res4.status_code, 200)
        self.assertEqual(res4.data["registration_status"], "COMPLETED")
        self.assertFalse(res4.data["is_active_attempt"])
        self.assertTrue(res4.data["already_completed"])

    def test_dynamic_reusable_section_library_and_attempt_flow(self):
        """
        Regression: Admin creates reusable section, attaches to assessment with allocation,
        candidate takes assessment and snapshots are properly tagged with the section.
        """
        from apps.assessments.models import AssessmentSection, AssessmentSectionAllocation
        self.client.force_login(self.admin_user)

        # 1. Admin creates reusable section via API
        sec_res = self.client.post(
            "/api/csl-admin/sections/",
            {
                "name": "Logical Reasoning",
                "code": "LOGICAL",
                "description": "Critical thinking and logic puzzles",
                "is_active": True,
            },
            content_type="application/json",
        )
        self.assertEqual(sec_res.status_code, 201)
        sec_id = sec_res.data["id"]

        # 2. Add question to Question Bank for this dynamic section
        QuestionBank.objects.create(
            prompt="Logic Q1: If all A are B...",
            section_id=sec_id,
            section_type="LOGICAL",
            option_a="Yes", option_b="No", option_c="Maybe", option_d="Unknown",
            correct_option="A",
            is_active=True,
        )

        # 3. Create assessment with dynamic section allocation
        assess_res = self.client.post(
            "/api/csl-admin/assessments/",
            {
                "title": "Logic Test 2026",
                "code": "LOGIC-2026",
                "duration_minutes": 20,
                "total_marks": 2,
                "eligible_college_ids": [self.college.id],
                "sections": [
                    {
                        "section_id": sec_id,
                        "question_count": 1,
                        "marks_per_question": 2,
                    }
                ],
            },
            content_type="application/json",
        )
        self.assertEqual(assess_res.status_code, 201)
        assess_id = assess_res.data["id"]

        # 4. Open assessment
        open_res = self.client.post(f"/api/csl-admin/assessments/{assess_id}/open/")
        self.assertEqual(open_res.status_code, 200)

        # 5. Candidate registers and takes test
        cand_res = self.client.post(
            "/api/assessment/register/",
            {
                "full_name": "Priya V",
                "register_number": "PRIYA-001",
                "college_id": self.college.id,
                "email": "priya@example.com",
                "department": "IT",
                "year_of_study": "Final Year",
                "phone_number": "9123456789",
                "assessment_id": assess_id,
            },
            content_type="application/json",
        )
        self.assertEqual(cand_res.status_code, 201)
        cand_token = cand_res.data["assessment_token"]

        # 6. Start assessment
        start_res = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": assess_id},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {cand_token}",
        )
        self.assertEqual(start_res.status_code, 200)
        attempt_id = start_res.data["id"]
        questions = start_res.data["questions"]
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["section_type"], "LOGICAL")
        self.assertEqual(start_res.data["total_questions"], 2)  # max_marks is 2


class AdminAssessmentDetailViewRegressionTests(TestCase):
    def setUp(self):
        from apps.users.models import User
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin_detail_tester",
            email="admin_detail@csl.com",
            password="AdminPassword123!",
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
            is_staff=True,
            is_superuser=True,
        )
        self.college = College.objects.create(
            name="Testing Institute of Technology",
            code="TIT01",
            contact_email="tit@example.com",
            is_active=True,
        )
        self.assessment = Assessment.objects.create(
            code="DET-TEST-01",
            title="Detail View Test Assessment",
            duration_minutes=45,
            total_marks=50,
            aptitude_count=25,
            coding_count=25,
            status=Assessment.Status.DRAFT,
        )
        self.assessment.eligible_colleges.add(self.college)

    def test_admin_assessment_detail_requires_auth(self):
        url = f"/api/csl-admin/assessments/{self.assessment.id}/"
        res = self.client.get(url)
        self.assertIn(res.status_code, [401, 403])

    def test_admin_assessment_detail_success(self):
        self.client.force_login(self.admin)
        url = f"/api/csl-admin/assessments/{self.assessment.id}/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        data = res.data
        self.assertEqual(data["id"], str(self.assessment.id))
        self.assertEqual(data["code"], "DET-TEST-01")
        self.assertEqual(data["title"], "Detail View Test Assessment")
        self.assertIn("sections", data)
        self.assertIn("eligible_colleges", data)
        self.assertTrue(isinstance(data["eligible_colleges"], list))
        self.assertEqual(len(data["eligible_colleges"]), 1)
        self.assertEqual(data["eligible_colleges"][0]["code"], "TIT01")
        self.assertIn("audit_logs", data)

    def test_admin_assessment_detail_invalid_uuid(self):
        self.client.force_login(self.admin)
        url = "/api/csl-admin/assessments/not-a-valid-uuid/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 404)

    def test_admin_assessment_detail_non_existent_uuid(self):
        self.client.force_login(self.admin)
        random_uuid = uuid.uuid4()
        url = f"/api/csl-admin/assessments/{random_uuid}/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 404)


class AssessmentOpenRegressionTests(TestCase):
    def setUp(self):
        from apps.users.models import User
        from apps.assessments.models import AssessmentSection, AssessmentSectionAllocation
        self.client = Client()
        self.admin = User.objects.create_user(
            username="open_tester_admin",
            email="open_tester@csl.com",
            password="AdminPassword123!",
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
            is_staff=True,
            is_superuser=True,
        )
        self.college = College.objects.create(
            name="Alpha Engineering College",
            code="AEC01",
            contact_email="aec@example.com",
            is_active=True,
        )
        self.section_apt, _ = AssessmentSection.objects.get_or_create(
            code="APTITUDE",
            defaults={"name": "General Aptitude", "is_active": True, "order": 1},
        )
        self.section_cod, _ = AssessmentSection.objects.get_or_create(
            code="CODING",
            defaults={"name": "Coding Fundamentals", "is_active": True, "order": 2},
        )

        # Seed 10 questions for each section
        for i in range(10):
            QuestionBank.objects.create(
                prompt=f"Aptitude Q{i+1}",
                section=self.section_apt,
                section_type="APTITUDE",
                difficulty="MEDIUM",
                option_a="1", option_b="2", option_c="3", option_d="4",
                correct_option="A",
                is_active=True,
            )
            QuestionBank.objects.create(
                prompt=f"Coding Q{i+1}",
                section=self.section_cod,
                section_type="CODING",
                difficulty="MEDIUM",
                option_a="1", option_b="2", option_c="3", option_d="4",
                correct_option="B",
                is_active=True,
            )

    def test_open_assessment_fails_insufficient_bank_returns_structured_bank_error(self):
        """
        When question bank lacks enough questions, /open/ returns 400 with a string detail
        and structured bank_error (not an unformatted dict that crashes React),
        and the assessment status remains in its previous valid state (DRAFT).
        """
        self.client.force_login(self.admin)
        from apps.assessments.models import AssessmentSection, AssessmentSectionAllocation

        unique_sec = AssessmentSection.objects.create(
            name="Advanced Quantum",
            code="QUANTUM_TEST",
            is_active=True,
            order=1,
        )

        assessment = Assessment.objects.create(
            code="INSUF-01",
            title="Insufficient Bank Test",
            duration_minutes=30,
            total_marks=20,
            status=Assessment.Status.DRAFT,
        )
        assessment.eligible_colleges.add(self.college)

        # Requires 20 questions, but bank has 0
        AssessmentSectionAllocation.objects.create(
            assessment=assessment,
            section=unique_sec,
            question_count=20,
            marks_per_question=1,
            order=1,
        )

        url = f"/api/csl-admin/assessments/{assessment.id}/open/"
        res = self.client.post(url)
        self.assertEqual(res.status_code, 400)

        # Verify structured response shape
        self.assertIn("detail", res.data)
        self.assertIsInstance(res.data["detail"], str)
        self.assertIn("bank_error", res.data)
        self.assertIsInstance(res.data["bank_error"], str)
        self.assertIn("Insufficient", res.data["detail"])

        # Assessment MUST remain in DRAFT status
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, Assessment.Status.DRAFT)
        self.assertIsNone(assessment.opened_at)

    def test_open_assessment_fails_when_no_colleges_assigned(self):
        """
        Opening an assessment with no eligible colleges returns 400 with string detail.
        """
        self.client.force_login(self.admin)
        from apps.assessments.models import AssessmentSectionAllocation

        assessment = Assessment.objects.create(
            code="NO-COLLEGE-01",
            title="No College Test",
            duration_minutes=30,
            total_marks=10,
            status=Assessment.Status.DRAFT,
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment,
            section=self.section_apt,
            question_count=5,
            marks_per_question=1,
            order=1,
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment,
            section=self.section_cod,
            question_count=5,
            marks_per_question=1,
            order=2,
        )

        url = f"/api/csl-admin/assessments/{assessment.id}/open/"
        res = self.client.post(url)
        self.assertEqual(res.status_code, 400)
        self.assertIsInstance(res.data["detail"], str)
        self.assertIn("college", res.data["detail"].lower())

        assessment.refresh_from_db()
        self.assertEqual(assessment.status, Assessment.Status.DRAFT)

    def test_open_assessment_fails_when_archived(self):
        """
        Opening an archived assessment returns 400 with a clear message and does not alter status.
        """
        self.client.force_login(self.admin)
        assessment = Assessment.objects.create(
            code="ARCH-01",
            title="Archived Assessment",
            duration_minutes=30,
            total_marks=10,
            status=Assessment.Status.ARCHIVED,
        )
        assessment.eligible_colleges.add(self.college)

        url = f"/api/csl-admin/assessments/{assessment.id}/open/"
        res = self.client.post(url)
        self.assertEqual(res.status_code, 400)
        self.assertIsInstance(res.data["detail"], str)
        self.assertIn("archived", res.data["detail"].lower())

        assessment.refresh_from_db()
        self.assertEqual(assessment.status, Assessment.Status.ARCHIVED)

    def test_open_assessment_success_and_student_full_lifecycle(self):
        """
        When question bank is sufficient and colleges are assigned:
        1. Admin successfully opens assessment.
        2. Student registers with college and assessment.
        3. Student starts assessment with X-Assessment-Token.
        4. Student receives questions.
        5. Student saves answer.
        6. Student finalizes attempt.
        """
        self.client.force_login(self.admin)
        from apps.assessments.models import AssessmentSectionAllocation

        assessment = Assessment.objects.create(
            code="SUCC-01",
            title="Success Assessment",
            duration_minutes=30,
            total_marks=4,
            status=Assessment.Status.DRAFT,
        )
        assessment.eligible_colleges.add(self.college)
        AssessmentSectionAllocation.objects.create(
            assessment=assessment,
            section=self.section_apt,
            question_count=2,
            marks_per_question=1,
            order=1,
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment,
            section=self.section_cod,
            question_count=2,
            marks_per_question=1,
            order=2,
        )

        # 1. Admin opens assessment
        url = f"/api/csl-admin/assessments/{assessment.id}/open/"
        open_res = self.client.post(url)
        self.assertEqual(open_res.status_code, 200)
        self.assertEqual(open_res.data["status"], Assessment.Status.OPEN)
        self.assertIsNotNone(open_res.data["opened_at"])

        assessment.refresh_from_db()
        self.assertEqual(assessment.status, Assessment.Status.OPEN)

        # 2. Student registers
        reg_res = self.client.post(
            "/api/assessment/register/",
            {
                "full_name": "Rohan Kumar",
                "register_number": "ROHAN-007",
                "college_id": self.college.id,
                "email": "rohan@example.com",
                "department": "CSE",
                "year_of_study": "3rd Year",
                "phone_number": "9876543210",
                "assessment_id": str(assessment.id),
            },
            content_type="application/json",
        )
        self.assertEqual(reg_res.status_code, 201)
        token = reg_res.data["assessment_token"]

        # 3. Student starts assessment with X-Assessment-Token
        start_res = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_ASSESSMENT_TOKEN=token,
        )
        self.assertEqual(start_res.status_code, 200)
        attempt_id = start_res.data["id"]
        questions = start_res.data["questions"]
        self.assertEqual(len(questions), 4)

        # 4. Student saves answer
        first_q = questions[0]
        save_res = self.client.post(
            f"/api/assessment/attempts/{attempt_id}/answer/",
            {
                "question_order": first_q["question_order"],
                "selected_option": "A",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_ASSESSMENT_TOKEN=token,
        )
        self.assertEqual(save_res.status_code, 200)

        # 5. Student submits attempt
        submit_res = self.client.post(
            f"/api/assessment/attempts/{attempt_id}/finalize/",
            {},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_ASSESSMENT_TOKEN=token,
        )
        self.assertEqual(submit_res.status_code, 200)
        self.assertEqual(submit_res.data["state"], "SUBMITTED")


class AssessmentGenerationAndPoolThresholdTests(TestCase):
    """
    Comprehensive tests for assessment generation and question pool threshold logic:
    - Settings are the source of truth for required question counts
    - Pool with exact, extra, or substantially more questions
    - Custom sections with independent counts
    - Error reporting for insufficient questions with exact section and shortage
    - Difficulty distribution preservation
    - Guarantee of unique questions with no IntegrityError
    - Randomized subsets on repeated attempts
    """
    def setUp(self):
        from apps.users.models import User
        self.admin = User.objects.create_user(
            username="pool_test_admin",
            email="pool_admin@csl.com",
            password="AdminPassword123!",
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
            is_staff=True,
            is_superuser=True,
        )
        self.college = College.objects.create(
            name="Apex Institute of Technology",
            code="AIT-TEST",
            contact_email="ait@example.com",
            is_active=True,
        )

    def _create_candidate(self, email_prefix="cand"):
        unique_suffix = uuid.uuid4().hex[:6]
        return Candidate.objects.create(
            full_name=f"Student {unique_suffix}",
            register_number=f"REG-{unique_suffix}",
            email=f"{email_prefix}_{unique_suffix}@example.com",
            college_ref=self.college,
            college=self.college.name,
            is_active=True,
        )

    def _create_questions(self, count, section_code, section_obj=None, difficulty=None):
        questions = []
        diffs = [QuestionBank.Difficulty.EASY, QuestionBank.Difficulty.MEDIUM, QuestionBank.Difficulty.HARD]
        for i in range(count):
            diff = difficulty if difficulty else diffs[i % 3]
            q = QuestionBank.objects.create(
                prompt=f"Question {i+1} for section {section_code} diff {diff}",
                section=section_obj,
                section_type=section_code,
                difficulty=diff,
                option_a=f"Option A for {i}",
                option_b=f"Option B for {i}",
                option_c=f"Option C for {i}",
                option_d=f"Option D for {i}",
                correct_option="A",
                is_active=True,
            )
            questions.append(q)
        return questions

    def test_exact_pool_count_generates_successfully(self):
        """Required: 30, available: 30 -> generates 30 successfully."""
        assessment = Assessment.objects.create(
            code="EXACT-30",
            title="Exact 30 Pool Assessment",
            duration_minutes=60,
            total_marks=30,
            aptitude_count=15,
            coding_count=15,
            status=Assessment.Status.OPEN,
        )
        assessment.eligible_colleges.add(self.college)

        apt_qs = self._create_questions(15, QuestionBank.SectionType.APTITUDE)
        cod_qs = self._create_questions(15, QuestionBank.SectionType.CODING)
        assessment.questions.add(*(apt_qs + cod_qs))
        self.assertEqual(assessment.questions.count(), 30)

        cand = self._create_candidate("exact")
        token = generate_candidate_token(str(cand.id))

        client = Client()
        res = client.post(
            "/api/assessment/start/",
            {"assessment_id": str(assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["questions"]), 30)
        self.assertEqual(res.data["total_questions"], 30)

    def test_pool_with_more_questions_generates_exact_required_count(self):
        """Required: 30, available: 50 -> randomly selects exactly 30."""
        assessment = Assessment.objects.create(
            code="POOL-50-REQ-30",
            title="50 Pool Assessment",
            duration_minutes=60,
            total_marks=30,
            aptitude_count=15,
            coding_count=15,
            status=Assessment.Status.OPEN,
        )
        assessment.eligible_colleges.add(self.college)

        apt_qs = self._create_questions(25, QuestionBank.SectionType.APTITUDE)
        cod_qs = self._create_questions(25, QuestionBank.SectionType.CODING)
        assessment.questions.add(*(apt_qs + cod_qs))
        self.assertEqual(assessment.questions.count(), 50)

        cand = self._create_candidate("pool50")
        token = generate_candidate_token(str(cand.id))

        client = Client()
        res = client.post(
            "/api/assessment/start/",
            {"assessment_id": str(assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["questions"]), 30)
        # Verify 15 Aptitude and 15 Coding
        apt_count = sum(1 for q in res.data["questions"] if q["section_type"] == QuestionBank.SectionType.APTITUDE)
        cod_count = sum(1 for q in res.data["questions"] if q["section_type"] == QuestionBank.SectionType.CODING)
        self.assertEqual(apt_count, 15)
        self.assertEqual(cod_count, 15)

    def test_substantially_larger_pool_generates_exact_required_count(self):
        """Required: 30, available: 100+ -> randomly selects exactly 30."""
        assessment = Assessment.objects.create(
            code="POOL-100-REQ-30",
            title="100+ Pool Assessment",
            duration_minutes=60,
            total_marks=30,
            aptitude_count=15,
            coding_count=15,
            status=Assessment.Status.OPEN,
        )
        assessment.eligible_colleges.add(self.college)

        apt_qs = self._create_questions(60, QuestionBank.SectionType.APTITUDE)
        cod_qs = self._create_questions(50, QuestionBank.SectionType.CODING)
        assessment.questions.add(*(apt_qs + cod_qs))
        self.assertEqual(assessment.questions.count(), 110)

        cand = self._create_candidate("pool100")
        token = generate_candidate_token(str(cand.id))

        client = Client()
        res = client.post(
            "/api/assessment/start/",
            {"assessment_id": str(assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["questions"]), 30)

    def test_insufficient_total_questions_returns_clear_error(self):
        """Required: 30 (15 Apt + 15 Cod), available: 20 Apt + 10 Cod -> reports shortage."""
        assessment = Assessment.objects.create(
            code="SHORTAGE-30",
            title="Shortage Assessment",
            duration_minutes=60,
            total_marks=30,
            aptitude_count=15,
            coding_count=15,
            status=Assessment.Status.OPEN,
        )
        assessment.eligible_colleges.add(self.college)

        apt_qs = self._create_questions(20, QuestionBank.SectionType.APTITUDE)
        cod_qs = self._create_questions(10, QuestionBank.SectionType.CODING)
        assessment.questions.add(*(apt_qs + cod_qs))

        cand = self._create_candidate("shortage")
        token = generate_candidate_token(str(cand.id))

        client = Client()
        res = client.post(
            "/api/assessment/start/",
            {"assessment_id": str(assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res.status_code, 400)
        error_text = str(res.data)
        self.assertIn("Insufficient coding questions", error_text)
        self.assertIn("found 10, requires 15", error_text)

    def test_multiple_custom_sections_independent_question_counts(self):
        """
        Custom Sections A (10), B (10), C (10) with pools 40, 25, 50.
        Selects exactly 10 from each, generating a 30-question assessment.
        """
        sec_a = AssessmentSection.objects.create(name="Section Alpha", code="SEC_A", order=1)
        sec_b = AssessmentSection.objects.create(name="Section Beta", code="SEC_B", order=2)
        sec_c = AssessmentSection.objects.create(name="Section Gamma", code="SEC_C", order=3)

        assessment = Assessment.objects.create(
            code="CUSTOM-ABC-30",
            title="Custom Sections Assessment",
            duration_minutes=60,
            total_marks=30,
            status=Assessment.Status.OPEN,
        )
        assessment.eligible_colleges.add(self.college)

        AssessmentSectionAllocation.objects.create(assessment=assessment, section=sec_a, question_count=10, marks_per_question=1, order=1)
        AssessmentSectionAllocation.objects.create(assessment=assessment, section=sec_b, question_count=10, marks_per_question=1, order=2)
        AssessmentSectionAllocation.objects.create(assessment=assessment, section=sec_c, question_count=10, marks_per_question=1, order=3)

        qs_a = self._create_questions(40, sec_a.code, section_obj=sec_a)
        qs_b = self._create_questions(25, sec_b.code, section_obj=sec_b)
        qs_c = self._create_questions(50, sec_c.code, section_obj=sec_c)
        assessment.questions.add(*(qs_a + qs_b + qs_c))

        cand = self._create_candidate("custom_abc")
        token = generate_candidate_token(str(cand.id))

        client = Client()
        res = client.post(
            "/api/assessment/start/",
            {"assessment_id": str(assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res.status_code, 200)
        questions = res.data["questions"]
        self.assertEqual(len(questions), 30)

        a_count = sum(1 for q in questions if q["section_type"] == "SEC_A")
        b_count = sum(1 for q in questions if q["section_type"] == "SEC_B")
        c_count = sum(1 for q in questions if q["section_type"] == "SEC_C")
        self.assertEqual(a_count, 10)
        self.assertEqual(b_count, 10)
        self.assertEqual(c_count, 10)

    def test_one_custom_section_insufficient_identifies_exact_section(self):
        """Custom sections A (10), B (10), C (10) where B only has 7 questions."""
        sec_a = AssessmentSection.objects.create(name="Section Alpha 2", code="SEC_A2", order=1)
        sec_b = AssessmentSection.objects.create(name="Section Beta 2", code="SEC_B2", order=2)
        sec_c = AssessmentSection.objects.create(name="Section Gamma 2", code="SEC_C2", order=3)

        assessment = Assessment.objects.create(
            code="CUSTOM-SHORT-B",
            title="Short Section B Assessment",
            duration_minutes=60,
            total_marks=30,
            status=Assessment.Status.OPEN,
        )
        assessment.eligible_colleges.add(self.college)

        AssessmentSectionAllocation.objects.create(assessment=assessment, section=sec_a, question_count=10, marks_per_question=1, order=1)
        AssessmentSectionAllocation.objects.create(assessment=assessment, section=sec_b, question_count=10, marks_per_question=1, order=2)
        AssessmentSectionAllocation.objects.create(assessment=assessment, section=sec_c, question_count=10, marks_per_question=1, order=3)

        qs_a = self._create_questions(40, sec_a.code, section_obj=sec_a)
        qs_b = self._create_questions(7, sec_b.code, section_obj=sec_b)
        qs_c = self._create_questions(50, sec_c.code, section_obj=sec_c)
        assessment.questions.add(*(qs_a + qs_b + qs_c))

        cand = self._create_candidate("short_b")
        token = generate_candidate_token(str(cand.id))

        client = Client()
        res = client.post(
            "/api/assessment/start/",
            {"assessment_id": str(assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res.status_code, 400)
        error_text = str(res.data)
        self.assertIn("Section Beta 2", error_text)
        self.assertIn("SEC_B2", error_text)
        self.assertIn("found 7, requires 10", error_text)

    def test_difficulty_distribution_preserved_during_random_selection(self):
        """Verify stratified sampling preserves difficulty distribution when selecting from pool."""
        sec = AssessmentSection.objects.create(name="Balanced Section", code="BAL_SEC")
        assessment = Assessment.objects.create(
            code="BALANCED-DIFF",
            title="Balanced Difficulty Assessment",
            duration_minutes=60,
            total_marks=15,
            status=Assessment.Status.OPEN,
        )
        assessment.eligible_colleges.add(self.college)
        AssessmentSectionAllocation.objects.create(assessment=assessment, section=sec, question_count=15, marks_per_question=1)

        # Create 20 Easy, 20 Medium, 20 Hard
        easy_qs = self._create_questions(20, sec.code, section_obj=sec, difficulty=QuestionBank.Difficulty.EASY)
        med_qs = self._create_questions(20, sec.code, section_obj=sec, difficulty=QuestionBank.Difficulty.MEDIUM)
        hard_qs = self._create_questions(20, sec.code, section_obj=sec, difficulty=QuestionBank.Difficulty.HARD)
        assessment.questions.add(*(easy_qs + med_qs + hard_qs))

        cand = self._create_candidate("balanced")
        token = generate_candidate_token(str(cand.id))

        client = Client()
        res = client.post(
            "/api/assessment/start/",
            {"assessment_id": str(assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res.status_code, 200)
        attempt_id = res.data["id"]

        attempt = AssessmentAttempt.objects.get(id=attempt_id)
        selected_questions = [s.question for s in attempt.question_snapshots.all()]
        self.assertEqual(len(selected_questions), 15)

        easy_sel = sum(1 for q in selected_questions if q.difficulty == QuestionBank.Difficulty.EASY)
        med_sel = sum(1 for q in selected_questions if q.difficulty == QuestionBank.Difficulty.MEDIUM)
        hard_sel = sum(1 for q in selected_questions if q.difficulty == QuestionBank.Difficulty.HARD)

        # In stratified sampling of 15 questions from 3 equal buckets, each difficulty gets 5
        self.assertEqual(easy_sel, 5)
        self.assertEqual(med_sel, 5)
        self.assertEqual(hard_sel, 5)

    def test_no_duplicate_question_ids_across_snapshots(self):
        """Ensure all generated snapshots for an attempt have strictly unique question foreign keys."""
        sec_a = AssessmentSection.objects.create(name="Overlap Section A", code="OVL_A")
        sec_b = AssessmentSection.objects.create(name="Overlap Section B", code="OVL_B")

        assessment = Assessment.objects.create(
            code="UNIQUE-Q-TEST",
            title="Unique Question Test Assessment",
            duration_minutes=60,
            total_marks=20,
            status=Assessment.Status.OPEN,
        )
        assessment.eligible_colleges.add(self.college)

        AssessmentSectionAllocation.objects.create(assessment=assessment, section=sec_a, question_count=10, marks_per_question=1, order=1)
        AssessmentSectionAllocation.objects.create(assessment=assessment, section=sec_b, question_count=10, marks_per_question=1, order=2)

        qs_a = self._create_questions(25, sec_a.code, section_obj=sec_a)
        qs_b = self._create_questions(25, sec_b.code, section_obj=sec_b)
        assessment.questions.add(*(qs_a + qs_b))

        cand = self._create_candidate("unique_q")
        token = generate_candidate_token(str(cand.id))

        client = Client()
        res = client.post(
            "/api/assessment/start/",
            {"assessment_id": str(assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res.status_code, 200)
        attempt_id = res.data["id"]

        attempt = AssessmentAttempt.objects.get(id=attempt_id)
        snapshots = list(attempt.question_snapshots.all())
        self.assertEqual(len(snapshots), 20)

        # Check unique question IDs
        question_ids = [s.question_id for s in snapshots]
        self.assertEqual(len(question_ids), len(set(question_ids)))

        # Check unique question orders
        orders = [s.question_order for s in snapshots]
        self.assertEqual(orders, list(range(1, 21)))

    def test_repeated_attempts_generate_valid_randomized_subsets(self):
        """Different candidate attempts receive valid randomized subsets of the question pool."""
        assessment = Assessment.objects.create(
            code="RANDOM-SUBSET",
            title="Randomized Subsets Assessment",
            duration_minutes=60,
            total_marks=10,
            aptitude_count=5,
            coding_count=5,
            max_attempts=2,
            status=Assessment.Status.OPEN,
        )
        assessment.eligible_colleges.add(self.college)

        apt_qs = self._create_questions(30, QuestionBank.SectionType.APTITUDE)
        cod_qs = self._create_questions(30, QuestionBank.SectionType.CODING)
        assessment.questions.add(*(apt_qs + cod_qs))

        c1 = self._create_candidate("c1")
        c2 = self._create_candidate("c2")

        client = Client()

        t1 = generate_candidate_token(str(c1.id))
        res1 = client.post(
            "/api/assessment/start/",
            {"assessment_id": str(assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {t1}",
        )
        self.assertEqual(res1.status_code, 200)

        t2 = generate_candidate_token(str(c2.id))
        res2 = client.post(
            "/api/assessment/start/",
            {"assessment_id": str(assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {t2}",
        )
        self.assertEqual(res2.status_code, 200)

        att1 = AssessmentAttempt.objects.get(id=res1.data["id"])
        att2 = AssessmentAttempt.objects.get(id=res2.data["id"])

        q_ids1 = set(att1.question_snapshots.values_list("question_id", flat=True))
        q_ids2 = set(att2.question_snapshots.values_list("question_id", flat=True))

        self.assertEqual(len(q_ids1), 10)
        self.assertEqual(len(q_ids2), 10)
        # Verify that both subsets are drawn from the pool of 60 questions
        all_pool_ids = set(assessment.questions.values_list("id", flat=True))
        self.assertTrue(q_ids1.issubset(all_pool_ids))
        self.assertTrue(q_ids2.issubset(all_pool_ids))

    def test_admin_assign_questions_is_sufficient_dynamic_sections(self):
        """AdminAssignQuestionsView accurately reports sufficiency for custom section allocations."""
        sec_a = AssessmentSection.objects.create(name="Section A Suff", code="SAS_A")
        sec_b = AssessmentSection.objects.create(name="Section B Suff", code="SAS_B")

        assessment = Assessment.objects.create(
            code="ADMIN-SUFF-TEST",
            title="Admin Sufficiency Test",
            total_marks=20,
            status=Assessment.Status.DRAFT,
        )
        AssessmentSectionAllocation.objects.create(assessment=assessment, section=sec_a, question_count=10, marks_per_question=1, order=1)
        AssessmentSectionAllocation.objects.create(assessment=assessment, section=sec_b, question_count=10, marks_per_question=1, order=2)

        qs_a = self._create_questions(15, sec_a.code, section_obj=sec_a)
        qs_b = self._create_questions(5, sec_b.code, section_obj=sec_b)  # short by 5

        client = Client()
        client.force_login(self.admin)

        # Assign qs_a + qs_b (sec_b has only 5, requires 10) -> is_sufficient should be False
        res1 = client.post(
            f"/api/csl-admin/assessments/{assessment.id}/assign-questions/",
            {"question_ids": [q.id for q in (qs_a + qs_b)], "action": "set"},
            content_type="application/json",
        )
        self.assertEqual(res1.status_code, 200)
        self.assertFalse(res1.data["is_sufficient"])

        # Now add 10 more questions to sec_b -> is_sufficient should be True
        more_b = self._create_questions(10, sec_b.code, section_obj=sec_b)
        res2 = client.post(
            f"/api/csl-admin/assessments/{assessment.id}/assign-questions/",
            {"question_ids": [q.id for q in more_b], "action": "add"},
            content_type="application/json",
        )
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.data["is_sufficient"])

    def test_admin_bulk_update_custom_section_and_category(self):
        """AdminQuestionBulkUpdateView properly supports custom sections and categories."""
        custom_sec = AssessmentSection.objects.create(name="DevOps Engineering", code="DEVOPS")
        q1 = QuestionBank.objects.create(
            prompt="Docker question 1",
            section_type="APTITUDE",
            category="General",
            difficulty=QuestionBank.Difficulty.EASY,
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_option="A",
            is_active=True,
        )
        q2 = QuestionBank.objects.create(
            prompt="Kubernetes question 2",
            section_type="APTITUDE",
            category="General",
            difficulty=QuestionBank.Difficulty.EASY,
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_option="B",
            is_active=True,
        )

        client = Client()
        client.force_login(self.admin)

        # Bulk update to custom section DEVOPS and category Cloud
        res = client.post(
            "/api/csl-admin/questions/bulk-update/",
            {
                "ids": [q1.id, q2.id],
                "section_type": "DEVOPS",
                "category": "Cloud Infrastructure",
                "difficulty": "HARD",
            },
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["updated_count"], 2)

        q1.refresh_from_db()
        q2.refresh_from_db()
        self.assertEqual(q1.section_type, "DEVOPS")
        self.assertEqual(q1.section, custom_sec)
        self.assertEqual(q1.category, "Cloud Infrastructure")
        self.assertEqual(q1.difficulty, "HARD")

        self.assertEqual(q2.section_type, "DEVOPS")
        self.assertEqual(q2.section, custom_sec)
        self.assertEqual(q2.category, "Cloud Infrastructure")
        self.assertEqual(q2.difficulty, "HARD")

    def test_admin_empty_question_pool_and_validation(self):
        """Admin question endpoints validate assessment target pool and handle empty pools cleanly."""
        client = Client()
        client.force_login(self.admin)

        # Creating question without target assessment pool fails with 400
        res_create = client.post(
            "/api/csl-admin/questions/",
            {
                "prompt": "Orphan question without pool",
                "section_type": "APTITUDE",
                "difficulty": "EASY",
                "option_a": "1",
                "option_b": "2",
                "option_c": "3",
                "option_d": "4",
                "correct_option": "A",
                "assessment_id": "",
            },
            content_type="application/json",
        )
        self.assertEqual(res_create.status_code, 400)
        self.assertIn("Target assessment pool", str(res_create.data))

        # Filter by assessment with 0 questions returns empty list
        empty_assessment = Assessment.objects.create(
            code="EMPTY-POOL-ASSESSMENT",
            title="Empty Pool Assessment",
            total_marks=50,
            status=Assessment.Status.DRAFT,
        )
        res_list = client.get(f"/api/csl-admin/questions/?assessment_id={empty_assessment.id}")
        self.assertEqual(res_list.status_code, 200)
        # res_list.data is a list of questions directly
        self.assertEqual(len(res_list.data), 0)


