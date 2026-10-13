export interface StaffActivityItem {
  id: number;
  title: string;
  type: 'ASSESSMENT' | 'TASK' | 'PROJECT';
  description: string;
  course_id: number;
  course_name: string;
  course_code: string;
  batch_id: number | null;
  batch_name: string | null;
  deadline: string | null;
  max_marks: number;
  status: 'DRAFT' | 'ACTIVE' | 'ARCHIVED';
  is_active: boolean;
  created_by_name: string;
  created_at: string;
  updated_at: string;
  skills_covered: {
    id: number;
    name: string;
    subskills: { id: number; name: string }[];
  }[];
}

export interface ActivityOptions {
  courses: {
    id: number;
    name: string;
    code: string;
    batches: { id: number; name: string }[];
  }[];
  skills: {
    id: number;
    name: string;
    subskills: { id: number; name: string }[];
  }[];
}

export interface SkillMappingPayload {
  skill_id: number;
  subskill_ids?: number[];
}

export interface QuestionPayload {
  question_text: string;
  marks?: number;
  skill_id?: number | null;
  subskill_id?: number | null;
}

export interface SectionPayload {
  title: string;
  description?: string;
  display_order?: number;
  questions: QuestionPayload[];
}

export interface StaffActivityCreatePayload {
  title: string;
  description?: string;
  type: 'ASSESSMENT' | 'TASK' | 'PROJECT';
  course_id: number;
  batch_id?: number | null;
  max_marks: number;
  deadline?: string | null;
  status?: 'DRAFT' | 'ACTIVE' | 'ARCHIVED';
  skills?: SkillMappingPayload[];
  sections?: SectionPayload[];
}
