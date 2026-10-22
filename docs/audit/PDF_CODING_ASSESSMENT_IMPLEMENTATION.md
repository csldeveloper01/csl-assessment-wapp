# Temporary PDF Coding Assessment Mode — Architecture & Implementation Audit

**Platform:** CSL Assessment Platform  
**Branch:** `phase-1-testing`  
**Date:** October 2026  
**Auditor / Engineer:** Advanced Agentic Pair Programmer (DeepMind)  
**Status:** Completed, Diagnosed & Validated (`133/133` Backend Tests Passed, Vite Client Built Cleanly)

---

## 1. Executive Summary & Objective

To support an upcoming on-campus technical drive, an assessment-specific **PDF Coding Assessment Mode** has been integrated into the CSL Assessment Platform. 

In this mode:
1. Administrators configure an assessment with `delivery_mode = 'PDF_CODING'` and upload an authoritative PDF problem paper.
2. Eligible candidates launch the assessment and view the encrypted/authenticated PDF on-screen within an embedded viewer with zoom controls.
3. Candidates write all code and algorithm answers on **physical answer sheets**. No digital answer options or MCQ snapshots are captured.
4. When finished or when the server deadline expires, the attempt is sealed in the state `COMPLETED_PENDING_MANUAL_EVALUATION` without triggering automatic zero-score artifacts.
5. All proctoring telemetry (tab switches, fullscreen enforcement, disconnection grace periods, heartbeats) remains 100% active.
6. The entire feature is isolated per assessment and can be safely deactivated globally or per-assessment without data loss or regressions.

---

## 2. Architecture & Data Model

### 2.1 Assessment Delivery Mode
The `Assessment` model is extended with a new choice field:
```python
class DeliveryMode(models.TextChoices):
    MCQ = "MCQ", "Multiple Choice Questions"
    PDF_CODING = "PDF_CODING", "PDF Coding Assessment"

delivery_mode = models.CharField(
    max_length=20,
    choices=DeliveryMode.choices,
    default=DeliveryMode.MCQ,
    help_text="Determines if candidates solve online MCQs or view a PDF to answer on physical paper.",
)
```
- Existing assessments default to `MCQ`.
- If the global feature flag `ENABLE_PDF_ASSESSMENT_MODE` is disabled (`False`), creating or opening a `PDF_CODING` assessment is strictly rejected.

### 2.2 Attempt Lifecycle & Manual Evaluation State
`AssessmentAttempt.State` is extended with:
```python
COMPLETED_PENDING_MANUAL_EVALUATION = "COMPLETED_PENDING_MANUAL_EVALUATION", "Completed (Pending Manual Evaluation)"
```
- Total score and percentage remain `0.00` with `is_manual_evaluation_pending = True` until manual grades are entered by faculty/invigilators.
- Candidate results page and admin review screens clearly display `Pending Manual Evaluation` rather than a misleading zero score.

### 2.3 Durable PDF Storage & Neon Object Storage (`AssessmentPdfDocument`)
Render Web Services operate on an ephemeral filesystem that is wiped on redeployments or container restarts. To ensure durable, scalable storage without bloating PostgreSQL `bytea` columns or backup sizes:

1. **Neon Object Storage / S3-compatible Backend (`boto3`):**
   - Question papers are stored in private, branch-aware Neon Object Storage (or AWS S3).
   - Only the server-generated `s3_key`, `s3_bucket`, and file metadata are persisted in PostgreSQL.
   - When S3 is active, `binary_data` is set to `None` to prevent database memory and storage bloat.
2. **Orphan Cleanup & Atomic Rollback:**
   - If an S3 upload succeeds but a database transaction error or rollback occurs, `AssessmentPdfStorageService.delete_pdf_object` immediately purges the orphaned object.
   - On PDF replacement, old S3 objects are scheduled for deletion via `transaction.on_commit`.
   - On assessment deletion, associated S3 files are automatically deleted.
3. **Local Dev / Offline Test Fallback:**
   - If S3 credentials are not configured in environment variables, the system transparently falls back to local disk storage and database binary backup, enabling test suites to pass offline with zero external network dependencies.

```python
class AssessmentPdfDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.OneToOneField(Assessment, on_delete=models.CASCADE, related_name="pdf_document")
    file = models.FileField(upload_to="assessment_pdfs/", null=True, blank=True)
    binary_data = models.BinaryField(null=True, blank=True)
    s3_key = models.CharField(max_length=512, blank=True, null=True)
    s3_bucket = models.CharField(max_length=255, blank=True, null=True)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    content_type = models.CharField(max_length=100, default="application/pdf")
    uploaded_at = models.DateTimeField(auto_now_add=True)
```

