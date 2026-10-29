export type Goal = "courses" | "schedule" | "roadmap"
export type YearId = "y1" | "y2" | "y3" | "y4" | "y5plus" | "grad" | "other"

export const MAJOR_UNDECIDED = "__undecided"
export const MAJOR_OTHER = "__other"

export interface GoalOption {
  id: Goal
  title: string
  description: string
  intro: string
  openingQuestion: string
}

export const GOALS: readonly GoalOption[] = [
  {
    id: "courses",
    title: "Course & Faculty Info",
    description: "Explore courses, prerequisites, and professors.",
    intro: "Let’s dig into courses and faculty.",
    openingQuestion: "Which course or professor would you like to know about?",
  },
  {
    id: "schedule",
    title: "Schedule Generation",
    description: "Build a semester schedule around your needs.",
    intro: "Let’s build a semester schedule around your needs.",
    openingQuestion:
      "Which semester are you planning for, and are there any times you want to keep free?",
  },
  {
    id: "roadmap",
    title: "Graduation Roadmap",
    description: "Plan your remaining courses toward graduation.",
    intro: "Let’s map out your remaining courses toward graduation.",
    openingQuestion: "What is your target graduation term?",
  },
]

export function goalOption(id: Goal): GoalOption {
  return GOALS.find((goal) => goal.id === id)!
}

export function isPlanningGoal(goal: Goal | null): boolean {
  return goal === "schedule" || goal === "roadmap"
}

interface YearOption {
  id: YearId
  label: string
}

export const YEAR_OPTIONS: readonly YearOption[] = [
  { id: "y1", label: "1st year" },
  { id: "y2", label: "2nd year" },
  { id: "y3", label: "3rd year" },
  { id: "y4", label: "4th year" },
  { id: "y5plus", label: "5th year or above" },
  { id: "grad", label: "Graduate student" },
  { id: "other", label: "Other" },
]

// ── Transcript ──────────────────────────────────────────────────
// Consent, file selection, upload completion, and analysis are tracked separately.

export type TranscriptChoice = "upload" | "none"
export type UploadStatus = "idle" | "uploading" | "uploaded" | "failed"
/** No transcript-processing service is connected, so analysis never runs. */
export type AnalysisStatus = "not-connected"

export interface TranscriptAnswer {
  choice: TranscriptChoice | null
  consent: boolean
  file: File | null
  uploadStatus: UploadStatus
  uploadProgress: number
  message: string | null
  analysisStatus: AnalysisStatus
}

export interface OnboardingAnswers {
  goal: Goal | null
  major: string | null
  majorOther: string
  year: YearId | null
  yearOther: string
  transcript: TranscriptAnswer
}

export const EMPTY_TRANSCRIPT: TranscriptAnswer = {
  choice: null,
  consent: false,
  file: null,
  uploadStatus: "idle",
  uploadProgress: 0,
  message: null,
  analysisStatus: "not-connected",
}

export const EMPTY_ANSWERS: OnboardingAnswers = {
  goal: null,
  major: null,
  majorOther: "",
  year: null,
  yearOther: "",
  transcript: EMPTY_TRANSCRIPT,
}

// ── Chat context ────────────────────────────────────────────────

export interface StudentContext {
  goal: Goal
  personalized: boolean
  /** Program name or the student's own wording; null when skipped or undecided. */
  major: string | null
  majorUndecided: boolean
  year: YearId | null
  yearLabel: string | null
  transcript: {
    choice: TranscriptChoice
    consent: boolean
    fileName: string | null
    uploadStatus: UploadStatus
    analysisStatus: AnalysisStatus
  }
}

export function buildStudentContext(
  answers: OnboardingAnswers,
  personalized: boolean,
): StudentContext | null {
  if (!answers.goal) return null

  let major: string | null = null
  let majorUndecided = false
  if (personalized && answers.major) {
    if (answers.major === MAJOR_UNDECIDED) majorUndecided = true
    else if (answers.major === MAJOR_OTHER)
      major = answers.majorOther.trim() || null
    else major = answers.major
  }

  let year: YearId | null = null
  let yearLabel: string | null = null
  const yearOther = answers.yearOther.trim()
  if (personalized && answers.year && (answers.year !== "other" || yearOther)) {
    year = answers.year
    yearLabel =
      answers.year === "other"
        ? yearOther
        : YEAR_OPTIONS.find((option) => option.id === answers.year)!.label
  }

  const t = answers.transcript
  const uploaded =
    personalized &&
    t.choice === "upload" &&
    t.consent &&
    t.file !== null &&
    t.uploadStatus === "uploaded"

  return {
    goal: answers.goal,
    personalized,
    major,
    majorUndecided,
    year,
    yearLabel,
    transcript: uploaded
      ? {
          choice: "upload",
          consent: true,
          fileName: t.file!.name,
          uploadStatus: "uploaded",
          analysisStatus: t.analysisStatus,
        }
      : {
          choice: "none",
          consent: false,
          fileName: null,
          uploadStatus: "idle",
          analysisStatus: t.analysisStatus,
        },
  }
}

