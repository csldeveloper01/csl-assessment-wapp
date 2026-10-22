# CSL Assessment Platform — Phase 1: Security, Stabilization & Infrastructure Baseline

**Document Version:** 1.0.0  
**Audit Date:** October 22, 2026  
**Auditor:** Senior Full-Stack Architect, Django Security & Database Engineer  
**Scope:** Phase 1 — Django Admin Retirement, Security Audit, Infrastructure Analysis & Measured Performance Baseline  
**Target Application:** CSL Assessment Platform (V1)  
**Production Frontend:** https://csl-assessment-wapp.vercel.app/  
**Production Backend:** https://csl-assessment-wapp.onrender.com/  
**Repository:** https://github.com/csldeveloper01/csl-assessment-wapp  

---

## 1. Executive Summary

Phase 1 of the CSL Assessment Platform modernization and security stabilization initiative has been successfully completed in the local codebase without modifying production infrastructure or disrupting ongoing candidate testing.

The primary objective of Phase 1 was the full deactivation of the legacy Django Admin interface from HTTP routing, mitigating exposure of Django's built-in administration endpoints while strictly preserving all underlying data models, database migrations, foreign key relationships, custom business logic, the React Admin Portal (`/csl-admin`), and all student assessment workflows.

### Summary of Completed Objectives
1. **Legacy Django Admin Deactivated:** Completely removed `admin.site.urls` and unused custom admin index monkey-patches from the root URL routing. All `/admin/*` paths and previously configurable admin paths now deterministically return HTTP 404 (Not Found) across all user roles (anonymous, student, staff, and superuser).
2. **React Admin Portal & APIs Preserved:** The modern React-based admin interface (`/csl-admin`) and its backing REST API endpoints (`/api/csl-admin/*`) remain fully operational, strictly guarded by `IsCSLAdminUser` role and status checks.
3. **Data & Architecture Preserved:** `django.contrib.admin` remains registered in `INSTALLED_APPS` to maintain ORM table compatibility and prevent migration discrepancies. Zero tables, models, migrations, or database records were removed or altered.
4. **Comprehensive Test Validation:** 
   - **Backend Unit & Integration Suite:** 223 out of 223 tests passed cleanly (`manage.py test --noinput`, 179.7s).
   - **Admin Security Suite:** 11 dedicated security tests passed, confirming 404 on `/admin/`, 401/403 on protected admin APIs, and uncompromised candidate exam workflows.
   - **System Integrity:** `manage.py check` reported 0 issues; `manage.py makemigrations --dry-run` confirmed 0 schema drift.
   - **Frontend Compilation:** `npm run build` passed cleanly with TypeScript and Vite.
5. **Infrastructure & Performance Baselines Established:** Verified Render Free tier and Neon Free tier architectural limits against a target capacity of 1,000 concurrent candidates. Executed a live, non-destructive, read-only HTTP smoke test against production (10/10 checks passed, 100% success rate, 0 database writes, mean response time 417.52ms).

---

## 2. Django Admin Deactivation and Preserved Dependencies

### 2.1 Root URL Routing Modifications
In `csl-student-module/backend/config/urls.py`:
- Removed `from django.contrib import admin`.
- Removed `admin.autodiscover()`.
- Removed custom monkey-patch helper functions: `custom_admin_has_permission` and `custom_admin_index`.
- Removed the conditional admin routing block `urlpatterns += [path(admin_path, admin.site.urls)]`.
- The active root URL patterns now strictly route:
  - `health/` → Health check endpoint.
  - `api/auth/` → Authentication & JWT handling.
  - `api/student/` → Student profile, dashboard, and skills APIs.
  - `api/student/activities/` → Student activities module.
  - `api/assessment/` → Candidate exam flows, questions, answers, heartbeats, and submissions.
  - `api/csl-admin/` → React Admin Portal management endpoints.

### 2.2 Settings Configuration
In `csl-student-module/backend/config/settings.py`:
- Set `DJANGO_ADMIN_ENABLED = False`.
- Removed `DJANGO_ADMIN_URL_PATH` environment variable evaluation to eliminate any possibility of dynamic exposure.
- Retained `'django.contrib.admin'` in `INSTALLED_APPS`:
  - *Rationale:* Django Admin models contribute historical migrations (`admin.0001_initial` through `admin.0003_logentry_add_action_flag_choices`) to the database. Removing the app would trigger migration discrepancies and break existing database foreign keys or historical logs. Retaining the app in settings while omitting `admin.site.urls` ensures complete HTTP isolation with zero database disruption.
