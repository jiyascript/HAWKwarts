import {
  useState,
  useRef,
  CSSProperties,
  useEffect,
  useLayoutEffect,
} from "react"
import Onboarding from "./onboarding/Onboarding"
import {
  EMPTY_ANSWERS,
  answersFromStored,
  buildOpeningMessage,
  buildStudentContext,
  contextSummary,
  loadStoredProfile,
  sameContext,
  saveStoredProfile,
  type Goal,
  type OnboardingAnswers,
  type OpeningKind,
  type StudentContext,
} from "./onboarding/profile"
import { AcademicContextPanel } from "./workspace/AcademicContextPanel"
import { SuggestedQuestionChips } from "./workspace/SuggestedQuestionChips"
import { AdvisorBird, preloadPerchAssets } from "./mascot/AdvisorBird"
import {
  afterNextPaint,
  freshGif,
  loadGifBlob,
  sleep,
} from "./mascot/gifPlayback"

const MASCOT_SRCS = {
  hat: "/assets/hat-bf0c14.png",
  transform: "/assets/hat-to-bird-fast.gif",
  reverse: "/assets/bird-to-hat-fast.gif",
  flight: "/assets/bird-flight.gif",
} as const

/** Both transformation GIFs run 12 frames in ~1040ms and do not loop. */
const TRANSFORM_MS = 1040
const FLY_EASE = "cubic-bezier(0.4,0,0.2,1)"

type Screen = "landing" | "onboarding" | "chat"
/** Screens that host the static hat. */
type HatHost = "landing" | "onboarding"
/** On narrow and short screens the workspace shows one pane at a time. */
type WorkspacePane = "academic" | "advisor"

interface Flyer {
  src: string
  style: CSSProperties
}

// Message types
interface CourseCard {
  code: string
  name: string
  credits: number
  description: string
  tags: string[]
  prereqs: string
}
interface Message {
  from: "hawkwarts" | "student"
  text: string
  /** Secondary, smaller line under the message (e.g. transcript status). */
  note?: string
  cards?: CourseCard[]
}

// Plan types
type CourseStatus = "completed" | "planned"
interface PlanCourse {
  code: string
  name: string
  credits: number
  status: CourseStatus
  suggested?: boolean
}
interface PlanSemester {
  id: string
  label: string
  sublabel: string
  courses: PlanCourse[]
  upcoming?: boolean
}
interface ArrowDatum {
  x1: number
  y1: number
  x2: number
  y2: number
  type: "prereq" | "coreq"
}

const SUGGESTED_PROMPTS = [
  "How do I register for courses?",
  "Find open sections for Math 100",
  "Tell me about Dr. Jacek",
  "What are the add/drop deadlines?",
]

const PLANNER_MESSAGES: Message[] = [
  {
    from: "student",
    text: "I only have two semesters left. Can you help me finish my AI requirements?",
  },
  {
    from: "hawkwarts",
    text: "Absolutely. I opened a sample two-semester plan in the Schedule Builder so you can see how the remaining AI requirements and their prerequisites fit together. It isn’t built from your records yet, so tell me which courses you’ve already completed and we can refine it.",
  },
]

