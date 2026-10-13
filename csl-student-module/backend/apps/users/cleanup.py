import sys
import atexit
import signal
import os

_cleanup_done = False


def cleanup_pending_students():
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True

    try:
        from apps.users.models import User

        pending_users = User.objects.filter(
            role=User.Role.STUDENT,
            status=User.AccountStatus.PENDING,
        )
        count = pending_users.count()
        if count > 0:
            print("\nCSL: Cleaning up pending registration requests...")
            pending_users.delete()
            print(f"CSL: Removed {count} pending registration request(s).")
            print("CSL: Shutting down.")
        else:
            print("\nCSL: No pending registration requests to clean up.")
            print("CSL: Shutting down.")
    except Exception as e:
        # Avoid crashing during process teardown
        print(f"\nCSL: Note during pending user cleanup: {e}")


def register_shutdown_cleanup():
    """
    Register cleanup handlers for normal termination and shutdown signals.
    Respects Django autoreload by checking RUN_MAIN when in runserver mode.
    """
    # Only run shutdown cleanup if running server commands (runserver, gunicorn, etc.)
    # We do not want cleanup on administrative management commands like migrate, makemigrations, admin_cli, check.
    server_commands = {"runserver", "runserver_plus", "gunicorn", "uvicorn", "daphne"}
    command = sys.argv[1] if len(sys.argv) > 1 else ""

    if command not in server_commands and not any(cmd in sys.argv[0].lower() for cmd in server_commands):
        return

    # If running via runserver, only register in the worker process (RUN_MAIN == 'true')
    # to avoid double execution on reload.
    is_runserver = "runserver" in sys.argv
    is_main_reload_child = os.environ.get("RUN_MAIN") == "true"
    if is_runserver and not is_main_reload_child:
        return

    # atexit handles normal python interpreter termination
    atexit.register(cleanup_pending_students)

    # Signal handlers for SIGINT (Ctrl+C) and SIGTERM
    def signal_handler(signum, frame):
        cleanup_pending_students()
        # Re-raise standard exit behavior
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, signal_handler)
    except (ValueError, AttributeError):
        pass

    try:
        signal.signal(signal.SIGTERM, signal_handler)
    except (ValueError, AttributeError):
        pass

    if hasattr(signal, "SIGBREAK"):
        try:
            signal.signal(signal.SIGBREAK, signal_handler)
        except (ValueError, AttributeError):
            pass