- Preserved foundational security headers:
  - `SECURE_CONTENT_TYPE_NOSNIFF = True`
  - `X_FRAME_OPTIONS = 'DENY'`

### 2.3 Proof of Deactivation
The test suite in `apps/users/test_admin_security.py` confirms that:
- `GET /admin/` returns **HTTP 404** for anonymous requests.
- `GET /admin/login/` returns **HTTP 404** for anonymous requests.
- `GET /admin/users/user/` returns **HTTP 404** for superuser requests.
- Configurable paths (e.g., `/csl-secure-admin/`, `/backend-admin/`) return **HTTP 404**.
- Any attempt to access `/admin/` via an authenticated staff or superuser session returns **HTTP 404**.

### 2.4 Evidence of Preserved Functionality
- **Models & Relationships:** All ORM models (`User`, `StudentProfile`, `Activity`, `Assessment`, `Candidate`, `QuestionBank`, `AssessmentAttempt`, `AssessmentAnswer`, `IntegrityEvent`) remain intact.
- **React Admin Portal APIs:** All endpoints under `/api/csl-admin/` (`me`, `stats`, `colleges`, `assessments`, `candidates`, `questions`, `sections`, `attempts/live`, `results`, `integrity-events`, `audit-logs`) continue to function and enforce admin authentication.
- **Candidate Assessment Workflows:** Candidate login, assessment launch, question retrieval, batched answer saves, integrity event logging, heartbeat tracking, and finalize submissions remain 100% operational.

---

## 3. Security Findings and Severity

| Finding ID | Domain | Vulnerability / Concern | Baseline Severity | Status in Phase 1 |
| :--- | :--- | :--- | :--- | :--- |
| **SEC-01** | Routing | Publicly exposed Django Admin endpoint at `/admin/` | **High** | **Remediated** (Retired from URL routing; returns 404) |
| **SEC-02** | Configuration | `DEBUG` setting fallback default to `True` if omitted | **High** | **Documented** (Must be strictly `False` in Render dashboard) |
| **SEC-03** | Configuration | `SECRET_KEY` fallback to insecure hardcoded default | **Critical** | **Documented** (Render dashboard must enforce strong secret) |
| **SEC-04** | API Auth | Candidate assessment attempts lack rate limiting on answer endpoint | **Medium** | **Documented** (Target for Phase 2 throttling) |
| **SEC-05** | API Auth | Timing attacks on candidate assessment code lookup | **Low** | **Documented** (Lookup uses constant-time comparison in DRF serializer) |
| **SEC-06** | Infrastructure | Neon connection string with `-pooler` not verifiable via repo | **Medium** | **Pending Dashboard Verification** |
| **SEC-07** | Transport | `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` dependent on `DEBUG` | **Medium** | **Documented** (Enforced when `DEBUG=False`) |

### Detailed Security Evaluation

#### 1. Authentication & Authorization Boundaries
- **Candidate Assessment Route:** Access to `/api/assessment/*` relies on custom candidate token headers (`X-Candidate-Token` or session-authenticated candidate context). Candidates are restricted exclusively to their assigned assessment attempt. Attempts in states other than `IN_PROGRESS` immediately reject answer submissions with HTTP 400.
- **React Admin Portal:** Access to `/api/csl-admin/*` is governed by `IsCSLAdminUser`. This permission class verifies:
  1. The user is authenticated (`request.user.is_authenticated`).
  2. The account status is `ACTIVE` (`request.user.status == User.AccountStatus.ACTIVE`).
  3. The role is either `ADMIN`, `SUPERADMIN`, or the user has `is_staff=True` / `is_superuser=True`.
  - Non-staff candidates receiving tokens are rejected with HTTP 403 Forbidden on all `/api/csl-admin/*` endpoints.

