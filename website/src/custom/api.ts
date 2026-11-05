import type { SemesterSchedule } from "@/workspace/WeeklySchedule"

export interface FacultyPublication {
  title: string
  year: number | null
}

export interface FacultyResearch {
  name: string | null
  works_count: number | null
  citations: number | null
  openalex_url: string | null
  publications: FacultyPublication[]
}

export interface FacultyProfile {
  name: string
  titles: string[]
  email: string | null
  profile_url: string | null
  bio: string | null
  position: string | null
  education: string | null
  research_interests: string | null
  phones: string[]
  office: string | null
  research: FacultyResearch | null
}

export interface FacultyPanelData {
  type: "professor"
  profile: FacultyProfile
}

export interface CourseSection {
  crn: string | null
  section: string | null
  instructor: string | null
  meeting: string | null
  seats: string | null
}

export interface CourseCard {
  code: string
  title: string | null
  credits: string | null
  description: string | null
  prerequisites: string | null
  corequisites: string | null
  satisfies: string | null
  catalog_url: string | null
  term: string | null
  sections: CourseSection[]
}

export interface CoursePanelData {
  type: "course"
  course: CourseCard
}

export type PanelData = FacultyPanelData | CoursePanelData

export interface AdvisorReply {
  answer: string
  panels: PanelData[]
  schedule: SemesterSchedule | null
}

export interface ScheduleCourse {
  code: string
  title?: string | null
  credits: number
  status: string
}

export interface ScheduleSemester {
  term: string
  existing_courses: ScheduleCourse[]
  planned_courses: ScheduleCourse[]
  total_credits: number
}

export interface ScheduleResult {
  status: string
  message?: string
  semesters: ScheduleSemester[]
  total_planned_credits: number
}

export async function fetchSchedule(): Promise<ScheduleResult> {
  const response = await fetch("http://localhost:8000/schedule", {
    method: "POST",
  })
  if (!response.ok) {
    throw new Error("Server error: " + response.status)
  }
  return await response.json()
}

export async function askAdvisorFull(question: string): Promise<AdvisorReply> {
  const response = await fetch("http://localhost:8000/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    throw new Error("Server error: " + response.status);
  }

  const data = await response.json();
  const panels: PanelData[] = data.panels ?? (data.panel ? [data.panel] : []);
  return { answer: data.answer, panels, schedule: data.schedule ?? null };
}

export async function askAdvisor(question: string): Promise<string> {
  return (await askAdvisorFull(question)).answer;
}
