import http from 'k6/http';
import { check } from 'k6';

const base = __ENV.TARGET_URL || 'https://csl-assessment-wapp.onrender.com';

export const options = {
  vus: 1,
  iterations: 5,
};

export default function () {
  const health = http.get(`${base}/health/`);
  check(health, {
    'Backend health is OK': (r) => r.status === 200,
  });

  const colleges = http.get(`${base}/api/assessment/colleges/`);
  check(colleges, {
    'Student colleges API is OK': (r) => r.status === 200,
  });
}
