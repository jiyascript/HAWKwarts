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
let uploadedHistory: Record<string, unknown> | null = null

export async function fetchSchedule(): Promise<ScheduleResult> {
  if (!uploadedHistory) {
    throw new Error("Upload a transcript before generating a plan.")
  }

  const response = await fetch("/api/schedule", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ history: uploadedHistory }),
  })

  if (!response.ok) {
    throw new Error("Server error: " + response.status)
  }

  return await response.json()
}

export async function askAdvisorFull(question: string): Promise<AdvisorReply> {
  const response = await fetch("/api/chat", {
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

export interface TranscriptResult {
  semesters: {
    id: string
    label: string
    courses: { code: string; name: string; credits: number }[]
  }[]
  counts: { completed: number; transfer: number; in_progress: number }
  warnings: string[]
  validation_errors: string[]
  agent_loaded: boolean
}

export async function uploadTranscript(file: File): Promise<TranscriptResult> {
  const form = new FormData()
  form.append("file", file)

  const response = await fetch("/api/transcript", {
    method: "POST",
    body: form,
  })

  if (!response.ok) {
    let message = "Server error: " + response.status
    try {
      const data = await response.json()
      if (data.detail) message = data.detail
    } catch {
    }
    throw new Error(message)
  }
  const result = await response.json()
  uploadedHistory = result.academic_history ?? null
  return result
}