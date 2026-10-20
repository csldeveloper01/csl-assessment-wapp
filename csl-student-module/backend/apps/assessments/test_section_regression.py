from django.test import TestCase, Client
from rest_framework.exceptions import ValidationError
from apps.users.models import User
from apps.assessments.models import (
    QuestionBank,
    AssessmentConfig,
    College,
    Assessment,
    Candidate,
    AssessmentAttempt,
    AssessmentSection,
    AssessmentSectionAllocation,
)
from apps.assessments.services import (
    start_assessment_for_candidate,
    validate_question_bank_sufficiency,
    select_balanced_questions,
    finalize_assessment_attempt,
)
from apps.assessments.tokens import generate_candidate_token


class SectionRegressionScenariosTestCase(TestCase):
    """
    Comprehensive regression test suite for data-driven assessment section handling:
    1. An assessment containing Coding and Aptitude.
    2. An assessment containing a custom section such as Database Engineering.
    3. An assessment containing multiple custom sections.
    4. An assessment containing only Coding.
    5. An assessment containing only Aptitude.
    6. An assessment containing neither Coding nor Aptitude.
    7. An empty or invalid section configuration.
    8. A section whose question pool is insufficient for its configured allocation.
    9. Sections with different question types or allocation rules supported by the existing model.
    10. Correct ordering, question allocation, and protection against accidental duplicate selection.
    """

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin_sec_reg",
            email="admin_sec_reg@example.com",
            password="SecurePassword123!",
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
            is_staff=True,
            is_superuser=True,
        )
        self.config = AssessmentConfig.objects.create(
            title="Global Config",
            duration_minutes=60,
            total_marks=50,
            is_active=True,
        )
        self.college = College.objects.create(
            name="Testing Institute of Technology",
            code="TIT001",
            is_active=True,
        )

        # Standard reusable sections
        self.sec_apt, _ = AssessmentSection.objects.get_or_create(
            code="APTITUDE", defaults={"name": "Aptitude", "order": 1}
        )
        self.sec_cod, _ = AssessmentSection.objects.get_or_create(
            code="CODING", defaults={"name": "Coding", "order": 2}
        )
        self.sec_db, _ = AssessmentSection.objects.get_or_create(
            code="DB_ENG", defaults={"name": "Database Engineering", "order": 3}
        )
        self.sec_sys, _ = AssessmentSection.objects.get_or_create(
            code="SYS_DESIGN", defaults={"name": "System Design", "order": 4}
        )

    def _create_candidate(self, email="cand@example.com", reg_no="REG001"):
        return Candidate.objects.create(
            full_name="Candidate One",
            register_number=reg_no,
            email=email,
            college=self.college.name,
            college_ref=self.college,
            department="CSE",
            year_of_study="4",
        )

    def _create_assessment(self, code, title, duration_minutes=60, total_marks=50, aptitude_count=0, coding_count=0):
        assessment = Assessment.objects.create(
            code=code,
            title=title,
            duration_minutes=duration_minutes,
            total_marks=total_marks,
            aptitude_count=aptitude_count,
            coding_count=coding_count,
            status=Assessment.Status.OPEN,
        )
        assessment.eligible_colleges.add(self.college)
        return assessment

    def _seed_questions(self, assessment, section, count, difficulty="EASY"):
        created = []
        for i in range(count):
            q = QuestionBank.objects.create(
                section=section,
                section_type=section.code,
                difficulty=difficulty,
                prompt=f"Question {i+1} for {section.code} ({difficulty})",
                option_a="Option A",
                option_b="Option B",
                option_c="Option C",
                option_d="Option D",
                correct_option="A",
                is_active=True,
            )
            assessment.questions.add(q)
            created.append(q)
        return created

    def test_scenario_1_coding_and_aptitude_assessment(self):
        """Scenario 1: Assessment containing Coding and Aptitude sections."""
        assessment = self._create_assessment(
            code="SCEN-1-APT-COD",
            title="Aptitude and Coding Assessment",
            duration_minutes=45,
            total_marks=20,
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment, section=self.sec_apt, question_count=3, marks_per_question=2, order=1
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment, section=self.sec_cod, question_count=2, marks_per_question=7, order=2
        )
        self._seed_questions(assessment, self.sec_apt, 5)
        self._seed_questions(assessment, self.sec_cod, 4)

        # Sufficiency
        self.assertTrue(validate_question_bank_sufficiency(assessment=assessment))

        # Start attempt
        cand = self._create_candidate("scen1@example.com", "REG-S1")
        attempt = start_assessment_for_candidate(cand, assessment=assessment)
        snapshots = list(attempt.question_snapshots.all())
        self.assertEqual(len(snapshots), 5)

        apt_snapshots = [s for s in snapshots if s.section_type == "APTITUDE"]
        cod_snapshots = [s for s in snapshots if s.section_type == "CODING"]
        self.assertEqual(len(apt_snapshots), 3)
        self.assertEqual(len(cod_snapshots), 2)

    def test_scenario_2_custom_section_database_engineering(self):
        """Scenario 2: Assessment containing a custom section such as Database Engineering."""
        assessment = self._create_assessment(
            code="SCEN-2-DB",
            title="Database Specialist Assessment",
            duration_minutes=60,
            total_marks=30,
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment, section=self.sec_db, question_count=4, marks_per_question=5, order=1
        )
        self._seed_questions(assessment, self.sec_db, 6)

        self.assertTrue(validate_question_bank_sufficiency(assessment=assessment))

        cand = self._create_candidate("scen2@example.com", "REG-S2")
        attempt = start_assessment_for_candidate(cand, assessment=assessment)
        snapshots = list(attempt.question_snapshots.all())
        self.assertEqual(len(snapshots), 4)
        for snap in snapshots:
            self.assertEqual(snap.section_type, "DB_ENG")

    def test_scenario_3_multiple_custom_sections(self):
        """Scenario 3: Assessment containing multiple custom sections (Database + System Design)."""
        assessment = self._create_assessment(
            code="SCEN-3-MULTI-CUSTOM",
            title="Advanced Architecture Assessment",
            duration_minutes=60,
            total_marks=50,
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment, section=self.sec_db, question_count=3, marks_per_question=10, order=1
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment, section=self.sec_sys, question_count=2, marks_per_question=10, order=2
        )
        self._seed_questions(assessment, self.sec_db, 5)
        self._seed_questions(assessment, self.sec_sys, 4)

        self.assertTrue(validate_question_bank_sufficiency(assessment=assessment))

        cand = self._create_candidate("scen3@example.com", "REG-S3")
        attempt = start_assessment_for_candidate(cand, assessment=assessment)
        snapshots = list(attempt.question_snapshots.all())
        self.assertEqual(len(snapshots), 5)
        self.assertEqual(len([s for s in snapshots if s.section_type == "DB_ENG"]), 3)
        self.assertEqual(len([s for s in snapshots if s.section_type == "SYS_DESIGN"]), 2)

    def test_scenario_4_only_coding(self):
        """Scenario 4: Assessment containing only Coding."""
        assessment = self._create_assessment(
            code="SCEN-4-ONLY-COD",
            title="Pure Coding Exam",
            duration_minutes=60,
            total_marks=50,
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment, section=self.sec_cod, question_count=5, marks_per_question=10, order=1
        )
        self._seed_questions(assessment, self.sec_cod, 8)

        self.assertTrue(validate_question_bank_sufficiency(assessment=assessment))

        cand = self._create_candidate("scen4@example.com", "REG-S4")
        attempt = start_assessment_for_candidate(cand, assessment=assessment)
        snapshots = list(attempt.question_snapshots.all())
        self.assertEqual(len(snapshots), 5)
        self.assertEqual(len([s for s in snapshots if s.section_type == "CODING"]), 5)
        self.assertEqual(len([s for s in snapshots if s.section_type == "APTITUDE"]), 0)

    def test_scenario_5_only_aptitude(self):
        """Scenario 5: Assessment containing only Aptitude."""
        assessment = self._create_assessment(
            code="SCEN-5-ONLY-APT",
            title="Pure Aptitude Exam",
            duration_minutes=40,
            total_marks=30,
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment, section=self.sec_apt, question_count=6, marks_per_question=5, order=1
        )
        self._seed_questions(assessment, self.sec_apt, 9)

        self.assertTrue(validate_question_bank_sufficiency(assessment=assessment))

        cand = self._create_candidate("scen5@example.com", "REG-S5")
        attempt = start_assessment_for_candidate(cand, assessment=assessment)
        snapshots = list(attempt.question_snapshots.all())
        self.assertEqual(len(snapshots), 6)
        self.assertEqual(len([s for s in snapshots if s.section_type == "APTITUDE"]), 6)
        self.assertEqual(len([s for s in snapshots if s.section_type == "CODING"]), 0)

    def test_scenario_6_neither_coding_nor_aptitude(self):
        """Scenario 6: Assessment containing neither Coding nor Aptitude."""
        assessment = self._create_assessment(
            code="SCEN-6-NEITHER",
            title="System Architecture Only Exam",
            duration_minutes=45,
            total_marks=20,
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment, section=self.sec_sys, question_count=4, marks_per_question=5, order=1
        )
        self._seed_questions(assessment, self.sec_sys, 7)

        self.assertTrue(validate_question_bank_sufficiency(assessment=assessment))

        cand = self._create_candidate("scen6@example.com", "REG-S6")
        attempt = start_assessment_for_candidate(cand, assessment=assessment)
        snapshots = list(attempt.question_snapshots.all())
        self.assertEqual(len(snapshots), 4)
        for s in snapshots:
            self.assertEqual(s.section_type, "SYS_DESIGN")

    def test_scenario_7_empty_or_invalid_section_configuration(self):
        """Scenario 7: Empty or invalid section configuration raises clear validation error."""
        assessment = self._create_assessment(
            code="SCEN-7-EMPTY",
            title="Empty Configuration Assessment",
            duration_minutes=30,
            total_marks=50,
            aptitude_count=0,
            coding_count=0,
        )
        cand = self._create_candidate("scen7@example.com", "REG-S7")

        # Sufficiency check fails
        with self.assertRaises(ValidationError) as ctx:
            validate_question_bank_sufficiency(assessment=assessment)
        self.assertIn("Assessment has no configured sections or questions", str(ctx.exception))

        # Starting attempt fails
        with self.assertRaises(ValidationError) as ctx:
            start_assessment_for_candidate(cand, assessment=assessment)
        self.assertIn("Assessment has no configured sections or questions", str(ctx.exception))

    def test_scenario_8_insufficient_pool_for_section(self):
        """Scenario 8: A section whose question pool is insufficient for its allocation raises ValidationError."""
        assessment = self._create_assessment(
            code="SCEN-8-SHORTAGE",
            title="Shortage Assessment",
            duration_minutes=30,
            total_marks=50,
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment, section=self.sec_db, question_count=10, marks_per_question=5, order=1
        )
        # Only seed 3 questions when 10 are required
        self._seed_questions(assessment, self.sec_db, 3)

        with self.assertRaises(ValidationError) as ctx:
            validate_question_bank_sufficiency(assessment=assessment)
        self.assertIn("Insufficient", str(ctx.exception))
        self.assertIn("shortage of 7", str(ctx.exception))

    def test_scenario_9_sections_with_distinct_marks_allocation(self):
        """Scenario 9: Sections with different question counts and marks per question scored correctly."""
        assessment = self._create_assessment(
            code="SCEN-9-WEIGHTS",
            title="Weighted Multi-Section Exam",
            duration_minutes=60,
            total_marks=26,
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment, section=self.sec_apt, question_count=3, marks_per_question=2, order=1
        )  # 6 marks
        AssessmentSectionAllocation.objects.create(
            assessment=assessment, section=self.sec_db, question_count=2, marks_per_question=10, order=2
        )  # 20 marks
        self._seed_questions(assessment, self.sec_apt, 5)
        self._seed_questions(assessment, self.sec_db, 5)

        cand = self._create_candidate("scen9@example.com", "REG-S9")
        attempt = start_assessment_for_candidate(cand, assessment=assessment)

        # Answer 1 Aptitude correctly (2 marks) and 1 DB correctly (10 marks) -> 12 marks
        snapshots = sorted(attempt.question_snapshots.all(), key=lambda s: s.question_order)
        apt_snap = [s for s in snapshots if s.section_type == "APTITUDE"][0]
        db_snap = [s for s in snapshots if s.section_type == "DB_ENG"][0]

        apt_snap.selected_option = apt_snap.correct_option_key
        apt_snap.save(update_fields=["selected_option"])
        db_snap.selected_option = db_snap.correct_option_key
        db_snap.save(update_fields=["selected_option"])

        finalized = finalize_assessment_attempt(attempt)
        self.assertEqual(finalized.total_score, 12)
        expected_percentage = round((12 / 26.0) * 100.0, 2)
        self.assertEqual(finalized.percentage, expected_percentage)

    def test_scenario_10_ordering_and_duplicate_protection(self):
        """Scenario 10: Section ordering is preserved, question count matches allocation, no duplicates."""
        assessment = self._create_assessment(
            code="SCEN-10-ORDER",
            title="Ordered Multi-Section Exam",
            duration_minutes=60,
            total_marks=40,
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment, section=self.sec_sys, question_count=3, marks_per_question=5, order=1
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment, section=self.sec_cod, question_count=4, marks_per_question=5, order=2
        )
        AssessmentSectionAllocation.objects.create(
            assessment=assessment, section=self.sec_apt, question_count=3, marks_per_question=5, order=3
        )

        self._seed_questions(assessment, self.sec_sys, 8)
        self._seed_questions(assessment, self.sec_cod, 8)
        self._seed_questions(assessment, self.sec_apt, 8)

        cand = self._create_candidate("scen10@example.com", "REG-S10")
        attempt = start_assessment_for_candidate(cand, assessment=assessment)

        snapshots = sorted(attempt.question_snapshots.all(), key=lambda s: s.question_order)
        self.assertEqual(len(snapshots), 10)

        # Verify ordering: first 3 are SYS_DESIGN, next 4 are CODING, last 3 are APTITUDE
        sys_group = snapshots[0:3]
        cod_group = snapshots[3:7]
        apt_group = snapshots[7:10]

        self.assertTrue(all(s.section_type == "SYS_DESIGN" for s in sys_group))
        self.assertTrue(all(s.section_type == "CODING" for s in cod_group))
        self.assertTrue(all(s.section_type == "APTITUDE" for s in apt_group))

        # Protection against duplicates
        seen_question_ids = set()
        for s in snapshots:
            self.assertNotIn(s.question_id, seen_question_ids, "Duplicate question detected across sections!")
            seen_question_ids.add(s.question_id)
