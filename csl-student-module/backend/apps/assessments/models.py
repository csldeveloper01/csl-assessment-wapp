import uuid
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


class QuestionBank(models.Model):
    class SectionType(models.TextChoices):
        APTITUDE = "APTITUDE", "Aptitude"
        CODING = "CODING", "Coding Fundamentals"

    class Difficulty(models.TextChoices):
        EASY = "EASY", "Easy"
        MEDIUM = "MEDIUM", "Medium"
        HARD = "HARD", "Hard"

    prompt = models.TextField(help_text="MCQ question text or problem statement")
    section_type = models.CharField(max_length=20, choices=SectionType.choices, db_index=True)
    category = models.CharField(max_length=100, db_index=True, help_text="e.g. Quantitative, Logical, Python, OOP")
    difficulty = models.CharField(max_length=20, choices=Difficulty.choices, default=Difficulty.MEDIUM, db_index=True)
    assessment_type = models.CharField(
        max_length=50,
        blank=True,
        default="INITIAL_DIAGNOSTIC",
        db_index=True,
        help_text="e.g. INITIAL_DIAGNOSTIC, TECHNICAL_MOCK, PLACEMENT_DRIVE",
    )
    
    # MCQ Options
    option_a = models.TextField()
    option_b = models.TextField()
    option_c = models.TextField()
    option_d = models.TextField()
    
    # Correct Answer (Never exposed to student APIs)
    correct_option = models.CharField(
        max_length=1,
        choices=[("A", "Option A"), ("B", "Option B"), ("C", "Option C"), ("D", "Option D")],
        help_text="The single correct option key (A, B, C, or D)",
    )
    explanation = models.TextField(blank=True, default="", help_text="Optional explanation for admin review")
    
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["section_type", "category", "id"]
        indexes = [
            models.Index(fields=["section_type", "is_active"]),
            models.Index(fields=["section_type", "difficulty", "is_active"]),
        ]

    def __str__(self):
        return f"[{self.section_type}] {self.category} ({self.difficulty}): {self.prompt[:60]}"


class AssessmentConfig(models.Model):
    title = models.CharField(max_length=200, default="CSL Initial Assessment")
    description = models.TextField(blank=True, default="CSL 50-mark balanced diagnostic assessment.")
    duration_minutes = models.PositiveIntegerField(default=60, help_text="Duration in minutes (e.g. 60)")
    total_marks = models.PositiveIntegerField(default=50)
    aptitude_count = models.PositiveIntegerField(default=25, help_text="Required aptitude questions")
    coding_count = models.PositiveIntegerField(default=25, help_text="Required coding questions")
    max_attempts = models.PositiveIntegerField(default=1, help_text="Default 1 attempt per student")
    
    # Integrity monitoring thresholds
    max_tab_switches_warning = models.PositiveIntegerField(
        default=2,
        help_text="Permitted tab-switch warnings (default 2; 3rd switch triggers auto-submission)",
    )
    auto_submit_on_tab_limit = models.BooleanField(
        default=True,
        help_text="Automatically submit and flag attempt when tab switch limit is exceeded",
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Assessment Configuration"
        verbose_name_plural = "Assessment Configurations"

    def clean(self):
        errors = {}
        if self.duration_minutes < 1:
            errors["duration_minutes"] = "Duration must be at least 1 minute."
        if self.aptitude_count < 1:
            errors["aptitude_count"] = "Aptitude question count must be at least 1."
        if self.coding_count < 1:
            errors["coding_count"] = "Coding question count must be at least 1."
        if self.total_marks != (self.aptitude_count + self.coding_count):
            errors["total_marks"] = (
                f"Total marks ({self.total_marks}) must equal aptitude ({self.aptitude_count}) + coding ({self.coding_count})."
            )
        if self.max_attempts < 1:
            errors["max_attempts"] = "Max attempts must be at least 1."
        if self.max_tab_switches_warning < 1:
            errors["max_tab_switches_warning"] = "Tab switch limit must be at least 1."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.duration_minutes} mins, {self.total_marks} marks)"


