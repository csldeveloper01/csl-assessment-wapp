from django.test import TestCase, Client, override_settings
from django.urls import reverse
from apps.users.models import User
from apps.assessments.models import Assessment


class AdminRouteAndApiSecurityTestCase(TestCase):
    """
    Security regression test suite:
    1. An anonymous user cannot access protected administrative pages or actions.
    2. An authenticated non-staff user cannot access staff-only administration.
    3. Authorized staff/superusers can access required admin functionality when it is enabled.
    4. Sensitive API endpoints enforce the intended permissions independently of the admin page.
    5. Production configuration does not accidentally expose debug-only functionality, and
       DJANGO_ADMIN_ENABLED properly disables the route when set to False.
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

        # Inactive staff user (suspended or deactivated)
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

    def test_security_1_anonymous_user_blocked_from_admin(self):
        """Anonymous user cannot access Django admin index or protected operational views."""
        response = self.client.get("/admin/")
        # Should redirect to login page (302) or return 401/403/404, never 200 with dashboard data
        self.assertIn(response.status_code, [302, 401, 403])
        if response.status_code == 302:
            self.assertIn("/admin/login/", response["Location"])

    def test_security_2_authenticated_student_blocked_from_admin(self):
        """Authenticated student cannot access Django admin or perform administrative actions."""
        self.client.force_login(self.student)
        response = self.client.get("/admin/")
        # Must be redirected to admin login or forbidden, never allowed to view administration
        self.assertIn(response.status_code, [302, 403])
        if response.status_code == 302:
            self.assertIn("/admin/login/", response["Location"])

    def test_security_3_authorized_staff_can_access_admin(self):
        """Authorized active staff/superuser can access admin dashboard."""
        self.client.force_login(self.admin)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)

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

    def test_security_5_admin_route_can_be_disabled_via_setting(self):
        """
        When DJANGO_ADMIN_ENABLED is False, /admin/ route is not registered or accessible.
        """
        from importlib import reload
        from django.urls import clear_url_caches, set_urlconf
        from config import urls as config_urls

        with override_settings(DJANGO_ADMIN_ENABLED=False):
            # Reload URLconf with DJANGO_ADMIN_ENABLED=False
            reload(config_urls)
            clear_url_caches()
            set_urlconf(None)
            client = Client()
            res = client.get("/admin/")
            self.assertEqual(res.status_code, 404)

        # Restore URLconf with DJANGO_ADMIN_ENABLED=True
        reload(config_urls)
        clear_url_caches()
        set_urlconf(None)
