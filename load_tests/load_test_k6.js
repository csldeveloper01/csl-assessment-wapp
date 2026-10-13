import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// Custom Metrics
const failureRate = new Rate('failed_requests');
const saveAnswerDuration = new Trend('save_answer_duration');
const integrityEventsRecorded = new Counter('integrity_events_total');

// Test Configuration
// Target URL can be overridden via CLI:
// k6 run -e TARGET_URL=https://csl-backend.onrender.com load_test_k6.js
const TARGET_URL = __ENV.TARGET_URL || 'http://127.0.0.1:8000';

export const options = {
  stages: [
    { duration: '30s', target: 10 },   // Warm-up / baseline
    { duration: '1m',  target: 25 },   // Ramp up to 25
    { duration: '1m',  target: 50 },   // Mid concurrency (50 candidates)
    { duration: '2m',  target: 100 },  // Peak target (100 concurrent candidates)
    { duration: '1m',  target: 120 },  // Stress threshold (120 candidates)
    { duration: '1m',  target: 0 },    // Ramp-down / drain
  ],
  thresholds: {
    'http_req_duration': ['p(95)<1500'], // 95% of requests must complete within 1.5s
    'failed_requests': ['rate<0.05'],     // Error rate must stay below 5%
    'save_answer_duration': ['p(95)<1000'],
  },
};

export default function () {
  const vuId = __VU;
  const iterId = __ITER;
  const timestamp = Date.now();

  // 1. Health Check
  const healthRes = http.get(`${TARGET_URL}/health/`);
  const isHealthy = check(healthRes, {
    'health check returns 200': (r) => r.status === 200,
  });
  failureRate.add(!isHealthy);

  // 2. Fetch Active Colleges
  const collegesRes = http.get(`${TARGET_URL}/api/assessment/colleges/`);
  let selectedCollege = null;
  if (check(collegesRes, { 'colleges list fetched': (r) => r.status === 200 })) {
    try {
      const colleges = JSON.parse(collegesRes.body);
      if (Array.isArray(colleges) && colleges.length > 0) {
        selectedCollege = colleges[vuId % colleges.length];
      }
    } catch (e) {
      // JSON parse error handled gracefully
    }
  }

  // 3. Register Candidate (contract: /api/assessment/register/)
  const regPayload = JSON.stringify({
    full_name: `Candidate ${vuId}-${iterId}`,
    email: `k6_${vuId}_${iterId}_${timestamp}@testcsl.edu`,
    phone_number: `9${Math.floor(100000000 + Math.random() * 900000000)}`,
    register_number: `REG${vuId}${iterId}${Math.floor(1000 + Math.random() * 9000)}`,
    department: 'Computer Science',
    year_of_study: 'Final Year',
    college_id: selectedCollege ? selectedCollege.id : null,
    college: selectedCollege ? selectedCollege.name : 'CSL Testing Institute',
  });

  const regHeaders = { 'Content-Type': 'application/json' };
  const regRes = http.post(`${TARGET_URL}/api/assessment/register/`, regPayload, { headers: regHeaders });
  
  const regOk = check(regRes, {
    'candidate registered (201 or 200)': (r) => r.status === 201 || r.status === 200,
  });
  failureRate.add(!regOk);

  let token = null;
  try {
    const regBody = JSON.parse(regRes.body);
    token = regBody.assessment_token;
  } catch (e) {}

  if (!token) {
    sleep(2);
    return;
  }

  const authHeaders = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
    'X-Assessment-Token': token,
  };

  // 4. Fetch Eligible Assessments
  const eligibleRes = http.get(`${TARGET_URL}/api/assessment/candidate-assessments/`, { headers: authHeaders });
  let targetAssessmentId = null;
  if (eligibleRes.status === 200) {
    try {
      const eligibleBody = JSON.parse(eligibleRes.body);
      if (eligibleBody.assessments && eligibleBody.assessments.length > 0) {
        const openAssessments = eligibleBody.assessments.filter((a) => a.is_open && a.user_can_attempt);
        if (openAssessments.length > 0) {
          targetAssessmentId = openAssessments[0].id;
        }
      }
    } catch (e) {}
  }

  // 5. Start Assessment (contract: /api/assessment/start/)
  const startPayload = JSON.stringify(targetAssessmentId ? { assessment_id: targetAssessmentId } : {});
  const startRes = http.post(`${TARGET_URL}/api/assessment/start/`, startPayload, { headers: authHeaders });
  
  const startOk = check(startRes, {
    'assessment started (200)': (r) => r.status === 200,
  });
  failureRate.add(!startOk);

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

  // 6. Assessment Session: Save Answers & Heartbeat Integrity Events
  if (attemptId && questions.length > 0) {
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

      check(saveRes, {
        'answer saved successfully': (r) => r.status === 200,
      });

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
        if (integrityRes.status === 200) {
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
    check(finRes, {
      'assessment finalized': (r) => r.status === 200,
    });
  }

  sleep(2);
}