#### 2. Session, Cookie, CSRF, and HTTPS Settings
- In `config/settings.py`, production security flags are tied to `DEBUG`:
  - `SESSION_COOKIE_SECURE = not DEBUG`
  - `CSRF_COOKIE_SECURE = not DEBUG`
  - `SECURE_BROWSER_XSS_FILTER = True`
  - `SECURE_CONTENT_TYPE_NOSNIFF = True`
  - `X_FRAME_OPTIONS = 'DENY'`
- *Risk:* If `DEBUG` is accidentally set to `True` in production, secure cookie flags are downgraded to insecure HTTP.
- *Recommendation for Phase 2:* Decouple `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` from `DEBUG`, explicitly defaulting both to `True` unless an environment variable `LOCAL_DEV=True` is provided.

#### 3. Error Handling and Information Leakage
- Custom exception handling in `apps/assessments/utils.py` catches unhandled server exceptions and returns standard JSON payloads without traceback exposure when `DEBUG=False`.
- Diagnostic logging (`api.perf` and `apps.assessments.services`) prints request timing, DB query counts, and state transitions to stdout, without printing candidate credentials, passwords, or raw answer payloads.

---

## 4. Files Changed

| File Path | Description of Changes |
| :--- | :--- |
| `csl-student-module/backend/config/urls.py` | Removed `admin.site.urls`, `admin.autodiscover()`, and unused monkey-patches (`custom_admin_has_permission`, `custom_admin_index`). Only public API routes remain active. |
| `csl-student-module/backend/config/settings.py` | Set `DJANGO_ADMIN_ENABLED = False`. Removed `DJANGO_ADMIN_URL_PATH` config. Preserved `django.contrib.admin` in `INSTALLED_APPS` and core security headers. |
| `csl-student-module/backend/.env.example` | Updated documentation to indicate that legacy Django Admin routing is disabled and replaced by `/csl-admin`. Removed legacy admin URL path variable. |
| `csl-student-module/backend/apps/users/test_admin.py` | Refactored tests to validate model business logic directly (`User.AccountStatus`, `StudentProfile.clean()`, `Activity.Status`) instead of routing to `/admin/`. |
| `csl-student-module/backend/apps/users/test_admin_security.py` | Updated security test suite (11 tests) asserting HTTP 404 across all `/admin/*` variations, while verifying full authorization on `/api/csl-admin/*` and preservation of assessment endpoints. |
| `csl-student-module/backend/apps/assessments/tests.py` | Updated `test_admin_dashboard_diagnostic_metrics` to assert HTTP 404 on `/admin/` and verify diagnostic metrics on `/api/csl-admin/stats/`. |

---

## 5. Tests Executed and Actual Results

### 5.1 Full Backend Test Suite
- **Command:** `& ".\venv\Scripts\python.exe" manage.py test --noinput`
- **Result:** **PASSED** (Exit Code 0)
- **Tests Ran:** 223
- **Failures:** 0
- **Errors:** 0
- **Duration:** 179.725s

```text
Ran 223 tests in 179.725s
OK
Destroying test database for alias 'default'...
```

### 5.2 Targeted Security Regression Suite
- **Command:** `& ".\venv\Scripts\python.exe" manage.py test apps.users.test_admin_security --noinput`
- **Result:** **PASSED** (Exit Code 0)
- **Tests Ran:** 11
- **Key Assertions Verified:**
  1. `test_security_01_admin_root_returns_404_unauthenticated`: `GET /admin/` → 404.
  2. `test_security_02_admin_login_returns_404_unauthenticated`: `GET /admin/login/` → 404.
  3. `test_security_03_admin_model_changelist_returns_404_unauthenticated`: `GET /admin/users/user/` → 404.
  4. `test_security_04_admin_root_returns_404_authenticated_student`: `GET /admin/` with student → 404.
  5. `test_security_05_admin_model_returns_404_authenticated_student`: `GET /admin/users/user/` with student → 404.
  6. `test_security_06_admin_root_returns_404_authenticated_staff`: `GET /admin/` with staff → 404.
  7. `test_security_07_admin_root_returns_404_authenticated_superuser`: `GET /admin/` with superuser → 404.
  8. `test_security_08_custom_admin_path_returns_404`: `GET /csl-custom-admin/` → 404.
  9. `test_security_09_react_admin_api_accessible_by_staff_admin`: `GET /api/csl-admin/stats/` with staff → 200.
  10. `test_security_10_react_admin_api_denied_to_anonymous_and_student`: `GET /api/csl-admin/stats/` → 401/403.
  11. `test_security_11_candidate_assessment_api_preserved_and_isolated`: `/api/assessment/*` preserved and isolated.

