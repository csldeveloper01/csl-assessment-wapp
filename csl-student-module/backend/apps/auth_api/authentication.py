from rest_framework.authentication import SessionAuthentication


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
    """

    def enforce_csrf(self, request):
        return  # Bypassed in favor of strict CORS origin checking
