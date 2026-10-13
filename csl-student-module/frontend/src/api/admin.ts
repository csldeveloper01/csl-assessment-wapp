import axios from 'axios';

function getCookie(name: string): string | null {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    return parts.pop()?.split(';').shift() || null;
  }
  return null;
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export const adminApi = axios.create({
  baseURL: `${API_BASE}/api/csl-admin`,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

adminApi.interceptors.request.use((config) => {
  const csrfToken = getCookie('csrftoken');
  if (csrfToken && config.headers) {
    config.headers['X-CSRFToken'] = csrfToken;
  }
  return config;
});

export interface AdminUser {
  email: string;
  name: string;
  role: string;
  is_staff: boolean;
  is_superuser: boolean;
}

export interface AdminStats {
  colleges_count: number;
  assessments_count: number;
  open_assessments_count: number;
  candidates_count: number;
  attempts_count: number;
  in_progress_count: number;
  submitted_count: number;
  timed_out_count: number;
  flagged_count: number;
  aptitude_questions_count: number;
  coding_questions_count: number;
  total_questions_count: number;
}

export interface AdminCollege {
  id: number;
  name: string;
  code: string;
  address?: string;
  location?: string;
  contact_email?: string;
  contact_phone?: string;
  admin_contact_name?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  candidates_count?: number;
  assigned_assessments_count?: number;
  active_attempts_count?: number;
}

export interface AdminCollegeDetail extends AdminCollege {
  candidates?: AdminCandidate[];
  assigned_assessments?: {
    id: string;
    code: string;
    title: string;
    status: string;
    is_open: boolean;
    duration_minutes: number;
    total_marks: number;
  }[];
}

export interface AdminAssessmentAuditLog {
  id: number;
  action: string;
  entity_type: string;
  entity_id: string;
  performed_by_name: string;
  timestamp: string;
  details: Record<string, unknown>;
}

export interface AdminAssessment {
  id: string;
  code: string;
  title: string;
  description: string;
  status: 'DRAFT' | 'READY' | 'SCHEDULED' | 'OPEN' | 'CLOSED' | 'ARCHIVED';
  is_open: boolean;
  assessment_type?: 'STANDARD' | 'MOCK' | 'SELECTION' | 'SURVEY';
  is_results_released?: boolean;
  pool_questions_count?: number;
  pool_aptitude_count?: number;
  pool_coding_count?: number;
  pool_sufficient?: boolean;
  duration_minutes: number;
  total_marks: number;
  aptitude_count: number;
  coding_count: number;
  max_attempts: number;
  max_tab_switches_warning: number;
  auto_submit_on_tab_limit: boolean;
  scheduled_start_time?: string | null;
  scheduled_end_time?: string | null;
  opened_at?: string | null;
  closed_at?: string | null;
  close_policy: 'ALLOW_FINISH' | 'STRICT_CUTOFF';
  created_at: string;
  updated_at: string;
  eligible_colleges: { id: number; name: string; code: string }[];
  eligible_colleges_count: number;
  attempts_count: number;
  in_progress_count: number;
  submitted_count: number;
}

export interface AdminAssessmentDetail extends AdminAssessment {
  audit_logs: AdminAssessmentAuditLog[];
}

export interface AdminCandidate {
  id: string;
  full_name: string;
  register_number: string;
  college: string;
  college_ref_id?: number | null;
  college_code?: string;
  email: string;
  department: string;
  year_of_study: string;
  phone_number?: string;
  is_active: boolean;
  created_at: string;
  attempts_count: number;
  latest_state?: string;
  latest_score?: number;
}

export interface AdminQuestion {
  id: number;
  prompt: string;
  section_type: 'APTITUDE' | 'CODING';
  category: string;
  difficulty: 'EASY' | 'MEDIUM' | 'HARD';
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_option: 'A' | 'B' | 'C' | 'D';
  explanation?: string;
  assessment_type?: string;
  assessment_id?: string;
  assessment_title?: string;
  assigned_assessments?: { id: string; code: string; title: string }[];
  is_active: boolean;
  created_at?: string;
}

export interface AdminAssessmentConfig {
  id: number;
  title: string;
  description: string;
  duration_minutes: number;
  total_marks: number;
  aptitude_count: number;
  coding_count: number;
  max_attempts: number;
  max_tab_switches_warning: number;
  auto_submit_on_tab_limit: boolean;
  is_active: boolean;
  updated_at: string;
}

export interface AdminLiveAttempt {
  id: string;
  candidate_id: string;
  candidate_name: string;
  register_number: string;
  college: string;
  college_id?: number;
  assessment_id?: string;
  assessment_title?: string;
  assessment_code?: string;
  state: string;
  started_at: string;
  deadline: string;
  remaining_seconds: number;
  answered_count: number;
  total_questions: number;
  tab_switch_count: number;
  fullscreen_exit_count: number;
  integrity_events_count: number;
  is_flagged: boolean;
  flag_reason?: string;
  total_score: number;
}

export interface AdminQuestionReviewSnapshot {
  id: number;
  question_order: number;
  section_type: string;
  category: string;
  prompt: string;
  option_a_text: string;
  option_b_text: string;
  option_c_text: string;
  option_d_text: string;
  correct_option_key: string | null;
  selected_option: string;
  is_correct: boolean | null;
  marks_awarded?: number;
  explanation: string;
  answered_at: string | null;
}

export interface AdminIntegrityEvent {
  id: number;
  event_id?: string;
  attempt_id: string;
  assessment_id?: string;
  candidate_name: string;
  register_number: string;
  college: string;
  event_type: string;
  metadata: Record<string, unknown>;
  created_at: string;
  timestamp?: string;
  is_reviewed?: boolean;
  review_notes?: string;
  reviewed_by_name?: string | null;
  reviewed_at?: string | null;
}

export interface AdminAttemptReview {
  id: string;
  candidate: AdminCandidate;
  assessment_id?: string;
  assessment_title?: string;
  assessment_code?: string;
  state: string;
  started_at: string;
  deadline: string;
  submitted_at: string;
  aptitude_score: number;
  coding_score: number;
  total_score: number;
  percentage: number;
  tab_switch_count: number;
  fullscreen_exit_count: number;
  is_flagged: boolean;
  flag_reason: string;
  total_questions: number;
  answered_count: number;
  questions: AdminQuestionReviewSnapshot[];
  integrity_events: AdminIntegrityEvent[];
}

export interface AdminResult {
  id: string;
  candidate_id: string;
  candidate_name: string;
  register_number: string;
  college: string;
  college_id?: number;
  assessment_id?: string;
  assessment_title?: string;
  assessment_code?: string;
  department: string;
  year_of_study: string;
  state: string;
  aptitude_score: number;
  coding_score: number;
  total_score: number;
  percentage: number;
  started_at: string;
  submitted_at: string;
  tab_switch_count: number;
  fullscreen_exit_count: number;
  is_flagged: boolean;
  flag_reason?: string;
}

// ─── AUTH & STATS ───────────────────────────────────────────────────────────
export async function getAdminMe(): Promise<AdminUser> {
  const res = await adminApi.get<AdminUser>('/me/');
  return res.data;
}

export async function getAdminStats(): Promise<AdminStats> {
  const res = await adminApi.get<AdminStats>('/stats/');
  return res.data;
}

// ─── COLLEGES MODULE ────────────────────────────────────────────────────────
export async function getAdminColleges(params?: { search?: string; is_active?: string }): Promise<AdminCollege[]> {
  const res = await adminApi.get<AdminCollege[]>('/colleges/', { params });
  return res.data;
}

export async function getAdminCollegeDetail(id: number): Promise<AdminCollegeDetail> {
  const res = await adminApi.get<AdminCollegeDetail>(`/colleges/${id}/`);
  return res.data;
}

export async function createAdminCollege(data: Partial<AdminCollege>): Promise<AdminCollege> {
  const res = await adminApi.post<AdminCollege>('/colleges/', data);
  return res.data;
}

export async function updateAdminCollege(id: number, data: Partial<AdminCollege>): Promise<AdminCollegeDetail> {
  const res = await adminApi.patch<AdminCollegeDetail>(`/colleges/${id}/`, data);
  return res.data;
}

export async function toggleAdminCollegeStatus(id: number): Promise<{ id: number; is_active: boolean; message: string }> {
  const res = await adminApi.post(`/colleges/${id}/toggle-status/`);
  return res.data;
}

export async function importAdminCollegeCandidates(
  collegeId: number,
  file?: File,
  csvContent?: string
): Promise<{ total_rows: number; created_count: number; updated_count: number; errors: string[] }> {
  if (file) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await adminApi.post(`/colleges/${collegeId}/import-candidates/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  } else {
    const res = await adminApi.post(`/colleges/${collegeId}/import-candidates/`, { csv_content: csvContent });
    return res.data;
  }
}

// ─── ASSESSMENTS MODULE ─────────────────────────────────────────────────────
export async function getAdminAssessments(params?: { status?: string; search?: string }): Promise<AdminAssessment[]> {
  const res = await adminApi.get<AdminAssessment[]>('/assessments/', { params });
  return res.data;
}

export async function getAdminAssessmentDetail(id: string): Promise<AdminAssessmentDetail> {
  const res = await adminApi.get<AdminAssessmentDetail>(`/assessments/${id}/`);
  return res.data;
}

export async function createAdminAssessment(data: Partial<AdminAssessment> & { eligible_college_ids?: number[] }): Promise<AdminAssessmentDetail> {
  const res = await adminApi.post<AdminAssessmentDetail>('/assessments/', data);
  return res.data;
}

export async function updateAdminAssessment(id: string, data: Partial<AdminAssessment> & { eligible_college_ids?: number[] }): Promise<AdminAssessmentDetail> {
  const res = await adminApi.patch<AdminAssessmentDetail>(`/assessments/${id}/`, data);
  return res.data;
}

export async function prepareAdminAssessment(id: string): Promise<{ message: string; status: string }> {
  const res = await adminApi.post(`/assessments/${id}/prepare/`);
  return res.data;
}

export async function openAdminAssessment(id: string): Promise<{ message: string; status: string; opened_at: string }> {
  const res = await adminApi.post(`/assessments/${id}/open/`);
  return res.data;
}

export async function closeAdminAssessment(id: string, closePolicy?: 'ALLOW_FINISH' | 'STRICT_CUTOFF'): Promise<{ message: string; status: string; closed_at: string; close_policy: string }> {
  const res = await adminApi.post(`/assessments/${id}/close/`, { close_policy: closePolicy });
  return res.data;
}

export async function archiveAdminAssessment(id: string): Promise<{ message: string; status: string }> {
  const res = await adminApi.post(`/assessments/${id}/archive/`);
  return res.data;
}

export async function assignAdminAssessmentColleges(id: string, collegeIds: number[]): Promise<{ message: string; eligible_colleges: { id: number; name: string; code: string }[] }> {
  const res = await adminApi.post(`/assessments/${id}/assign-colleges/`, { college_ids: collegeIds });
  return res.data;
}

export async function assignAdminAssessmentQuestions(
  id: string,
  data: { question_ids?: number[]; action?: 'assign' | 'remove' | 'set'; assessment_type?: string }
): Promise<{
  message: string;
  total_assigned: number;
  aptitude_count: number;
  coding_count: number;
  is_sufficient: boolean;
}> {
  const res = await adminApi.post(`/assessments/${id}/assign-questions/`, data);
  return res.data;
}

export async function releaseAdminAssessmentResults(
  id: string,
  isReleased: boolean = true
): Promise<{
  message: string;
  is_results_released: boolean;
  results_released_at: string | null;
}> {
  const res = await adminApi.post(`/assessments/${id}/release-results/`, { is_results_released: isReleased });
  return res.data;
}

export async function getAdminAssessmentAuditLogs(id: string): Promise<AdminAssessmentAuditLog[]> {
  const res = await adminApi.get<AdminAssessmentAuditLog[]>(`/assessments/${id}/audit-logs/`);
  return res.data;
}

export async function getAdminGlobalAuditLogs(): Promise<AdminAssessmentAuditLog[]> {
  const res = await adminApi.get<AdminAssessmentAuditLog[]>('/audit-logs/');
  return res.data;
}

// ─── CANDIDATES MODULE ──────────────────────────────────────────────────────
export async function getAdminCandidates(params?: { search?: string; college_id?: string | number; is_active?: string }): Promise<AdminCandidate[]> {
  const res = await adminApi.get<AdminCandidate[]>('/candidates/', { params });
  return res.data;
}

export async function getAdminCandidateDetail(id: string): Promise<AdminCandidate & { attempts: unknown[] }> {
  const res = await adminApi.get(`/candidates/${id}/`);
  return res.data;
}

export async function toggleAdminCandidateStatus(id: string): Promise<{ id: string; is_active: boolean; message: string }> {
  const res = await adminApi.post(`/candidates/${id}/toggle-status/`);
  return res.data;
}

export async function exportAdminCandidatesCSV(params?: {
  college_id?: string | number;
  search?: string;
  is_active?: string;
}): Promise<Blob> {
  const res = await adminApi.get('/candidates/export-csv/', {
    params,
    responseType: 'blob',
  });
  return res.data;
}

// ─── QUESTION BANK MODULE ───────────────────────────────────────────────────
export async function getAdminQuestions(params?: {
  section_type?: string;
  category?: string;
  difficulty?: string;
  is_active?: string;
  search?: string;
  assessment_id?: string;
  assessment_type?: string;
}): Promise<AdminQuestion[]> {
  const res = await adminApi.get<AdminQuestion[]>('/questions/', { params });
  return res.data;
}

export async function createAdminQuestion(data: Partial<AdminQuestion> & { assessment_id?: string }): Promise<AdminQuestion> {
  const res = await adminApi.post<AdminQuestion>('/questions/', data);
  return res.data;
}

export async function updateAdminQuestion(
  id: number,
  data: Partial<AdminQuestion> & { assessment_id?: string }
): Promise<AdminQuestion> {
  const res = await adminApi.put<AdminQuestion>(`/questions/${id}/`, data);
  return res.data;
}

export async function toggleAdminQuestion(id: number): Promise<{ id: number; is_active: boolean }> {
  const res = await adminApi.post(`/questions/${id}/toggle/`);
  return res.data;
}

export async function bulkUpdateAdminQuestions(
  ids: number[],
  updates: {
    section_type?: 'APTITUDE' | 'CODING';
    category?: string;
    difficulty?: 'EASY' | 'MEDIUM' | 'HARD';
    is_active?: boolean;
  }
): Promise<{ updated_count: number; message: string }> {
  const res = await adminApi.post('/questions/bulk-update/', { ids, ...updates });
  return res.data;
}

export async function importAdminQuestionsCSV(
  assessmentId: string,
  file?: File,
  csvContent?: string
): Promise<{
  success_count: number;
  error_count: number;
  errors: string[];
  assessment_id?: string;
  assessment_title?: string;
  total_pool_count?: number;
}> {
  if (file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('assessment_id', assessmentId);
    const res = await adminApi.post('/questions/import-csv/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  } else {
    const res = await adminApi.post('/questions/import-csv/', {
      assessment_id: assessmentId,
      csv_content: csvContent,
    });
    return res.data;
  }
}

// ─── CONFIGURATION MODULE ───────────────────────────────────────────────────
export async function getAdminConfig(): Promise<AdminAssessmentConfig> {
  const res = await adminApi.get<AdminAssessmentConfig>('/config/');
  return res.data;
}

export async function updateAdminConfig(data: Partial<AdminAssessmentConfig>): Promise<AdminAssessmentConfig> {
  const res = await adminApi.put<AdminAssessmentConfig>('/config/', data);
  return res.data;
}

// ─── LIVE SESSIONS & RESULTS ────────────────────────────────────────────────
export async function getAdminLiveAttempts(params?: {
  state?: string;
  search?: string;
  assessment_id?: string;
  college_id?: string | number;
}): Promise<AdminLiveAttempt[]> {
  const res = await adminApi.get<AdminLiveAttempt[]>('/attempts/live/', { params });
  return res.data;
}

export async function getAdminAttemptReview(attemptId: string): Promise<AdminAttemptReview> {
  const res = await adminApi.get<AdminAttemptReview>(`/attempts/${attemptId}/review/`);
  return res.data;
}

export async function updateAdminAttemptReviewStatus(
  attemptId: string,
  action: 'CLEAR_FLAG' | 'FLAG',
  notes?: string
): Promise<{ message: string }> {
  const res = await adminApi.post(`/attempts/${attemptId}/review/`, { action, notes });
  return res.data;
}

export async function getAdminResults(params?: {
  search?: string;
  assessment_id?: string;
  college_id?: string | number;
}): Promise<AdminResult[]> {
  const res = await adminApi.get<AdminResult[]>('/results/', { params });
  return res.data;
}

export async function getAdminIntegrityEvents(params?: {
  event_type?: string;
  is_reviewed?: boolean | string;
  attempt_id?: string;
  assessment_id?: string;
  college_id?: string | number;
  search?: string;
}): Promise<AdminIntegrityEvent[]> {
  const res = await adminApi.get<AdminIntegrityEvent[]>('/integrity-events/', { params });
  return res.data;
}

export async function reviewAdminIntegrityEvent(
  id: number,
  is_reviewed: boolean,
  review_notes?: string
): Promise<{ event: AdminIntegrityEvent; message: string }> {
  const res = await adminApi.post(`/integrity-events/${id}/review/`, {
    is_reviewed,
    review_notes,
  });
  return res.data;
}
