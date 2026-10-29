import type { ReactNode } from "react"
import type { Goal, StudentContext } from "../onboarding/profile"
import { SuggestedQuestionChips } from "./SuggestedQuestionChips"
import "./workspace.css"

// ── Copy per view ───────────────────────────────────────────────
// Views mirror the onboarding goals, so the workspace opens on the student's choice.

const VIEWS: readonly {
  id: Goal
  tab: string
  eyebrow: string
  heading: string
  description: string
}[] = [
  {
    id: "roadmap",
    tab: "Roadmap",
    eyebrow: "Graduation Roadmap",
    heading: "Your degree roadmap.",
    description:
      "Track completed courses, review prerequisites, and plan your remaining semesters.",
  },
  {
    id: "schedule",
    tab: "Schedule",
    eyebrow: "Schedule Generation",
    heading: "Your semester plan.",
    description:
      "See how remaining requirements and their prerequisites fit across upcoming semesters.",
  },
  {
    id: "courses",
    tab: "Courses",
    eyebrow: "Course & Faculty Info",
    heading: "Courses and faculty.",
    description:
      "Look up courses, prerequisites, and professors with your advisor.",
  },
]

// ── Sample roadmap ──────────────────────────────────────────────
// Demonstration rows only. No degree-audit or transcript-analysis service is
// connected, so nothing here comes from the student's record.

export type AcademicStatus = "completed" | "in-progress" | "planned"

interface RoadmapCourse {
  code: string
  name: string
  semester: string
  status: AcademicStatus
}

const SAMPLE_PROGRAM = "CS — Computer Science B.S."

const SAMPLE_ROADMAP: readonly RoadmapCourse[] = [
  {
    code: "CS 101",
    name: "Intro to Computer Science",
    semester: "Fall 2023",
    status: "completed",
  },
  {
    code: "MATH 151",
    name: "Calculus I",
    semester: "Fall 2023",
    status: "completed",
  },
  {
    code: "CS 201",
    name: "Data Structures",
    semester: "Spring 2024",
    status: "completed",
  },
  {
    code: "MATH 152",
    name: "Calculus II",
    semester: "Spring 2024",
    status: "completed",
  },
  {
    code: "CS 301",
    name: "Algorithms",
    semester: "Fall 2024",
    status: "in-progress",
  },
  {
    code: "CS 310",
    name: "Database Systems",
    semester: "Fall 2024",
    status: "in-progress",
  },
  {
    code: "CS 401",
    name: "Machine Learning",
    semester: "Spring 2025",
    status: "planned",
  },
  {
    code: "CS 450",
    name: "Distributed Systems",
    semester: "Spring 2025",
    status: "planned",
  },
]

const STATUS_LABEL: Record<AcademicStatus, string> = {
  completed: "Completed",
  "in-progress": "In Progress",
  planned: "Planned",
}

const COURSE_QUESTIONS = [
  "Tell me about Dr. Jacek",
  "Find open sections for Math 100",
]

/** Explains why sample data is shown, without implying a transcript was read. */
function recordNote(context: StudentContext | null): string {
  const transcript = context?.transcript
  if (transcript?.uploadStatus === "uploaded") {
    return `Your transcript (${transcript.fileName}) is uploaded for this session, but transcript analysis isn’t connected yet, so it hasn’t been read.`
  }
  return "Personalized degree audits aren’t connected yet."
}

// ── Components ──────────────────────────────────────────────────

export function AcademicStatusBadge({ status }: { status: AcademicStatus }) {
  return (
    <span className={`status-badge status-badge-${status}`}>
      <span className="status-badge-dot" aria-hidden="true" />
      {STATUS_LABEL[status]}
    </span>
  )
}

function SampleNotice({ children }: { children: ReactNode }) {
  return (
    <p className="ws-notice">
      <svg
        className="ws-notice-icon"
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="16" x2="12" y2="12" />
        <line x1="12" y1="8" x2="12.01" y2="8" />
      </svg>
      <span>{children}</span>
    </p>
  )
}

