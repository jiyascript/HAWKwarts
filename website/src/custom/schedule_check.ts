import {
  expandCourses,
  toMinutes,
  type SelectedCourse,
  type SemesterSchedule,
} from "../workspace/WeeklySchedule"

const VALID_DAYS = ["M", "T", "W", "R", "F"]
const TIME_PATTERN = /^([01]?\d|2[0-3]):[0-5]\d$/

export function parseScheduleJson(text: string): SemesterSchedule {
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch {
    throw new Error("That file isn't valid JSON.")
  }

  const record = data as { term?: unknown; courses?: unknown }

  if (typeof record.term !== "string" || record.term === "") {
    throw new Error('Missing "term" (for example "Spring 2027").')
  }
  if (!Array.isArray(record.courses) || record.courses.length === 0) {
    throw new Error('"courses" must be a list with at least one course.')
  }

  const courses: SelectedCourse[] = record.courses.map((item, index) => {
    const course = item as Partial<SelectedCourse>
    const code = typeof course.code === "string" ? course.code : ""
    const days = Array.isArray(course.days) ? course.days : []
    const start = typeof course.start === "string" ? course.start : ""
    const end = typeof course.end === "string" ? course.end : ""

    if (code === "") {
      throw new Error(`Course ${index + 1} is missing its "code".`)
    }
    if (days.length === 0 || days.some((day) => !VALID_DAYS.includes(day))) {
      throw new Error(`${code}: "days" must be a list using M, T, W, R, F.`)
    }
    if (!TIME_PATTERN.test(start) || !TIME_PATTERN.test(end)) {
      throw new Error(`${code}: "start" and "end" must look like "10:00" (24-hour).`)
    }
    if (toMinutes(end) <= toMinutes(start)) {
      throw new Error(`${code}: "end" must be after "start".`)
    }

    return {
      code,
      title: typeof course.title === "string" ? course.title : "",
      days,
      start,
      end,
      location: typeof course.location === "string" ? course.location : undefined,
    }
  })

  return { term: record.term, meetings: expandCourses(courses) }
}

