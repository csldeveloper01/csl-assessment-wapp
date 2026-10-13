from datetime import date
from io import StringIO

from django.core.management import call_command
from django.db.models import ProtectedError
from django.test import TestCase

from apps.courses.cli import CourseManagementCLI
from apps.courses.models import Batch, Course, CourseSkill
from apps.skills.models import Skill, SkillCategory, SubSkill
from apps.users.models import StudentProfile, User


class _FakeCommand:
    """Minimal stand-in for BaseCommand for CourseManagementCLI testing."""

    def __init__(self, out):
        self.stdout = _Stdout(out)
        self.style = _NoStyle()


class _Stdout:
    def __init__(self, out):
        self._out = out

    def write(self, text=""):
        self._out.write(str(text) + "\n")


class _NoStyle:
    def SUCCESS(self, text):
        return text

    def WARNING(self, text):
        return text

    def ERROR(self, text):
        return text


def make_course_cli(out, script):
    """Build a CourseManagementCLI whose input comes from a scripted list."""
    answers = iter(script)

    def input_fn(_label):
        return next(answers)

    return CourseManagementCLI(_FakeCommand(out), input_fn=input_fn)


class AdminCliCourseMenuTests(TestCase):
    """Full admin CLI integration tests testing course menus and navigation."""

    def _run(self, script):
        out = StringIO()
        answers = iter(script)

        def scripted_input(_label):
            return next(answers)

        import builtins
        old_input = builtins.input
        builtins.input = scripted_input
        try:
            call_command("admin_cli", stdout=out)
        finally:
            builtins.input = old_input
        return out.getvalue()

    def test_main_menu_lists_course_management(self):
        output = self._run(["5"])
        self.assertIn("4. Course Management", output)
        self.assertIn("Exiting Admin CLI", output)

    def test_course_management_entry_point_opens(self):
        output = self._run(["4", "8", "5"])
        self.assertIn("COURSE MANAGEMENT", output)
        self.assertIn("1. List Courses", output)
        self.assertIn("6. Manage Batches", output)
        self.assertIn("7. Manage Required Skills", output)
        self.assertIn("Exiting Admin CLI", output)

    def test_add_course_through_admin_cli(self):
        output = self._run(["4", "2", "CS101", "Computer Science", "", "8", "5"])
        self.assertIn("Course 'CS101 - Computer Science' created.", output)
        self.assertTrue(Course.objects.filter(code="CS101").exists())

    def test_assign_student_course_batch_cli(self):
        student = User.objects.create_user(
            username="student_assign@example.com",
            email="student_assign@example.com",
            password="testpassword123",
            first_name="Jane",
            role=User.Role.STUDENT,
            status=User.AccountStatus.ACTIVE,
        )
        course = Course.objects.create(name="Data Science", code="DS101", is_active=True)
        batch = Batch.objects.create(course=course, name="2026-Alpha", start_date="2026-01-01", is_active=True)

        # In admin_cli:
        # 2: User Management
        # 2: Assign Student Course/Batch
        # 1: Select Student 1
        # 1: Select Course 1
        # 1: Select Batch 1
        # y: Confirm
        # 4: Back to Main Menu
        # 5: Exit
        output = self._run(["2", "2", "1", "1", "1", "y", "4", "5"])
        self.assertIn("assigned to DS101 / 2026-Alpha", output)

        student_profile = StudentProfile.objects.get(user=student)
        self.assertEqual(student_profile.course, course)
        self.assertEqual(student_profile.batch, batch)



