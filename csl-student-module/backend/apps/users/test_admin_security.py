from django.test import TestCase, Client, override_settings
from apps.users.models import User
from apps.assessments.models import Assessment


class AdminRouteAndApiSecurityTestCase(TestCase):
    """
    Security regression test suite verifying the retirement of legacy Django Admin
    and the protection of React Admin APIs:
    1. The legacy Django Admin interface is removed from active URL routing and returns HTTP 404.
    2. Any attempt (anonymous, student, or staff) to access /admin/ or subpaths returns 404.
    3. Configurable admin paths cannot expose the retired interface.
    4. The React Admin Portal APIs (/api/csl-admin/*) are fully operational and strictly enforce authorization.
    5. Candidate assessment workflows (/api/assessment/*) continue to function without degradation.
    """

    def setUp(self):
        self.client = Client()

        # Regular student user
        self.student = User.objects.create_user(
            username="student_user",
            email="student@example.com",
            password="StudentPassword123!",
            role=User.Role.STUDENT,
            status=User.AccountStatus.ACTIVE,
            is_staff=False,
            is_superuser=False,
        )

        # Authorized staff/admin user
        self.admin = User.objects.create_user(
            username="staff_admin_user",
            email="staff_admin@example.com",
            password="AdminPassword123!",
            role=User.Role.ADMIN,
            status=User.AccountStatus.ACTIVE,
            is_staff=True,
            is_superuser=True,
        )

        # Inactive staff user (suspended or pending)
        self.inactive_staff = User.objects.create_user(
            username="inactive_staff",
            email="inactive_staff@example.com",
            password="InactivePassword123!",
            role=User.Role.ADMIN,
            status=User.AccountStatus.PENDING,
            is_staff=True,
            is_superuser=False,
            is_active=False,
        )

    def test_security_1_anonymous_user_receives_404_on_admin(self):
        """Anonymous user requesting /admin/ receives 404 Not Found."""
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 404, "Retired /admin/ route must return 404.")

    def test_security_2_authenticated_student_receives_404_on_admin(self):
        """Authenticated student requesting /admin/ receives 404 Not Found."""
        self.client.force_login(self.student)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 404, "Retired /admin/ route must return 404.")

    def test_security_3_authorized_staff_receives_404_on_retired_admin(self):
        """Even authorized staff receive 404 on retired legacy Django admin route."""
        self.client.force_login(self.admin)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 404, "Legacy Django admin is unrouted and must return 404.")

    def test_security_4_api_enforces_permissions_independently(self):
        """
        Sensitive administrative REST API endpoints enforce permissions independently of the admin page.
        Anonymous users and student accounts receive 401/403.
        """
        # Anonymous on CSL admin stats API
        res_anon = self.client.get("/api/csl-admin/stats/")
        self.assertIn(res_anon.status_code, [401, 403])

        # Student user on CSL admin stats API
        self.client.force_login(self.student)
        res_student = self.client.get("/api/csl-admin/stats/")
        self.assertEqual(res_student.status_code, 403)

        # Inactive staff on CSL admin stats API
        self.client.force_login(self.inactive_staff)
        res_inactive = self.client.get("/api/csl-admin/stats/")
        self.assertEqual(res_inactive.status_code, 403)

        # Authorized admin has access
        self.client.force_login(self.admin)
        res_admin = self.client.get("/api/csl-admin/stats/")
        self.assertEqual(res_admin.status_code, 200)

    def test_security_5_admin_route_permanently_unrouted(self):
        """
        Verifies that /admin/ and /admin/login/ are completely unrouted.
        """
        res_root = self.client.get("/admin/")
        self.assertEqual(res_root.status_code, 404)

        res_login = self.client.get("/admin/login/")
        self.assertEqual(res_login.status_code, 404)

    def test_security_6_all_admin_model_changelists_return_404(self):
        """
        All model changelists and custom admin export views return 404 for anonymous requests.
        """
        for route in [
            "/admin/users/user/",
            "/admin/assessments/assessment/",
            "/admin/assessments/candidate/",
            "/admin/assessments/questionbank/export-csv/",
            "/admin/assessments/questionbank/import-csv/",
        ]:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 404, f"Route {route} must return 404.")

    def test_security_7_authenticated_student_blocked_from_all_admin_endpoints(self):
        """
        Authenticated student accounts receive 404 on all legacy admin routes.
        """
        self.client.force_login(self.student)
        for route in [
            "/admin/users/user/",
            "/admin/assessments/assessment/",
            "/admin/assessments/candidate/",
            "/admin/assessments/questionbank/export-csv/",
            "/admin/assessments/questionbank/import-csv/",
        ]:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 404, f"Route {route} must return 404.")

    def test_security_8_authenticated_student_cannot_execute_admin_actions(self):
        """
        Authenticated student accounts cannot POST to legacy admin actions.
        """
        pending_user = User.objects.create_user(
            username="pending_test_target",
            email="pending_target@example.com",
            password="TargetPassword123!",
            role=User.Role.STUDENT,
            status=User.AccountStatus.PENDING,
        )
        self.client.force_login(self.student)
        post_data = {
            "action": "approve_students",
            "_selected_action": [str(pending_user.id)],
        }
        res = self.client.post("/admin/users/user/", post_data)
        self.assertEqual(res.status_code, 404)
        pending_user.refresh_from_db()
        self.assertEqual(pending_user.status, User.AccountStatus.PENDING, "Student was able to execute admin action!")

    def test_security_9_configurable_admin_paths_cannot_expose_admin(self):
        """
        Verifies that any previously configurable admin path cannot expose the legacy admin interface.
        """
        from importlib import reload
        from django.urls import clear_url_caches, set_urlconf
        from config import urls as config_urls

        with override_settings(DJANGO_ADMIN_URL_PATH="custom-ops/", DJANGO_ADMIN_ENABLED=True):
            reload(config_urls)
            clear_url_caches()
            set_urlconf(None)
            client = Client()

            res_default = client.get("/admin/")
            self.assertEqual(res_default.status_code, 404)

            res_custom = client.get("/custom-ops/")
            self.assertEqual(res_custom.status_code, 404)

        # Restore
        reload(config_urls)
        clear_url_caches()
        set_urlconf(None)

    def test_security_10_candidate_assessment_workflow_unaffected(self):
        """
        Verifies student-facing assessment APIs continue to work without regression.
        """
        from apps.assessments.models import College
        college = College.objects.create(name="CSL Test Institute", code="CSLTI", is_active=True)

        res_colleges = self.client.get("/api/assessment/colleges/")
        self.assertEqual(res_colleges.status_code, 200)

        reg_data = {
            "full_name": "Security Test Candidate",
            "email": "sectest@example.com",
            "register_number": "SEC-REG-01",
            "college_id": college.id,
            "department": "Computer Science",
            "year_of_study": "Final Year",
            "phone_number": "9876543210",
        }
        res_reg = self.client.post("/api/assessment/register/", reg_data, content_type="application/json")
        self.assertIn(res_reg.status_code, [200, 201])
        self.assertIn("assessment_token", res_reg.data)

    def test_security_11_comprehensive_api_admin_views_protected(self):
        """
        Verifies all major /api/csl-admin/ endpoints reject unauthenticated and student users,
        and allow authorized staff.
        """
        endpoints = [
            "/api/csl-admin/me/",
            "/api/csl-admin/colleges/",
            "/api/csl-admin/assessments/",
            "/api/csl-admin/candidates/",
            "/api/csl-admin/questions/",
            "/api/csl-admin/sections/",
            "/api/csl-admin/attempts/live/",
            "/api/csl-admin/results/",
            "/api/csl-admin/integrity-events/",
            "/api/csl-admin/audit-logs/",
        ]
        for ep in endpoints:
            # Anonymous
            self.client.logout()
            res_anon = self.client.get(ep)
            self.assertIn(res_anon.status_code, [401, 403], f"Anonymous allowed on {ep}")

            # Student
            self.client.force_login(self.student)
            res_student = self.client.get(ep)
            self.assertEqual(res_student.status_code, 403, f"Student allowed on {ep}")

            # Admin
            self.client.force_login(self.admin)
            res_admin = self.client.get(ep)
            self.assertEqual(res_admin.status_code, 200, f"Admin rejected on {ep}")
