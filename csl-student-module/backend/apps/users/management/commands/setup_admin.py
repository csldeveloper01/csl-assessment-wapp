from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import getpass

User = get_user_model()


class Command(BaseCommand):
    help = "Safely setup or promote the primary CSL admin account (csldeveloper01@gmail.com)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default="csldeveloper01@gmail.com",
            help="Admin email address (default: csldeveloper01@gmail.com)",
        )
        parser.add_argument(
            "--password",
            default="",
            help="Optional password for non-interactive admin creation or reset",
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password_arg = options.get("password", "").strip()
        user = User.objects.filter(email=email).first()

        if user:
            user.role = User.Role.ADMIN
            user.status = User.AccountStatus.ACTIVE
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            update_fields = ["role", "status", "is_staff", "is_superuser", "is_active"]
            if password_arg:
                user.set_password(password_arg)
                update_fields.append("password")
            user.save(update_fields=update_fields)
            self.stdout.write(self.style.SUCCESS(f"User {email} successfully promoted to Admin & Superuser."))
        else:
            self.stdout.write(f"Account {email} does not exist yet.")
            password = password_arg
            if not password:
                password = getpass.getpass("Enter password for new admin: ")
                confirm = getpass.getpass("Confirm password: ")
                if not password:
                    self.stdout.write(self.style.ERROR("Password cannot be empty."))
                    return
                if password != confirm:
                    self.stdout.write(self.style.ERROR("Passwords do not match."))
                    return

            username = email.split("@")[0]
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=User.Role.ADMIN,
                status=User.AccountStatus.ACTIVE,
                is_staff=True,
                is_superuser=True,
                is_active=True,
            )
            self.stdout.write(self.style.SUCCESS(f"Superuser account {email} created successfully."))