class CourseManagementCLITests(TestCase):
    """Targeted tests for Course, Batch, and CourseSkill CLI logic."""

    def setUp(self):
        self.out = StringIO()
        self.course = Course.objects.create(code="CS101", name="Intro to CS")
        self.category = SkillCategory.objects.create(name="Programming")
        self.skill = Skill.objects.create(category=self.category, name="Python")
        self.sub_skill1 = SubSkill.objects.create(skill=self.skill, name="Fundamentals")
        self.sub_skill2 = SubSkill.objects.create(skill=self.skill, name="OOP")

    # ── Course operations ─────────────────────────────────────────────────
    def test_list_courses(self):
        cli = make_course_cli(self.out, [""])
        cli.list_courses()
        output = self.out.getvalue()
        self.assertIn("[CS101] Intro to CS", output)
        self.assertIn("Batches: 0", output)

    def test_add_course_success(self):
        cli = make_course_cli(self.out, ["DS201", "Data Science", "Desc"])
        cli.add_course()
        self.assertIn("Course 'DS201 - Data Science' created.", self.out.getvalue())
        self.assertTrue(Course.objects.filter(code="DS201").exists())

    def test_add_course_duplicate_code_rejected(self):
        cli = make_course_cli(self.out, ["CS101"])
        cli.add_course()
        self.assertIn("already exists", self.out.getvalue())
        self.assertEqual(Course.objects.count(), 1)

    def test_edit_course(self):
        # 1 selects course 1, then new code (Enter keeps), new name, new desc
        cli = make_course_cli(self.out, ["1", "", "Advanced CS", "Updated desc"])
        cli.edit_course()
        self.course.refresh_from_db()
        self.assertEqual(self.course.name, "Advanced CS")
        self.assertEqual(self.course.description, "Updated desc")

    def test_toggle_course(self):
        cli = make_course_cli(self.out, ["1"])
        cli.toggle_course()
        self.course.refresh_from_db()
        self.assertFalse(self.course.is_active)
        self.assertIn("now inactive", self.out.getvalue())

    def test_delete_course_success(self):
        cli = make_course_cli(self.out, ["1", "y"])
        cli.delete_course()
        self.assertIn("deleted", self.out.getvalue())
        self.assertEqual(Course.objects.count(), 0)

    def test_delete_course_cancelled(self):
        cli = make_course_cli(self.out, ["1", "n"])
        cli.delete_course()
        self.assertIn("cancelled", self.out.getvalue())
        self.assertEqual(Course.objects.count(), 1)

    def test_delete_course_protected_by_student(self):
        user = User.objects.create_user(
            username="stu1",
            email="stu1@example.com",
            role=User.Role.STUDENT,
        )
        StudentProfile.objects.create(
            user=user,
            registration_number="REG001",
            first_name="Alice",
            course=self.course,
        )
        cli = make_course_cli(self.out, ["1", "y"])
        cli.delete_course()
        self.assertIn("Cannot delete course", self.out.getvalue())
        self.assertEqual(Course.objects.count(), 1)

    # ── Batch operations ──────────────────────────────────────────────────
    def test_add_batch_success(self):
        cli = make_course_cli(self.out, ["2026-A", "2026-01-15", "2026-06-30"])
        cli.add_batch(self.course)
        self.assertIn("Batch '2026-A' created", self.out.getvalue())
        self.assertTrue(Batch.objects.filter(course=self.course, name="2026-A").exists())

    def test_add_batch_duplicate_name_rejected(self):
        Batch.objects.create(course=self.course, name="2026-A", start_date=date(2026, 1, 1))
        cli = make_course_cli(self.out, ["2026-A"])
        cli.add_batch(self.course)
        self.assertIn("already exists", self.out.getvalue())
        self.assertEqual(Batch.objects.filter(course=self.course).count(), 1)

    def test_add_batch_invalid_dates(self):
        cli = make_course_cli(self.out, ["2026-A", "2026-06-01", "2026-01-01"])
        cli.add_batch(self.course)
        self.assertIn("cannot be earlier than start date", self.out.getvalue())
        self.assertEqual(Batch.objects.filter(course=self.course).count(), 0)

    def test_edit_batch(self):
        batch = Batch.objects.create(course=self.course, name="2026-A", start_date=date(2026, 1, 1))
        cli = make_course_cli(self.out, ["1", "2026-B", "", ""])
        cli.edit_batch(self.course)
        batch.refresh_from_db()
        self.assertEqual(batch.name, "2026-B")

    def test_toggle_batch(self):
        batch = Batch.objects.create(course=self.course, name="2026-A", start_date=date(2026, 1, 1))
        cli = make_course_cli(self.out, ["1"])
        cli.toggle_batch(self.course)
        batch.refresh_from_db()
        self.assertFalse(batch.is_active)

    def test_delete_batch_protected(self):
        batch = Batch.objects.create(course=self.course, name="2026-A", start_date=date(2026, 1, 1))
        user = User.objects.create_user(
            username="stu2",
            email="stu2@example.com",
            role=User.Role.STUDENT,
        )
        StudentProfile.objects.create(
            user=user,
            registration_number="REG002",
            first_name="Bob",
            course=self.course,
            batch=batch,
        )
        cli = make_course_cli(self.out, ["1", "y"])
        cli.delete_batch(self.course)
        self.assertIn("Cannot delete batch", self.out.getvalue())
        self.assertEqual(Batch.objects.filter(course=self.course).count(), 1)

    # ── Required Skills operations ────────────────────────────────────────
    def test_add_required_subskills_all(self):
        # 1 selects category, 1 selects skill, 'ALL' selects both subskills
        cli = make_course_cli(self.out, ["1", "1", "ALL"])
        cli.add_required_skill(self.course)
        self.assertIn("Successfully mapped 2 subskill(s)", self.out.getvalue())
        self.assertEqual(CourseSkill.objects.filter(course=self.course).count(), 2)

    def test_add_required_subskills_by_numbers(self):
        # 1 selects category, 1 selects skill, '1, 2' selects both
        cli = make_course_cli(self.out, ["1", "1", "1, 2"])
        cli.add_required_skill(self.course)
        self.assertIn("Successfully mapped 2 subskill(s)", self.out.getvalue())
        self.assertTrue(
            CourseSkill.objects.filter(
                course=self.course, skill=self.skill, sub_skill=self.sub_skill1
            ).exists()
        )

    def test_add_required_skill_duplicate_protection(self):
        CourseSkill.objects.create(
            course=self.course, skill=self.skill, sub_skill=self.sub_skill1
        )
        # Attempt to add subskill 1 again
        cli = make_course_cli(self.out, ["1", "1", "1"])
        cli.add_required_skill(self.course)
        self.assertIn("already exists. Skipped.", self.out.getvalue())
        self.assertEqual(CourseSkill.objects.filter(course=self.course).count(), 1)

    def test_add_required_skill_without_subskill(self):
        skill_no_sub = Skill.objects.create(category=self.category, name="Git")
        # 1 selects category, 1 is 'Git' (ordered by name: Git, Python), 'y' confirms whole skill
        cli = make_course_cli(self.out, ["1", "1", "y"])
        cli.add_required_skill(self.course)
        self.assertIn("Skill 'Git' added to CS101.", self.out.getvalue())
        self.assertTrue(
            CourseSkill.objects.filter(
                course=self.course, skill=skill_no_sub, sub_skill__isnull=True
            ).exists()
        )

    def test_view_required_skills_hierarchy(self):
        CourseSkill.objects.create(
            course=self.course, skill=self.skill, sub_skill=self.sub_skill1
        )
        CourseSkill.objects.create(
            course=self.course, skill=self.skill, sub_skill=self.sub_skill2
        )
        cli = make_course_cli(self.out, [""])
        cli.view_required_skills(self.course)
        output = self.out.getvalue()
        self.assertIn("Programming", output)
        self.assertIn("└── Python", output)
        self.assertIn("├── Fundamentals", output)
        self.assertIn("└── OOP", output)

    def test_remove_required_skill(self):
        mapping = CourseSkill.objects.create(
            course=self.course, skill=self.skill, sub_skill=self.sub_skill1
        )
        cli = make_course_cli(self.out, ["1", "y"])
        cli.remove_required_skill(self.course)
        self.assertIn("Removed 'Python → Fundamentals'", self.out.getvalue())
        self.assertEqual(CourseSkill.objects.filter(course=self.course).count(), 0)

    # ── Safe navigation & input tests ─────────────────────────────────────
    def test_back_selection_returns_none(self):
        cli = make_course_cli(self.out, ["b"])
        self.assertIsNone(cli.select_course())

    def test_invalid_selection_does_not_crash(self):
        cli = make_course_cli(self.out, ["999"])
        self.assertIsNone(cli.select_course())
        self.assertIn("Selection out of range", self.out.getvalue())