// Columns arranged so the primary AI chain (col 2) runs straight down:
// CS 115 → CS 116 → CS 331 → CS 480 → CS 584 → CS 583
const PLAN_SEMESTERS: PlanSemester[] = [
  {
    id: "s1",
    label: "Fall 2022",
    sublabel: "Completed",
    courses: [
      {
        code: "CS 100",
        name: "Intro to the Profession",
        credits: 1,
        status: "completed",
      },
      { code: "MATH 151", name: "Calculus I", credits: 5, status: "completed" },
      {
        code: "CS 115",
        name: "Object-Oriented Programming I",
        credits: 3,
        status: "completed",
      },
    ],
  },
  {
    id: "s2",
    label: "Spring 2023",
    sublabel: "Completed",
    courses: [
      {
        code: "CS 330",
        name: "Discrete Structures",
        credits: 3,
        status: "completed",
      },
      {
        code: "MATH 152",
        name: "Calculus II",
        credits: 4,
        status: "completed",
      },
      {
        code: "CS 116",
        name: "Object-Oriented Programming II",
        credits: 3,
        status: "completed",
      },
    ],
  },
  {
    id: "s3",
    label: "Fall 2023",
    sublabel: "Completed",
    courses: [
      {
        code: "CS 350",
        name: "Computer Organization",
        credits: 3,
        status: "completed",
      },
      {
        code: "MATH 474",
        name: "Probability & Statistics",
        credits: 3,
        status: "completed",
      },
      {
        code: "CS 331",
        name: "Data Structures & Algorithms",
        credits: 3,
        status: "completed",
      },
    ],
  },
  {
    id: "s4",
    label: "Spring 2024",
    sublabel: "Completed",
    courses: [
      {
        code: "CS 430",
        name: "Introduction to Algorithms",
        credits: 3,
        status: "completed",
      },
      {
        code: "CS 440",
        name: "Programming Languages",
        credits: 3,
        status: "completed",
      },
      {
        code: "CS 480",
        name: "Artificial Intelligence",
        credits: 3,
        status: "completed",
      },
    ],
  },
  {
    id: "s5",
    label: "Fall 2024",
    sublabel: "Completed",
    courses: [
      {
        code: "CS 481",
        name: "AI Language Understanding",
        credits: 3,
        status: "completed",
      },
      { code: "CS 422", name: "Data Mining", credits: 3, status: "completed" },
      {
        code: "CS 425",
        name: "Database Organization",
        credits: 3,
        status: "completed",
      },
    ],
  },
  {
    id: "s6",
    label: "Spring 2025",
    sublabel: "Completed",
    courses: [
      {
        code: "CS 485",
        name: "Computers & Society",
        credits: 3,
        status: "completed",
      },
      { code: "FREE", name: "Free Elective", credits: 3, status: "completed" },
      {
        code: "CS 584",
        name: "Machine Learning",
        credits: 3,
        status: "completed",
      },
    ],
  },
  {
    id: "s7",
    label: "Fall 2026",
    sublabel: "Planned",
    upcoming: true,
    courses: [
      {
        code: "TECH-EL",
        name: "Technical Elective",
        credits: 3,
        status: "planned",
      },
      {
        code: "CS 577",
        name: "Adv. Deep Learning Topics",
        credits: 3,
        status: "planned",
        suggested: true,
      },
      {
        code: "CS 583",
        name: "Deep Learning",
        credits: 3,
        status: "planned",
        suggested: true,
      },
    ],
  },
  {
    id: "s8",
    label: "Spring 2027",
    sublabel: "Planned",
    upcoming: true,
    courses: [
      {
        code: "IPRO",
        name: "IPRO / Degree Requirement",
        credits: 3,
        status: "planned",
      },
      {
        code: "TECH-EL-2",
        name: "Technical Elective",
        credits: 3,
        status: "planned",
      },
      { code: "AI-EL", name: "AI Elective", credits: 3, status: "planned" },
    ],
  },
]

// Prerequisite connections — col positions designed to minimise crossings.
// Primary AI chain (col 2) is all-straight: CS115→CS116→CS331→CS480→CS584→CS583→AI-EL
const PLAN_CONNECTIONS: [string, string, "prereq" | "coreq"][] = [
  ["CS 115", "CS 116", "prereq"],
  ["MATH 151", "MATH 152", "prereq"],
  ["CS 116", "CS 331", "prereq"],
  ["CS 330", "CS 331", "prereq"],
  ["MATH 152", "MATH 474", "prereq"],
  ["CS 331", "CS 430", "prereq"],
  ["CS 331", "CS 480", "prereq"],
  ["CS 480", "CS 481", "prereq"],
  ["CS 480", "CS 584", "prereq"],
  ["CS 584", "CS 583", "prereq"],
  ["CS 584", "CS 577", "prereq"],
  ["CS 583", "AI-EL", "prereq"],
]

function boxStyle(rect: DOMRect, extra?: CSSProperties): CSSProperties {
  return {
    left: `${rect.left}px`,
    top: `${rect.top}px`,
    width: `${rect.width}px`,
    height: `${rect.height}px`,
    ...extra,
  }
}

/** Undefined when the element is missing or not rendered (e.g. inside a hidden mobile pane). */
function visibleRect(el: Element | null | undefined): DOMRect | undefined {
  const rect = el?.getBoundingClientRect()
  return rect && rect.width > 0 && rect.height > 0 ? rect : undefined
}

function moveTransition(seconds: number): string {
  return ["left", "top", "width", "height"]
    .map((prop) => `${prop} ${seconds}s ${FLY_EASE}`)
    .join(", ")
}

function openingMessage(context: StudentContext, kind: OpeningKind): Message {
  const { text, note } = buildOpeningMessage(context, kind)
  return { from: "hawkwarts", text, note }
}

function Disclaimer() {
  return (
    <div className="disclaimer">
      <div className="disclaimer-inner">
        <svg
          className="disclaimer-icon"
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <p className="disclaimer-text">
          <strong>Always verify important information.</strong> AI can make
          mistakes or produce inaccurate information. We recommend confirming
          final decisions about courses, registration, degree requirements, and
          other academic matters with your <strong>academic advisor</strong> or
          the appropriate <strong>university office</strong>.
        </p>
      </div>
    </div>
  )
}