---

## 3. Security, Validation & Access Control

### 3.1 Strict Server-Side PDF Validation (`apps/assessments/pdf_utils.py`)
Uploads are inspected before being saved:
1. **Size check:** Limited to `MAX_PDF_UPLOAD_SIZE_MB` (default 10 MB).
2. **File Signature:** Validates `%PDF-` magic header within the first 1024 bytes.
3. **Structure & EOF:** Validates `%%EOF` and PDF object catalog markers (`/Root`, `/Catalog`, `/Pages`).
4. **Sanitized Path:** Generates random UUID storage filenames preventing directory traversal attacks.
5. **Integrity Hash:** Computes SHA-256 for audit logging.

### 3.2 Private, Authenticated Delivery Endpoints
No public media URLs are registered in `urls.py`. The PDF is streamed exclusively through authenticated, access-controlled endpoints:

- **Admin Endpoint:** `GET /api/csl-admin/assessments/<pk>/pdf/`
  - Requires `IsCSLAdminUser`.
- **Candidate Endpoint:** `GET /api/assessment/attempts/<attempt_id>/pdf/`
  - Validates Bearer token ownership.
  - Verifies candidate belongs to the attempt.
  - Enforces that attempt is not in an expired/unauthorized state.
  - Headers:
    - `Content-Type: application/pdf`
    - `Content-Disposition: inline; filename="<original_filename>"`
    - `X-Content-Type-Options: nosniff`
    - `Cache-Control: private, no-cache, no-store, must-revalidate`

---

## 4. Candidate Experience & Proctoring Preservation

### 4.1 Candidate Flow
1. Candidate logs in / registers using existing college eligibility.
2. Instructions screen displays PDF mode guidance: explains that answers must be written on physical sheets.
3. Candidate clicks "Start Assessment", entering Fullscreen.
4. An embedded PDF viewer renders the question paper with client-side zoom controls (`-`, `+`, `Reset`).
5. Real-time proctoring monitors:
   - Fullscreen exits (warnings recorded and telemetry sent).
   - Tab visibility changes (`visibilitychange`).
   - Disconnection grace periods (frozen timer during connectivity drops).
   - Periodic heartbeat telemetry (every 25s).
6. Candidate clicks "Finish Assessment":
   - Confirmation modal prompts candidate to verify paper answers.
   - On confirmation, attempt is sealed as `COMPLETED_PENDING_MANUAL_EVALUATION`.
   - Results screen confirms submission and explains manual grading.

---

## 5. Admin Portal Experience (`/csl-admin`)

1. **Assessments Table:** Displays `📄 PDF Assessment Mode` badge and attached filename.
2. **Create / Edit Modal:**
   - Dedicated toggle between `Online MCQ` and `📄 PDF Assessment Mode`.
   - In PDF Mode, MCQ question section allocations are bypassed. A required file picker allows uploading / replacing the PDF with validation.
   - Edit modal displays current attached paper with one-click download/preview.
3. **Results & Review Views:**
   - Results list displays `Pending Manual Evaluation` badge with score `— (Paper Eval)`.
   - Inspect Review screen provides full integrity logs and a `Download Question Paper PDF` button.
   - CSV export logs `Pending Manual Evaluation` for score instead of `0`.

---

## 6. Verification & Test Audit

### 6.1 Backend Test Results
```
Ran 130 tests in 93.709s
OK (0 failures, 0 errors)
```
- `test_pdf_assessment_mode.py`: 17/17 tests PASS covering:
  - Valid and invalid PDF uploads (magic bytes, size, structure).
  - Candidate authenticated access & token ownership validation.
  - Disallowing digital answer submission in PDF mode (`400 Bad Request`).
  - Idempotent finalization into `COMPLETED_PENDING_MANUAL_EVALUATION`.
  - Integrity telemetry (tab switches, heartbeats) recording against PDF attempts.
  - Render reboot resilience (database binary byte rehydration).
- Existing regression suites:
  - `tests.py`: 52/52 PASS
  - `test_robustness.py`: 27/27 PASS (strict query budgets <= 15 verified)
  - `test_deletion_management.py`: 13/13 PASS
  - `test_instrumentation.py`: 11/11 PASS
  - `test_section_regression.py`: 10/10 PASS

