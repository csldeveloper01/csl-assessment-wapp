import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// Custom Failure & Performance Metrics
const failureRate = new Rate('failed_requests');
const saveAnswerDuration = new Trend('save_answer_duration');
const integrityEventsRecorded = new Counter('integrity_events_total');

// Workflow Stage Counters
const candidatesLaunched = new Counter('candidates_launched');
const registrationsSuccessful = new Counter('registrations_successful');
const assessmentLookupsSuccessful = new Counter('assessment_lookups_successful');
const startAttempts = new Counter('start_attempts');
const successfulStarts = new Counter('successful_starts');
const answerSaves = new Counter('answer_saves');
const completedFinalizations = new Counter('completed_finalizations');

// Helper to parse and validate positive integer environment variables
function parsePositiveInt(val, name, defaultValue) {
  if (val === undefined || val === null || val === '') {
    return defaultValue;
  }
  const parsed = Number(val);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`Invalid environment variable ${name}='${val}': must be a positive integer.`);
  }
  return parsed;
}

// Test Configuration
// Target URL, VUs, and Iterations can be overridden via CLI:
// k6 run -e TARGET_URL=https://csl-backend.onrender.com -e VUS=5 -e ITERATIONS=1 load_tests/load_test_k6_small.js
const TARGET_URL = __ENV.TARGET_URL || 'http://127.0.0.1:8000';
const VUS = parsePositiveInt(__ENV.VUS, 'VUS', 10);
const ITERATIONS = parsePositiveInt(__ENV.ITERATIONS, 'ITERATIONS', 1);

