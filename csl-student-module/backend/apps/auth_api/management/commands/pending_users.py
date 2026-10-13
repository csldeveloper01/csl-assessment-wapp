from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "List all pending student registration requests."

    def handle(self, *args, **options):
        pending = User.objects.filter(
            role=User.Role.STUDENT,
            status=User.AccountStatus.PENDING,
        )

        if not pending.exists():
            self.stdout.write("No pending student requests.")
            return

        self.stdout.write("\nPending Student Requests:\n")
        for i, user in enumerate(pending, start=1):
            self.stdout.write(f"{i}. {user.email}")
            self.stdout.write(f"   Name: {user.first_name or '(not set)'}")
            self.stdout.write(f"   Status: {user.status}")
            self.stdout.write("")
