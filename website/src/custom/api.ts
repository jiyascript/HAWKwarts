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

export async function askAdvisor(question: string): Promise<string> {
  const response = await fetch("http://localhost:8000/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    throw new Error("Server error: " + response.status);
  }

  const data = await response.json();
  return data.answer;
}