import { apiClient } from './client';
import type {
  StaffActivityItem,
  ActivityOptions,
  StaffActivityCreatePayload,
} from '../types/staffActivity';

/**
 * Fetch list of activities for staff management with optional status and course filtering.
 */
export async function getStaffActivities(params?: {
  status?: string;
  course_id?: number;
}): Promise<StaffActivityItem[]> {
  const res = await apiClient.get<any>('/student/activities/manage/', {
    params,
  });
  if (res.data && Array.isArray(res.data.activities)) {
    return res.data.activities;
  }
  if (Array.isArray(res.data)) {
    return res.data;
  }
  return [];
}

/**
 * Fetch courses, batches, and skills options for activity creation.
 */
export async function getActivityOptions(): Promise<ActivityOptions> {
  const res = await apiClient.get<ActivityOptions>('/student/activities/options/');
  return res.data;
}

/**
 * Create a new activity (Task, Project, or Assessment).
 */
export async function createStaffActivity(
  data: StaffActivityCreatePayload
): Promise<StaffActivityItem> {
  const res = await apiClient.post<StaffActivityItem>('/student/activities/manage/', data);
  return res.data;
}

/**
 * Update an existing activity (e.g. status DRAFT -> ACTIVE or ARCHIVED).
 */
export async function updateStaffActivity(
  id: number,
  data: Partial<StaffActivityCreatePayload>
): Promise<StaffActivityItem> {
  const res = await apiClient.patch<StaffActivityItem>(
    `/student/activities/manage/${id}/`,
    data
  );
  return res.data;
}

/**
 * Soft delete an activity.
 */
export async function deleteStaffActivity(id: number): Promise<void> {
  await apiClient.delete(`/student/activities/manage/${id}/`);
}
