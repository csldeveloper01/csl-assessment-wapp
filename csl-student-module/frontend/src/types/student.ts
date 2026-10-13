export interface StudentProfile {
  name: string;
  email: string;
  student_id: string;
  course: string | null;
  batch: string | null;
}

export interface StudentCourseInfo {
  id: number;
  name: string;
  code: string;
}

export interface StudentBatchInfo {
  id: number;
  name: string;
}

export interface StudentSubSkill {
  id: number;
  name: string;
  status: string;
}

export interface StudentSkill {
  id: number;
  name: string;
  category: string;
  status: string;
  subskills: StudentSubSkill[];
}

export interface StudentSkillsResponse {
  course: StudentCourseInfo | null;
  batch: StudentBatchInfo | null;
  skills: StudentSkill[];
}

export interface StudentDashboardIdentity {
  name: string;
  student_id: string;
  course: string | null;
  course_code: string | null;
  batch: string | null;
}

export interface StudentDashboardSkills {
  available: boolean;
  total_skills: number;
  total_subskills: number;
  assessed: number;
  unassessed: number;
  assessed_subskills: number;
  unassessed_subskills: number;
}

export interface StudentDashboardPerformance {
  score: number | null;
  status: string;
  message: string;
}

export interface StudentDashboardActivities {
  available: boolean;
  total: number;
  pending: number;
  message: string;
}

export interface StudentDashboardResponse {
  student: StudentDashboardIdentity;
  skills: StudentDashboardSkills;
  performance: StudentDashboardPerformance;
  activities: StudentDashboardActivities;
}



export interface StudentActivitySummary {
  id: number;
  title: string;
  type: string;
  description: string;
  course: string;
  batch: string | null;
  due_date: string | null;
  max_marks: number;
  status: string;
}

export interface StudentActivitiesResponse {
  activities: StudentActivitySummary[];
}

export interface CoveredSubSkill {
  id: number;
  name: string;
}

export interface CoveredSkill {
  id: number;
  name: string;
  subskills: CoveredSubSkill[];
}

export interface StudentActivityDetail {
  id: number;
  title: string;
  type: string;
  description: string;
  course: string;
  course_code: string;
  batch: string | null;
  due_date: string | null;
  max_marks: number;
  status: string;
  skills_covered: CoveredSkill[];
  created_at: string;
}
