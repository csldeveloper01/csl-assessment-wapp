from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from apps.users.models import StudentProfile
from apps.courses.models import Course, Batch, CourseSkill
from apps.skills.models import SkillCategory, Skill, SubSkill
from apps.activities.models import (
    Activity,
    Assessment,
    AssessmentSection,
    Question,
    Task,
    Project,
    TaskSkill,
    ProjectSkill,
)

User = get_user_model()


class DjangoAdminIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_password = "SecretAdminPassword123!"
        self.admin_user = User.objects.create_user(
            username="csldeveloper01",
            email="csldeveloper01@gmail.com",
            password=self.admin_password,
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )

        # Create category, skill, subskills
        self.category = SkillCategory.objects.create(name="Programming")
        self.skill = Skill.objects.create(category=self.category, name="Python")
        self.sub1 = SubSkill.objects.create(skill=self.skill, name="Syntax", display_order=1)
        self.sub2 = SubSkill.objects.create(skill=self.skill, name="OOP", display_order=2)

        # Create course, batch
        self.course = Course.objects.create(code="CS101", name="Computer Science 101")
        self.batch = Batch.objects.create(
            course=self.course,
            name="2026-A",
            start_date=timezone.now().date(),
        )

        # Student user
        self.student_user = User.objects.create_user(
            username="student_test",
            email="student_test@example.com",
            password="StudentPass123!",
            role=User.Role.STUDENT,
            status=User.AccountStatus.PENDING,
        )
        self.profile = StudentProfile.objects.create(
            user=self.student_user,
            registration_number="CSL0099",
            first_name="Jane",
            last_name="Doe",
        )

    def test_admin_login_with_email(self):
        login_success = self.client.login(email="csldeveloper01@gmail.com", password=self.admin_password)
        self.assertTrue(login_success)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CSL Skill Matrix Administration")
        self.assertContains(response, "CSL Operational Dashboard")

    def test_approve_and_reject_student_actions(self):
        self.client.login(email="csldeveloper01@gmail.com", password=self.admin_password)
        # Verify student starts PENDING
        self.assertEqual(self.student_user.status, User.AccountStatus.PENDING)

        # Run approve_students action
        post_data = {
            "action": "approve_students",
            "_selected_action": [str(self.student_user.id)],
        }
        res = self.client.post("/admin/users/user/", post_data, follow=True)
        self.assertEqual(res.status_code, 200)
        self.student_user.refresh_from_db()
        self.assertEqual(self.student_user.status, User.AccountStatus.ACTIVE)
        self.assertTrue(self.student_user.is_active)

        # Run reject_students action
        post_data = {
            "action": "reject_students",
            "_selected_action": [str(self.student_user.id)],
        }
        res = self.client.post("/admin/users/user/", post_data, follow=True)
        self.assertEqual(res.status_code, 200)
        self.student_user.refresh_from_db()
        self.assertEqual(self.student_user.status, User.AccountStatus.REJECTED)

    def test_assign_student_course_and_batch_in_admin(self):
        self.client.login(email="csldeveloper01@gmail.com", password=self.admin_password)
        post_data = {
            "user": str(self.student_user.id),
            "registration_number": "CSL0099",
            "first_name": "Jane",
            "last_name": "Doe",
            "course": str(self.course.id),
            "batch": str(self.batch.id),
        }
        res = self.client.post(f"/admin/users/studentprofile/{self.profile.id}/change/", post_data, follow=True)
        self.assertEqual(res.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.course, self.course)
        self.assertEqual(self.profile.batch, self.batch)

    def test_course_skill_assignment_integrity(self):
        self.client.login(email="csldeveloper01@gmail.com", password=self.admin_password)
        # Create course skill requirement
        cs = CourseSkill.objects.create(
            course=self.course,
            skill=self.skill,
            sub_skill=self.sub1,
        )
        self.assertEqual(cs.course, self.course)
        self.assertEqual(cs.skill, self.skill)
        self.assertEqual(cs.sub_skill, self.sub1)

        # Check subskill display ordering
        subskills = list(SubSkill.objects.filter(skill=self.skill))
        self.assertEqual(subskills[0], self.sub1)
        self.assertEqual(subskills[1], self.sub2)

    def test_activity_lifecycle_actions_and_student_visibility(self):
        self.client.login(email="csldeveloper01@gmail.com", password=self.admin_password)

        # Setup student with Course and Batch and ACTIVE status
        self.student_user.status = User.AccountStatus.ACTIVE
        self.student_user.save()
        self.profile.course = self.course
        self.profile.batch = self.batch
        self.profile.save()

        # Create Task activity in DRAFT
        task = Task.objects.create(
            title="Django Admin Test Task",
            description="Testing via admin",
            course=self.course,
            batch=self.batch,
            created_by=self.admin_user,
            max_marks=100,
            deadline=timezone.now() + timedelta(days=5),
            status=Activity.Status.DRAFT,
        )
        TaskSkill.objects.create(task=task, skill=self.skill, sub_skill=self.sub1)

        # Student logs in to API -> DRAFT activity should NOT be visible
        student_client = Client()
        student_client.login(email="student_test@example.com", password="StudentPass123!")
        api_res = student_client.get("/api/student/activities/")
        self.assertEqual(api_res.status_code, 200)
        self.assertEqual(len(api_res.data["activities"]), 0)

        # Admin runs publish_activities action
        post_data = {
            "action": "publish_activities",
            "_selected_action": [str(task.id)],
        }
        res = self.client.post("/admin/activities/activity/", post_data, follow=True)
        self.assertEqual(res.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, Activity.Status.ACTIVE)

        # Student now checks API -> Task is VISIBLE
        api_res = student_client.get("/api/student/activities/")
        self.assertEqual(api_res.status_code, 200)
        self.assertEqual(len(api_res.data["activities"]), 1)
        self.assertEqual(api_res.data["activities"][0]["title"], "Django Admin Test Task")

        # Admin archives activity
        post_data = {
            "action": "archive_activities",
            "_selected_action": [str(task.id)],
        }
        res = self.client.post("/admin/activities/activity/", post_data, follow=True)
        self.assertEqual(res.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, Activity.Status.ARCHIVED)

        # Student checks API -> ARCHIVED activity is NOT visible
        api_res = student_client.get("/api/student/activities/")
        self.assertEqual(api_res.status_code, 200)
        self.assertEqual(len(api_res.data["activities"]), 0)

    def test_assessment_and_questions_management(self):
        assessment = Assessment.objects.create(
            title="Midterm Assessment",
            description="Covers Python basics",
            course=self.course,
            batch=self.batch,
            created_by=self.admin_user,
            max_marks=200,
            status=Activity.Status.DRAFT,
        )
        sec = AssessmentSection.objects.create(
            assessment=assessment,
            title="Section A - Core",
            order=1,
        )
        q = Question.objects.create(
            section=sec,
            prompt="Explain Python GIL",
            skill=self.skill,
            sub_skill=self.sub1,
            max_marks=20,
            order=1,
        )
        self.assertEqual(assessment.sections.count(), 1)
        self.assertEqual(sec.questions.count(), 1)
        self.assertEqual(q.skill, self.skill)
        self.assertEqual(q.sub_skill, self.sub1)

    def test_admin_cannot_assign_batch_from_another_course(self):
        self.client.login(email="csldeveloper01@gmail.com", password=self.admin_password)
        other_course = Course.objects.create(code="BIO101", name="Biology 101")
        other_batch = Batch.objects.create(
            course=other_course,
            name="2026-BIO",
            start_date=timezone.now().date(),
        )

        post_data = {
            "user": str(self.student_user.id),
            "registration_number": "CSL0099",
            "first_name": "Jane",
            "last_name": "Doe",
            "course": str(self.course.id),
            "batch": str(other_batch.id),  # Mismatch!
        }
        res = self.client.post(f"/admin/users/studentprofile/{self.profile.id}/change/", post_data)
        # Form validation should fail and return 200 with error message rendered
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, f"Batch &#x27;{other_batch.name}&#x27; does not belong to Course &#x27;{self.course.name}&#x27;.")

    def test_coding_assessment_creation_and_configuration(self):
        self.client.login(email="csldeveloper01@gmail.com", password=self.admin_password)
        assessment = Assessment.objects.create(
            title="Coding Practical Exam",
            description="Algorithm assessment",
            course=self.course,
            batch=self.batch,
            created_by=self.admin_user,
            max_marks=100,
            status=Activity.Status.ACTIVE,
            deadline=timezone.now() + timedelta(days=7),
        )
        sec = AssessmentSection.objects.create(
            assessment=assessment,
            title="Coding Problems",
            order=1,
        )
        coding_q = Question.objects.create(
            section=sec,
            question_type=Question.QuestionType.CODING,
            prompt="Write a program to invert a binary tree",
            input_description="Root node of the binary tree",
            output_description="Root of inverted binary tree",
            constraints="Nodes <= 10^5",
            sample_input="[4,2,7,1,3,6,9]",
            sample_output="[4,7,2,9,6,3,1]",
            allowed_languages="Python, C++, Java",
            time_limit_seconds=2,
            memory_limit_mb=256,
            skill=self.skill,
            sub_skill=self.sub2,
            max_marks=50,
            order=1,
        )
        self.assertEqual(coding_q.question_type, Question.QuestionType.CODING)
        self.assertEqual(coding_q.allowed_languages, "Python, C++, Java")
        self.assertEqual(coding_q.time_limit_seconds, 2)
        self.assertEqual(coding_q.memory_limit_mb, 256)

    def test_student_cannot_see_activity_of_another_batch(self):
        # Activity assigned to Batch 2
        batch2 = Batch.objects.create(
            course=self.course,
            name="2026-B",
            start_date=timezone.now().date(),
        )
        task = Task.objects.create(
            title="Batch B Exclusive Task",
            description="Only for 2026-B students",
            course=self.course,
            batch=batch2,
            created_by=self.admin_user,
            max_marks=50,
            deadline=timezone.now() + timedelta(days=3),
            status=Activity.Status.ACTIVE,
        )

        # Student is in Batch 1 (2026-A)
        self.student_user.status = User.AccountStatus.ACTIVE
        self.student_user.save()
        self.profile.course = self.course
        self.profile.batch = self.batch
        self.profile.save()

        student_client = Client()
        student_client.login(email="student_test@example.com", password="StudentPass123!")
        res = student_client.get("/api/student/activities/")
        self.assertEqual(res.status_code, 200)
        # Should NOT see Batch B's task
        titles = [a["title"] for a in res.data["activities"]]
        self.assertNotIn("Batch B Exclusive Task", titles)

