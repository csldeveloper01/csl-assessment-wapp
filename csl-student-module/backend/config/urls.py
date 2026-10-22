"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import logging
from django.urls import path, include
from django.http import JsonResponse
from django.db import connection

logger = logging.getLogger(__name__)

def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_status = "healthy"
        status_code = 200
    except Exception as e:
        logger.error(f"Health check database failure: {e}", exc_info=True)
        db_status = "unhealthy"
        status_code = 503

    return JsonResponse({"status": "ok" if db_status == "healthy" else "error", "database": db_status}, status=status_code)

urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('api/auth/', include('apps.auth_api.urls')),
    path('api/student/', include('apps.users.urls')),
    path('api/student/activities/', include('apps.activities.urls')),
    path('api/assessment/', include('apps.assessments.urls')),
    path('api/csl-admin/', include('apps.assessments.admin_urls')),
]


