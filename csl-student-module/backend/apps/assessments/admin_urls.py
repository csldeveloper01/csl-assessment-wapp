from django.urls import path
from .admin_views import (
    AdminMeView,
    AdminStatsView,
    AdminCollegeListView,
    AdminCollegeDetailView,
    AdminCollegeToggleStatusView,
    AdminCollegeImportCandidatesView,
    AdminAssessmentListView,
    AdminAssessmentDetailView,
    AdminAssessmentPrepareView,
    AdminAssessmentOpenView,
    AdminAssessmentCloseView,
    AdminAssessmentArchiveView,
    AdminAssessmentAssignCollegesView,
    AdminAssessmentAssignQuestionsView,
    AdminAssessmentReleaseResultsView,
    AdminAssessmentAuditLogsView,
    AdminCandidateListView,
    AdminCandidateExportCSVView,
    AdminCandidateDetailView,
    AdminCandidateToggleStatusView,
    AdminQuestionListView,
    AdminQuestionDetailView,
    AdminQuestionToggleView,
    AdminQuestionImportCSVView,
    AdminQuestionBulkUpdateView,
    AdminConfigView,
    AdminLiveAttemptsView,
    AdminAttemptReviewView,
    AdminResultsView,
    AdminIntegrityEventsView,
    AdminIntegrityEventReviewActionView,
    AdminGlobalAuditLogsView,
)

urlpatterns = [
    path("me/", AdminMeView.as_view(), name="admin-me"),
    path("stats/", AdminStatsView.as_view(), name="admin-stats"),
    
    # Colleges
    path("colleges/", AdminCollegeListView.as_view(), name="admin-colleges"),
    path("colleges/<int:pk>/", AdminCollegeDetailView.as_view(), name="admin-college-detail"),
    path("colleges/<int:pk>/toggle-status/", AdminCollegeToggleStatusView.as_view(), name="admin-college-toggle-status"),
    path("colleges/<int:pk>/import-candidates/", AdminCollegeImportCandidatesView.as_view(), name="admin-college-import-candidates"),

    # Assessments
    path("assessments/", AdminAssessmentListView.as_view(), name="admin-assessments"),
    path("assessments/<uuid:pk>/", AdminAssessmentDetailView.as_view(), name="admin-assessment-detail"),
    path("assessments/<uuid:pk>/prepare/", AdminAssessmentPrepareView.as_view(), name="admin-assessment-prepare"),
    path("assessments/<uuid:pk>/open/", AdminAssessmentOpenView.as_view(), name="admin-assessment-open"),
    path("assessments/<uuid:pk>/close/", AdminAssessmentCloseView.as_view(), name="admin-assessment-close"),
    path("assessments/<uuid:pk>/archive/", AdminAssessmentArchiveView.as_view(), name="admin-assessment-archive"),
    path("assessments/<uuid:pk>/assign-colleges/", AdminAssessmentAssignCollegesView.as_view(), name="admin-assessment-assign-colleges"),
    path("assessments/<uuid:pk>/assign-questions/", AdminAssessmentAssignQuestionsView.as_view(), name="admin-assessment-assign-questions"),
    path("assessments/<uuid:pk>/release-results/", AdminAssessmentReleaseResultsView.as_view(), name="admin-assessment-release-results"),
    path("assessments/<uuid:pk>/audit-logs/", AdminAssessmentAuditLogsView.as_view(), name="admin-assessment-audit-logs"),

    # Candidates
    path("candidates/", AdminCandidateListView.as_view(), name="admin-candidates"),
    path("candidates/export-csv/", AdminCandidateExportCSVView.as_view(), name="admin-candidates-export-csv"),
    path("candidates/<uuid:candidate_id>/", AdminCandidateDetailView.as_view(), name="admin-candidate-detail"),
    path("candidates/<uuid:candidate_id>/toggle-status/", AdminCandidateToggleStatusView.as_view(), name="admin-candidate-toggle-status"),

    # Questions
    path("questions/", AdminQuestionListView.as_view(), name="admin-questions"),
    path("questions/<int:pk>/", AdminQuestionDetailView.as_view(), name="admin-question-detail"),
    path("questions/<int:pk>/toggle/", AdminQuestionToggleView.as_view(), name="admin-question-toggle"),
    path("questions/bulk-update/", AdminQuestionBulkUpdateView.as_view(), name="admin-questions-bulk-update"),
    path("questions/import-csv/", AdminQuestionImportCSVView.as_view(), name="admin-question-import-csv"),

    # Config (legacy fallback)
    path("config/", AdminConfigView.as_view(), name="admin-config"),

    # Attempts & Results
    path("attempts/live/", AdminLiveAttemptsView.as_view(), name="admin-live-attempts"),
    path("attempts/<uuid:attempt_id>/review/", AdminAttemptReviewView.as_view(), name="admin-attempt-review"),
    path("results/", AdminResultsView.as_view(), name="admin-results"),
    path("integrity-events/", AdminIntegrityEventsView.as_view(), name="admin-integrity-events"),
    path("integrity-events/<int:pk>/review/", AdminIntegrityEventReviewActionView.as_view(), name="admin-integrity-event-review"),

    # Audit Logs
    path("audit-logs/", AdminGlobalAuditLogsView.as_view(), name="admin-audit-logs"),
]