export const options = {
  scenarios: {
    student_flow: {
      executor: 'per-vu-iterations',
      vus: VUS,
      iterations: ITERATIONS,
      maxDuration: '3m',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<1500'],
    failed_requests: ['rate<0.05'],
    save_answer_duration: ['p(95)<1000'],
  },
};

/**
 * Sanitizes and truncates response bodies for diagnostic logging.
 * Scrubs tokens, passwords, and sensitive fields to avoid credential exposure.
 */
function sanitizeBody(body) {
  if (!body) return 'empty/no body';
  let str = typeof body === 'string' ? body : JSON.stringify(body);
  str = str.replace(/eyJ[a-zA-Z0-9_\-.]+/g, '[TOKEN_REDACTED]');
  str = str.replace(/"(password|token|assessment_token|access_token|refresh_token|email|phone_number)"\s*:\s*"[^"]+"/gi, '"$1":"[REDACTED]"');
  return str.slice(0, 200).replace(/[\r\n\t]+/g, ' ').trim();
}

/**
 * Standardized diagnostic logger for failed HTTP steps.
 */
function logFailure(endpoint, vuId, res) {
  const status = res ? res.status : 'NO_RESPONSE';
  const body = res ? sanitizeBody(res.body) : 'empty/no body';
  console.error(`[FAILURE] endpoint=${endpoint} vu=${vuId} status=${status} body="${body}"`);
}

export default function () {
  const vuId = __VU;
  const iterId = __ITER;
  const timestamp = Date.now();

  candidatesLaunched.add(1);

  // 1. Health Check
  const healthRes = http.get(`${TARGET_URL}/health/`);
  const isHealthy = check(healthRes, {
    'health check returns 200': (r) => r.status === 200,
  });
  failureRate.add(!isHealthy);
  if (!isHealthy) {
    logFailure('/health/', vuId, healthRes);
  }

  // 2. Fetch Active Colleges
  const collegesRes = http.get(`${TARGET_URL}/api/assessment/colleges/`);
  const collegesOk = check(collegesRes, {
    'colleges list fetched (200)': (r) => r.status === 200,
  });
  failureRate.add(!collegesOk);

  if (!collegesOk) {
    logFailure('/api/assessment/colleges/', vuId, collegesRes);
    return;
  }

  let selectedCollege = null;
  try {
    const colleges = JSON.parse(collegesRes.body);
    if (Array.isArray(colleges) && colleges.length > 0) {
      selectedCollege = colleges[vuId % colleges.length];
    }
  } catch (e) {
    console.error(`[PARSE_ERROR] endpoint=/api/assessment/colleges/ vu=${vuId} error="${e.message}"`);
  }

  if (!selectedCollege || !selectedCollege.id) {
    console.warn(`[SKIP] endpoint=/api/assessment/colleges/ vu=${vuId} reason="No usable colleges available; aborting iteration to prevent unenrolled college fallback"`);
    return;
  }

  // 3. Register Candidate (contract: /api/assessment/register/)
  const regPayload = JSON.stringify({
    full_name: `Candidate ${vuId}-${iterId}`,
    email: `k6_${vuId}_${iterId}_${timestamp}@testcsl.edu`,
    phone_number: `9${Math.floor(100000000 + Math.random() * 900000000)}`,
    register_number: `REG${vuId}${iterId}${Math.floor(1000 + Math.random() * 9000)}`,
    department: 'Computer Science',
    year_of_study: 'Final Year',
    college_id: selectedCollege.id,
    college: selectedCollege.name,
  });

  const regHeaders = { 'Content-Type': 'application/json' };
  const regRes = http.post(`${TARGET_URL}/api/assessment/register/`, regPayload, { headers: regHeaders });
  console.log(`Registration response: ${regRes.timings.duration} ms`);

  const regOk = check(regRes, {
    'candidate registered (201 or 200)': (r) => r.status === 201 || r.status === 200,
  });
  failureRate.add(!regOk);

  if (!regOk) {
    logFailure('/api/assessment/register/', vuId, regRes);
    return;
  }

  let token = null;
  try {
    const regBody = JSON.parse(regRes.body);
    token = regBody.assessment_token;
  } catch (e) {}

  if (!token) {
    console.warn(`[SKIP] endpoint=/api/assessment/register/ vu=${vuId} reason="Registration response missing assessment_token"`);
    return;
  }

  registrationsSuccessful.add(1);

  const authHeaders = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
    'X-Assessment-Token': token,
  };

  // 4. Fetch Eligible Assessments
  const eligibleRes = http.get(`${TARGET_URL}/api/assessment/candidate-assessments/`, { headers: authHeaders });
  console.log(`Assessment lookup response: ${eligibleRes.timings.duration} ms`);

  const eligibleOk = check(eligibleRes, {
    'candidate assessments fetched (200)': (r) => r.status === 200,
  });
  failureRate.add(!eligibleOk);

  if (!eligibleOk) {
    logFailure('/api/assessment/candidate-assessments/', vuId, eligibleRes);
    return;
  }

  let targetAssessmentId = null;
  try {
    const eligibleBody = JSON.parse(eligibleRes.body);
    if (eligibleBody.assessments && Array.isArray(eligibleBody.assessments)) {
      const openAssessments = eligibleBody.assessments.filter((a) => a.is_open && a.user_can_attempt);
      if (openAssessments.length > 0) {
        targetAssessmentId = openAssessments[0].id;
      }
    }
  } catch (e) {}

  if (!targetAssessmentId) {
    console.warn(`[SKIP] endpoint=/api/assessment/candidate-assessments/ vu=${vuId} reason="No eligible open assessment found; skipping candidate"`);
    return;
  }

  assessmentLookupsSuccessful.add(1);

  // 5. Start Assessment (contract: /api/assessment/start/)
  const startPayload = JSON.stringify({ assessment_id: targetAssessmentId });

  startAttempts.add(1);
  const startRes = http.post(
    `${TARGET_URL}/api/assessment/start/`,
    startPayload,
    { headers: authHeaders }
  );
  console.log(`Assessment start response: ${startRes.timings.duration} ms`);

  const startOk = check(startRes, {
    'assessment started (200)': (r) => r.status === 200,
  });
  failureRate.add(!startOk);

  if (!startOk) {
    logFailure('/api/assessment/start/', vuId, startRes);
    return;
  }

  successfulStarts.add(1);

  let attemptId = null;
  let questions = [];
  try {
    const startBody = JSON.parse(startRes.body);
    attemptId = startBody.id;
    if (startBody.assessment_token) {
      authHeaders['Authorization'] = `Bearer ${startBody.assessment_token}`;
      authHeaders['X-Assessment-Token'] = startBody.assessment_token;
    }
    if (Array.isArray(startBody.questions)) {
      questions = startBody.questions;
    }
  } catch (e) {}

  if (!attemptId || questions.length === 0) {
    console.warn(`[SKIP] endpoint=/api/assessment/start/ vu=${vuId} reason="Attempt ID or questions list missing from start response"`);
    return;
  }

  // 6. Assessment Session: Save Answers & Heartbeat Integrity Events
  const numToAnswer = Math.min(questions.length, 5);
  for (let i = 0; i < numToAnswer; i++) {
    sleep(2 + Math.random() * 2);

    const q = questions[i];
    const selectedOption = ['A', 'B', 'C', 'D'][Math.floor(Math.random() * 4)];

    // Save Answer (contract: /api/assessment/attempts/{id}/answer/)
    const startSave = Date.now();
    const saveRes = http.post(
      `${TARGET_URL}/api/assessment/attempts/${attemptId}/answer/`,
      JSON.stringify({
        question_order: q.question_order,
        selected_option: selectedOption,
      }),
      { headers: authHeaders }
    );
    saveAnswerDuration.add(Date.now() - startSave);

    const saveOk = check(saveRes, {
      'answer saved successfully (200)': (r) => r.status === 200,
    });
    failureRate.add(!saveOk);

    if (!saveOk) {
      logFailure(`/api/assessment/attempts/${attemptId}/answer/`, vuId, saveRes);
    } else {
      answerSaves.add(1);
    }

    // Occasional benign integrity ping (TAB_VISIBLE reconnect)
    if (i === 1) {
      const integrityRes = http.post(
        `${TARGET_URL}/api/assessment/attempts/${attemptId}/integrity-event/`,
        JSON.stringify({
          event_type: 'TAB_VISIBLE',
          event_id: `evt-${vuId}-${iterId}-${i}`,
          client_timestamp: new Date().toISOString(),
          metadata: {},
        }),
        { headers: authHeaders }
      );

      const integrityOk = check(integrityRes, {
        'integrity event recorded (200)': (r) => r.status === 200,
      });
      failureRate.add(!integrityOk);

      if (!integrityOk) {
        logFailure(`/api/assessment/attempts/${attemptId}/integrity-event/`, vuId, integrityRes);
      } else {
        integrityEventsRecorded.add(1);
      }
    }
  }

  // 7. Finalize Assessment (contract: /api/assessment/attempts/{id}/finalize/)
  sleep(1);
  const finRes = http.post(
    `${TARGET_URL}/api/assessment/attempts/${attemptId}/finalize/`,
    JSON.stringify({}),
    { headers: authHeaders }
  );

  const finOk = check(finRes, {
    'assessment finalized (200)': (r) => r.status === 200,
  });
  failureRate.add(!finOk);

  if (!finOk) {
    logFailure(`/api/assessment/attempts/${attemptId}/finalize/`, vuId, finRes);
  } else {
    completedFinalizations.add(1);
  }

  sleep(2);
}
