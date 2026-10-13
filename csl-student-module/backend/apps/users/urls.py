from django.urls import path
from .views import StudentProfileView, StudentSkillsView, StudentDashboardView

urlpatterns = [
    path("profile/", StudentProfileView.as_view(), name="student-profile"),
    path("skills/", StudentSkillsView.as_view(), name="student-skills"),
    path("dashboard/", StudentDashboardView.as_view(), name="student-dashboard"),
]


