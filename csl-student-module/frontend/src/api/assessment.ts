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

export const assessmentApi = axios.create({
  baseURL: `${API_BASE}/api/assessment`,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

assessmentApi.interceptors.request.use((config) => {
  const csrfToken = getCookie('csrftoken');
  if (csrfToken && config.headers) {
    config.headers['X-CSRFToken'] = csrfToken;
  }

  // Inject secure assessment token if stored
  const token = sessionStorage.getItem('csl_assessment_token') || localStorage.getItem('csl_assessment_token');
  if (token && config.headers) {
    config.headers['Authorization'] = `Bearer ${token}`;
    config.headers['X-Assessment-Token'] = token;
  }

  return config;
});

export interface CollegeOption {
  id: number;
  name: string;
  code: string;
  location?: string;
}

export interface CandidateAssessmentItem {
  id: string;
  code: string;
  title: string;
  description: string;
  duration_minutes: number;
  total_marks: number;
  aptitude_count: number;
  coding_count: number;
  max_attempts: number;
  status: string;
  is_open: boolean;
  scheduled_start_time?: string;
  scheduled_end_time?: string;
  attempts_count: number;
  user_can_attempt: boolean;
  latest_attempt_id?: string | null;
  latest_attempt_state?: string | null;
  latest_attempt_score?: number | null;
}

export interface CandidateAssessmentsResponse {
  candidate: {
    id: string;
    full_name: string;
    register_number: string;
    college: string;
    college_id?: number | null;
    department: string;
    year_of_study: string;
    is_active: boolean;
  };
  assessments: CandidateAssessmentItem[];
}

export interface RegistrationPayload {
  full_name: string;
  register_number: string;
  college?: string;
  college_id?: number;
  email: string;
  department: string;
  year_of_study: string;
  phone_number: string;
}

export interface RegisterResponse {
  candidate_id: string;
  assessment_token: string;
  full_name?: string;
  college?: string;
  college_id?: number | null;
  already_completed: boolean;
  is_active_attempt?: boolean;
  attempt_id?: string;
  attempt_state?: string;
  assessment_title?: string;
  assessment_code?: string;
  remaining_seconds?: number;
  message?: string;
}

export interface QuestionOption {
  key: string;
  text: string;
}

export interface QuestionSnapshot {
  question_order: number;
  section_type: 'APTITUDE' | 'CODING';
  category?: string;
  prompt: string;
  options: QuestionOption[];
  selected_option: string;
}

export interface AttemptDetailResponse {
  id: string;
  assessment_id?: string;
  assessment_title?: string;
  assessment_code?: string;
  state: 'CREATED' | 'IN_PROGRESS' | 'SUBMITTED' | 'TIMED_OUT' | 'FLAGGED_FOR_REVIEW';
  started_at: string;
  deadline: string;
  remaining_seconds: number;
  server_time?: string;
  candidate_name: string;
  college: string;
  total_questions: number;
  tab_switch_count: number;
  fullscreen_exit_count: number;
  max_tab_switches: number;
  remaining_tab_switches: number;
  is_flagged?: boolean;
  flag_reason?: string;
  questions: QuestionSnapshot[];
  assessment_token?: string;
}

export interface SectionBreakdown {
  score: number;
  total: number;
  percentage: number;
  correct: number;
  incorrect: number;
  unattempted: number;
}

export interface ResultBreakdown {
  total_questions: number;
  time_taken_seconds: number;
  time_taken_display: string;
  aptitude: SectionBreakdown;
  coding: SectionBreakdown;
}

export interface ResultResponse {
  id: string;
  assessment_id?: string;
  assessment_title?: string;
  assessment_code?: string;
  candidate_name: string;
  register_number: string;
  college: string;
  department: string;
  year_of_study?: string;
  state: string;
  aptitude_score: number;
  coding_score: number;
  total_score: number;
  percentage: number;
  duration_minutes?: number;
  max_marks?: number;
  total_questions?: number;
  tab_switch_count?: number;
  fullscreen_exit_count?: number;
  is_flagged?: boolean;
  flag_reason?: string;
  is_results_released?: boolean;
  message?: string;
  started_at: string;
  submitted_at: string;
  breakdown?: ResultBreakdown;
}

export interface IntegrityEventResponse {
  status: string;
  event_type: string;
  tab_switches: number;
  max_switches: number;
  remaining_switches: number;
  is_finalized: boolean;
  state: string;
  flag_reason: string;
}

export const getStudentColleges = async (): Promise<CollegeOption[]> => {
  const res = await assessmentApi.get<CollegeOption[]>('/colleges/');
  return res.data;
};

export const getCandidateAssessments = async (): Promise<CandidateAssessmentsResponse> => {
  const res = await assessmentApi.get<CandidateAssessmentsResponse>('/candidate-assessments/');
  return res.data;
};

export const registerCandidate = async (payload: RegistrationPayload): Promise<RegisterResponse> => {
  const res = await assessmentApi.post<RegisterResponse>('/register/', payload);
  if (res.data.assessment_token) {
    sessionStorage.setItem('csl_assessment_token', res.data.assessment_token);
    sessionStorage.setItem('csl_candidate_id', res.data.candidate_id);
  }
  return res.data;
};

export const startAssessment = async (assessmentId?: string): Promise<AttemptDetailResponse> => {
  const payload = assessmentId ? { assessment_id: assessmentId } : {};
  const res = await assessmentApi.post<AttemptDetailResponse>('/start/', payload);
  if (res.data.assessment_token) {
    sessionStorage.setItem('csl_assessment_token', res.data.assessment_token);
  }
  if (res.data.id) {
    sessionStorage.setItem('csl_attempt_id', res.data.id);
  }
  return res.data;
};

export const getAttemptState = async (attemptId: string): Promise<AttemptDetailResponse> => {
  const res = await assessmentApi.get<AttemptDetailResponse>(`/attempts/${attemptId}/`);
  return res.data;
};

export const saveAnswer = async (
  attemptId: string,
  questionOrder: number,
  selectedOption: string
): Promise<{ question_order: number; selected_option: string; status: string }> => {
  const res = await assessmentApi.post(`/attempts/${attemptId}/answer/`, {
    question_order: questionOrder,
    selected_option: selectedOption,
  });
  return res.data;
};

export const recordIntegrityEvent = async (
  attemptId: string,
  eventType: string,
  eventId: string = '',
  metadata: Record<string, unknown> = {}
): Promise<IntegrityEventResponse> => {
  const res = await assessmentApi.post<IntegrityEventResponse>(`/attempts/${attemptId}/integrity-event/`, {
    event_type: eventType,
    event_id: eventId,
    client_timestamp: new Date().toISOString(),
    metadata,
  });
  return res.data;
};

export const finalizeAssessment = async (attemptId: string): Promise<ResultResponse> => {
  const res = await assessmentApi.post<ResultResponse>(`/attempts/${attemptId}/finalize/`);
  return res.data;
};

export const getAssessmentResult = async (attemptId: string): Promise<ResultResponse> => {
  const res = await assessmentApi.get<ResultResponse>(`/attempts/${attemptId}/result/`);
  return res.data;
};