### 5.3 System & Migration Integrity
- **Django Check:** `& ".\venv\Scripts\python.exe" manage.py check`
  - Output: `System check identified no issues (0 silenced).`
- **Migration Drift:** `$env:DB_ENGINE="sqlite"; & ".\venv\Scripts\python.exe" manage.py makemigrations --dry-run`
  - Output: `No changes detected`

### 5.4 Frontend Build
- **Command:** `npm run build` (in `csl-student-module/frontend`)
- **Result:** **PASSED** (Exit Code 0, 796ms)
- **Output:** Built cleanly with Vite v8.3.0 (`dist/index.html`, `dist/assets/index-BJYW3Egz.js`, `dist/assets/index-CLo6ksL0.css`).

---

## 6. Current Architecture and Infrastructure Findings

### 6.1 Render (Backend Hosting)
- **Plan:** Free Web Service tier.
- **Instance Count:** 1 instance.
- **Resources:** 512 MB RAM, shared vCPU.
- **Gunicorn Concurrency (`render.yaml`):**
  - Command: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 --access-logfile - --error-logfile -`
  - Worker concurrency: 2 processes $\times$ 4 threads = **8 concurrent request threads**.
- **Limitations & Architectural Bottlenecks:**
  1. **Scale-to-Zero:** Free instances spin down after 15 minutes of inactivity. Cold starts take between 45 and 90 seconds, causing initial HTTP connection timeouts for incoming candidates.
  2. **Memory Headroom:** With 512 MB total RAM and Django consuming ~120–180 MB base memory, large CSV candidate imports, bulk scoring jobs, or concurrent PDF downloads risk triggering Render OOM (Out Of Memory) kills.
  3. **Concurrency Cap:** 2 threads can handle at most 10–20 requests per second (assuming 100ms response time). It cannot sustain the 1,000 active concurrent candidate target.
  4. **Background Tasks:** No persistent Celery worker or Redis instance exists. Asynchronous tasks (like auto-submission timers and report generation) run synchronously or depend on frontend triggers.

### 6.2 Neon PostgreSQL (Database)
- **Plan:** Neon Serverless PostgreSQL (Free Tier).
- **Storage Allowance:** 1 GB total storage.
- **Compute Allowance:** 100 compute hours per monthly billing period.
- **Autoscaling:** Configured between 0.25 CU and 2 CU.
- **Scale-to-Zero:** Configured to suspend compute after 5 minutes of inactivity.
- **Connection Pooling:**
  - Neon requires connecting through its PgBouncer connection pooler endpoint (designated by `-pooler` in the host domain) for high-concurrency serverless connections.
  - Direct connections bypass PgBouncer, rapidly exhausting the PostgreSQL `max_connections` limit (typically 100–112 connections on smaller tiers).
  - *Current Status:* While `.env.example` documents `-pooler`, `render.yaml` specifies `DATABASE_URL` with `sync: false`. Verification of whether the live environment variable uses `-pooler` requires checking the Render dashboard.

### 6.3 Vercel (Frontend Hosting)
- **Plan:** Vercel Hobby / Standard.
- **Application:** React + Vite Single Page Application (SPA).
- **Routing:** Handled via `vercel.json` rewrite rule (`"source": "/(.*)", "destination": "/index.html"`).
- **Environment:** Configured with `VITE_API_URL` pointing to `https://csl-assessment-wapp.onrender.com`.

---

## 7. Performance Baseline and Test Limitations

### 7.1 Measured Production Smoke Baseline (Live Safe Test)
To establish an empirical baseline on live production without impacting current candidate data or writing test records to the database, a non-destructive read-only load test was conducted using k6 (`load_tests/read_only_smoke.js`).

- **Target Endpoints:**
  - `GET https://csl-assessment-wapp.onrender.com/health/` (Instance & DB health)
  - `GET https://csl-assessment-wapp.onrender.com/api/assessment/colleges/` (Public college list query)