export function CourseProgressTable({
  courses,
}: {
  courses: readonly RoadmapCourse[]
}) {
  return (
    <div
      className="course-table-scroll"
      tabIndex={0}
      aria-label="Course progress table"
    >
      <table className="course-table">
        <caption className="ob-sr-only">Sample course progress</caption>
        <thead>
          <tr>
            <th scope="col">Code</th>
            <th scope="col">Course Name</th>
            <th scope="col" className="course-table-semester">
              Semester
            </th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {courses.map((course) => (
            <tr key={course.code}>
              <td className="course-table-code">{course.code}</td>
              <td className="course-table-name">
                {course.name}
                {/* Narrow cards fold the semester column in here. */}
                <span className="course-table-sub">{course.semester}</span>
              </td>
              <td className="course-table-semester">{course.semester}</td>
              <td>
                <AcademicStatusBadge status={course.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function DegreeRoadmapPanel({
  context,
}: {
  context: StudentContext | null
}) {
  const count = (status: AcademicStatus) =>
    SAMPLE_ROADMAP.filter((course) => course.status === status).length
  const total = SAMPLE_ROADMAP.length
  const completed = count("completed")
  const inProgress = count("in-progress")
  const planned = count("planned")

  return (
    <article className="degree-card" aria-labelledby="degree-card-title">
      <header className="degree-card-head">
        <h3 id="degree-card-title" className="degree-card-title">
          {SAMPLE_PROGRAM}
        </h3>
        <span className="sample-pill">Sample data</span>
      </header>
      <SampleNotice>
        These rows illustrate the roadmap and aren’t your academic record.{" "}
        {recordNote(context)}
      </SampleNotice>
      <CourseProgressTable courses={SAMPLE_ROADMAP} />
      <footer className="degree-card-foot">
        <div className="roadmap-progress" aria-hidden="true">
          <span
            className="roadmap-progress-done"
            style={{ width: `${(completed / total) * 100}%` }}
          />
          <span
            className="roadmap-progress-active"
            style={{ width: `${(inProgress / total) * 100}%` }}
          />
        </div>
        <p className="roadmap-summary">
          <strong>
            {completed} of {total} courses completed
          </strong>
          <span className="roadmap-summary-rest">
            {" "}
            · {inProgress} in progress · {planned} planned
          </span>
        </p>
      </footer>
    </article>
  )
}

function CourseFacultyPanel({ onAsk }: { onAsk: (question: string) => void }) {
  return (
    <section className="ws-empty" aria-labelledby="ws-empty-title">
      <span className="ws-empty-icon" aria-hidden="true">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="11" cy="11" r="7" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      </span>
      <h3 id="ws-empty-title" className="ws-empty-title">
        Course and faculty data isn’t connected yet
      </h3>
      <p className="ws-empty-text">
        HAWKwarts can’t show real sections, professors, or availability here
        until the course catalog and faculty directory are connected.
      </p>
      <p className="ws-empty-label">Start a question in the advisor chat</p>
      <SuggestedQuestionChips
        className="ws-empty-chips"
        questions={COURSE_QUESTIONS}
        onPick={onAsk}
        label="Course and faculty questions"
      />
    </section>
  )
}

interface AcademicContextPanelProps {
  view: Goal
  onViewChange: (view: Goal) => void
  context: StudentContext | null
  /** The existing interactive Schedule Builder, rendered unchanged. */
  schedule: ReactNode
  onAsk: (question: string) => void
}

export function AcademicContextPanel({
  view,
  onViewChange,
  context,
  schedule,
  onAsk,
}: AcademicContextPanelProps) {
  const copy = VIEWS.find((option) => option.id === view) ?? VIEWS[0]

  return (
    <>
      <div className="ws-intro">
        <p className="ws-eyebrow">{copy.eyebrow}</p>
        <h2 className="ws-heading">{copy.heading}</h2>
        <p className="ws-description">{copy.description}</p>
      </div>

      <div
        className="ws-segmented ws-view-switch"
        role="group"
        aria-label="Academic view"
      >
        {VIEWS.map((option) => (
          <button
            key={option.id}
            type="button"
            aria-pressed={view === option.id}
            onClick={() => onViewChange(option.id)}
          >
            {option.tab}
            {option.id === "courses" && (
              <span className="ws-tab-extra"> & Faculty</span>
            )}
          </button>
        ))}
      </div>

      <div className="ws-academic-body">
        {view === "roadmap" && <DegreeRoadmapPanel context={context} />}
        {view === "schedule" && (
          <>
            <SampleNotice>
              Sample plan for illustration — it isn’t built from your records
              yet.
            </SampleNotice>
            {schedule}
          </>
        )}
        {view === "courses" && <CourseFacultyPanel onAsk={onAsk} />}
      </div>
    </>
  )
}
