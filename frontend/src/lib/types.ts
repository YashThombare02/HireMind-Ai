export type User = {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
};

export type ResumeEntry = { title?: string; details?: string; raw?: string; [key: string]: unknown };

export type Resume = {
  id: string;
  skills: string[];
  education: ResumeEntry[];
  experience: ResumeEntry[];
  projects: ResumeEntry[];
  certifications: string[];
  created_at: string;
};

export type JobDescription = {
  id: string;
  title: string;
  required_skills: string[];
  preferred_skills: string[];
  experience_required: string | null;
  responsibilities: string[];
  created_at: string;
};

export type AtsResult = {
  id: string;
  resume_id: string;
  jd_id: string;
  match_score: number;
  matched_skills: string[];
  missing_skills: string[];
  experience_relevance: number | null;
  recommendation: string | null;
  created_at: string;
};
