from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.courses.models import Course, Batch
from apps.users.models import StudentProfile

User = get_user_model()


class StudentProfileAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student_user = User.objects.create_user(
            username="student1@example.com",
            email="student1@example.com",
            password="testpassword123",
            first_name="Alice",
            last_name="Smith",
            role=User.Role.STUDENT,
            status=User.AccountStatus.ACTIVE,
        )
        self.tutor_user = User.objects.create_user(
            username="tutor1@example.com",
            email="tutor1@example.com",
            password="testpassword123",
            first_name="Bob",
            role=User.Role.TUTOR,
            status=User.AccountStatus.ACTIVE,
        )

    def test_unauthenticated_request_fails(self):
        response = self.client.get("/api/student/profile/")
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_student_profile_without_course_and_batch(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get("/api/student/profile/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["name"], "Alice Smith")
        self.assertEqual(data["email"], "student1@example.com")
        self.assertIn("CSL", data["student_id"])
        self.assertIsNone(data["course"])
        self.assertIsNone(data["batch"])
        # Ensure password or internal credentials are NOT exposed
        self.assertNotIn("password", data)
        self.assertNotIn("role", data)
        self.assertNotIn("status", data)

    def test_student_profile_with_course_and_batch(self):
        course = Course.objects.create(name="Full Stack Dev", code="FSD101")
        batch = Batch.objects.create(course=course, name="Batch 2026-A", start_date="2026-01-01")
        profile = StudentProfile.objects.create(
            user=self.student_user,
            registration_number="CSL2026001",
            first_name="Alice",
            last_name="Smith",
            course=course,
            batch=batch,
        )

        self.client.force_authenticate(user=self.student_user)
        response = self.client.get("/api/student/profile/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["student_id"], "CSL2026001")
        self.assertEqual(data["course"], "Full Stack Dev")
        self.assertEqual(data["batch"], "Batch 2026-A")

    def test_non_student_cannot_access_student_profile(self):
        self.client.force_authenticate(user=self.tutor_user)
        response = self.client.get("/api/student/profile/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class StudentSkillsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = User.objects.create_user(
            username="student_skills@example.com",
            email="student_skills@example.com",
            password="testpassword123",
            first_name="Sam",
            last_name="Student",
            role=User.Role.STUDENT,
            status=User.AccountStatus.ACTIVE,
        )
        self.other_student = User.objects.create_user(
            username="other_student@example.com",
            email="other_student@example.com",
            password="testpassword123",
            first_name="Other",
            last_name="One",
            role=User.Role.STUDENT,
            status=User.AccountStatus.ACTIVE,
        )
        self.tutor = User.objects.create_user(
            username="tutor_skills@example.com",
            email="tutor_skills@example.com",
            password="testpassword123",
            first_name="Prof",
            role=User.Role.TUTOR,
            status=User.AccountStatus.ACTIVE,
        )

        from apps.skills.models import SkillCategory, Skill, SubSkill
        from apps.courses.models import CourseSkill

        self.category = SkillCategory.objects.create(name="Programming")
        self.skill = Skill.objects.create(category=self.category, name="Python")
        self.sub1 = SubSkill.objects.create(skill=self.skill, name="Fundamentals", display_order=1)
        self.sub2 = SubSkill.objects.create(skill=self.skill, name="Control Flow", display_order=2)
        self.sub3 = SubSkill.objects.create(skill=self.skill, name="OOP", display_order=3)

        self.course = Course.objects.create(name="Computer Science", code="CS101")
        self.batch = Batch.objects.create(course=self.course, name="2026-A", start_date="2026-01-01")

        CourseSkill.objects.create(course=self.course, skill=self.skill, sub_skill=self.sub1)
        CourseSkill.objects.create(course=self.course, skill=self.skill, sub_skill=self.sub2)
        CourseSkill.objects.create(course=self.course, skill=self.skill, sub_skill=self.sub3)

    def test_unauthenticated_request_fails(self):
        response = self.client.get("/api/student/skills/")
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_non_student_cannot_access_skills(self):
        self.client.force_authenticate(user=self.tutor)
        response = self.client.get("/api/student/skills/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unassigned_student_receives_empty_state(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get("/api/student/skills/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsNone(data["course"])
        self.assertIsNone(data["batch"])
        self.assertEqual(data["skills"], [])

    def test_assigned_student_receives_required_skills_in_order(self):
        profile, _ = StudentProfile.objects.get_or_create(
            user=self.student,
            defaults={"registration_number": "CSL9001", "first_name": "Sam"},
        )
        profile.course = self.course
        profile.batch = self.batch
        profile.save()

        self.client.force_authenticate(user=self.student)
        response = self.client.get("/api/student/skills/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["course"]["code"], "CS101")
        self.assertEqual(data["course"]["name"], "Computer Science")
        self.assertEqual(data["batch"]["name"], "2026-A")
        self.assertEqual(len(data["skills"]), 1)

        skill_data = data["skills"][0]
        self.assertEqual(skill_data["name"], "Python")
        self.assertEqual(skill_data["status"], "UNASSESSED")

        sub_names = [s["name"] for s in skill_data["subskills"]]
        self.assertEqual(sub_names, ["Fundamentals", "Control Flow", "OOP"])
        for s in skill_data["subskills"]:
            self.assertEqual(s["status"], "UNASSESSED")

    def test_student_cannot_access_another_students_skills(self):
        # Even if request has query parameters or manipulated data, session decides user
        profile, _ = StudentProfile.objects.get_or_create(
            user=self.student,
            defaults={"registration_number": "CSL9001", "first_name": "Sam"},
        )
        profile.course = self.course
        profile.batch = self.batch
        profile.save()

        # other_student is unassigned
        self.client.force_authenticate(user=self.other_student)
        response = self.client.get(f"/api/student/skills/?student_id={self.student.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsNone(data["course"])
        self.assertEqual(data["skills"], [])



class StudentDashboardAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = User.objects.create_user(
            username="dash_student@example.com",
            email="dash_student@example.com",
            password="testpassword123",
            first_name="Dana",
            last_name="Scully",
            role=User.Role.STUDENT,
            status=User.AccountStatus.ACTIVE,
        )
        self.other_student = User.objects.create_user(
            username="other_dash@example.com",
            email="other_dash@example.com",
            password="testpassword123",
            first_name="Fox",
            last_name="Mulder",
            role=User.Role.STUDENT,
            status=User.AccountStatus.ACTIVE,
        )
        self.tutor = User.objects.create_user(
            username="dash_tutor@example.com",
            email="dash_tutor@example.com",
            password="testpassword123",
            first_name="Walter",
            role=User.Role.TUTOR,
            status=User.AccountStatus.ACTIVE,
        )

        from apps.skills.models import SkillCategory, Skill, SubSkill
        from apps.courses.models import CourseSkill

        self.category = SkillCategory.objects.create(name="Forensics")
        self.skill1 = Skill.objects.create(category=self.category, name="Pathology")
        self.sub1 = SubSkill.objects.create(skill=self.skill1, name="Autopsy", display_order=1)
        self.sub2 = SubSkill.objects.create(skill=self.skill1, name="Toxicology", display_order=2)

        self.skill2 = Skill.objects.create(category=self.category, name="Ballistics")
        self.sub3 = SubSkill.objects.create(skill=self.skill2, name="Trajectory", display_order=1)

        self.course = Course.objects.create(name="Investigation", code="INV101")
        self.batch = Batch.objects.create(course=self.course, name="Batch-X", start_date="2026-01-01")

        CourseSkill.objects.create(course=self.course, skill=self.skill1, sub_skill=self.sub1)
        CourseSkill.objects.create(course=self.course, skill=self.skill1, sub_skill=self.sub2)
        CourseSkill.objects.create(course=self.course, skill=self.skill2, sub_skill=self.sub3)

    def test_unauthenticated_dashboard_fails(self):
        response = self.client.get("/api/student/dashboard/")
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_non_student_cannot_access_dashboard(self):
        self.client.force_authenticate(user=self.tutor)
        response = self.client.get("/api/student/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unassigned_student_dashboard_state(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get("/api/student/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["student"]["name"], "Dana Scully")
        self.assertIsNone(data["student"]["course"])
        self.assertIsNone(data["student"]["batch"])
        self.assertFalse(data["skills"]["available"])
        self.assertEqual(data["skills"]["total_skills"], 0)
        self.assertEqual(data["performance"]["status"], "NOT_ASSESSED")
        self.assertEqual(data["performance"]["message"], "Not assessed yet")
        self.assertFalse(data["activities"]["available"])
        self.assertEqual(data["activities"]["message"], "No activities yet")

    def test_assigned_student_dashboard_counts(self):
        profile, _ = StudentProfile.objects.get_or_create(
            user=self.student,
            defaults={
                "registration_number": "CSL7777",
                "first_name": "Dana",
                "last_name": "Scully",
            },
        )
        profile.course = self.course
        profile.batch = self.batch
        profile.save()

        self.client.force_authenticate(user=self.student)
        response = self.client.get("/api/student/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["student"]["name"], "Dana Scully")
        self.assertEqual(data["student"]["course"], "Investigation")
        self.assertEqual(data["student"]["course_code"], "INV101")
        self.assertEqual(data["student"]["batch"], "Batch-X")

        self.assertTrue(data["skills"]["available"])
        self.assertEqual(data["skills"]["total_skills"], 2)
        self.assertEqual(data["skills"]["total_subskills"], 3)
        self.assertEqual(data["skills"]["assessed"], 0)
        self.assertEqual(data["skills"]["unassessed"], 2)

    def test_student_cannot_access_another_students_dashboard(self):
        profile, _ = StudentProfile.objects.get_or_create(
            user=self.student,
            defaults={"registration_number": "CSL7777", "first_name": "Dana"},
        )
        profile.course = self.course
        profile.batch = self.batch
        profile.save()

        self.client.force_authenticate(user=self.other_student)
        response = self.client.get(f"/api/student/dashboard/?student_id={self.student.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["student"]["name"], "Fox Mulder")
        self.assertIsNone(data["student"]["course"])
