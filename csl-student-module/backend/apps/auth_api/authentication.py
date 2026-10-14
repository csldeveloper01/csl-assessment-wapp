import logging
from rest_framework.authentication import SessionAuthentication
from django.contrib.auth import get_user_model, load_backend
from django.contrib.auth import HASH_SESSION_KEY, SESSION_KEY, BACKEND_SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore

logger = logging.getLogger(__name__)
User = get_user_model()


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication subclass that exempts CSRF validation.

    In decoupled cross-origin frontend-backend architectures (e.g. Vercel SPA
    talking to Render backend), browsers isolate cookies such that `document.cookie`
    cannot access the backend's CSRF cookie to populate `X-CSRFToken`.

    Protection against cross-origin attacks is enforced via `django-cors-headers`
    strictly restricting origins (`CORS_ALLOWED_ORIGINS`), `SameSite`/`Secure` cookies,
    and requiring JSON `Content-Type` on mutating API calls (which enforces browser
    CORS preflight).

    Additionally supports modern browser third-party cookie restrictions (e.g.
    Safari ITP, Chrome Privacy Sandbox, Incognito/InPrivate) by resolving the
    active Django session from the X-Session-ID header if the cookie was dropped
    by the client browser.
    """

    def enforce_csrf(self, request):
        return  # Bypassed in favor of strict CORS origin checking

    def authenticate(self, request):
        # 1. Standard Django session authentication via cookie
        user_auth = super().authenticate(request)
        if user_auth is not None:
            return user_auth

        # 2. Cross-origin session fallback via X-Session-ID header
        session_key = (
            request.headers.get("X-Session-ID")
            or request.headers.get("x-session-id")
            or request.META.get("HTTP_X_SESSION_ID")
        )
        if not session_key:
            return None

        try:
            session = SessionStore(session_key=session_key)
            if not session.exists(session_key):
                return None

            user_id = session.get(SESSION_KEY)
            backend_path = session.get(BACKEND_SESSION_KEY)
            if not user_id or not backend_path:
                return None

            backend = load_backend(backend_path)
            user = backend.get_user(user_id)
            if not user or not user.is_active:
                return None

            # Verify session auth hash if set
            session_hash = session.get(HASH_SESSION_KEY)
            if session_hash:
                user_hash = user.get_session_auth_hash()
                if session_hash != user_hash:
                    return None

            # Attach session and user to underlying Django HttpRequest
            request._request.session = session
            request._request.user = user
            return (user, None)
        except Exception as e:
            logger.warning(f"Failed to authenticate session from header: {e}")
            return None