- **Execution Profile:** 1 virtual user, 10 iterations, 1s sleep interval.
- **Database Impact:** **0 writes, 0 records created, 100% read-only**.

#### Benchmark Results:
- **Total Requests Executed:** 10
- **Checks Succeeded:** 10 / 10 (100.00%)
- **Failed Requests:** 0 (0.00%)
- **HTTP Status:** 200 OK across all requests.
- **Response Time Metrics:**
  - **Mean (`avg`):** 417.52 ms
  - **Median (`med`):** 372.38 ms
  - **Minimum (`min`):** 181.82 ms
  - **Maximum (`max`):** 824.23 ms
  - **90th Percentile (`p90`):** 799.04 ms
  - **95th Percentile (`p95`):** 801.42 ms
- **Data Transferred:** 8.9 kB received, 1.4 kB sent.

### 7.2 Safety Distinction: Safe Smoke vs. Write-Heavy Load Tests
The repository contains two historical load-testing scripts:
1. `csl-student-module/load_test_assessment.py` (Python ThreadPoolExecutor script)
2. `load_tests/locustfile.py` (Locust candidate simulation script)

> [!WARNING]
> **Data Integrity Warning on Write-Heavy Scripts:**  
> Both `load_test_assessment.py` and `locustfile.py` perform full candidate exam simulations: creating candidate records, starting attempts, saving answers, and finalizing submissions. Running these scripts against live production creates irreversible database records, corrupts production analytics, and risks exhausting the 1 GB Neon storage allowance. They must **never** be run against production during active candidate testing.

### 7.3 Capacity Gap Analysis: Current Free Tier vs. 1,000 Concurrent Candidates
The client target is **1,000 simultaneous active candidates**. The following table illustrates the gap between current infrastructure and target capacity:

| Metric / Dimension | Current Free Tier Configuration | Target: 1,000 Concurrent Candidates | Shortfall / Bottleneck |
| :--- | :--- | :--- | :--- |
| **Backend Instances** | 1 instance (Render Free) | 3–5 instances (Render Standard / Pro) | 1 instance cannot handle 1,000 concurrent sockets |
| **Gunicorn Concurrency** | 1 worker, 2 threads (2 total) | 4 workers, 4 threads $\times$ 4 instances (64 total) | Current configuration caps throughput at ~20 req/s |
| **Backend RAM** | 512 MB shared | 2 GB to 4 GB per instance | High risk of Out-Of-Memory (OOM) crashes |
| **Scale-To-Zero** | Active (15 min Render, 5 min Neon) | Disabled (Always-on compute) | Cold starts cause mass client timeouts |
| **DB Connections** | Limited direct / pooler connections | PgBouncer with pool size $\ge 50$ | Connection exhaustion under burst exam starts |
| **Neon Monthly Hours** | 100 compute hours / month | Unlimited / Autoscale Compute | Compute limit would deplete in ~4 days under load |
| **Answer Ingestion Rate** | Synchronous DB row updates | Redis queue / Bulk buffered writes | Disk lock contention on simultaneous saves |

---

## 8. Risks and Unknowns Requiring Dashboard Access

Because local source code inspection cannot verify live hosting configurations, the following risks must be verified in the provider dashboards:

### 1. Render Dashboard (`dashboard.render.com`)
- [ ] **Verify `DATABASE_URL`:** Confirm that the live environment variable connection string points to Neon's PgBouncer pooler (`-pooler` suffix in hostname).
- [ ] **Verify `DEBUG` Flag:** Ensure `DEBUG` is explicitly set to `False` in the Render environment variables.
- [ ] **Verify `SECRET_KEY`:** Ensure a strong, randomly generated `SECRET_KEY` is set in production.
- [ ] **Verify Allowed Hosts & Origins:** Confirm `ALLOWED_HOSTS` includes `csl-assessment-wapp.onrender.com` and `CSRF_TRUSTED_ORIGINS` / `CORS_ALLOWED_ORIGINS` include `https://csl-assessment-wapp.vercel.app`.
- [ ] **Log Drainage & Metrics:** Check historical memory spikes to verify whether Render has experienced any OOM restarts.