export function sameContext(
  a: StudentContext | null,
  b: StudentContext | null,
): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

export function contextSummary(context: StudentContext): string[] {
  const parts = [goalOption(context.goal).title]
  if (context.major) parts.push(context.major)
  else if (context.majorUndecided) parts.push("Undecided major")
  if (context.yearLabel) parts.push(context.yearLabel)
  parts.push(
    context.transcript.uploadStatus === "uploaded"
      ? "Transcript uploaded, not analyzed"
      : "No transcript",
  )
  return parts
}

const YEAR_ADJECTIVE: Partial<Record<YearId, string>> = {
  y1: "first-year",
  y2: "second-year",
  y3: "third-year",
  y4: "fourth-year",
}

function article(word: string): string {
  return /^[aeiou]/i.test(word) ? "an" : "a"
}

function describeStudent({
  major,
  majorUndecided,
  year,
  yearLabel,
}: StudentContext): string | null {
  const adjective = year ? YEAR_ADJECTIVE[year] : undefined
  if (major) {
    if (adjective)
      return `you’re ${article(adjective)} ${adjective} ${major} student`
    if (year === "y5plus")
      return `you’re ${article(major)} ${major} student in your fifth year or beyond`
    if (year === "grad")
      return `you’re ${article(major)} ${major} graduate student`
    if (year === "other" && yearLabel)
      return `you’re studying ${major} (${yearLabel})`
    return `you’re studying ${major}`
  }
  const exploring = majorUndecided ? " and still exploring majors" : ""
  if (adjective)
    return `you’re ${article(adjective)} ${adjective} student${exploring}`
  if (year === "y5plus")
    return `you’re in your fifth year or beyond${exploring}`
  if (year === "grad") return `you’re a graduate student${exploring}`
  if (year === "other" && yearLabel)
    return `you described where you are as “${yearLabel}”${exploring}`
  if (majorUndecided) return "you’re still exploring majors"
  return null
}

export type OpeningKind = "new" | "returning" | "updated"

export interface OpeningMessage {
  text: string
  note?: string
}

/** Goal-specific first message. Never claims transcript contents were read. */
export function buildOpeningMessage(
  context: StudentContext,
  kind: OpeningKind,
): OpeningMessage {
  const goal = goalOption(context.goal)
  const parts: string[] = []

  if (kind === "returning") parts.push("Welcome back!")
  else if (kind === "updated")
    parts.push("Got it — I’ve updated your preferences.")
  else if (context.personalized)
    parts.push("Thanks for telling me a little about yourself.")

  const student = describeStudent(context)
  if (student) parts.push(`I’ll keep in mind that ${student}.`)

  parts.push(goal.intro)

  const hasTranscript = context.transcript.uploadStatus === "uploaded"
  if (isPlanningGoal(context.goal) && !hasTranscript) {
    parts.push(
      "As we go, I’ll ask which courses you’ve already completed when it matters.",
    )
  }
  parts.push(goal.openingQuestion)

  const note = hasTranscript
    ? `Your transcript (${context.transcript.fileName}) is uploaded for this session, but transcript analysis isn’t connected yet, so I haven’t read its contents. I’ll ask about completed courses when they matter.`
    : undefined

  return { text: parts.join(" "), note }
}

// ── Returning students ──────────────────────────────────────────
// Profile answers persist in this browser. Transcript files are kept in memory
// for the current visit only and are never written to storage.

const STORAGE_KEY = "hawkwarts.onboarding.v1"

export interface StoredProfile {
  version: 1
  goal: Goal
  personalized: boolean
  major: string | null
  majorOther: string
  year: YearId | null
  yearOther: string
  completedAt: string
}

export function loadStoredProfile(): StoredProfile | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    if (data?.version !== 1 || !GOALS.some((goal) => goal.id === data.goal))
      return null
    return {
      version: 1,
      goal: data.goal,
      personalized: data.personalized !== false,
      major: typeof data.major === "string" ? data.major : null,
      majorOther: typeof data.majorOther === "string" ? data.majorOther : "",
      year: YEAR_OPTIONS.some((option) => option.id === data.year)
        ? data.year
        : null,
      yearOther: typeof data.yearOther === "string" ? data.yearOther : "",
      completedAt: typeof data.completedAt === "string" ? data.completedAt : "",
    }
  } catch {
    return null
  }
}

export function saveStoredProfile(
  answers: OnboardingAnswers,
  personalized: boolean,
): StoredProfile | null {
  if (!answers.goal) return null
  const profile: StoredProfile = {
    version: 1,
    goal: answers.goal,
    personalized,
    major: answers.major,
    majorOther: answers.majorOther,
    year: answers.year,
    yearOther: answers.yearOther,
    completedAt: new Date().toISOString(),
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(profile))
  } catch {
    // Storage can be unavailable (private mode); the session still works.
  }
  return profile
}

export function answersFromStored(profile: StoredProfile): OnboardingAnswers {
  return {
    goal: profile.goal,
    major: profile.major,
    majorOther: profile.majorOther,
    year: profile.year,
    yearOther: profile.yearOther,
    transcript: EMPTY_TRANSCRIPT,
  }
}