class College(models.Model):
    """
    Managed institutional record. Candidates and assessments belong to or are assigned to colleges.
    """
    name = models.CharField(max_length=200, help_text="Official college / institution name")
    code = models.CharField(max_length=50, unique=True, db_index=True, help_text="Unique institutional code (e.g. CIT, RATHINAM)")
    address = models.TextField(blank=True, default="", help_text="Campus address")
    location = models.CharField(max_length=150, blank=True, default="", help_text="City, State, or Region")
    contact_email = models.EmailField(blank=True, default="", help_text="Official institutional contact email")
    contact_phone = models.CharField(max_length=30, blank=True, default="", help_text="Contact phone number")
    admin_contact_name = models.CharField(max_length=150, blank=True, default="", help_text="TPO or faculty representative name")
    is_active = models.BooleanField(default=True, db_index=True, help_text="Active or deactivated status")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active", "name"]),
        ]

    def clean(self):
        if self.name:
            self.name = self.name.strip()
        if self.code:
            self.code = self.code.strip().upper()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Assessment(models.Model):
    """
    Independent assessment entity with self-contained configuration, eligible colleges,
    and server-enforced lifecycle states (DRAFT -> READY -> SCHEDULED -> OPEN -> CLOSED -> ARCHIVED).
    """
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        READY = "READY", "Ready"
        SCHEDULED = "SCHEDULED", "Scheduled"
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"
        ARCHIVED = "ARCHIVED", "Archived"

    class ClosePolicy(models.TextChoices):
        ALLOW_FINISH = "ALLOW_FINISH", "Allow In-Progress Attempts to Finish"
        STRICT_CUTOFF = "STRICT_CUTOFF", "Strict Cutoff (Terminate Active Attempts)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True, db_index=True, help_text="Unique assessment code (e.g. CSL-DIAG-01)")
    title = models.CharField(max_length=200, help_text="Assessment display title")
    description = models.TextField(blank=True, default="", help_text="Instructions and description for candidates")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    assessment_type = models.CharField(
        max_length=50,
        default="INITIAL_DIAGNOSTIC",
        db_index=True,
        help_text="Classification of assessment type (e.g. INITIAL_DIAGNOSTIC, TECHNICAL_MOCK)",
    )

    # Independent configuration parameters
    duration_minutes = models.PositiveIntegerField(default=60, help_text="Duration in minutes per attempt")
    total_marks = models.PositiveIntegerField(default=50, help_text="Total marks obtainable")
    aptitude_count = models.PositiveIntegerField(default=25, help_text="Number of aptitude questions to sample")
    coding_count = models.PositiveIntegerField(default=25, help_text="Number of coding questions to sample")
    max_attempts = models.PositiveIntegerField(default=1, help_text="Maximum allowed attempts per candidate")

    # Proctoring thresholds
    max_tab_switches_warning = models.PositiveIntegerField(default=2, help_text="Permitted tab switch warnings (3rd switch auto-submits)")
    auto_submit_on_tab_limit = models.BooleanField(default=True, help_text="Auto-submit attempt when tab limit is breached")

    # Scheduling & Timing
    scheduled_start_time = models.DateTimeField(null=True, blank=True, help_text="Optional scheduled opening time")
    scheduled_end_time = models.DateTimeField(null=True, blank=True, help_text="Optional scheduled closing time")
    opened_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when explicitly opened")
    closed_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when closed")
    close_policy = models.CharField(max_length=20, choices=ClosePolicy.choices, default=ClosePolicy.ALLOW_FINISH)

    # Results Release Policy
    is_results_released = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether candidates are permitted to view scores and scorecard",
    )
    results_released_at = models.DateTimeField(null=True, blank=True)
    results_released_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="released_assessments",
    )

    # College eligibility (M2M)
    eligible_colleges = models.ManyToManyField(College, blank=True, related_name="assigned_assessments")

    # Assessment-specific question pool (M2M)
    questions = models.ManyToManyField(
        QuestionBank,
        blank=True,
        related_name="assigned_assessments",
        help_text="Scoped pool of questions eligible for this assessment",
    )

    # Administrative audit tracking
    created_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_assessments",
    )
    opened_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="opened_assessments",
    )
    closed_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="closed_assessments",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["code"]),
        ]

    def clean(self):
        if self.code:
            self.code = self.code.strip().upper()
        if self.title:
            self.title = self.title.strip()
        errors = {}
        if self.duration_minutes < 1:
            errors["duration_minutes"] = "Duration must be at least 1 minute."
        if self.aptitude_count < 1 and self.coding_count < 1:
            errors["aptitude_count"] = "At least one question must be configured."
        if self.total_marks != (self.aptitude_count + self.coding_count):
            errors["total_marks"] = f"Total marks ({self.total_marks}) must equal aptitude ({self.aptitude_count}) + coding ({self.coding_count})."
        if self.max_attempts < 1:
            errors["max_attempts"] = "Max attempts must be at least 1."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def is_currently_open(self):
        if self.status != self.Status.OPEN:
            return False
        now = timezone.now()
        if self.scheduled_end_time and now > self.scheduled_end_time:
            return False
        return True

    def __str__(self):
        return f"[{self.code}] {self.title} ({self.status})"


