from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Reject a pending student by email."

    def add_arguments(self, parser):
        parser.add_argument("email", type=str, help="Student email address")

    def handle(self, *args, **options):
        email = options["email"].strip().lower()

        try:
            user = User.objects.get(email=email, role=User.Role.STUDENT)
        except User.DoesNotExist:
            raise CommandError(f"No student found with email: {email}")

        if user.status == User.AccountStatus.REJECTED:
            self.stdout.write(f"Student {email} is already REJECTED.")
            return

        user.status = User.AccountStatus.REJECTED
        user.save(update_fields=["status", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"Student request rejected: {email}"))
