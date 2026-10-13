from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    label = "users"
    verbose_name = "Users"

    def ready(self):
        from .cleanup import register_shutdown_cleanup
        register_shutdown_cleanup()