class Candidate(models.Model):
    """
    Candidate registered specifically for assessments. Belongs to a managed College record.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=150)
    register_number = models.CharField(max_length=100)
    college = models.CharField(max_length=200, help_text="College / Institution name (legacy text)")
    college_ref = models.ForeignKey(
        College,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="candidates",
        help_text="Managed college relationship",
    )
    email = models.EmailField(db_index=True)
    department = models.CharField(max_length=150, help_text="Department / Course")
    year_of_study = models.CharField(max_length=50, help_text="e.g. 1st Year, 2nd Year, Final Year")
    phone_number = models.CharField(max_length=30, blank=True, default="", help_text="Mobile / contact phone number")
    is_active = models.BooleanField(default=True, db_index=True, help_text="Candidate eligibility status")
    
    # Optional link to formal User account (once activated/approved)
    user = models.OneToOneField(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assessment_candidate",
    )
    
    # Expiring single-use activation token for later account claim
    activation_token = models.CharField(max_length=100, blank=True, default="", db_index=True)
    activation_token_expires_at = models.DateTimeField(null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # College-scoped uniqueness for register_number, plus global uniqueness for normalized email
            models.UniqueConstraint(fields=["college", "register_number"], name="uniq_candidate_college_regno"),
            models.UniqueConstraint(fields=["email"], name="uniq_candidate_email"),
        ]

    def clean(self):
        if self.email:
            self.email = self.email.strip().lower()
        if self.register_number:
            self.register_number = self.register_number.strip().upper()
        if self.full_name:
            self.full_name = self.full_name.strip()
        if self.college_ref and not self.college:
            self.college = self.college_ref.name
        elif self.college:
            self.college = self.college.strip()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.register_number} - {self.college})"


class AssessmentAttempt(models.Model):
    class State(models.TextChoices):
        CREATED = "CREATED", "Created"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        SUBMITTED = "SUBMITTED", "Submitted"
        TIMED_OUT = "TIMED_OUT", "Timed Out"
        FLAGGED_FOR_REVIEW = "FLAGGED_FOR_REVIEW", "Flagged for Review"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="attempts")
    config = models.ForeignKey(AssessmentConfig, on_delete=models.PROTECT, related_name="attempts")
    assessment = models.ForeignKey(
        Assessment,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="attempts",
        help_text="Associated multi-assessment entity",
    )
    
    state = models.CharField(max_length=30, choices=State.choices, default=State.CREATED, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    
    # Computed marks (Backend authoritative)
    aptitude_score = models.IntegerField(default=0)
    coding_score = models.IntegerField(default=0)
    total_score = models.IntegerField(default=0)
    percentage = models.FloatField(default=0.0)
    
    # Integrity flags
    tab_switch_count = models.PositiveIntegerField(default=0)
    fullscreen_exit_count = models.PositiveIntegerField(default=0)
    is_flagged = models.BooleanField(default=False)
    flag_reason = models.TextField(blank=True, default="")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["candidate", "state"]),
            models.Index(fields=["state", "deadline"]),
        ]

    def __str__(self):
        return f"{self.candidate.full_name} - {self.state} ({self.total_score}/50)"

    def is_expired(self):
        if self.deadline and timezone.now() > self.deadline:
            return True
        return False


class AttemptQuestionSnapshot(models.Model):
    """
    Immutable snapshot of the exact 50 questions selected for a candidate attempt,
    including the stable randomized option ordering for that attempt.
    """
    attempt = models.ForeignKey(AssessmentAttempt, on_delete=models.CASCADE, related_name="question_snapshots")
    question = models.ForeignKey(QuestionBank, on_delete=models.PROTECT, related_name="attempt_snapshots")
    question_order = models.PositiveIntegerField(help_text="1 to 50 ordering in attempt")
    section_type = models.CharField(max_length=20, choices=QuestionBank.SectionType.choices)
    
    # Captured prompt and shuffled options mapping for student rendering
    prompt = models.TextField()
    option_a_text = models.TextField()
    option_b_text = models.TextField()
    option_c_text = models.TextField()
    option_d_text = models.TextField()
    
    # The actual original key that maps to the correct option for this shuffled display
    correct_option_key = models.CharField(max_length=1, help_text="A, B, C, or D for this snapshot display")
    
    # Student's answer
    selected_option = models.CharField(max_length=1, blank=True, default="", help_text="A, B, C, or D")
    is_correct = models.BooleanField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["attempt", "question_order"]
        constraints = [
            models.UniqueConstraint(fields=["attempt", "question_order"], name="uniq_attempt_question_order"),
            models.UniqueConstraint(fields=["attempt", "question"], name="uniq_attempt_question_dup"),
        ]

    def __str__(self):
        return f"Attempt {self.attempt_id} - Q{self.question_order} ({self.section_type})"


class IntegrityEvent(models.Model):
    class EventType(models.TextChoices):
        ATTEMPT_STARTED = "ATTEMPT_STARTED", "Attempt Started"
        FULLSCREEN_ENTER = "FULLSCREEN_ENTER", "Full-screen Entered"
        FULLSCREEN_EXIT = "FULLSCREEN_EXIT", "Full-screen Exited"
        TAB_HIDDEN = "TAB_HIDDEN", "Tab Switched / Hidden"
        TAB_VISIBLE = "TAB_VISIBLE", "Tab Restored / Visible"
        RECONNECTED = "RECONNECTED", "Connection Restored"
        SUBMITTED = "SUBMITTED", "Submitted"
        TIMED_OUT = "TIMED_OUT", "Timed Out"
        DEVTOOLS_SHORTCUT = "DEVTOOLS_SHORTCUT", "Developer Tools Shortcut Attempt"
        CONTEXT_MENU_BLOCKED = "CONTEXT_MENU_BLOCKED", "Context Menu Blocked"

    attempt = models.ForeignKey(AssessmentAttempt, on_delete=models.CASCADE, related_name="integrity_events")
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    event_id = models.CharField(max_length=100, blank=True, default="", db_index=True, help_text="Client deduplication token")
    client_timestamp = models.DateTimeField(null=True, blank=True)
    server_timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(blank=True, default=dict)

    # Review workflow
    is_reviewed = models.BooleanField(default=False, db_index=True)
    review_notes = models.TextField(blank=True, default="")
    reviewed_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_integrity_events",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-server_timestamp"]
        indexes = [
            models.Index(fields=["attempt", "event_type"]),
            models.Index(fields=["attempt", "event_id"]),
            models.Index(fields=["is_reviewed", "server_timestamp"]),
        ]

    def __str__(self):
        return f"{self.attempt_id} - {self.event_type} at {self.server_timestamp}"


class AssessmentAuditLog(models.Model):
    """
    Persisted audit trail for consequential administrative operations.
    """
    class Action(models.TextChoices):
        ASSESSMENT_CREATED = "ASSESSMENT_CREATED", "Assessment Created"
        ASSESSMENT_UPDATED = "ASSESSMENT_UPDATED", "Assessment Updated"
        ASSESSMENT_PREPARED = "ASSESSMENT_PREPARED", "Assessment Prepared / Validated"
        ASSESSMENT_OPENED = "ASSESSMENT_OPENED", "Assessment Opened"
        ASSESSMENT_CLOSED = "ASSESSMENT_CLOSED", "Assessment Closed"
        ASSESSMENT_ARCHIVED = "ASSESSMENT_ARCHIVED", "Assessment Archived"
        COLLEGE_ASSIGNED = "COLLEGE_ASSIGNED", "College Assigned"
        COLLEGE_REMOVED = "COLLEGE_REMOVED", "College Removed"
        COLLEGE_CREATED = "COLLEGE_CREATED", "College Created"
        COLLEGE_UPDATED = "COLLEGE_UPDATED", "College Updated"
        COLLEGE_STATUS_TOGGLED = "COLLEGE_STATUS_TOGGLED", "College Status Changed"
        CANDIDATES_IMPORTED = "CANDIDATES_IMPORTED", "Candidates Imported"
        QUESTIONS_ASSIGNED = "QUESTIONS_ASSIGNED", "Questions Assigned to Assessment Pool"
        RESULTS_RELEASED = "RESULTS_RELEASED", "Assessment Results Released"
        RESULTS_UNRELEASED = "RESULTS_UNRELEASED", "Assessment Results Withheld"

    action = models.CharField(max_length=40, choices=Action.choices, db_index=True)
    entity_type = models.CharField(max_length=30, db_index=True, help_text="ASSESSMENT, COLLEGE, CANDIDATE")
    entity_id = models.CharField(max_length=100, db_index=True)
    performed_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assessment_audit_logs",
    )
    performed_by_name = models.CharField(max_length=150, blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    details = models.JSONField(blank=True, default=dict)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["action", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.action} on {self.entity_type} {self.entity_id} by {self.performed_by_name or 'System'}"
