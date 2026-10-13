from django.urls import path
from .views import (
    StudentActivitiesListView,
    StudentActivityDetailView,
    StaffActivityListCreateView,
    StaffActivityDetailView,
    CourseBatchOptionsView,
)

urlpatterns = [
    # Student endpoints
    path("", StudentActivitiesListView.as_view(), name="student-activities-list"),
    path("<int:pk>/", StudentActivityDetailView.as_view(), name="student-activity-detail"),
    # Staff management endpoints
    path("manage/", StaffActivityListCreateView.as_view(), name="staff-activities-list-create"),
    path("manage/<int:pk>/", StaffActivityDetailView.as_view(), name="staff-activity-detail"),
    path("options/", CourseBatchOptionsView.as_view(), name="staff-activity-options"),
]