// ── Schedule Builder ────────────────────────────────────────────

function ScheduleBuilder() {
  const blockRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const contentRef = useRef<HTMLDivElement>(null)
  const [arrows, setArrows] = useState<ArrowDatum[]>([])

  const reg = (code: string) => (el: HTMLDivElement | null) => {
    if (el) blockRefs.current.set(code, el)
    else blockRefs.current.delete(code)
  }

  useLayoutEffect(() => {
    const content = contentRef.current
    if (!content) return
    const measure = () => {
      const base = content.getBoundingClientRect()
      const computed: ArrowDatum[] = []
      for (const [from, to, type] of PLAN_CONNECTIONS) {
        const a = blockRefs.current.get(from)
        const b = blockRefs.current.get(to)
        if (!a || !b) continue
        const ar = a.getBoundingClientRect()
        const br = b.getBoundingClientRect()
        computed.push({
          x1: ar.left - base.left + ar.width / 2,
          y1: ar.bottom - base.top,
          x2: br.left - base.left + br.width / 2,
          y2: br.top - base.top,
          type,
        })
      }
      setArrows(computed)
    }
    measure()
    // Arrows use pixel coordinates, so re-measure when a resize or rotation reflows the timeline.
    const observer = new ResizeObserver(measure)
    observer.observe(content)
    return () => observer.disconnect()
  }, [])

  function pathD(a: ArrowDatum): string {
    if (Math.abs(a.x2 - a.x1) < 4) {
      return `M ${a.x1} ${a.y1} L ${a.x2} ${a.y2}`
    }
    const cy = (a.y1 + a.y2) / 2
    return `M ${a.x1} ${a.y1} C ${a.x1} ${cy} ${a.x2} ${cy} ${a.x2} ${a.y2}`
  }

  const completedSems = PLAN_SEMESTERS.filter((s) => !s.upcoming)
  const plannedSems = PLAN_SEMESTERS.filter((s) => s.upcoming)

  return (
    <div className="builder">
      <div className="builder-header">
        <div className="builder-head-left">
          <h2 className="builder-title">Schedule Builder</h2>
          <p className="builder-subtitle">
            Build and visualize your academic plan.
          </p>
        </div>
        <div className="builder-head-right">
          <span className="builder-meta">CS &mdash; AI Track</span>
          <span className="builder-meta-sep">·</span>
          <span className="builder-meta builder-meta-rem">
            2 semesters remaining
          </span>
        </div>
      </div>

      <div className="builder-scroll">
        <div className="builder-content" ref={contentRef}>
          {/* SVG prerequisite arrow overlay */}
          <svg className="builder-svg" aria-hidden="true">
            <defs>
              <marker
                id="mh-pre"
                markerWidth="7"
                markerHeight="7"
                refX="6"
                refY="3.5"
                orient="auto"
                markerUnits="userSpaceOnUse"
              >
                <path
                  d="M 1,1 L 6,3.5 L 1,6"
                  fill="none"
                  stroke="#c2b5ab"
                  strokeWidth="1.1"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              </marker>
              <marker
                id="mh-co"
                markerWidth="7"
                markerHeight="7"
                refX="6"
                refY="3.5"
                orient="auto"
                markerUnits="userSpaceOnUse"
              >
                <path
                  d="M 1,1 L 6,3.5 L 1,6"
                  fill="none"
                  stroke="#c2b5ab"
                  strokeWidth="1.1"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              </marker>
            </defs>
            {arrows.map((a, i) => (
              <path
                key={i}
                d={pathD(a)}
                fill="none"
                stroke="#ccc2b8"
                strokeWidth="1.25"
                strokeDasharray={a.type === "coreq" ? "4.5 2.5" : undefined}
                markerEnd={`url(#mh-${a.type === "prereq" ? "pre" : "co"})`}
              />
            ))}
          </svg>

          {/* Previous coursework */}
          <div className="plan-section-divider">
            <span className="plan-section-label">Previous Coursework</span>
          </div>

          {completedSems.map((sem) => (
            <div key={sem.id} className="sem-row">
              <div className="sem-label-col">
                <span className="sem-name">{sem.label}</span>
                <span className="sem-badge sem-badge-done">Completed</span>
              </div>
              <div className="sem-track">
                {sem.courses.map((c) => (
                  <div key={c.code} ref={reg(c.code)} className="cb cb-done">
                    <div className="cb-head">
                      <span className="cb-code">{c.code}</span>
                      <span className="cb-check" aria-label="Completed">
                        ✓
                      </span>
                    </div>
                    <span className="cb-name">{c.name}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}

          {/* Upcoming plan */}
          <div className="plan-section-divider plan-section-divider-upcoming">
            <span className="plan-section-label">
              Remaining &mdash; 2 Semesters
            </span>
          </div>

          {plannedSems.map((sem) => (
            <div key={sem.id} className="sem-row sem-row-upcoming">
              <div className="sem-label-col">
                <span className="sem-name sem-name-upcoming">{sem.label}</span>
                <span className="sem-badge sem-badge-plan">Planned</span>
              </div>
              <div className="sem-track">
                {sem.courses.map((c) => (
                  <div
                    key={c.code}
                    ref={reg(c.code)}
                    className={`cb cb-plan${
                      c.suggested ? " cb-suggested" : ""
                    }`}
                  >
                    <div className="cb-head">
                      <span className="cb-code cb-code-plan">{c.code}</span>
                      {c.suggested ? (
                        <span
                          className="cb-hw-badge"
                          title="Recommended by HAWKwarts"
                        >
                          ★
                        </span>
                      ) : (
                        <span className="cb-plan-dot" />
                      )}
                    </div>
                    <span className="cb-name cb-name-plan">{c.name}</span>
                    <span className="cb-credits">{c.credits} cr</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="builder-legend">
        <div className="legend-item">
          <svg width="34" height="10" viewBox="0 0 34 10" aria-hidden="true">
            <line
              x1="1"
              y1="5"
              x2="27"
              y2="5"
              stroke="#76777B"
              strokeWidth="1.3"
            />
            <path
              d="M 24,2.5 L 30,5 L 24,7.5"
              stroke="#76777B"
              strokeWidth="1.3"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span>Prerequisite</span>
        </div>
        <div className="legend-item">
          <svg width="34" height="10" viewBox="0 0 34 10" aria-hidden="true">
            <line
              x1="1"
              y1="5"
              x2="27"
              y2="5"
              stroke="#76777B"
              strokeWidth="1.3"
              strokeDasharray="4 2.5"
            />
            <path
              d="M 24,2.5 L 30,5 L 24,7.5"
              stroke="#76777B"
              strokeWidth="1.3"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span>Corequisite</span>
        </div>
        <div className="legend-sep" />
        <div className="legend-item">
          <span className="legend-chip legend-chip-done">✓</span>
          <span>Completed</span>
        </div>
        <div className="legend-item">
          <span className="legend-chip legend-chip-plan">—</span>
          <span>Planned</span>
        </div>
        <div className="legend-item">
          <span className="legend-chip legend-chip-hw">★</span>
          <span>HAWKwarts suggestion</span>
        </div>
      </div>
    </div>
  )
}

// ── App ─────────────────────────────────────────────────────────

const PLANNING_RE = /plan|semester|schedule|degree|pathway|curriculum|sequence/i

export default function App() {
  const [storedProfile] = useState(loadStoredProfile)

  // `screen` is where the app is (or is heading); `shown` is the page currently faded in.
  const [screen, setScreen] = useState<Screen>("landing")
  const [shown, setShown] = useState<Screen>("landing")
  const [transitioning, setTransitioning] = useState(false)
  // Synchronous guard: rejects repeat clicks before React re-renders or GIF loading finishes.
  const transitionLock = useRef(false)

  // Whether the scripted planner conversation has been added (once per visit to the workspace).
  const [plannerOpened, setPlannerOpened] = useState(false)
  const [academicView, setAcademicView] = useState<Goal>(
    () => storedProfile?.goal ?? "roadmap",
  )
  const [workspacePane, setWorkspacePane] = useState<WorkspacePane>("advisor")
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const [answers, setAnswers] = useState<OnboardingAnswers>(() =>
    storedProfile ? answersFromStored(storedProfile) : EMPTY_ANSWERS,
  )
  const [context, setContext] = useState<StudentContext | null>(() =>
    storedProfile
      ? buildStudentContext(
          answersFromStored(storedProfile),
          storedProfile.personalized,
        )
      : null,
  )
  const [onboardingOrigin, setOnboardingOrigin] = useState<"landing" | "chat">(
    "landing",
  )
  const [onboardingRun, setOnboardingRun] = useState(0)
  const answersSnapshot = useRef<OnboardingAnswers | null>(null)

  const [landingHatHidden, setLandingHatHidden] = useState(false)
  const [onboardingHatHidden, setOnboardingHatHidden] = useState(true)
  const [chatHawkHidden, setChatHawkHidden] = useState(false)
  const [flyer, setFlyer] = useState<Flyer | null>(null)

  const flyerRef = useRef<HTMLImageElement>(null)
  const landingHatRef = useRef<HTMLDivElement>(null)
  const onboardingHatRef = useRef<HTMLDivElement>(null)
  const chatHawkRef = useRef<HTMLImageElement>(null)
  const chatInputRef = useRef<HTMLInputElement>(null)

  const isSettled = (s: Screen) => screen === s && !transitioning
  const hasStudentMessage = messages.some(
    (message) => message.from === "student",
  )

  useEffect(() => {
    Object.values(MASCOT_SRCS).forEach((src) => {
      const image = new Image()
      image.src = src
    })
    loadGifBlob(MASCOT_SRCS.transform).catch(() => undefined)
    loadGifBlob(MASCOT_SRCS.reverse).catch(() => undefined)
    preloadPerchAssets(MASCOT_SRCS.flight)
  }, [])

  // Put keyboard focus in the composer once chat settles (skipped on touch so no keyboard pops up).
  useEffect(() => {
    if (
      screen === "chat" &&
      !transitioning &&
      window.matchMedia("(pointer: fine)").matches
    ) {
      chatInputRef.current?.focus({ preventScroll: true })
    }
  }, [screen, transitioning])

  // ── Mascot choreography ──

  function hatElement(host: HatHost) {
    return (host === "landing" ? landingHatRef : onboardingHatRef).current
  }

  function setHatHidden(host: HatHost, hidden: boolean) {
    ;(host === "landing" ? setLandingHatHidden : setOnboardingHatHidden)(hidden)
  }

  function beginTransition(): boolean {
    if (transitionLock.current) return false
    transitionLock.current = true
    setTransitioning(true)
    return true
  }

  async function runTransition(target: Screen, sequence: () => Promise<void>) {
    try {
      await sequence()
    } catch (error) {
      console.error(error)
      // Never strand the student mid-animation: snap to the destination.
      setFlyer(null)
      setScreen(target)
      setShown(target)
      setLandingHatHidden(false)
      setOnboardingHatHidden(false)
      setChatHawkHidden(false)
    } finally {
      transitionLock.current = false
      setTransitioning(false)
    }
  }

  /** The static hat glides between the landing and onboarding positions while the pages crossfade. */
  async function glideHat(from: HatHost, to: HatHost) {
    const start = hatElement(from)?.getBoundingClientRect()
    setHatHidden(to, true)
    setScreen(to)
    if (start) setFlyer({ src: MASCOT_SRCS.hat, style: boxStyle(start) })
    await afterNextPaint()
    setHatHidden(from, true)
    setShown(to)
    const end = hatElement(to)?.getBoundingClientRect()
    if (start && end) {
      setFlyer({
        src: MASCOT_SRCS.hat,
        style: boxStyle(end, { transition: moveTransition(0.7) }),
      })
      await sleep(720)
    } else {
      await sleep(450)
    }
    setHatHidden(to, false)
    setFlyer(null)
    setHatHidden(from, false)
  }

  /** Hat → bird in place, then the bird flies to its perch above the chat panel. */
  async function transformToChat(from: HatHost) {
    setChatHawkHidden(true)
    const gif = await freshGif(MASCOT_SRCS.transform)
    const start = hatElement(from)?.getBoundingClientRect()
    setScreen("chat")
    if (!start) {
      gif.release()
      setShown("chat")
      await sleep(450)
      setChatHawkHidden(false)
      return
    }

    setFlyer({ src: gif.url, style: boxStyle(start) })
    await afterNextPaint()
    await flyerRef.current?.decode().catch(() => undefined)
    // The fresh GIF starts at its first frame (the hat) the moment it is painted.
    const transformationDone = sleep(TRANSFORM_MS)

    // Keep the static hat in place until the first GIF frame has painted over it.
    await afterNextPaint()
    setHatHidden(from, true)

    // Hold the current page until the transformation reaches its final frame.
    await transformationDone

    // Begin the page crossfade as the completed transformation starts flying.
    setShown("chat")
    setFlyer({ src: MASCOT_SRCS.flight, style: boxStyle(start) })
    await sleep(30)
    gif.release()
    const end = visibleRect(chatHawkRef.current)
    if (end) {
      setFlyer({
        src: MASCOT_SRCS.flight,
        style: boxStyle(end, { transition: moveTransition(0.72) }),
      })
      await sleep(750)
      setFlyer({
        src: MASCOT_SRCS.flight,
        style: boxStyle(end, {
          top: `${end.top + 9}px`,
          transition: "top 0.11s ease-in",
        }),
      })
      await sleep(110)
      setFlyer({
        src: MASCOT_SRCS.flight,
        style: boxStyle(end, { transition: "top 0.14s ease-out" }),
      })
      await sleep(140)
    }
    setChatHawkHidden(false)
    setFlyer(null)
    setHatHidden(from, false)
  }

  /** The bird flies from the chat panel to a hat position, then transforms back into the hat. */
  async function birdToHat(to: HatHost) {
    const start = visibleRect(chatHawkRef.current)
    const reverse = freshGif(MASCOT_SRCS.reverse)
    setHatHidden(to, true)
    setScreen(to)
    if (start) setFlyer({ src: MASCOT_SRCS.flight, style: boxStyle(start) })
    setChatHawkHidden(true)
    await sleep(30)
    const end = hatElement(to)?.getBoundingClientRect()
    if (!start || !end) {
      setShown(to)
      await sleep(450)
      ;(await reverse).release()
      setHatHidden(to, false)
      setFlyer(null)
      return
    }

    setFlyer({
      src: MASCOT_SRCS.flight,
      style: boxStyle(end, { transition: moveTransition(0.65) }),
    })
    await sleep(200)
    setShown(to)
    await sleep(480)

    // Transform the returned bird back into the hat at its resting position.
    const gif = await reverse
    setFlyer({ src: gif.url, style: boxStyle(end) })
    await afterNextPaint()
    await flyerRef.current?.decode().catch(() => undefined)
    await sleep(TRANSFORM_MS)

    setHatHidden(to, false)
    setFlyer(null)
    gif.release()
  }

  // ── Flows ──

  function prepareOnboarding(origin: "landing" | "chat") {
    answersSnapshot.current = answers
    setOnboardingOrigin(origin)
    // A fresh run starts at the first question; saved answers stay filled in.
    setOnboardingRun((run) => run + 1)
  }

  function openOnboarding() {
    if (!beginTransition()) return
    prepareOnboarding("landing")
    void runTransition("onboarding", () => glideHat("landing", "onboarding"))
  }

  function editPreferences() {
    if (!beginTransition()) return
    prepareOnboarding("chat")
    void runTransition("onboarding", () => birdToHat("onboarding"))
  }

  function exitOnboarding() {
    if (!beginTransition()) return
    // Students with saved preferences leave without saving: discard unsaved edits.
    if (context && answersSnapshot.current) setAnswers(answersSnapshot.current)
    answersSnapshot.current = null
    if (onboardingOrigin === "chat") {
      setWorkspacePane("advisor")
      void runTransition("chat", () => transformToChat("onboarding"))
    } else {
      void runTransition("landing", () => glideHat("onboarding", "landing"))
    }
  }

  /** The workspace opens on the student's goal, with the advisor pane up so the bird lands in view. */
  function prepareWorkspace(goal: Goal) {
    setAcademicView(goal)
    setWorkspacePane("advisor")
  }

  function finishOnboarding(personalized: boolean) {
    const next = buildStudentContext(answers, personalized)
    if (!next || !beginTransition()) return
    saveStoredProfile(answers, personalized)
    const unchanged = sameContext(context, next)
    // Greet once; afterwards only acknowledge preferences that actually changed.
    const kind: OpeningKind | null =
      messages.length === 0
        ? unchanged
          ? "returning"
          : "new"
        : unchanged
          ? null
          : "updated"
    setContext(next)
    if (kind) setMessages((prev) => [...prev, openingMessage(next, kind)])
    answersSnapshot.current = null
    prepareWorkspace(next.goal)
    void runTransition("chat", () => transformToChat("onboarding"))
  }

  function continueToChat() {
    if (!context || !beginTransition()) return
    if (messages.length === 0)
      setMessages([openingMessage(context, "returning")])
    prepareWorkspace(context.goal)
    void runTransition("chat", () => transformToChat("landing"))
  }

  function goToLanding() {
    if (!beginTransition()) return
    void runTransition("landing", async () => {
      await birdToHat("landing")
      setPlannerOpened(false)
    })
  }

  // ── Chat ──

  function openPlanner() {
    setPlannerOpened(true)
    setAcademicView("schedule")
    setMessages((prev) => [...prev, ...PLANNER_MESSAGES])
  }

  function sendMessage(overrideText?: string) {
    const text = (overrideText ?? input).trim()
    if (!text) return
    setInput("")
    if (PLANNING_RE.test(text) && !plannerOpened) openPlanner()
    else setMessages((prev) => [...prev, { from: "student", text }])
  }

  function pickSuggestion(prompt: string) {
    setInput(prompt)
    // Chips can live in the academic pane; bring the composer into view on narrow screens.
    setWorkspacePane("advisor")
    if (PLANNING_RE.test(prompt) && !plannerOpened) openPlanner()
    if (window.matchMedia("(pointer: fine)").matches) {
      requestAnimationFrame(() =>
        chatInputRef.current?.focus({ preventScroll: true }),
      )
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const screenStyle = (s: Screen): CSSProperties => ({
    opacity: shown === s ? 1 : 0,
    transition: transitioning ? "opacity 0.45s ease" : "none",
    pointerEvents: isSettled(s) ? "auto" : "none",
  })

  return (
    <div className="app-shell">
      {flyer && (
        <img
          ref={flyerRef}
          src={flyer.src}
          alt=""
          aria-hidden="true"
          className="flying-hat"
          style={flyer.style}
        />
      )}

      {/* Landing screen */}
      <div
        className="page-root landing-screen"
        style={screenStyle("landing")}
        inert={!isSettled("landing")}
      >
        <main className="hero">
          <div className="hero-inner">
            <button
              className="logo-btn"
              aria-label="Get started with HAWKwarts"
              onClick={openOnboarding}
              disabled={transitioning}
            >
              <div
                ref={landingHatRef}
                className={`logo-img-stack${
                  landingHatHidden ? " is-resting" : ""
                }`}
                style={{ opacity: landingHatHidden ? 0 : 1 }}
              >
                <img
                  src={MASCOT_SRCS.hat}
                  alt="HAWKwarts wizard hat logo"
                  className="logo-mascot-layer"
                />
              </div>
              <span className="logo-hint">Click to start</span>
            </button>
            <div className="hero-text">
              <h1 className="title">
                <em>Hawkwarts</em>
              </h1>
              <p className="description">
                Your AI guide to campus life — helping with registration,
                courses, professors, and everyday questions. Reliable answers,
                without the run
                <svg
                  className="runaround-svg"
                  viewBox="0 0 92 32"
                  xmlns="http://www.w3.org/2000/svg"
                  role="img"
                  aria-label="around"
                  style={{ overflow: "visible" }}
                >
                  <defs>
                    <path id="runaround-arc" d="M 3,5 Q 46,25 89,5" />
                  </defs>
                  <text
                    fontFamily="Georgia, serif"
                    fontSize="16"
                    fill="#1a1a1a"
                  >
                    <textPath
                      href="#runaround-arc"
                      startOffset="50%"
                      textAnchor="middle"
                    >
                      a r o u n d .
                    </textPath>
                  </text>
                </svg>
              </p>
              {context && (
                <div className="landing-return">
                  <button
                    type="button"
                    className="landing-return-btn"
                    onClick={continueToChat}
                    disabled={transitioning}
                  >
                    Continue to chat <span aria-hidden="true">&rarr;</span>
                  </button>
                  <span className="landing-return-hint">
                    or click the hat to update your answers
                  </span>
                </div>
              )}
            </div>
          </div>
        </main>
        <Disclaimer />
      </div>

      {/* Onboarding screen */}
      <div
        className="page-root onboarding-screen"
        style={screenStyle("onboarding")}
        inert={!isSettled("onboarding")}
      >
        <Onboarding
          key={onboardingRun}
          hatRef={onboardingHatRef}
          hatSrc={MASCOT_SRCS.hat}
          hatHidden={onboardingHatHidden}
          active={isSettled("onboarding")}
          origin={onboardingOrigin}
          answers={answers}
          setAnswers={setAnswers}
          onFinish={finishOnboarding}
          onExit={exitOnboarding}
        />
      </div>

      {/* Chat screen */}
      <div
        className="page-root chat-screen-overlay"
        style={screenStyle("chat")}
        inert={!isSettled("chat")}
      >
        <header className="chat-header">
          <div className="chat-header-row">
            <span className="chat-header-title">Illinois Tech</span>
            {context && (
              <div className="chat-context">
                <p className="chat-context-summary">
                  <span className="ob-sr-only">Your preferences: </span>
                  {contextSummary(context).map((part, i) => (
                    <span key={i} className="chat-context-item">
                      {part}
                    </span>
                  ))}
                </p>
                <button
                  type="button"
                  className="chat-edit-btn"
                  onClick={editPreferences}
                  disabled={transitioning}
                >
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4 11.5-11.5Z" />
                  </svg>
                  Edit preferences
                </button>
              </div>
            )}
          </div>
          <div className="chat-header-divider" />
        </header>

        {/* Narrow and short screens: one pane at a time; both stay mounted so chat state is kept. */}
        <div className="ws-switch">
          <div
            className="ws-segmented"
            role="group"
            aria-label="Workspace view"
          >
            <button
              type="button"
              aria-pressed={workspacePane === "academic"}
              onClick={() => setWorkspacePane("academic")}
            >
              Academic info
            </button>
            <button
              type="button"
              aria-pressed={workspacePane === "advisor"}
              onClick={() => setWorkspacePane("advisor")}
            >
              AI advisor
            </button>
          </div>
        </div>

        <main className="workspace" data-pane={workspacePane}>
          <section
            className="ws-panel ws-academic"
            aria-label="Academic information"
          >
            <AcademicContextPanel
              view={academicView}
              onViewChange={setAcademicView}
              context={context}
              schedule={<ScheduleBuilder />}
              onAsk={pickSuggestion}
            />
          </section>

          <section
            className="ws-panel ws-advisor"
            aria-labelledby="ws-advisor-heading"
          >
            <div className="ws-intro">
              <p className="ws-eyebrow">HAWKwarts AI</p>
              <h2 id="ws-advisor-heading" className="ws-heading">
                Your campus advisor,{" "}
                <span className="ws-heading-accent">always ready.</span>
              </h2>
              <p className="ws-description">
                Ask about registration, courses, professors, degree
                requirements, or any campus questions.
              </p>
            </div>

            <div className="chat-wrapper">
              <AdvisorBird
                imgRef={chatHawkRef}
                flightSrc={MASCOT_SRCS.flight}
                active={isSettled("chat")}
                hidden={chatHawkHidden}
              />
              <div className="chat-container">
                <div className="advisor-header">
                  <p className="advisor-status">
                    Preview · AI replies aren’t connected yet
                  </p>
                </div>
                <div className="chat-messages">
                  {messages.length === 0 ? (
                    <div className="chat-empty">
                      <p className="chat-empty-heading">
                        What can I help you with?
                      </p>
                      <p className="chat-empty-sub">
                        Ask about courses, registration, degree planning, or
                        campus life.
                      </p>
                    </div>
                  ) : (
                    messages.map((msg, i) => (
                      <div key={i} className={`message message-${msg.from}`}>
                        <span className="message-label">
                          {msg.from === "hawkwarts" ? "Hawkwarts" : "You"}
                        </span>
                        <p className="message-text">{msg.text}</p>
                        {msg.note && <p className="message-note">{msg.note}</p>}
                        {msg.cards && (
                          <div className="course-cards">
                            {msg.cards.map((card) => (
                              <div key={card.code} className="course-card">
                                <div className="course-card-top">
                                  <div className="course-card-identity">
                                    <span className="course-code">
                                      {card.code}
                                    </span>
                                    <span className="course-name">
                                      {card.name}
                                    </span>
                                  </div>
                                  <span className="course-credits">
                                    {card.credits} cr.
                                  </span>
                                </div>
                                <p className="course-desc">
                                  {card.description}
                                </p>
                                <div className="course-tags">
                                  {card.tags.map((tag) => (
                                    <span key={tag} className="course-tag">
                                      {tag}
                                    </span>
                                  ))}
                                </div>
                                <div className="course-prereqs">
                                  <span className="course-prereqs-label">
                                    Prereq:
                                  </span>{" "}
                                  {card.prereqs}
                                </div>
                                <div className="course-actions">
                                  <button className="course-btn-secondary">
                                    View details
                                  </button>
                                  <button className="course-btn-primary">
                                    Add to plan
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                  <div ref={messagesEndRef} />
                </div>
                <SuggestedQuestionChips
                  className={`advisor-chips${
                    hasStudentMessage ? " advisor-chips-compact" : ""
                  }`}
                  questions={SUGGESTED_PROMPTS}
                  onPick={pickSuggestion}
                  label="Suggested questions"
                />
                <div className="chat-input-row">
                  <input
                    ref={chatInputRef}
                    className="chat-input"
                    type="text"
                    placeholder="Ask about courses, professors, registration..."
                    aria-label="Message HAWKwarts"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                  />
                  <button
                    className="chat-send-btn"
                    onClick={() => sendMessage()}
                    aria-label="Send message"
                  >
                    <svg
                      width="15"
                      height="15"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <line x1="22" y1="2" x2="11" y2="13" />
                      <polygon points="22 2 15 22 11 13 2 9 22 2" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </section>
        </main>

        <Disclaimer />

        <button className="chat-back-btn" onClick={goToLanding}>
          &#8592; Back
        </button>
      </div>
    </div>
  )
}
