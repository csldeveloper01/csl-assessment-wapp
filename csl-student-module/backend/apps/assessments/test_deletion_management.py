import uuid
from django.test import TestCase, Client
from django.utils import timezone
from apps.users.models import User
from apps.assessments.models import (
    College,
    Assessment,
    AssessmentConfig,
    Candidate,
    AssessmentAttempt,
    AttemptQuestionSnapshot,
    IntegrityEvent,
    AssessmentSection,
    QuestionBank,
)


class DeletionManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_user(
            username="super_admin",
            email="super_admin@csl.com",
            password="AdminPassword123!",
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.superuser)

        self.config = AssessmentConfig.objects.create(
            title="Global Policy Config",
            duration_minutes=60,
            total_marks=50,
            is_active=True,
        )

        self.college = College.objects.create(
            name="Apex University",
            code="APEX01",
            is_active=True,
        )

        self.assessment = Assessment.objects.create(
            title="Standard Engineering Placement",
            code="SEP2026",
            duration_minutes=60,
            total_marks=50,
            status=Assessment.Status.READY,
        )
        self.assessment.eligible_colleges.add(self.college)

        self.section = AssessmentSection.objects.create(
            name="Analytical Reasoning",
            code="AR01",
            is_active=True,
        )

    # ─── 1. CANDIDATE DELETION TESTS ──────────────────────────────────────────
    def test_candidate_single_delete_without_attempts(self):
        candidate = Candidate.objects.create(
            full_name="Fresh Candidate",
            email="fresh@college.edu",
            register_number="REG-FRESH-01",
            college=self.college.name,
            college_ref=self.college,
        )
        resp = self.client.delete(f"/api/csl-admin/candidates/{candidate.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Candidate.objects.filter(id=candidate.id).exists())

    def test_candidate_single_delete_with_attempts_anonymizes_pii(self):
        candidate = Candidate.objects.create(
            full_name="Active Testee",
            email="testee@college.edu",
            register_number="REG-TESTEE-01",
            phone_number="9876543210",
            college=self.college.name,
            college_ref=self.college,
        )
        attempt = AssessmentAttempt.objects.create(
            candidate=candidate,
            config=self.config,
            assessment=self.assessment,
            state=AssessmentAttempt.State.SUBMITTED,
            total_score=42,
            started_at=timezone.now(),
            submitted_at=timezone.now(),
        )

        resp = self.client.delete(f"/api/csl-admin/candidates/{candidate.id}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("action"), "ANONYMIZED")

        # Candidate record must still exist so attempt isn't orphaned
        candidate.refresh_from_db()
        self.assertTrue(candidate.full_name.startswith("[Deleted Candidate"))
        self.assertTrue(candidate.email.endswith("@anonymized.csl"))
        self.assertEqual(candidate.phone_number, "")
        self.assertFalse(candidate.is_active)

        # Attempt and scores must remain intact
        attempt.refresh_from_db()
        self.assertEqual(attempt.candidate_id, candidate.id)
        self.assertEqual(attempt.total_score, 42)

    def test_candidate_bulk_delete_mixed(self):
        c_fresh1 = Candidate.objects.create(
            full_name="Fresh One",
            email="fresh1@college.edu",
            register_number="REG-B-01",
            college_ref=self.college,
        )
        c_fresh2 = Candidate.objects.create(
            full_name="Fresh Two",
            email="fresh2@college.edu",
            register_number="REG-B-02",
            college_ref=self.college,
        )
        c_attempt = Candidate.objects.create(
            full_name="Attempted One",
            email="attempted@college.edu",
            register_number="REG-B-03",
            college_ref=self.college,
        )
        AssessmentAttempt.objects.create(
            candidate=c_attempt,
            config=self.config,
            assessment=self.assessment,
            state=AssessmentAttempt.State.SUBMITTED,
            started_at=timezone.now(),
        )

        ids = [c_fresh1.id, c_fresh2.id, c_attempt.id]
        resp = self.client.post(
            "/api/csl-admin/candidates/bulk-delete/",
            {"ids": ids},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["deleted_count"], 2)
        self.assertEqual(data["anonymized_count"], 1)

        self.assertFalse(Candidate.objects.filter(id=c_fresh1.id).exists())
        self.assertFalse(Candidate.objects.filter(id=c_fresh2.id).exists())
        c_attempt.refresh_from_db()
        self.assertTrue(c_attempt.full_name.startswith("[Deleted Candidate"))

    # ─── 2. COLLEGE DELETION TESTS ────────────────────────────────────────────
    def test_college_delete_allowed_without_attempts(self):
        college2 = College.objects.create(name="Empty College", code="EMP01")
        # Candidate with no attempts
        Candidate.objects.create(
            full_name="Fresh Student",
            email="fresh.s@emp.edu",
            register_number="EMP-001",
            college_ref=college2,
        )
        resp = self.client.delete(f"/api/csl-admin/colleges/{college2.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(College.objects.filter(id=college2.id).exists())

    def test_college_delete_blocked_when_attempts_exist(self):
        cand = Candidate.objects.create(
            full_name="Attempted Student",
            email="attempt.s@apex.edu",
            register_number="APEX-001",
            college_ref=self.college,
        )
        AssessmentAttempt.objects.create(
            candidate=cand,
            config=self.config,
            assessment=self.assessment,
            state=AssessmentAttempt.State.SUBMITTED,
            started_at=timezone.now(),
        )

        # Single delete attempt is rejected with 400
        resp = self.client.delete(f"/api/csl-admin/colleges/{self.college.id}/")
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(College.objects.filter(id=self.college.id).exists())

        # Bulk delete attempt blocks deletion
        resp = self.client.post(
            "/api/csl-admin/colleges/bulk-delete/",
            {"ids": [self.college.id]},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["deleted_count"], 0)
        self.assertEqual(data["blocked_count"], 1)
        self.assertTrue(College.objects.filter(id=self.college.id).exists())

    # ─── 3. ASSESSMENT DELETION TESTS ─────────────────────────────────────────
    def test_assessment_delete_without_attempts(self):
        empty_asmt = Assessment.objects.create(
            title="Unused Assessment",
            code="UNUSED01",
            duration_minutes=30,
            total_marks=20,
        )
        resp = self.client.delete(f"/api/csl-admin/assessments/{empty_asmt.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Assessment.objects.filter(id=empty_asmt.id).exists())

    def test_assessment_bulk_delete_archives_when_attempts_exist(self):
        cand = Candidate.objects.create(
            full_name="Candidate Asmt",
            email="asmt@apex.edu",
            register_number="ASMT-001",
            college_ref=self.college,
        )
        AssessmentAttempt.objects.create(
            candidate=cand,
            config=self.config,
            assessment=self.assessment,
            state=AssessmentAttempt.State.SUBMITTED,
            started_at=timezone.now(),
        )

        empty_asmt = Assessment.objects.create(
            title="Empty Round",
            code="EMP_RND",
            duration_minutes=30,
            total_marks=25,
        )

        resp = self.client.post(
            "/api/csl-admin/assessments/bulk-delete/",
            {"ids": [str(self.assessment.id), str(empty_asmt.id)]},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["deleted_count"], 1)
        self.assertEqual(data["archived_count"], 1)

        self.assertFalse(Assessment.objects.filter(id=empty_asmt.id).exists())
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, Assessment.Status.ARCHIVED)

    # ─── 4. SECTION DELETION TESTS ────────────────────────────────────────────
    def test_section_delete_blocked_when_referenced(self):
        # Referenced by question
        QuestionBank.objects.create(
            prompt="Sample Logic Question?",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_option="A",
            section=self.section,
        )

        # Single delete is rejected with 400
        resp = self.client.delete(f"/api/csl-admin/sections/{self.section.id}/")
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(AssessmentSection.objects.filter(id=self.section.id).exists())

        # Bulk delete reports blocked
        resp = self.client.post(
            "/api/csl-admin/sections/bulk-delete/",
            {"ids": [self.section.id]},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["deleted_count"], 0)
        self.assertEqual(data["blocked_count"], 1)
        self.assertTrue(AssessmentSection.objects.filter(id=self.section.id).exists())

    def test_section_delete_succeeds_when_unreferenced(self):
        unref_sec = AssessmentSection.objects.create(
            name="Unreferenced Section",
            code="UNREF",
            is_active=True,
        )
        resp = self.client.delete(f"/api/csl-admin/sections/{unref_sec.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(AssessmentSection.objects.filter(id=unref_sec.id).exists())

    # ─── 5. ATTEMPT DELETION TESTS ────────────────────────────────────────────
    def test_attempt_single_and_bulk_delete_cascades(self):
        cand = Candidate.objects.create(
            full_name="Candidate Cascade",
            email="cascade@apex.edu",
            register_number="CASC-001",
            college_ref=self.college,
        )
        attempt1 = AssessmentAttempt.objects.create(
            candidate=cand,
            config=self.config,
            assessment=self.assessment,
            state=AssessmentAttempt.State.SUBMITTED,
            started_at=timezone.now(),
        )
        q = QuestionBank.objects.create(
            prompt="Snapshot Question 1",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_option="A",
            section=self.section,
        )
        AttemptQuestionSnapshot.objects.create(
            attempt=attempt1,
            question=q,
            question_order=1,
            section_type="APTITUDE",
            prompt="Snapshot Question 1",
            option_a_text="A",
            option_b_text="B",
            option_c_text="C",
            option_d_text="D",
            correct_option_key="A",
        )
        IntegrityEvent.objects.create(
            attempt=attempt1,
            event_type="TAB_HIDDEN",
        )

        # Single delete attempt
        resp = self.client.delete(f"/api/csl-admin/attempts/{attempt1.id}/review/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(AssessmentAttempt.objects.filter(id=attempt1.id).exists())
        self.assertFalse(AttemptQuestionSnapshot.objects.filter(attempt_id=attempt1.id).exists())
        self.assertFalse(IntegrityEvent.objects.filter(attempt_id=attempt1.id).exists())

        # Bulk delete attempts
        attempt2 = AssessmentAttempt.objects.create(
            candidate=cand,
            config=self.config,
            assessment=self.assessment,
            state=AssessmentAttempt.State.IN_PROGRESS,
            started_at=timezone.now(),
        )
        attempt3 = AssessmentAttempt.objects.create(
            candidate=cand,
            config=self.config,
            assessment=self.assessment,
            state=AssessmentAttempt.State.TIMED_OUT,
            started_at=timezone.now(),
        )
        resp = self.client.post(
            "/api/csl-admin/attempts/bulk-delete/",
            {"ids": [str(attempt2.id), str(attempt3.id)]},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["deleted_count"], 2)
        self.assertFalse(AssessmentAttempt.objects.filter(id__in=[attempt2.id, attempt3.id]).exists())

    # ─── 6. INTEGRITY EVENT DELETION TESTS ────────────────────────────────────
    def test_integrity_event_single_and_bulk_delete(self):
        cand = Candidate.objects.create(
            full_name="Candidate Integrity",
            email="integ@apex.edu",
            register_number="INTEG-001",
            college_ref=self.college,
        )
        att = AssessmentAttempt.objects.create(
            candidate=cand,
            config=self.config,
            assessment=self.assessment,
            state=AssessmentAttempt.State.IN_PROGRESS,
            started_at=timezone.now(),
        )
        ev1 = IntegrityEvent.objects.create(
            attempt=att,
            event_type="FULLSCREEN_EXIT",
        )
        ev2 = IntegrityEvent.objects.create(
            attempt=att,
            event_type="TAB_HIDDEN",
        )

        # Single delete
        resp = self.client.delete(f"/api/csl-admin/integrity-events/{ev1.id}/review/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(IntegrityEvent.objects.filter(id=ev1.id).exists())

        # Bulk delete
        resp = self.client.post(
            "/api/csl-admin/integrity-events/bulk-delete/",
            {"ids": [ev2.id]},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["deleted_count"], 1)
        self.assertFalse(IntegrityEvent.objects.filter(id=ev2.id).exists())

    # ─── 7. USER STATUS TOGGLE AND DELETION SAFETY TESTS ──────────────────────
    def test_user_self_deletion_and_deactivation_blocked(self):
        # Cannot deactivate self
        resp = self.client.post(f"/api/csl-admin/users/{self.superuser.id}/")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("cannot change the active status of your own account", resp.json().get("detail", "").lower())

        # Cannot delete self
        resp = self.client.delete(f"/api/csl-admin/users/{self.superuser.id}/")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("cannot delete your own", resp.json().get("detail", "").lower())

    def test_user_last_superuser_protection(self):
        # Create a second user who is staff but not superuser
        staff = User.objects.create_user(
            username="staff_member",
            email="staff@csl.com",
            password="StaffPassword123!",
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
            is_staff=True,
            is_superuser=False,
        )

        # Non-superuser cannot access admin users endpoint
        self.client.force_login(staff)
        resp = self.client.delete(f"/api/csl-admin/users/{staff.id}/")
        self.assertEqual(resp.status_code, 403)

        # Login back as superuser
        self.client.force_login(self.superuser)

        # Superuser deactivating staff member succeeds
        resp = self.client.post(f"/api/csl-admin/users/{staff.id}/")
        self.assertEqual(resp.status_code, 200)
        staff.refresh_from_db()
        self.assertFalse(staff.is_active)

        # Superuser deleting staff member succeeds
        resp = self.client.delete(f"/api/csl-admin/users/{staff.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(id=staff.id).exists())
