import type { ReactNode } from "react"
import { goalOption, type Goal } from "./profile"
import {
  AcademicStatusBadge,
  type AcademicStatus,
} from "../workspace/AcademicContextPanel"

/**
 * Local, illustrative miniature of the workspace each goal opens. It never
 * depends on a backend, transcript, or fetched data, and every label is generic.
 */

const AVAILABILITY: Record<Goal, string> = {
  courses:
    "Live course and faculty data isn’t connected yet — the advisor can help in the meantime.",
  schedule:
    "The workspace planner opens with a sample plan, not one generated from your records.",
  roadmap: "Personalized degree audits aren’t connected yet.",
}

export default function FeaturePreview({
  goal,
  compact = false,
}: {
  goal: Goal | null
  compact?: boolean
}) {
  if (!goal) {
    return (
      <aside
        className="fp fp-empty"
        aria-label="Feature preview"
        aria-live="polite"
      >
        <span className="fp-eyebrow">Feature preview</span>
        <p className="fp-empty-text">
          Select a goal above to see a preview of where you’ll start.
        </p>
      </aside>
    )
  }

  const title = goalOption(goal).title
  return (
    <aside
      className={`fp${compact ? " is-compact" : ""}`}
      aria-label={`Feature preview: ${title}`}
    >
      <header className="fp-head">
        <span className="fp-eyebrow">Feature preview</span>
        {/* Announces the swap when a different goal is chosen. */}
        <span className="fp-title" aria-live="polite">
          {title}
        </span>
      </header>
      {/* Keyed so a goal change replays the entrance in the same region. */}
      <div key={goal} className="fp-body">
        {goal === "courses" && <CoursePreview />}
        {goal === "schedule" && <SchedulePreview />}
        {goal === "roadmap" && <RoadmapPreview />}
      </div>
      <footer className="fp-foot">
        <p className="fp-label">
          Illustrative example — not your academic record.
        </p>
        <p className="fp-note">{AVAILABILITY[goal]}</p>
      </footer>
    </aside>
  )
}

// ── Course & Faculty Info ───────────────────────────────────────

function CoursePreview() {
  return (
    <div className="fp-courses">
      <div className="fp-search">
        <SearchGlyph />
        <span>Search courses or professors</span>
      </div>
      <div className="fp-course-card">
        <div className="fp-course-top">
          <span className="fp-code">XXX 100</span>
          <span className="fp-chip">Course</span>
        </div>
        <span className="fp-course-name">Example course</span>
        <div className="fp-prereq">
          <span className="fp-prereq-label">Prerequisites</span>
          <span className="fp-pill">Example course B</span>
          <span className="fp-pill">Example course C</span>
        </div>
      </div>
      <div className="fp-faculty">
        <span className="fp-avatar">
          <PersonGlyph />
        </span>
        <span className="fp-faculty-text">
          <span className="fp-faculty-title">Faculty information</span>
          <span className="fp-faculty-meta">
            Instructor · Office hours · Contact
          </span>
        </span>
      </div>
    </div>
  )
}

// ── Schedule Generation ─────────────────────────────────────────

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"] as const
const HOURS = ["9", "11", "1", "3"] as const

interface Block {
  label: string
  day: number
  /** Start and length in hours from 9:00. */
  start: number
  length: number
  tone?: "suggested"
}

const BLOCKS: Block[] = [
  { label: "Course A", day: 0, start: 0, length: 1.25 },
  { label: "Course A", day: 2, start: 0, length: 1.25 },
  { label: "Course B", day: 1, start: 1.75, length: 1.25 },
  { label: "Course B", day: 3, start: 1.75, length: 1.25 },
  { label: "Course C", day: 0, start: 4, length: 1 },
  { label: "Course C", day: 2, start: 4, length: 1 },
  { label: "Course C", day: 4, start: 4, length: 1 },
  { label: "Course D", day: 3, start: 5.75, length: 1.25, tone: "suggested" },
]

const SPAN_HOURS = 8

function SchedulePreview() {
  return (
    <div className="fp-week">
      <span className="fp-week-corner" />
      {DAYS.map((day) => (
        <span key={day} className="fp-week-day">
          {day}
        </span>
      ))}
      <div className="fp-week-hours">
        {HOURS.map((hour) => (
          <span key={hour}>{hour}</span>
        ))}
      </div>
      {DAYS.map((day, index) => (
        <div key={day} className="fp-week-col">
          {BLOCKS.filter((block) => block.day === index).map((block) => (
            <span
              key={`${block.label}-${block.start}`}
              className={`fp-block${
                block.tone === "suggested" ? " is-suggested" : ""
              }`}
              style={{
                top: `${(block.start / SPAN_HOURS) * 100}%`,
                height: `${(block.length / SPAN_HOURS) * 100}%`,
              }}
            >
              {block.label}
            </span>
          ))}
        </div>
      ))}
      <span className="fp-week-caption">
        Example week — not a generated or verified schedule
      </span>
    </div>
  )
}

// ── Graduation Roadmap ──────────────────────────────────────────

interface RoadmapRow {
  code: string
  name: string
  status: AcademicStatus
}

// Placeholder codes are deliberately not real course numbers.
const ROWS: RoadmapRow[] = [
  { code: "XXX 101", name: "Example course A", status: "completed" },
  { code: "XXX 201", name: "Example course B", status: "in-progress" },
  { code: "XXX 301", name: "Example course C", status: "planned" },
]

function RoadmapPreview() {
  return (
    <div className="fp-roadmap">
      <table className="fp-table">
        <thead>
          <tr>
            <th>Code</th>
            <th>Course Name</th>
            <th>Semester</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.name}>
              <td className="fp-code">{row.code}</td>
              <td>{row.name}</td>
              <td className="fp-term">Example term</td>
              <td>
                <AcademicStatusBadge status={row.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <span className="fp-week-caption">Sample statuses for illustration</span>
    </div>
  )
}

// ── Glyphs ──────────────────────────────────────────────────────

function Glyph({ children }: { children: ReactNode }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  )
}

function SearchGlyph() {
  return (
    <Glyph>
      <circle cx="11" cy="11" r="6.25" />
      <path d="m20 20-4.5-4.5" />
    </Glyph>
  )
}

function PersonGlyph() {
  return (
    <Glyph>
      <circle cx="12" cy="8.5" r="3.75" />
      <path d="M4.75 20c.9-3.6 3.9-5.5 7.25-5.5s6.35 1.9 7.25 5.5" />
    </Glyph>
  )
}
