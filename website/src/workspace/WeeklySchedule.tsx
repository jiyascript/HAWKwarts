export interface MeetingBlock {
  code: string // "CS 512"
  title: string
  day: "M" | "T" | "W" | "R" | "F" // Banner day letters (R = Thursday)
  start: string // "10:00" (24-hour)
  end: string // "11:15"
  location?: string
}

export interface SemesterSchedule {
  term: string
  meetings: MeetingBlock[]
}

const DAYS = [
  { key: "M", label: "Mon" },
  { key: "T", label: "Tue" },
  { key: "W", label: "Wed" },
  { key: "R", label: "Thu" },
  { key: "F", label: "Fri" },
]

const HOUR_HEIGHT = 48 // pixels per hour

export function toMinutes(time: string): number {
  const [hours, minutes] = time.split(":").map(Number)
  return hours * 60 + minutes
}

function hourLabel(hour: number): string {
  return `${hour % 12 || 12} ${hour < 12 ? "AM" : "PM"}`
}

export function WeeklySchedule({ term, meetings, isSample, }: SemesterSchedule & { isSample?: boolean }) {
  if (meetings.length === 0) return null

  // Show only the hours that are actually used
  const firstHour = Math.floor(Math.min(...meetings.map((m) => toMinutes(m.start))) / 60)
  const lastHour = Math.ceil(Math.max(...meetings.map((m) => toMinutes(m.end))) / 60)

  const hours: number[] = []
  for (let hour = firstHour; hour < lastHour; hour++) hours.push(hour)

  return (
    <div className="weekly">
      <h3 className="weekly-title">
        {term} schedule
        {isSample && <span className="sample-pill">Preview</span>}
      </h3>
      {isSample && ( 
        <p className="weekly-note">Sample data. Enter your data to see a customized one.</p>
      )}

      <div className="weekly-row weekly-head">
        <div />
        {DAYS.map((day) => (
          <div key={day.key} className="weekly-day-label">{day.label}</div>
        ))}
      </div>

      <div className="weekly-row">
        <div>
          {hours.map((hour) => (
            <div key={hour} className="weekly-hour" style={{ height: HOUR_HEIGHT }}>
              {hourLabel(hour)}
            </div>
          ))}
        </div>

        {DAYS.map((day) => (
          <div
            key={day.key}
            className="weekly-day"
            style={{ height: hours.length * HOUR_HEIGHT }}
          >
            {meetings
              .filter((meeting) => meeting.day === day.key)
              .map((meeting) => {
                const top = ((toMinutes(meeting.start) - firstHour * 60) / 60) * HOUR_HEIGHT
                const height = ((toMinutes(meeting.end) - toMinutes(meeting.start)) / 60) * HOUR_HEIGHT
                return (
                  <div
                    key={meeting.code + meeting.start}
                    className="weekly-block"
                    style={{ top, height }}
                    title={meeting.title}
                  >
                    <span className="weekly-block-code">{meeting.code}</span>
                    <span className="weekly-block-time">{meeting.start}–{meeting.end}</span>
                    {meeting.location && (
                      <span className="weekly-block-time">{meeting.location}</span>
                    )}
                  </div>
                )
              })}
          </div>
        ))}
      </div>
    </div>
  )
}

// one course with all its days, e.g. Mon/Wed 10:00–11:15
export interface SelectedCourse {
  code: string
  title: string
  days: MeetingBlock["day"][] // e.g. ["M", "W"]
  start: string // "10:00" (24-hour)
  end: string // "11:15"
  location?: string
}

// turns the course list into the blocks the grid draws (one per day)
export function expandCourses(courses: SelectedCourse[]): MeetingBlock[] {
  return courses.flatMap((course) =>
    course.days.map((day) => ({
      code: course.code,
      title: course.title,
      day,
      start: course.start,
      end: course.end,
      location: course.location,
    })),
  )
}