import { apiClient } from './client';
import type {
  StudentProfile,
  StudentSkillsResponse,
  StudentDashboardResponse,
  StudentActivitiesResponse,
  StudentActivityDetail,
} from '../types/student';

/**
 * Fetch the profile of the currently authenticated student.
 * The backend determines the student from the session; no ID is sent.
 */
export async function getStudentProfile(): Promise<StudentProfile> {
  const res = await apiClient.get<StudentProfile>('/student/profile/');
  return res.data;
}

/**
 * Fetch required skills and subskills for the currently authenticated student.
 */
export async function getStudentSkills(): Promise<StudentSkillsResponse> {
  const res = await apiClient.get<StudentSkillsResponse>('/student/skills/');
  return res.data;
}

/**
 * Fetch dashboard overview data for the currently authenticated student.
 */
export async function getStudentDashboard(): Promise<StudentDashboardResponse> {
  const res = await apiClient.get<StudentDashboardResponse>('/student/dashboard/');
  return res.data;
}

/**
 * Fetch all activities assigned to the currently authenticated student.
 */
export async function getStudentActivities(): Promise<StudentActivitiesResponse> {
  const res = await apiClient.get<StudentActivitiesResponse>('/student/activities/');
  return res.data;
}

/**
 * Fetch details of a specific activity for the currently authenticated student.
 */
export async function getStudentActivityDetail(id: number | string): Promise<StudentActivityDetail> {
  const res = await apiClient.get<StudentActivityDetail>(`/student/activities/${id}/`);
  return res.data;
}
