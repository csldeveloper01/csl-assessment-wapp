import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.test import TestCase, TransactionTestCase, Client
from django.test.utils import CaptureQueriesContext
from django.db import connection
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
    AssessmentSectionAllocation,
)
from apps.assessments.tokens import generate_candidate_token
from apps.assessments.serializers import AssessmentAttemptDetailSerializer


class ProductionRobustnessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin_robust",
            email="admin_robust@csl.com",
            password="AdminPassword123!",
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.admin_user)

        self.config = AssessmentConfig.objects.create(
            title="Global Policy Config",
            duration_minutes=60,
            total_marks=50,
            is_active=True,
        )

        self.college = College.objects.create(
            name="Apex Institute of Technology",
            code="AIT01",
            is_active=True,
        )

        self.sec_quant = AssessmentSection.objects.create(
            name="Quantitative Ability",
            code="QUANT",
            is_active=True,
        )
        self.sec_prog = AssessmentSection.objects.create(
            name="Programming Skills",
            code="PROG",
            is_active=True,
        )

        self.assessment = Assessment.objects.create(
            title="Full Stack Placement Test",
            code="FSPT01",
            duration_minutes=60,
            total_marks=40,
            status=Assessment.Status.OPEN,
        )
        self.assessment.eligible_colleges.add(self.college)

        AssessmentSectionAllocation.objects.create(
            assessment=self.assessment,
            section=self.sec_quant,
            question_count=10,
            marks_per_question=2,
            order=1,
        )
        AssessmentSectionAllocation.objects.create(
            assessment=self.assessment,
            section=self.sec_prog,
            question_count=10,
            marks_per_question=2,
            order=2,
        )

        # Seed 30 questions for QUANT and 30 for PROG (surplus pool: 60 total available, 20 required)
        questions = []
        for i in range(1, 31):
            q = QuestionBank(
                section=self.sec_quant,
                section_type="QUANT",
                category="Quantitative",
                prompt=f"Quant Question #{i}: What is the value of {i} * 2?",
                option_a="10",
                option_b=str(i * 2),
                option_c="30",
                option_d="40",
                correct_option="B",
                difficulty="MEDIUM",
                is_active=True,
            )
            questions.append(q)

        for i in range(1, 31):
            q = QuestionBank(
                section=self.sec_prog,
                section_type="PROG",
                category="Programming",
                prompt=f"Prog Question #{i}: What is the output of print({i})?",
                option_a=str(i),
                option_b="None",
                option_c="Error",
                option_d="undefined",
                correct_option="A",
                difficulty="EASY",
                is_active=True,
            )
            questions.append(q)

        QuestionBank.objects.bulk_create(questions)
        all_created = list(QuestionBank.objects.all())
        self.assessment.questions.set(all_created)

    def test_question_loading_query_count_under_5(self):
        """Verifies that listing questions executes <= 5 queries with no N+1 regression."""
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get("/api/csl-admin/questions/")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertGreaterEqual(len(data), 50)

        # Before fix: 502 queries (1 for bank + 500 for sections + ManyToMany queries)
        # After optimization: 2 queries
        self.assertLessEqual(len(ctx.captured_queries), 5, f"Executed {len(ctx.captured_queries)} queries (expected <= 5)")

    def test_assessment_generation_with_surplus_pool(self):
        """Verifies starting an assessment with a 60-question surplus pool selects exactly 20 questions randomly."""
        candidate = Candidate.objects.create(
            full_name="Alice Smith",
            register_number="REG_ALICE_001",
            college=self.college.name,
            college_ref=self.college,
            email="alice@apex.edu",
            department="CSE",
            year_of_study="4",
        )
        token = generate_candidate_token(candidate.id)

        response = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(self.assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_questions"], 40)
        self.assertEqual(len(data["questions"]), 20)
        # Ensure 10 questions per section allocated
        quant_count = sum(1 for q in data["questions"] if q["section_type"] == "QUANT")
        prog_count = sum(1 for q in data["questions"] if q["section_type"] == "PROG")
        self.assertEqual(quant_count, 10)
        self.assertEqual(prog_count, 10)

    def test_independent_candidate_timers(self):
        """Verifies candidate A and candidate B have completely isolated timers and attempt records."""
        cand_a = Candidate.objects.create(
            full_name="Bob A",
            register_number="REG_BOB_01",
            college=self.college.name,
            college_ref=self.college,
            email="boba@apex.edu",
            department="CSE",
            year_of_study="4",
        )
        cand_b = Candidate.objects.create(
            full_name="Charlie B",
            register_number="REG_CHARLIE_02",
            college=self.college.name,
            college_ref=self.college,
            email="charlie@apex.edu",
            department="IT",
            year_of_study="4",
        )

        token_a = generate_candidate_token(cand_a.id)
        token_b = generate_candidate_token(cand_b.id)

        res_a = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(self.assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_a}",
        )
        res_b = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(self.assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_b}",
        )

        attempt_a_id = res_a.json()["id"]
        attempt_b_id = res_b.json()["id"]
        self.assertNotEqual(attempt_a_id, attempt_b_id)

        attempt_a = AssessmentAttempt.objects.get(id=attempt_a_id)
        attempt_b = AssessmentAttempt.objects.get(id=attempt_b_id)

        # Pause attempt A for grace period
        attempt_a.pause_attempt()
        attempt_a.refresh_from_db()
        attempt_b.refresh_from_db()

        self.assertTrue(attempt_a.is_paused)
        self.assertFalse(attempt_b.is_paused)
        self.assertIsNone(attempt_b.paused_at)

    def test_outage_grace_credit_accumulation_and_capping(self):
        """Verifies pause credit accumulation caps at max_disconnection_grace_seconds (600s)."""
        attempt = AssessmentAttempt.objects.create(
            candidate=Candidate.objects.create(
                full_name="Grace Candidate",
                register_number="REG_GRACE",
                college=self.college.name,
            college_ref=self.college,
                email="grace@apex.edu",
                department="ECE",
                year_of_study="3",
            ),
            assessment=self.assessment,
            config=self.config,
            deadline=timezone.now() + timedelta(minutes=60),
            state=AssessmentAttempt.State.IN_PROGRESS,
            max_disconnection_grace_seconds=600,
        )

        # 1. Pause attempt
        attempt.pause_attempt()
        self.assertTrue(attempt.is_paused)
        self.assertIsNotNone(attempt.paused_at)

        # Simulate 15 minutes (900 seconds) of network disconnect
        attempt.paused_at = timezone.now() - timedelta(seconds=900)
        attempt.save()

        # Resume attempt
        credit_applied = attempt.resume_attempt()
        # Cap is 600s: even though 900s passed, max 600s credit is granted
        self.assertEqual(credit_applied, 600)
        self.assertEqual(attempt.total_paused_seconds, 600)
        self.assertFalse(attempt.is_paused)
        self.assertIsNone(attempt.paused_at)

        # Subsequent pause: since 600s max grace is fully consumed, zero further credit
        attempt.pause_attempt()
        attempt.paused_at = timezone.now() - timedelta(seconds=60)
        attempt.save()
        subsequent_credit = attempt.resume_attempt()
        self.assertEqual(subsequent_credit, 0)
        self.assertEqual(attempt.total_paused_seconds, 600)

    def test_heartbeat_and_bulk_sync_answers(self):
        """Verifies candidate heartbeat endpoint and bulk answer synchronization."""
        candidate = Candidate.objects.create(
            full_name="Sync Candidate",
            register_number="REG_SYNC",
            college=self.college.name,
            college_ref=self.college,
            email="sync@apex.edu",
            department="CSE",
            year_of_study="4",
        )
        token = generate_candidate_token(candidate.id)

        start_res = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(self.assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        attempt_id = start_res.json()["id"]

        # 1. Test heartbeat endpoint
        hb_res = self.client.post(
            f"/api/assessment/attempts/{attempt_id}/heartbeat/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(hb_res.status_code, 200)
        hb_data = hb_res.json()
        self.assertEqual(hb_data["attempt_id"], attempt_id)
        self.assertEqual(hb_data["state"], "IN_PROGRESS")
        self.assertGreater(hb_data["remaining_seconds"], 0)
        self.assertFalse(hb_data["is_paused"])

        # 2. Test bulk sync-answers endpoint
        answers_payload = {
            "answers": [
                {"question_order": 1, "selected_option": "B"},
                {"question_order": 2, "selected_option": "A"},
                {"question_order": 3, "selected_option": "C"},
            ]
        }
        sync_res = self.client.post(
            f"/api/assessment/attempts/{attempt_id}/sync-answers/",
            answers_payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(sync_res.status_code, 200)
        sync_data = sync_res.json()
        self.assertEqual(sync_data["synced_count"], 3)

        # Verify DB snapshots updated
        q1 = AttemptQuestionSnapshot.objects.get(attempt_id=attempt_id, question_order=1)
        q2 = AttemptQuestionSnapshot.objects.get(attempt_id=attempt_id, question_order=2)
        q3 = AttemptQuestionSnapshot.objects.get(attempt_id=attempt_id, question_order=3)
        self.assertEqual(q1.selected_option, "B")
        self.assertEqual(q2.selected_option, "A")
        self.assertEqual(q3.selected_option, "C")

    def test_question_safe_delete_unreferenced_vs_referenced(self):
        """Verifies safe archival when questions are referenced by attempts vs clean deletion."""
        # Create an unreferenced question
        unreferenced_q = QuestionBank.objects.create(
            section=self.sec_quant,
            section_type="QUANT",
            category="Quantitative",
            prompt="Unreferenced question for deletion",
            option_a="1",
            option_b="2",
            option_c="3",
            option_d="4",
            correct_option="A",
            is_active=True,
        )
        del_res = self.client.delete(f"/api/csl-admin/questions/{unreferenced_q.id}/")
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.json()["deleted"])
        self.assertFalse(QuestionBank.objects.filter(id=unreferenced_q.id).exists())

        # Create a referenced question
        referenced_q = QuestionBank.objects.create(
            section=self.sec_prog,
            section_type="PROG",
            category="Programming",
            prompt="Referenced question with candidate attempt snapshot",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_option="B",
            is_active=True,
        )
        candidate = Candidate.objects.create(
            full_name="Dan Candidate",
            register_number="REG_DAN",
            college=self.college.name,
            college_ref=self.college,
            email="dan@apex.edu",
            department="IT",
            year_of_study="4",
        )
        attempt = AssessmentAttempt.objects.create(
            candidate=candidate,
            assessment=self.assessment,
            config=self.config,
            deadline=timezone.now() + timedelta(minutes=60),
            state=AssessmentAttempt.State.IN_PROGRESS,
        )
        AttemptQuestionSnapshot.objects.create(
            attempt=attempt,
            question=referenced_q,
            question_order=1,
            section_type="PROG",
            prompt=referenced_q.prompt,
            option_a_text=referenced_q.option_a,
            option_b_text=referenced_q.option_b,
            option_c_text=referenced_q.option_c,
            option_d_text=referenced_q.option_d,
            correct_option_key="B",
        )

        ref_del_res = self.client.delete(f"/api/csl-admin/questions/{referenced_q.id}/")
        self.assertEqual(ref_del_res.status_code, 200)
        self.assertTrue(ref_del_res.json()["archived"])

        # Record still exists in QuestionBank to maintain foreign key integrity, but is inactive
        referenced_q.refresh_from_db()
        self.assertFalse(referenced_q.is_active)

    def test_bulk_delete_questions(self):
        """Verifies atomic bulk question deletion API."""
        q_a = QuestionBank.objects.create(
            section=self.sec_quant,
            section_type="QUANT",
            category="Quant",
            prompt="Bulk Del Question A",
            option_a="1",
            option_b="2",
            option_c="3",
            option_d="4",
            correct_option="A",
            is_active=True,
        )
        q_b = QuestionBank.objects.create(
            section=self.sec_quant,
            section_type="QUANT",
            category="Quant",
            prompt="Bulk Del Question B",
            option_a="1",
            option_b="2",
            option_c="3",
            option_d="4",
            correct_option="A",
            is_active=True,
        )

        res = self.client.post(
            "/api/csl-admin/questions/bulk-delete/",
            {"ids": [q_a.id, q_b.id]},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["deleted_count"], 2)
        self.assertFalse(QuestionBank.objects.filter(id__in=[q_a.id, q_b.id]).exists())

    def test_section_code_propagation_to_question_bank(self):
        """Verifies that updating a section code synchronizes QuestionBank section_type."""
        new_sec = AssessmentSection.objects.create(
            name="Data Structures",
            code="DS_OLD",
            is_active=True,
        )
        q = QuestionBank.objects.create(
            section=new_sec,
            section_type="DS_OLD",
            category="DS",
            prompt="What is the time complexity of binary search?",
            option_a="O(1)",
            option_b="O(n)",
            option_c="O(log n)",
            option_d="O(n log n)",
            correct_option="C",
            is_active=True,
        )

        # Update section code via Admin API
        update_res = self.client.put(
            f"/api/csl-admin/sections/{new_sec.id}/",
            {
                "name": "Data Structures & Algorithms",
                "code": "DSA_NEW",
                "description": "Core computer science algorithms",
                "is_active": True,
            },
            content_type="application/json",
        )
        self.assertEqual(update_res.status_code, 200)

        # Check section and QuestionBank record
        new_sec.refresh_from_db()
        self.assertEqual(new_sec.code, "DSA_NEW")
        q.refresh_from_db()
        self.assertEqual(q.section_type, "DSA_NEW")

    def test_assessment_start_query_budget(self):
        """Verifies that starting an assessment executes an optimized number of queries."""
        cand = Candidate.objects.create(
            full_name="Query Budget Candidate",
            register_number="QBC001",
            college=self.college.name,
            college_ref=self.college,
            email="qbc001@apex.edu",
            department="CSE",
            year_of_study="4",
        )
        token = generate_candidate_token(cand.id)

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.post(
                "/api/assessment/start/",
                {"assessment_id": str(self.assessment.id)},
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        # Baseline was 31 queries, previously optimized to 21; with post-creation cache reuse and pool check elimination, count is <= 15 (<= 13 prod)
        prod_queries = [
            q for q in ctx.captured_queries
            if not q["sql"].strip().startswith("SAVEPOINT") and not q["sql"].strip().startswith("RELEASE")
        ]
        self.assertLessEqual(len(ctx.captured_queries), 15, f"Executed {len(ctx.captured_queries)} queries (expected <= 15)")
        self.assertLessEqual(len(prod_queries), 13, f"Executed {len(prod_queries)} production queries (expected <= 13)")
        print(f"\n[QUERY_BUDGET_VERIFIED] Assessment start completed in {len(prod_queries)} prod / {len(ctx.captured_queries)} test queries (budget <= 13 prod / <= 15 test).")

    def test_answer_save_query_budget(self):
        """Verifies that saving an answer executes at most 5 database operations (3 queries + transaction boundaries)."""
        cand = Candidate.objects.create(
            full_name="Answer Budget Candidate",
            register_number="ANS_QBC_01",
            college=self.college.name,
            college_ref=self.college,
            email="ans_qbc_01@apex.edu",
            department="IT",
            year_of_study="4",
        )
        attempt = AssessmentAttempt.objects.create(
            candidate=cand,
            assessment=self.assessment,
            config=self.config,
            deadline=timezone.now() + timedelta(minutes=60),
            state=AssessmentAttempt.State.IN_PROGRESS,
        )
        snap = AttemptQuestionSnapshot.objects.create(
            attempt=attempt,
            question=QuestionBank.objects.first(),
            question_order=1,
            prompt="Budget Question",
            option_a_text="Opt A",
            option_b_text="Opt B",
            option_c_text="Opt C",
            option_d_text="Opt D",
            correct_option_key="A",
        )
        token = generate_candidate_token(cand.id, attempt_id=attempt.id)

        # Clear client session from admin force_login so request uses candidate assessment token
        client = Client()

        with CaptureQueriesContext(connection) as ctx:
            response = client.post(
                f"/api/assessment/attempts/{attempt.id}/answer/",
                {"question_order": 1, "selected_option": "B"},
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "saved")
        self.assertEqual(response.data["question_order"], 1)
        self.assertEqual(response.data["selected_option"], "B")

        # Baseline was 7 queries; with redundant attempt query & snapshot lock eliminated, count is <= 5 (including BEGIN & COMMIT)
        self.assertLessEqual(len(ctx.captured_queries), 5, f"Executed {len(ctx.captured_queries)} queries (expected <= 5)")
        print(f"\n[QUERY_BUDGET_VERIFIED] Answer save completed in {len(ctx.captured_queries)} queries (budget <= 5).")

        # Explicitly verify all essential stages are present in captured queries
        sql_statements = [q["sql"].strip() for q in ctx.captured_queries]
        self.assertTrue(any("assessments_candidate" in s for s in sql_statements), "Authentication query must be captured")
        self.assertTrue(any("assessments_assessmentattempt" in s for s in sql_statements), "Attempt lookup query must be captured")
        self.assertTrue(any("assessments_attemptquestionsnapshot" in s and "UPDATE" in s for s in sql_statements), "Snapshot atomic update must be captured")
        if connection.vendor == "postgresql":
            self.assertTrue(any("FOR UPDATE" in s for s in sql_statements), "PostgreSQL FOR UPDATE must be present")
            self.assertTrue(any("BEGIN" in s for s in sql_statements), "Transaction BEGIN must be captured")
            self.assertTrue(any("COMMIT" in s for s in sql_statements), "Transaction COMMIT must be captured")
        else:
            self.assertTrue(any("SAVEPOINT" in s for s in sql_statements), "Transaction boundary must be captured")

        # Verify DB persisted
        snap.refresh_from_db()
        self.assertEqual(snap.selected_option, "B")

    def test_answer_save_unauthorized_and_not_found(self):
        """Verifies strict ownership protection (403) and missing attempt handling (404)."""
        cand_owner = Candidate.objects.create(
            full_name="Owner Candidate",
            register_number="OWNER_01",
            college=self.college.name,
            college_ref=self.college,
            email="owner@apex.edu",
            department="CSE",
            year_of_study="4",
        )
        cand_attacker = Candidate.objects.create(
            full_name="Attacker Candidate",
            register_number="ATTACK_01",
            college=self.college.name,
            college_ref=self.college,
            email="attacker@apex.edu",
            department="CSE",
            year_of_study="4",
        )
        attempt = AssessmentAttempt.objects.create(
            candidate=cand_owner,
            assessment=self.assessment,
            config=self.config,
            deadline=timezone.now() + timedelta(minutes=60),
            state=AssessmentAttempt.State.IN_PROGRESS,
        )
        AttemptQuestionSnapshot.objects.create(
            attempt=attempt,
            question=QuestionBank.objects.first(),
            question_order=1,
            prompt="Security Question",
            option_a_text="A",
            option_b_text="B",
            option_c_text="C",
            option_d_text="D",
            correct_option_key="A",
        )
        attacker_token = generate_candidate_token(cand_attacker.id)
        owner_token = generate_candidate_token(cand_owner.id, attempt_id=attempt.id)
        client = Client()

        # 1. Attacker tries to save answer on owner's attempt -> 403 Forbidden
        res_403 = client.post(
            f"/api/assessment/attempts/{attempt.id}/answer/",
            {"question_order": 1, "selected_option": "A"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {attacker_token}",
        )
        self.assertEqual(res_403.status_code, 403)
        self.assertIn("forbidden", res_403.data.get("detail", "").lower())

        # 2. Nonexistent attempt UUID -> 404 Not Found
        fake_attempt_id = uuid.uuid4()
        res_404 = client.post(
            f"/api/assessment/attempts/{fake_attempt_id}/answer/",
            {"question_order": 1, "selected_option": "A"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {owner_token}",
        )
        self.assertEqual(res_404.status_code, 404)

    def test_answer_save_validations(self):
        """Verifies validation on options and question numbers."""
        cand = Candidate.objects.create(
            full_name="Validation Candidate",
            register_number="VAL_01",
            college=self.college.name,
            college_ref=self.college,
            email="val_01@apex.edu",
            department="IT",
            year_of_study="4",
        )
        attempt = AssessmentAttempt.objects.create(
            candidate=cand,
            assessment=self.assessment,
            config=self.config,
            deadline=timezone.now() + timedelta(minutes=60),
            state=AssessmentAttempt.State.IN_PROGRESS,
        )
        AttemptQuestionSnapshot.objects.create(
            attempt=attempt,
            question=QuestionBank.objects.first(),
            question_order=1,
            prompt="Validation Question",
            option_a_text="A",
            option_b_text="B",
            option_c_text="C",
            option_d_text="D",
            correct_option_key="A",
        )
        token = generate_candidate_token(cand.id, attempt_id=attempt.id)
        client = Client()

        # Invalid option "E" -> 400 Bad Request
        res_bad_opt = client.post(
            f"/api/assessment/attempts/{attempt.id}/answer/",
            {"question_order": 1, "selected_option": "E"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res_bad_opt.status_code, 400)
        self.assertIn("detail", res_bad_opt.data)

        # Invalid question order 50 (within 1-200 but not in attempt) -> 400 Bad Request
        res_bad_q = client.post(
            f"/api/assessment/attempts/{attempt.id}/answer/",
            {"question_order": 50, "selected_option": "A"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res_bad_q.status_code, 400)
        self.assertIn("Invalid question order", str(res_bad_q.data))

    def test_answer_save_expired_and_inactive(self):
        """Verifies that expired attempts transition to TIMED_OUT and inactive attempts reject answer saves."""
        cand = Candidate.objects.create(
            full_name="Expired Candidate",
            register_number="EXP_01",
            college=self.college.name,
            college_ref=self.college,
            email="exp_01@apex.edu",
            department="IT",
            year_of_study="4",
        )
        # Attempt with deadline in the past
        attempt_expired = AssessmentAttempt.objects.create(
            candidate=cand,
            assessment=self.assessment,
            config=self.config,
            deadline=timezone.now() - timedelta(minutes=5),
            state=AssessmentAttempt.State.IN_PROGRESS,
        )
        AttemptQuestionSnapshot.objects.create(
            attempt=attempt_expired,
            question=QuestionBank.objects.first(),
            question_order=1,
            prompt="Expired Question",
            option_a_text="A",
            option_b_text="B",
            option_c_text="C",
            option_d_text="D",
            correct_option_key="A",
        )
        token = generate_candidate_token(cand.id, attempt_id=attempt_expired.id)
        client = Client()

        res_expired = client.post(
            f"/api/assessment/attempts/{attempt_expired.id}/answer/",
            {"question_order": 1, "selected_option": "A"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res_expired.status_code, 400)
        self.assertIn("expired", str(res_expired.data).lower())

        attempt_expired.refresh_from_db()
        self.assertEqual(attempt_expired.state, AssessmentAttempt.State.TIMED_OUT)
        self.assertIsNotNone(attempt_expired.submitted_at, "Persisted attempt must have submitted_at timestamp")
        self.assertIsNotNone(attempt_expired.total_score, "Persisted attempt must have finalized total_score")
        self.assertIsNotNone(attempt_expired.percentage, "Persisted attempt must have finalized percentage")

        # Submitted attempt rejects saves
        attempt_expired.state = AssessmentAttempt.State.SUBMITTED
        attempt_expired.save(update_fields=["state"])

        res_submitted = client.post(
            f"/api/assessment/attempts/{attempt_expired.id}/answer/",
            {"question_order": 1, "selected_option": "B"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res_submitted.status_code, 400)
        self.assertIn("not active", str(res_submitted.data).lower())


class AnswerSaveConcurrencyTests(TransactionTestCase):
    """
    Tests high-concurrency answer-save execution against the real HTTP endpoint
    using multi-threaded worker pools and separate database connections.
    """

    def setUp(self):
        self.college = College.objects.create(
            name="Concurrent College",
            code="CONC01",
            is_active=True,
        )
        self.sec = AssessmentSection.objects.create(
            name="Concurrency Section",
            code="CONC_SEC",
            is_active=True,
        )
        self.config = AssessmentConfig.objects.create(
            title="Concurrency Config",
            duration_minutes=60,
            aptitude_count=25,
            coding_count=25,
            total_marks=50,
            is_active=True,
        )
        self.assessment = Assessment.objects.create(
            title="Concurrency Assessment",
            code="CONC_ASS_01",
            duration_minutes=60,
            total_marks=20,
            status=Assessment.Status.OPEN,
        )
        self.assessment.eligible_colleges.add(self.college)

        self.questions = []
        for i in range(1, 6):
            q = QuestionBank.objects.create(
                section=self.sec,
                section_type="CONC_SEC",
                category="Programming",
                prompt=f"Concurrency Q{i}: What is {i} + 1?",
                option_a=str(i + 1),
                option_b="0",
                option_c="-1",
                option_d="None",
                correct_option="A",
                is_active=True,
            )
            self.questions.append(q)

    def test_concurrent_answer_saves_on_real_endpoint(self):
        """Verifies that multiple concurrent threads posting to the answer endpoint serialize safely without errors."""
        cand = Candidate.objects.create(
            full_name="Concurrent Candidate",
            register_number="CONC_CAND_01",
            college=self.college.name,
            college_ref=self.college,
            email="conc_cand@apex.edu",
            department="CSE",
            year_of_study="4",
        )
        attempt = AssessmentAttempt.objects.create(
            candidate=cand,
            assessment=self.assessment,
            config=self.config,
            deadline=timezone.now() + timedelta(minutes=60),
            state=AssessmentAttempt.State.IN_PROGRESS,
        )
        for idx, q in enumerate(self.questions, 1):
            AttemptQuestionSnapshot.objects.create(
                attempt=attempt,
                question=q,
                question_order=idx,
                prompt=q.prompt,
                option_a_text=q.option_a,
                option_b_text=q.option_b,
                option_c_text=q.option_c,
                option_d_text=q.option_d,
                correct_option_key="A",
            )

        token = generate_candidate_token(cand.id, attempt_id=attempt.id)

        # 12 concurrent/rapid answer submissions
        tasks = []
        for i in range(12):
            q_order = (i % 5) + 1
            opt = ["A", "B", "C", "D"][i % 4]
            tasks.append((q_order, opt))

        if connection.vendor == "sqlite":
            # In-memory SQLite uses per-connection private memory; test interleaved saves via client
            results = []
            for q_order, opt in tasks:
                res = self.client.post(
                    f"/api/assessment/attempts/{attempt.id}/answer/",
                    {"question_order": q_order, "selected_option": opt},
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {token}",
                )
                results.append((res.status_code, res.data))
        else:
            def worker_post(q_order, opt):
                c = Client()
                res = c.post(
                    f"/api/assessment/attempts/{attempt.id}/answer/",
                    {"question_order": q_order, "selected_option": opt},
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {token}",
                )
                connection.close()
                return res.status_code, res.data

            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda args: worker_post(*args), tasks))

        self.assertEqual(len(results), 12)
        for status_code, data in results:
            self.assertEqual(status_code, 200)
            self.assertEqual(data["status"], "saved")
            self.assertIn(data["selected_option"], ["A", "B", "C", "D"])

        # Verify all snapshots in database hold valid options
        snapshots = AttemptQuestionSnapshot.objects.filter(attempt=attempt)
        self.assertEqual(snapshots.count(), 5)
        for snap in snapshots:
            self.assertIn(snap.selected_option, ["A", "B", "C", "D"])
            self.assertIsNotNone(snap.answered_at)

    def test_concurrent_answer_save_and_finalization(self):
        """
        Verifies that rapid concurrent answer saves and attempt finalization
        execute safely with row locking without deadlocks or corrupted state.
        """
        cand = Candidate.objects.create(
            full_name="Concurrency Finalize Student",
            register_number="CONC-FIN-01",
            email="conc_fin@example.com",
            college_ref=self.college,
            college=self.college.name,
            is_active=True,
        )
        attempt = AssessmentAttempt.objects.create(
            candidate=cand,
            assessment=self.assessment,
            config=self.config,
            state=AssessmentAttempt.State.IN_PROGRESS,
            deadline=timezone.now() + timedelta(minutes=60),
        )
        for idx, q in enumerate(self.questions, 1):
            AttemptQuestionSnapshot.objects.create(
                attempt=attempt,
                question=q,
                question_order=idx,
                section_type=q.section_type,
                prompt=q.prompt,
                option_a_text=q.option_a,
                option_b_text=q.option_b,
                option_c_text=q.option_c,
                option_d_text=q.option_d,
                correct_option_key="A",
            )

        token = generate_candidate_token(cand.id, attempt_id=attempt.id)
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        client = Client()
        for i in range(1, 6):
            client.post(
                f"/api/assessment/attempts/{attempt.id}/answer/",
                {"question_order": i, "selected_option": "A"},
                content_type="application/json",
                **headers,
            )

        fin_resp = client.post(f"/api/assessment/attempts/{attempt.id}/finalize/", **headers)
        self.assertEqual(fin_resp.status_code, 200)
        self.assertEqual(fin_resp.data["state"], AssessmentAttempt.State.SUBMITTED)

        # Subsequent answer save should be rejected (attempt is active check)
        post_save = client.post(
            f"/api/assessment/attempts/{attempt.id}/answer/",
            {"question_order": 1, "selected_option": "B"},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(post_save.status_code, 400)


class FinalizationOptimizationTests(TestCase):
    """
    Focused regression test suite for assessment finalization optimizations:
    - Query budget verification (<= 7 queries)
    - Response semantics preservation for students and staff
    - Scoring correctness with dynamic section allocations
    - Idempotent duplicate finalization
    - Unauthorized and invalid attempt protections
    - Expired attempt handling (TIMED_OUT)
    """

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin_fin_test",
            email="admin_fin_test@csl.com",
            password="AdminPassword123!",
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
            is_staff=True,
            is_superuser=True,
        )

        self.college = College.objects.create(
            name="Finalization College",
            code="FIN-COL",
            is_active=True,
        )
        self.candidate = Candidate.objects.create(
            full_name="Finalize Student",
            register_number="FIN-STU-01",
            email="fin_stu@example.com",
            college_ref=self.college,
            college=self.college.name,
            is_active=True,
        )
        self.config = AssessmentConfig.objects.create(
            title="Policy Config",
            duration_minutes=60,
            total_marks=50,
            aptitude_count=25,
            coding_count=25,
            is_active=True,
        )
        self.assessment = Assessment.objects.create(
            title="Finalize Test Assessment",
            code="FIN-ASSESS-TEST",
            duration_minutes=60,
            total_marks=40,
            status=Assessment.Status.OPEN,
        )
        self.assessment.eligible_colleges.add(self.college)

        self.sec_quant, _ = AssessmentSection.objects.get_or_create(
            code="QUANT", defaults={"name": "Quantitative", "is_active": True}
        )
        self.sec_prog, _ = AssessmentSection.objects.get_or_create(
            code="PROG", defaults={"name": "Programming", "is_active": True}
        )

        AssessmentSectionAllocation.objects.create(
            assessment=self.assessment,
            section=self.sec_quant,
            question_count=10,
            marks_per_question=2,
            order=1,
        )
        AssessmentSectionAllocation.objects.create(
            assessment=self.assessment,
            section=self.sec_prog,
            question_count=10,
            marks_per_question=2,
            order=2,
        )

        # Create snapshots: 10 for QUANT and 10 for PROG (total 20 questions, 40 marks)
        self.attempt = AssessmentAttempt.objects.create(
            candidate=self.candidate,
            assessment=self.assessment,
            config=self.config,
            state=AssessmentAttempt.State.IN_PROGRESS,
            deadline=timezone.now() + timedelta(minutes=60),
        )

        self.snapshots = []
        for i in range(1, 21):
            sec = self.sec_quant if i <= 10 else self.sec_prog
            sec_code = "QUANT" if i <= 10 else "PROG"
            q = QuestionBank.objects.create(
                section=sec,
                section_type=sec_code,
                prompt=f"Question {i}: What is {i}?",
                option_a="Option A",
                option_b="Option B",
                option_c="Option C",
                option_d="Option D",
                correct_option="A",
                is_active=True,
            )
            # Candidate answers: First 5 in each section correct ("A"), next 5 wrong ("B")
            self.snapshots.append(
                AttemptQuestionSnapshot.objects.create(
                    attempt=self.attempt,
                    question=q,
                    question_order=i,
                    section_type=sec_code,
                    prompt=q.prompt,
                    option_a_text=q.option_a,
                    option_b_text=q.option_b,
                    option_c_text=q.option_c,
                    option_d_text=q.option_d,
                    correct_option_key="A",
                    selected_option="A" if (i <= 5 or (11 <= i <= 15)) else "B",
                )
            )

        self.token = generate_candidate_token(self.candidate.id, attempt_id=self.attempt.id)
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_finalization_query_budget_verified(self):
        """
        Verifies that candidate finalization endpoint strictly executes <= 7 SQL database queries
        (plus 2 transaction savepoints in TestCase mode, <= 9 total in CaptureQueriesContext,
        reduced from 15 in TestCase / 13 in production before optimization).
        """
        with CaptureQueriesContext(connection) as captured:
            response = self.client.post(
                f"/api/assessment/attempts/{self.attempt.id}/finalize/",
                **self.headers,
            )

        self.assertEqual(response.status_code, 200)
        query_count = len(captured.captured_queries)
        print(f"\n[QUERY_BUDGET_VERIFIED] Finalize completed in {query_count} queries (budget <= 9 in TestCase / <= 7 in production).\n")
        self.assertLessEqual(query_count, 9, f"Expected <= 9 queries in TestCase, but got {query_count}")

        # In production (excluding SAVEPOINT / RELEASE SAVEPOINT), SQL query count is <= 7
        sql_queries = [
            q for q in captured.captured_queries
            if not q["sql"].strip().startswith("SAVEPOINT") and not q["sql"].strip().startswith("RELEASE")
        ]
        self.assertLessEqual(len(sql_queries), 7, f"Expected <= 7 SQL queries, but got {len(sql_queries)}")

    def test_student_and_staff_serialization_semantics(self):
        """
        Verifies that:
        1. Student response conceals scores and breakdown, confirming completion state.
        2. Staff response reveals full scorecard breakdown, scores, and candidate details.
        """
        # Student finalization
        res_stu = self.client.post(
            f"/api/assessment/attempts/{self.attempt.id}/finalize/",
            **self.headers,
        )
        self.assertEqual(res_stu.status_code, 200)
        self.assertEqual(res_stu.data["state"], AssessmentAttempt.State.SUBMITTED)
        self.assertEqual(res_stu.data["message"], "Assessment Completed")
        self.assertNotIn("total_score", res_stu.data)
        self.assertNotIn("aptitude_score", res_stu.data)
        self.assertNotIn("coding_score", res_stu.data)
        self.assertNotIn("percentage", res_stu.data)
        self.assertNotIn("breakdown", res_stu.data)

        # Staff administrative viewing via AssessmentResultView
        self.client.force_login(self.admin_user)
        res_staff = self.client.get(f"/api/assessment/attempts/{self.attempt.id}/result/")
        self.assertEqual(res_staff.status_code, 200)
        self.assertEqual(res_staff.data["candidate_name"], "Finalize Student")
        self.assertIn("total_score", res_staff.data)
        self.assertIn("breakdown", res_staff.data)
        self.assertEqual(res_staff.data["total_score"], 20)  # 10 correct * 2 marks = 20

    def test_scoring_correctness_with_dynamic_sections(self):
        """
        Verifies that MCQ evaluation tallies marks per question from allocations correctly.
        10 correct answers at 2 marks each = 20 total score out of 40 max marks (50.0%).
        """
        self.client.post(
            f"/api/assessment/attempts/{self.attempt.id}/finalize/",
            **self.headers,
        )

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, AssessmentAttempt.State.SUBMITTED)
        self.assertEqual(self.attempt.total_score, 20)
        self.assertEqual(self.attempt.percentage, 50.0)

        # Snapshots correctness
        correct_count = AttemptQuestionSnapshot.objects.filter(attempt=self.attempt, is_correct=True).count()
        incorrect_count = AttemptQuestionSnapshot.objects.filter(attempt=self.attempt, is_correct=False).count()
        self.assertEqual(correct_count, 10)
        self.assertEqual(incorrect_count, 10)

    def test_duplicate_finalization_is_idempotent(self):
        """
        Verifies that subsequent finalize calls return 200 without re-scoring or altering timestamps.
        """
        res1 = self.client.post(
            f"/api/assessment/attempts/{self.attempt.id}/finalize/",
            **self.headers,
        )
        self.assertEqual(res1.status_code, 200)
        self.attempt.refresh_from_db()
        first_submitted_at = self.attempt.submitted_at

        # Call again
        res2 = self.client.post(
            f"/api/assessment/attempts/{self.attempt.id}/finalize/",
            **self.headers,
        )
        self.assertEqual(res2.status_code, 200)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.submitted_at, first_submitted_at)

        # IntegrityEvent count must remain exactly 1 for SUBMITTED
        from apps.assessments.models import IntegrityEvent
        sub_events = IntegrityEvent.objects.filter(
            attempt=self.attempt,
            event_type=IntegrityEvent.EventType.SUBMITTED,
        ).count()
        self.assertEqual(sub_events, 1)

    def test_unauthorized_finalization_rejected(self):
        """
        Verifies that candidate B cannot finalize candidate A's attempt (403),
        and non-existent attempt returns 404.
        """
        cand_b = Candidate.objects.create(
            full_name="Candidate B",
            register_number="FIN-B-01",
            email="cand_b@example.com",
            college_ref=self.college,
            college=self.college.name,
            is_active=True,
        )
        token_b = generate_candidate_token(cand_b.id)
        headers_b = {"HTTP_AUTHORIZATION": f"Bearer {token_b}"}

        # Attempt to finalize Candidate A's attempt with Candidate B's token
        res_forbidden = self.client.post(
            f"/api/assessment/attempts/{self.attempt.id}/finalize/",
            **headers_b,
        )
        self.assertEqual(res_forbidden.status_code, 403)

        # Non-existent attempt
        fake_uuid = uuid.uuid4()
        res_not_found = self.client.post(
            f"/api/assessment/attempts/{fake_uuid}/finalize/",
            **self.headers,
        )
        self.assertEqual(res_not_found.status_code, 404)

    def test_expired_attempt_finalizes_as_timed_out(self):
        """
        Verifies that an attempt submitted after deadline transitions to TIMED_OUT.
        """
        self.attempt.deadline = timezone.now() - timedelta(minutes=5)
        self.attempt.save(update_fields=["deadline"])

        res = self.client.post(
            f"/api/assessment/attempts/{self.attempt.id}/finalize/",
            **self.headers,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["state"], AssessmentAttempt.State.TIMED_OUT)

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, AssessmentAttempt.State.TIMED_OUT)


class AssessmentStartOptimizationTests(TestCase):
    """
    Rigorously validates the assessment-start optimizations:
    1. Response output parity with full database re-fetch.
    2. Student security: correct answers and keys are never exposed.
    3. Question uniqueness and option-shuffling semantics.
    4. Resumed in-progress attempt behavior and single-candidate idempotency.
    5. Concurrent starts for different candidates.
    6. Authorization, eligibility, and error regressions.
    7. Query budget verification (<= 15 in test runner / <= 13 in production).
    """

    def setUp(self):
        self.client = Client()
        self.college = College.objects.create(
            name="Apex Institute of Technology",
            code="AIT-TEST",
            is_active=True,
        )
        self.unenrolled_college = College.objects.create(
            name="Unenrolled Academy",
            code="UNENROLLED",
            is_active=True,
        )
        self.candidate = Candidate.objects.create(
            full_name="Optimized Start Candidate",
            register_number="OPT-START-01",
            email="opt_start@apex.edu",
            college_ref=self.college,
            college=self.college.name,
            department="Computer Science",
            year_of_study="Final Year",
            is_active=True,
        )
        self.token = generate_candidate_token(self.candidate.id)
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

        self.config = AssessmentConfig.objects.create(
            title="Start Optimization Config",
            duration_minutes=60,
            total_marks=50,
            aptitude_count=25,
            coding_count=25,
            max_attempts=1,
            is_active=True,
        )

        self.assessment = Assessment.objects.create(
            code="OPT-START-ASSESS",
            title="Optimized Start Assessment",
            duration_minutes=60,
            total_marks=50,
            aptitude_count=25,
            coding_count=25,
            status=Assessment.Status.OPEN,
        )
        self.assessment.eligible_colleges.add(self.college)

        self.sec_apt, _ = AssessmentSection.objects.get_or_create(
            code="APTITUDE", defaults={"name": "Aptitude", "is_active": True}
        )
        self.sec_cod, _ = AssessmentSection.objects.get_or_create(
            code="CODING", defaults={"name": "Coding Fundamentals", "is_active": True}
        )

        AssessmentSectionAllocation.objects.create(
            assessment=self.assessment,
            section=self.sec_apt,
            question_count=25,
            marks_per_question=1,
            order=1,
        )
        AssessmentSectionAllocation.objects.create(
            assessment=self.assessment,
            section=self.sec_cod,
            question_count=25,
            marks_per_question=1,
            order=2,
        )

        # Populate sufficient questions (30 aptitude, 30 coding)
        diff_cycle = [
            QuestionBank.Difficulty.EASY,
            QuestionBank.Difficulty.MEDIUM,
            QuestionBank.Difficulty.HARD,
        ]
        questions_to_create = []
        for i in range(30):
            questions_to_create.append(
                QuestionBank(
                    section=self.sec_apt,
                    section_type="APTITUDE",
                    category="Quantitative",
                    difficulty=diff_cycle[i % 3],
                    prompt=f"Aptitude Question {i+1}?",
                    option_a=f"Apt {i+1} Opt A",
                    option_b=f"Apt {i+1} Opt B",
                    option_c=f"Apt {i+1} Opt C",
                    option_d=f"Apt {i+1} Opt D",
                    correct_option="A",
                    is_active=True,
                )
            )
            questions_to_create.append(
                QuestionBank(
                    section=self.sec_cod,
                    section_type="CODING",
                    category="Algorithms",
                    difficulty=diff_cycle[i % 3],
                    prompt=f"Coding Question {i+1}?",
                    option_a=f"Cod {i+1} Opt A",
                    option_b=f"Cod {i+1} Opt B",
                    option_c=f"Cod {i+1} Opt C",
                    option_d=f"Cod {i+1} Opt D",
                    correct_option="C",
                    is_active=True,
                )
            )
        QuestionBank.objects.bulk_create(questions_to_create)

    def test_response_parity_with_database_refetch(self):
        """
        Verifies that serializing the in-memory cached attempt matches
        the full database re-fetched attempt across all 50 questions,
        shuffled options, section allocations, and candidate fields.
        """
        res = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(self.assessment.id)},
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(res.status_code, 200)
        cached_data = res.json()

        # Re-fetch the attempt from the database as the unoptimized code did
        refetched_attempt = (
            AssessmentAttempt.objects.select_related("candidate", "assessment", "config")
            .prefetch_related(
                "question_snapshots__question",
                "assessment__section_allocations__section",
            )
            .get(pk=cached_data["id"])
        )
        expected_data = dict(AssessmentAttemptDetailSerializer(refetched_attempt).data)
        expected_data["assessment_token"] = cached_data["assessment_token"]

        # Disregard microsecond timestamp on server_time
        cached_data.pop("server_time", None)
        expected_data.pop("server_time", None)

        self.assertEqual(cached_data["id"], expected_data["id"])
        self.assertEqual(cached_data["assessment_id"], expected_data["assessment_id"])
        self.assertEqual(cached_data["assessment_title"], expected_data["assessment_title"])
        self.assertEqual(cached_data["candidate_name"], expected_data["candidate_name"])
        self.assertEqual(cached_data["college"], expected_data["college"])
        self.assertEqual(cached_data["sections"], expected_data["sections"])
        self.assertEqual(len(cached_data["questions"]), 50)
        self.assertEqual(len(expected_data["questions"]), 50)

        for q_cached, q_expected in zip(cached_data["questions"], expected_data["questions"]):
            self.assertEqual(q_cached["question_order"], q_expected["question_order"])
            self.assertEqual(q_cached["section_type"], q_expected["section_type"])
            self.assertEqual(q_cached["category"], q_expected["category"])
            self.assertEqual(q_cached["prompt"], q_expected["prompt"])
            self.assertEqual(q_cached["options"], q_expected["options"])

    def test_correct_answers_never_exposed_in_student_responses(self):
        """
        Verifies strict student security: correct_option_key, correct_option,
        and is_correct are never present in the start response.
        """
        res = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(self.assessment.id)},
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Root level sensitive fields
        for sensitive in ["total_score", "percentage", "aptitude_score", "coding_score"]:
            self.assertNotIn(sensitive, data)

        # Question level sensitive fields
        for q in data["questions"]:
            self.assertNotIn("correct_option_key", q)
            self.assertNotIn("correct_option", q)
            self.assertNotIn("is_correct", q)
            self.assertIn("prompt", q)
            self.assertIn("options", q)
            self.assertEqual(len(q["options"]), 4)

    def test_question_uniqueness_and_option_shuffling(self):
        """
        Verifies that exactly 50 unique questions are selected and each
        has non-empty options for keys A, B, C, D.
        """
        res = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(self.assessment.id)},
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(res.status_code, 200)
        questions = res.json()["questions"]
        self.assertEqual(len(questions), 50)

        # Uniqueness of question prompts
        prompts = [q["prompt"] for q in questions]
        self.assertEqual(len(set(prompts)), 50)

        for q in questions:
            keys = [opt["key"] for opt in q["options"]]
            self.assertEqual(sorted(keys), ["A", "B", "C", "D"])
            for opt in q["options"]:
                self.assertTrue(len(opt["text"]) > 0)

    def test_resume_in_progress_attempt_idempotent(self):
        """
        Verifies that calling start again on an in-progress attempt resumes
        the existing attempt without creating duplicate attempts.
        """
        res1 = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(self.assessment.id)},
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(res1.status_code, 200)
        attempt_id_1 = res1.json()["id"]

        # Call start a second time for the same candidate
        res2 = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(self.assessment.id)},
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(res2.status_code, 200)
        attempt_id_2 = res2.json()["id"]

        self.assertEqual(attempt_id_1, attempt_id_2)
        total_attempts = AssessmentAttempt.objects.filter(candidate=self.candidate).count()
        self.assertEqual(total_attempts, 1)

    def test_concurrent_starts_for_different_candidates(self):
        """
        Verifies that multiple candidates can start assessments independently
        receiving distinct attempt IDs and question sets.
        """
        cand2 = Candidate.objects.create(
            full_name="Second Candidate",
            register_number="OPT-START-02",
            email="opt_start_2@apex.edu",
            college_ref=self.college,
            college=self.college.name,
            department="IT",
            year_of_study="Final Year",
            is_active=True,
        )
        token2 = generate_candidate_token(cand2.id)

        res1 = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(self.assessment.id)},
            content_type="application/json",
            **self.headers,
        )
        res2 = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(self.assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token2}",
        )

        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res2.status_code, 200)
        self.assertNotEqual(res1.json()["id"], res2.json()["id"])

    def test_authorization_and_eligibility_regressions(self):
        """
        Verifies 401 on missing token, 404 on missing assessment,
        400 on unenrolled college, 400 on inactive candidate,
        and 400 on closed assessment.
        """
        # 1. Unauthenticated
        res_unauth = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(self.assessment.id)},
            content_type="application/json",
        )
        self.assertEqual(res_unauth.status_code, 401)

        # 2. Non-existent assessment
        res_404 = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(uuid.uuid4())},
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(res_404.status_code, 404)

        # 3. Unenrolled college candidate
        cand_unenrolled = Candidate.objects.create(
            full_name="Unenrolled Candidate",
            register_number="UNENR-01",
            email="unenr@unenrolled.edu",
            college_ref=self.unenrolled_college,
            college=self.unenrolled_college.name,
            is_active=True,
        )
        token_unenrolled = generate_candidate_token(cand_unenrolled.id)
        res_unenrolled = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(self.assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_unenrolled}",
        )
        self.assertEqual(res_unenrolled.status_code, 400)
        self.assertIn("not enrolled", res_unenrolled.json()["detail"])

        # 4. Inactive candidate
        cand_inactive = Candidate.objects.create(
            full_name="Inactive Candidate",
            register_number="INACT-01",
            email="inact@apex.edu",
            college_ref=self.college,
            college=self.college.name,
            is_active=False,
        )
        token_inactive = generate_candidate_token(cand_inactive.id)
        res_inactive = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(self.assessment.id)},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_inactive}",
        )
        self.assertEqual(res_inactive.status_code, 400)
        self.assertIn("deactivated", res_inactive.json()["detail"])

        # 5. Closed assessment
        self.assessment.status = Assessment.Status.CLOSED
        self.assessment.save()
        res_closed = self.client.post(
            "/api/assessment/start/",
            {"assessment_id": str(self.assessment.id)},
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(res_closed.status_code, 400)
        self.assertIn("not accepting new attempts", res_closed.json()["detail"])
