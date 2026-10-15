from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.users.models import StudentProfile

User = get_user_model()


class StudentRegistrationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = "/api/auth/register/"
        self.valid_payload = {
            "name": "Jane Doe",
            "registration_number": "REG-2026-001",
            "email": "janedoe@college.edu",
            "password": "SecurePassword123!",
        }

    def test_valid_registration(self):
        """Valid registration creates PENDING student and persists StudentProfile with registration_number."""
        response = self.client.post(self.register_url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("message", response.json())

        # Verify User model
        user = User.objects.get(email="janedoe@college.edu")
        self.assertEqual(user.first_name, "Jane Doe")
        self.assertEqual(user.username, "janedoe@college.edu")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertEqual(user.status, User.AccountStatus.PENDING)
        self.assertTrue(user.check_password("SecurePassword123!"))

        # Verify StudentProfile model
        profile = StudentProfile.objects.get(user=user)
        self.assertEqual(profile.registration_number, "REG-2026-001")
        self.assertEqual(profile.first_name, "Jane Doe")

    def test_missing_required_fields(self):
        """Each required field must return a field-specific error when omitted or empty."""
        response = self.client.post(self.register_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("name", data)
        self.assertIn("registration_number", data)
        self.assertIn("email", data)
        self.assertIn("password", data)

    def test_full_name_exceeding_50_chars(self):
        """Full name exceeding 50 characters fails with field-specific error."""
        payload = dict(self.valid_payload, name="A" * 51)
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("name", data)
        self.assertIn("50", str(data["name"][0]))

    def test_full_name_valid_special_characters(self):
        """Full names with legitimate spaces, hyphens, and apostrophes are accepted."""
        payload = dict(self.valid_payload, name="Mary-Jane O'Connor")
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="janedoe@college.edu")
        self.assertEqual(user.first_name, "Mary-Jane O'Connor")

    def test_full_name_invalid_characters(self):
        """Full names with numbers or illegal characters are rejected."""
        payload = dict(self.valid_payload, name="Jane123 Doe!")
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.json())

    def test_register_number_exceeding_25_chars(self):
        """Register number exceeding 25 characters fails with field-specific error."""
        payload = dict(self.valid_payload, registration_number="R" * 26)
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("registration_number", data)
        self.assertIn("25", str(data["registration_number"][0]))

    def test_register_number_blank_or_whitespace(self):
        """Register number that is blank or whitespace-only is rejected."""
        payload = dict(self.valid_payload, registration_number="   ")
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("registration_number", response.json())

    def test_register_number_valid_separators(self):
        """Register number with hyphens, slashes, numbers, letters, spaces is accepted."""
        payload = dict(self.valid_payload, registration_number="CS/2026-A 01")
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        profile = StudentProfile.objects.get(registration_number="CS/2026-A 01")
        self.assertEqual(profile.user.email, "janedoe@college.edu")

    def test_duplicate_register_number(self):
        """Duplicate register number (case-insensitive) fails with field-specific error."""
        self.client.post(self.register_url, self.valid_payload, format="json")

        payload2 = dict(
            self.valid_payload,
            email="otherstudent@college.edu",
            registration_number="reg-2026-001",
        )
        response = self.client.post(self.register_url, payload2, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("registration_number", data)
        self.assertIn("already exists", str(data["registration_number"][0]).lower())

    def test_invalid_college_email_formats(self):
        """Malformed emails, emails missing domain or TLD, or emails with spaces are rejected."""
        invalid_emails = [
            "plainaddress",
            "missingdomain@.com",
            "@missingusername.edu",
            "missingatcollege.edu",
            "two@@atmarks.edu",
            "space in@college.edu",
            "student@college",
        ]
        for bad_email in invalid_emails:
            payload = dict(self.valid_payload, email=bad_email)
            response = self.client.post(self.register_url, payload, format="json")
            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Expected 400 for bad email: {bad_email}, got {response.status_code}",
            )
            self.assertIn("email", response.json())

    def test_duplicate_account_email(self):
        """Duplicate account email (case-insensitive) fails with field-specific error."""
        self.client.post(self.register_url, self.valid_payload, format="json")

        payload2 = dict(
            self.valid_payload,
            email="JaneDoe@College.EDU",
            registration_number="REG-2026-002",
        )
        response = self.client.post(self.register_url, payload2, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("email", data)
        self.assertIn("already exists", str(data["email"][0]).lower())

    def test_password_min_length(self):
        """Password shorter than 8 characters fails validation."""
        payload = dict(self.valid_payload, password="short")
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.json())