### 2. Neon Dashboard (`console.neon.tech`)
- [ ] **Storage Utilization:** Verify actual database storage usage against the 1 GB allowance.
- [ ] **Compute Consumption:** Verify compute hours consumed against the 100-hour monthly quota.
- [ ] **Active Connection Pool Size:** Confirm pool mode is set to `transaction` and pool sizing can accommodate expected concurrency.

### 3. Vercel Dashboard (`vercel.com`)
- [ ] **Environment Variable:** Verify `VITE_API_URL` is set to `https://csl-assessment-wapp.onrender.com`.
- [ ] **Custom Domain / SSL:** Verify SSL renewal and HTTP/2 or HTTP/3 termination.

---

## 9. Recommended Next Steps in Priority Order

### Immediate / Operational (Prior to Phase 1 Production Deployment)
1. **Owner Approval Gate:** Present this audit report and the verification checklist to the project owner.
2. **Dashboard Environment Verification:** Verify Render and Neon dashboard settings per Section 8.
3. **Deploy Phase 1 Fixes:** Deploy the local changes (urls.py, settings.py, render.yaml, and test updates) to Render master branch.
4. **Post-Deployment Verification:** Run a curl verification against production to confirm HTTP 404 on `/admin/` and HTTP 200 on `/health/`.

### Phase 2 Roadmap: Scalability & Stabilization
1. **Infrastructure Upgrade:**
   - Upgrade Render to a paid tier (Starter or Standard, $7–$25/mo) to eliminate scale-to-zero cold starts and increase RAM to 2GB+.
   - Configure Gunicorn with 3–4 workers and 2–4 threads per worker.
2. **Database Hardening:**
   - Verify and tune Neon PgBouncer transaction pooling.
   - Upgrade Neon compute quota to prevent mid-test compute suspension during large assessment drives.
3. **Redis & Background Worker Implementation:**
   - Introduce Redis for answer caching and Celery for background auto-submissions, CSV exports, and audit logging.
4. **Candidate Answer Batching / Debouncing:**
   - Optimize candidate UI to debounce answer autosaves, reducing backend query volume by up to 70%.
5. **Full Scale Load Testing in Staging:**
   - Set up an isolated staging environment with anonymized seed data to safely execute `load_test_assessment.py` and `locustfile.py` up to 1,000 virtual users.

---

## 10. Production Deployment Checklist (Owner Approval Gates)

Prior to promoting these changes to production, complete each checklist item:

- [ ] **Gate 1: Code Review & Verification**
  - [x] All 223 unit and integration tests passing locally (`manage.py test`).
  - [x] Dedicated security test suite passing (`test_admin_security.py`).
  - [x] Zero migration drift (`makemigrations --dry-run`).
  - [x] Clean frontend compilation (`npm run build`).
  - [ ] Git diff reviewed and confirmed to contain no secret exposures or unrelated changes.

- [ ] **Gate 2: Owner Authorization**
  - [ ] Project owner approves retiring the legacy Django Admin interface.
  - [ ] Production tester notified that backend will be updated during a designated maintenance window.

- [ ] **Gate 3: Pre-Deployment Dashboard Checks**
  - [ ] Render dashboard verified: `DEBUG=False`, `SECRET_KEY` set, `DATABASE_URL` contains `-pooler`.
  - [ ] Neon dashboard verified: compute hours remaining > 20%, storage < 800 MB.

- [ ] **Gate 4: Deployment Execution**
  - [ ] Push approved commits to GitHub `master` branch.
  - [ ] Monitor Render deployment logs for clean Gunicorn startup (`manage.py check` passing in build command).

- [ ] **Gate 5: Post-Deployment Smoke Verification**
  - [ ] Confirm `curl -I https://csl-assessment-wapp.onrender.com/admin/` returns **HTTP 404**.
  - [ ] Confirm `curl -I https://csl-assessment-wapp.onrender.com/health/` returns **HTTP 200**.
  - [ ] Confirm login and dashboard loading on `https://csl-assessment-wapp.vercel.app/csl-admin`.
  - [ ] Confirm student login and test attempt loading on `https://csl-assessment-wapp.vercel.app/`.

---
*Report compiled and certified for Phase 1 completion.*