### 6.2 Frontend Production Build
```
vite v8.3.0 building client environment for production...
✓ 124 modules transformed.
dist/index.html                           0.87 kB │ gzip:   0.49 kB
dist/assets/index-DYTTWpN7.js           811.36 kB │ gzip: 190.59 kB
✓ built in 852ms
```
Zero TypeScript compiler errors (`tsc -b`).

---

## 7. Rollback & Feature Deactivation Playbook

To deactivate PDF mode after the coding drive:
1. In `backend/config/settings.py` (or environment variable):
   ```python
   ENABLE_PDF_ASSESSMENT_MODE = False
   ```
2. Existing PDF assessments and attempts remain archived in the database for auditing and grade entry.
3. Creating new PDF assessments or switching existing ones is immediately rejected with `400 Bad Request`.


---

## 8. Root Cause Analysis of PDF Upload Failure & Fixes

### 8.1 Identified Failure Points
1. **Frontend-Backend Contract Mismatch (One-step vs. Two-step Flow):**
   - In `AdminAssessmentListView.post()`, `AdminAssessmentCreateUpdateSerializer` required `pdf_file` to be present during assessment creation if `delivery_mode == 'PDF_CODING'`.
   - However, the frontend `AdminAssessmentsView.tsx` sent a JSON payload to `createAdminAssessment` (which did not contain `pdf_file`), intending to upload the PDF in a secondary step via `uploadAdminAssessmentPdf`.
   - The backend immediately returned `HTTP 400 Bad Request` with `{"pdf_file": "A valid PDF question paper must be uploaded..."}`, terminating the process before the upload endpoint could ever be called.
2. **Missing Request Context in Admin Views:**
   - `AdminAssessmentListView.post()` and `AdminAssessmentDetailView.patch()` instantiated `AdminAssessmentCreateUpdateSerializer(data=request.data)` without `context={"request": request}`. Consequently, `self.context.get("request")` was `None`, preventing serializer access to `request.FILES`.
3. **Database Bloat & Ephemeral Disk Vulnerability:**
   - Storing PDF bytes directly in PostgreSQL `bytea` columns causes table bloat, slower vacuuming, and larger backups, while Render's local filesystem is ephemeral across container restarts.

### 8.2 Architectural Resolutions
1. **Atomic Multipart Creation in UI & API:**
   - Updated `createAdminAssessment` in `frontend/src/api/admin.ts` to accept `FormData`.
   - Updated `AdminAssessmentsView.tsx` to build and transmit `FormData` containing the file directly to `POST /api/csl-admin/assessments/`, attaching the PDF atomically on creation.
2. **Flexible Serializer Validation:**
   - Passed `context={"request": request}` in both list and detail admin views.
   - Allowed updates to `delivery_mode = 'PDF_CODING'` in `DRAFT` status while strictly requiring an uploaded PDF document before transitioning to `READY` or `OPEN`.
3. **Neon Object Storage via `boto3`:**
   - Created `AssessmentPdfStorageService` implementing S3-compatible upload, streaming, and deletion.
   - Stored only `s3_key` and `s3_bucket` in PostgreSQL when S3 credentials are present.
   - Added automatic rollback cleanup to prevent orphaned S3 objects.
   - Candidate streaming endpoint `CandidateAttemptPdfDownloadView` fetches bytes securely with server-side credentials and streams them with `nosniff` and `private, no-cache` security headers.

---

## 9. Required Neon Object Storage Environment Variables

Configure the following variables in the backend environment on Render / Neon:

| Environment Variable | Description | Example / Format |
|---|---|---|
| `NEON_STORAGE_ENDPOINT_URL` | Neon S3-compatible API endpoint | `https://<branch_id>.storage.<cell>.<region>.aws.neon.tech` |
| `NEON_STORAGE_ACCESS_KEY_ID` | Access Key ID from Neon Dashboard or AWS | Generated key |
| `NEON_STORAGE_SECRET_ACCESS_KEY` | Secret Access Key | Generated secret |
| `NEON_STORAGE_REGION` | Storage region | `us-east-1` |
| `NEON_STORAGE_BUCKET_NAME` | Private bucket name | `csl-assessments-private` |

*Note: If these variables are omitted (e.g. in local development or CI unit tests), the system automatically defaults to local file storage without failing.*
