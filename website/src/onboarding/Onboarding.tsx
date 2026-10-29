import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type DragEvent,
  type KeyboardEvent,
  type ReactNode,
  type Ref,
  type SetStateAction,
} from "react"
import {
  GOALS,
  MAJOR_OTHER,
  MAJOR_UNDECIDED,
  YEAR_OPTIONS,
  goalOption,
  type Goal,
  type OnboardingAnswers,
  type TranscriptAnswer,
  type TranscriptChoice,
  type YearId,
} from "./profile"
import { ILLINOIS_TECH_PROGRAMS, matchesProgram } from "./programs"
import {
  TRANSCRIPT_ACCEPT,
  UploadCancelled,
  formatBytes,
  uploadTranscript,
  validateTranscriptFile,
  type TranscriptUpload,
} from "./transcript"
import "./onboarding.css"

type StepId = "goal" | "major" | "year" | "transcript"
type ProgressState = "done" | "skipped" | "current" | "todo"

const STEPS: readonly StepId[] = ["goal", "major", "year", "transcript"]

interface StepCopy {
  title: string
  subtitle: string
}

const STEP_COPY: Record<StepId, StepCopy> = {
  goal: {
    title: "What would you like help with?",
    subtitle: "Choose a starting point. You can change it later.",
  },
  major: {
    title: "What’s your major?",
    subtitle: "This helps us tailor your academic guidance.",
  },
  year: {
    title: "Where are you in your studies?",
    subtitle: "This helps us suggest courses at the right level.",
  },
  transcript: {
    title: "Would you like to upload your transcript?",
    subtitle:
      "Your completed courses can help us personalize your schedule or graduation plan. You can also continue without uploading.",
  },
}

export interface OnboardingProps {
  hatRef: Ref<HTMLDivElement>
  hatSrc: string
  hatHidden: boolean
  /** False while the mascot is transitioning in or out; all controls are locked. */
  active: boolean
  origin: "landing" | "chat"
  answers: OnboardingAnswers
  setAnswers: Dispatch<SetStateAction<OnboardingAnswers>>
  onFinish: (personalized: boolean) => void
  onExit: () => void
}

export default function Onboarding({
  hatRef,
  hatSrc,
  hatHidden,
  active,
  origin,
  answers,
  setAnswers,
  onFinish,
  onExit,
}: OnboardingProps) {
  const [stepIndex, setStepIndex] = useState(0)
  const [direction, setDirection] = useState<"forward" | "back">("forward")
  const headingRef = useRef<HTMLHeadingElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const hatImgRef = useRef<HTMLImageElement>(null)
  const uploadRef = useRef<TranscriptUpload | null>(null)

  const step = STEPS[stepIndex]
  const { goal, transcript } = answers
  const profileOptional = goal === "courses"
  const isLast = stepIndex === STEPS.length - 1

  const answered: Record<StepId, boolean> = {
    goal: goal !== null,
    major:
      answers.major !== null &&
      (answers.major !== MAJOR_OTHER || answers.majorOther.trim() !== ""),
    year:
      answers.year !== null &&
      (answers.year !== "other" || answers.yearOther.trim() !== ""),
    transcript:
      transcript.choice === "none" ||
      (transcript.choice === "upload" &&
        transcript.consent &&
        transcript.uploadStatus === "uploaded"),
  }
  const canContinue = answered[step]
  const canSkipStep = profileOptional && (step === "major" || step === "year")
  const stepOptional = canSkipStep || step === "transcript"
  const hint = canContinue ? null : hintFor(step, answers, profileOptional)
  const progress: ProgressState[] = STEPS.map((id, i) =>
    i === stepIndex
      ? "current"
      : i > stepIndex
        ? "todo"
        : answered[id]
          ? "done"
          : "skipped",
  )

  // Move focus to each new question for keyboard and screen-reader users.
  useEffect(() => {
    if (active) headingRef.current?.focus({ preventScroll: true })
  }, [active, stepIndex])

  // Leaving mid-upload: stop reading and drop the unfinished upload state so a
  // late result can never land in answers that were since saved or reverted.
  useEffect(() => {
    const abandonUpload = () => {
      if (!uploadRef.current) return
      uploadRef.current.cancel()
      uploadRef.current = null
      setAnswers((a) =>
        a.transcript.uploadStatus === "uploading"
          ? {
              ...a,
              transcript: {
                ...a.transcript,
                uploadStatus: "idle",
                uploadProgress: 0,
              },
            }
          : a,
      )
    }
    if (!active) {
      // Settle any nod before the hat hands off to a transition.
      hatImgRef.current
        ?.getAnimations()
        .forEach((animation) => animation.cancel())
      abandonUpload()
    }
    return abandonUpload
  }, [active, setAnswers])

  /** A small acknowledging tilt of the hat whenever the student picks an answer. */
  function nod() {
    const img = hatImgRef.current
    if (
      !img ||
      !active ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    )
      return
    img.getAnimations().forEach((animation) => animation.cancel())
    img.animate(
      [
        { transform: "rotate(0deg) translateY(0)" },
        { transform: "rotate(-6deg) translateY(-4px)", offset: 0.35 },
        { transform: "rotate(3deg) translateY(0)", offset: 0.7 },
        { transform: "rotate(0deg) translateY(0)" },
      ],
      { duration: 600, easing: "ease-in-out" },
    )
  }

  function update(patch: Partial<OnboardingAnswers>) {
    setAnswers((a) => ({ ...a, ...patch }))
  }

  function select(patch: Partial<OnboardingAnswers>) {
    update(patch)
    nod()
  }

  function updateTranscript(patch: Partial<TranscriptAnswer>) {
    setAnswers((a) => ({ ...a, transcript: { ...a.transcript, ...patch } }))
  }

  // ── Transcript ──

  function cancelUpload() {
    uploadRef.current?.cancel()
    uploadRef.current = null
  }

  function chooseTranscript(choice: TranscriptChoice) {
    if (choice === "none" && transcript.uploadStatus === "uploading") {
      cancelUpload()
      updateTranscript({ choice, uploadStatus: "idle", uploadProgress: 0 })
    } else {
      updateTranscript({ choice })
    }
    nod()
  }

  function selectFile(file: File | undefined) {
    if (!file) return
    const error = validateTranscriptFile(file)
    if (error) {
      // Keep any previous valid selection; just explain why this one was refused.
      updateTranscript({ message: error })
      return
    }
    cancelUpload()
    updateTranscript({
      file,
      uploadStatus: "idle",
      uploadProgress: 0,
      message: null,
    })
  }

  function removeFile() {
    cancelUpload()
    updateTranscript({
      file: null,
      uploadStatus: "idle",
      uploadProgress: 0,
      message: null,
    })
  }

  function setConsent(consent: boolean) {
    if (consent) {
      updateTranscript({ consent })
      return
    }
    // Withdrawing consent also withdraws any upload made under it.
    cancelUpload()
    updateTranscript({ consent, uploadStatus: "idle", uploadProgress: 0 })
  }

  async function startUpload() {
    const { file, consent, uploadStatus } = transcript
    if (
      !active ||
      !file ||
      !consent ||
      uploadStatus === "uploading" ||
      uploadStatus === "uploaded"
    )
      return
    cancelUpload()
    const handle: TranscriptUpload = uploadTranscript(file, (progress) => {
      if (uploadRef.current === handle)
        updateTranscript({ uploadProgress: progress })
    })
    uploadRef.current = handle
    updateTranscript({
      uploadStatus: "uploading",
      uploadProgress: 0.04,
      message: null,
    })
    try {
      await handle.promise
      if (uploadRef.current !== handle) return
      updateTranscript({ uploadStatus: "uploaded", uploadProgress: 1 })
    } catch (error) {
      if (uploadRef.current !== handle || error instanceof UploadCancelled)
        return
      updateTranscript({
        uploadStatus: "failed",
        uploadProgress: 0,
        message:
          error instanceof Error
            ? error.message
            : "The upload didn’t finish. Please try again.",
      })
    } finally {
      if (uploadRef.current === handle) uploadRef.current = null
    }
  }

  // ── Navigation ──

  function goTo(index: number, dir: "forward" | "back") {
    setDirection(dir)
    setStepIndex(index)
    scrollRef.current?.scrollTo({ top: 0 })
  }

  function handleBack() {
    if (!active) return
    if (stepIndex === 0) onExit()
    else goTo(stepIndex - 1, "back")
  }

  function handleContinue() {
    if (!active || !canContinue) return
    if (isLast) onFinish(true)
    else goTo(stepIndex + 1, "forward")
  }

  function skipStep() {
    if (!active || !canSkipStep) return
    if (step === "major") update({ major: null, majorOther: "" })
    else update({ year: null, yearOther: "" })
    goTo(stepIndex + 1, "forward")
  }

  function skipPersonalization() {
    if (active && goal === "courses") onFinish(false)
  }

  const copy = STEP_COPY[step]
  const pathTitle = goal ? goalOption(goal).title : null

  return (
    // Swallow stray file drops so the browser doesn't navigate away from the app.
    <div className="ob" onDragOver={preventDefault} onDrop={preventDefault}>
      <div className="ob-top">
        <div
          ref={hatRef}
          className={`ob-hat-stack${hatHidden ? " is-resting" : ""}`}
          style={{ opacity: hatHidden ? 0 : 1 }}
        >
          <img ref={hatImgRef} src={hatSrc} alt="" className="ob-hat-img" />
        </div>

        <div className="ob-progress">
          <ol className="ob-progress-track" aria-hidden="true">
            {progress.map((state, i) => (
              <li key={STEPS[i]} className={`ob-progress-seg is-${state}`} />
            ))}
          </ol>
          <p className="ob-progress-caption">
            <span>
              Step {stepIndex + 1} of {STEPS.length}
            </span>
            {pathTitle && stepIndex > 0 && (
              <>
                <span className="ob-dot" aria-hidden="true" />
                <span className="ob-progress-path">{pathTitle}</span>
              </>
            )}
            {stepOptional && <span className="ob-tag">Optional</span>}
          </p>
        </div>
      </div>

      <div className="ob-scroll" ref={scrollRef}>
        <section
          key={step}
          className={`ob-step${direction === "back" ? " is-back" : ""}`}
          aria-labelledby="ob-step-title"
        >
          <h1
            id="ob-step-title"
            ref={headingRef}
            tabIndex={-1}
            className="ob-title"
          >
            {copy.title}
          </h1>
          <p className="ob-sub">{copy.subtitle}</p>

          <div className="ob-content">
            {step === "goal" && (
              <GoalStep
                value={goal}
                onSelect={(value) => select({ goal: value })}
              />
            )}
            {step === "major" && (
              <MajorStep
                value={answers.major}
                other={answers.majorOther}
                onSelect={(value) => select({ major: value })}
                onOtherChange={(text) => update({ majorOther: text })}
              />
            )}
            {step === "year" && (
              <YearStep
                value={answers.year}
                other={answers.yearOther}
                onSelect={(value) => select({ year: value })}
                onOtherChange={(text) => update({ yearOther: text })}
              />
            )}
            {step === "transcript" && (
              <TranscriptStep
                transcript={transcript}
                active={active}
                onChoose={chooseTranscript}
                onFile={selectFile}
                onRemove={removeFile}
                onConsent={setConsent}
                onUpload={startUpload}
              />
            )}
          </div>
        </section>
      </div>

      <footer className="ob-footer">
        <div className="ob-footer-inner">
          <button
            type="button"
            className="ob-back"
            onClick={handleBack}
            disabled={!active}
          >
            <ArrowLeftIcon />
            {stepIndex === 0 && origin === "chat" ? "Back to chat" : "Back"}
          </button>
          <span className="ob-footer-spacer" />
          {hint && <span className="ob-hint">{hint}</span>}
          {step === "goal" && goal === "courses" && (
            <button
              type="button"
              className="ob-secondary"
              onClick={skipPersonalization}
              disabled={!active}
            >
              Skip personalization and start chatting
            </button>
          )}
          {canSkipStep && (
            <button
              type="button"
              className="ob-secondary"
              onClick={skipStep}
              disabled={!active}
            >
              Skip this question
            </button>
          )}
          <button
            type="button"
            className="ob-primary"
            onClick={handleContinue}
            disabled={!active || !canContinue}
          >
            {isLast ? "Start chatting" : "Continue"}
            <ArrowRightIcon />
          </button>
        </div>
      </footer>
    </div>
  )
}

function preventDefault(event: DragEvent) {
  event.preventDefault()
}

function hintFor(
  step: StepId,
  answers: OnboardingAnswers,
  profileOptional: boolean,
): string {
  switch (step) {
    case "goal":
      return "Choose a starting point to continue."
    case "major":
      if (answers.major === MAJOR_OTHER) return "Enter your major to continue."
      return profileOptional
        ? "Choose a major, or skip this question."
        : "Choose a major. Undecided is fine."
    case "year":
      if (answers.year === "other")
        return "Add a short description to continue."
      return profileOptional
        ? "Choose an option, or skip this question."
        : "Choose where you are to continue."
    case "transcript":
      if (answers.transcript.choice !== "upload")
        return "Choose an option to finish."
      if (answers.transcript.uploadStatus === "uploading")
        return "Finishing your upload…"
      return "Upload your transcript, or continue without one."
  }
}

// ── Steps ───────────────────────────────────────────────────────

const GOAL_ICONS: Record<Goal, ReactNode> = {
  courses: <BookIcon />,
  schedule: <CalendarIcon />,
  roadmap: <GraduationIcon />,
}

function GoalStep({
  value,
  onSelect,
}: {
  value: Goal | null
  onSelect: (goal: Goal) => void
}) {
  return (
    <fieldset className="ob-grid ob-grid-3">
      <legend className="ob-sr-only">Choose a starting point</legend>
      {GOALS.map((goal) => (
        <OptionCard
          key={goal.id}
          name="ob-goal"
          value={goal.id}
          checked={value === goal.id}
          onSelect={() => onSelect(goal.id)}
          icon={GOAL_ICONS[goal.id]}
          title={goal.title}
          description={goal.description}
        />
      ))}
    </fieldset>
  )
}

interface MajorStepProps {
  value: string | null
  other: string
  onSelect: (major: string) => void
  onOtherChange: (text: string) => void
}

function MajorStep({ value, other, onSelect, onOtherChange }: MajorStepProps) {
  const [query, setQuery] = useState("")
  const listRef = useRef<HTMLDivElement>(null)
  const otherRef = useRef<HTMLInputElement>(null)
  const results = useMemo(
    () =>
      ILLINOIS_TECH_PROGRAMS.filter((program) =>
        matchesProgram(program, query),
      ),
    [query],
  )
  const selectedProgram =
    value && value !== MAJOR_OTHER && value !== MAJOR_UNDECIDED ? value : null

  // When returning to this step, bring the saved program into view.
  useEffect(() => {
    const list = listRef.current
    const selected = list?.querySelector<HTMLElement>(".ob-row.is-selected")
    if (list && selected)
      list.scrollTop =
        selected.offsetTop - list.clientHeight / 2 + selected.offsetHeight / 2
  }, [])

  function choose(major: string) {
    onSelect(major)
    if (major === MAJOR_OTHER)
      requestAnimationFrame(() => otherRef.current?.focus())
  }

  function handleSearchKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" && results.length === 1) {
      event.preventDefault()
      choose(results[0])
    } else if (event.key === "ArrowDown") {
      event.preventDefault()
      const list = listRef.current
      ;(
        list?.querySelector<HTMLInputElement>(".ob-row.is-selected input") ??
        list?.querySelector<HTMLInputElement>("input")
      )?.focus()
    }
  }

  const trimmed = query.trim()

  return (
    <div className="ob-major">
      <fieldset className="ob-search-panel">
        <legend className="ob-sr-only">Programs</legend>
        <div className="ob-search">
          <SearchIcon />
          <input
            type="search"
            className="ob-search-input"
            placeholder="Search programs"
            aria-label="Search programs"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={handleSearchKey}
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        <div className="ob-major-status">
          {selectedProgram ? (
            <span>
              Selected: <strong>{selectedProgram}</strong>
            </span>
          ) : (
            <span>
              {trimmed
                ? `${results.length} ${
                    results.length === 1 ? "match" : "matches"
                  }`
                : `${ILLINOIS_TECH_PROGRAMS.length} programs`}
            </span>
          )}
        </div>
        <div className="ob-major-list" ref={listRef}>
          {results.map((program) => (
            <label
              key={program}
              className={`ob-row${value === program ? " is-selected" : ""}`}
            >
              <input
                className="ob-sr-input"
                type="radio"
                name="ob-major"
                value={program}
                checked={value === program}
                onChange={() => choose(program)}
              />
              <span className="ob-row-label">
                <Highlight text={program} query={trimmed} />
              </span>
              <span className="ob-row-check" aria-hidden="true">
                <CheckIcon />
              </span>
            </label>
          ))}
          {results.length === 0 && (
            <p className="ob-major-empty">
              No programs match “{trimmed}”. Choose <strong>Other</strong> to
              type your major.
            </p>
          )}
        </div>
      </fieldset>

      <div className="ob-major-alt">
        <OptionCard
          variant="compact"
          name="ob-major"
          value={MAJOR_UNDECIDED}
          checked={value === MAJOR_UNDECIDED}
          onSelect={() => choose(MAJOR_UNDECIDED)}
          title="Undecided"
          description="Still exploring"
        />
        <OptionCard
          variant="compact"
          name="ob-major"
          value={MAJOR_OTHER}
          checked={value === MAJOR_OTHER}
          onSelect={() => choose(MAJOR_OTHER)}
          title="Other"
          description="My major isn’t listed"
        />
      </div>

      {value === MAJOR_OTHER && (
        <label className="ob-field">
          <span className="ob-field-label">Your major</span>
          <input
            ref={otherRef}
            className="ob-text-input"
            type="text"
            value={other}
            maxLength={80}
            placeholder="Enter your major"
            onChange={(event) => onOtherChange(event.target.value)}
          />
        </label>
      )}
    </div>
  )
}

interface YearStepProps {
  value: YearId | null
  other: string
  onSelect: (year: YearId) => void
  onOtherChange: (text: string) => void
}

function YearStep({ value, other, onSelect, onOtherChange }: YearStepProps) {
  const otherRef = useRef<HTMLInputElement>(null)

  return (
    <div className="ob-year">
      <fieldset className="ob-grid-years">
        <legend className="ob-sr-only">Year of study</legend>
        {YEAR_OPTIONS.map((option) => (
          <OptionCard
            key={option.id}
            variant="compact"
            name="ob-year"
            value={option.id}
            checked={value === option.id}
            title={option.label}
            onSelect={() => {
              onSelect(option.id)
              if (option.id === "other")
                requestAnimationFrame(() => otherRef.current?.focus())
            }}
          />
        ))}
      </fieldset>

      {value === "other" && (
        <label className="ob-field ob-field-narrow">
          <span className="ob-field-label">Tell us where you are</span>
          <input
            ref={otherRef}
            className="ob-text-input"
            type="text"
            value={other}
            maxLength={60}
            placeholder="e.g., Exchange student"
            onChange={(event) => onOtherChange(event.target.value)}
          />
        </label>
      )}
    </div>
  )
}

interface TranscriptStepProps {
  transcript: TranscriptAnswer
  active: boolean
  onChoose: (choice: TranscriptChoice) => void
  onFile: (file: File | undefined) => void
  onRemove: () => void
  onConsent: (consent: boolean) => void
  onUpload: () => void
}

function TranscriptStep({
  transcript,
  active,
  onChoose,
  onFile,
  onRemove,
  onConsent,
  onUpload,
}: TranscriptStepProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const [dragging, setDragging] = useState(false)
  const { choice, file, consent, uploadStatus, uploadProgress, message } =
    transcript
  const uploading = uploadStatus === "uploading"
  const uploaded = uploadStatus === "uploaded"
  const percent = Math.round(uploadProgress * 100)

  function choose(next: TranscriptChoice) {
    onChoose(next)
    if (next === "upload") {
      requestAnimationFrame(() =>
        panelRef.current?.scrollIntoView({
          block: "nearest",
          behavior: "smooth",
        }),
      )
    }
  }

  function openPicker() {
    fileInputRef.current?.click()
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    if (active) onFile(event.dataTransfer.files[0])
  }

  const fileStatus = uploading
    ? "Uploading…"
    : uploaded
      ? "Uploaded for this session · Not analyzed"
      : uploadStatus === "failed"
        ? "Upload didn’t finish"
        : consent
          ? "Ready to upload"
          : "Waiting for your consent"

  return (
    <div className="ob-transcript">
      <fieldset className="ob-grid ob-grid-2">
        <legend className="ob-sr-only">Transcript</legend>
        <OptionCard
          variant="row"
          name="ob-transcript"
          value="upload"
          checked={choice === "upload"}
          onSelect={() => choose("upload")}
          icon={<UploadDocIcon />}
          title="Upload my transcript"
          description="Use my completed courses to personalize guidance."
        />
        <OptionCard
          variant="row"
          name="ob-transcript"
          value="none"
          checked={choice === "none"}
          onSelect={() => choose("none")}
          icon={<ChatIcon />}
          title="Continue without a transcript"
          description="I can share my course history in the conversation."
        />
      </fieldset>

      {choice === "upload" && (
        <div
          ref={panelRef}
          className={`ob-upload${dragging ? " is-dragging" : ""}`}
          onDragEnter={(event) => {
            event.preventDefault()
            setDragging(true)
          }}
          onDragOver={(event) => {
            event.preventDefault()
            event.dataTransfer.dropEffect = "copy"
          }}
          onDragLeave={(event) => {
            if (
              !event.currentTarget.contains(event.relatedTarget as Node | null)
            )
              setDragging(false)
          }}
          onDrop={handleDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={TRANSCRIPT_ACCEPT}
            hidden
            onChange={(event) => {
              onFile(event.target.files?.[0])
              event.target.value = ""
            }}
          />

          {file ? (
            <div className={`ob-file is-${uploadStatus}`}>
              <span className="ob-file-icon" aria-hidden="true">
                {uploaded ? <CheckIcon /> : <FileIcon />}
              </span>
              <div className="ob-file-main">
                <span className="ob-file-name" title={file.name}>
                  {file.name}
                </span>
                <span className="ob-file-meta">
                  {formatBytes(file.size)} · {fileStatus}
                </span>
                {uploading && (
                  <span
                    className="ob-file-bar"
                    role="progressbar"
                    aria-label="Upload progress"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={percent}
                  >
                    <span style={{ width: `${percent}%` }} />
                  </span>
                )}
              </div>
              <div className="ob-file-actions">
                <button
                  type="button"
                  className="ob-link-btn"
                  onClick={openPicker}
                  disabled={!active}
                >
                  Replace
                </button>
                <button
                  type="button"
                  className="ob-link-btn"
                  onClick={onRemove}
                  disabled={!active}
                >
                  Remove
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              className="ob-dropzone"
              onClick={openPicker}
              disabled={!active}
            >
              <span className="ob-dropzone-icon" aria-hidden="true">
                <UploadIcon />
              </span>
              <span className="ob-drop-title">
                Drag your transcript here, or{" "}
                <span className="ob-drop-link">browse files</span>
              </span>
              <span className="ob-drop-meta">
                PDF, PNG, or JPG · up to 10 MB
              </span>
            </button>
          )}

          {message && (
            <p className="ob-upload-error" role="alert">
              <AlertIcon />
              <span>{message}</span>
            </p>
          )}

          <label className="ob-consent">
            <input
              type="checkbox"
              className="ob-sr-input"
              checked={consent}
              onChange={(event) => onConsent(event.target.checked)}
              disabled={!active}
            />
            <span className="ob-checkbox" aria-hidden="true">
              <CheckIcon />
            </span>
            <span>
              I agree to use this transcript to personalize my academic
              guidance.
            </span>
          </label>

          {!uploaded && (
            <div className="ob-upload-actions">
              <button
                type="button"
                className="ob-btn-outline"
                onClick={onUpload}
                disabled={!active || !file || !consent || uploading}
              >
                {uploading && (
                  <span className="ob-spinner" aria-hidden="true" />
                )}
                {uploading
                  ? "Uploading…"
                  : uploadStatus === "failed"
                    ? "Try again"
                    : "Upload transcript"}
              </button>
              {!uploading && (!file || !consent) && (
                <span className="ob-upload-req">
                  {!file
                    ? "Choose a file to upload."
                    : "Check the box above to upload."}
                </span>
              )}
            </div>
          )}

          <p className="ob-upload-note">
            <InfoIcon />
            <span>
              Your file stays in this browser for this visit and isn’t sent to a
              server. Transcript analysis isn’t connected yet, so HAWKwarts
              won’t read your completed courses from it. You can share them in
              the chat instead.
            </span>
          </p>

          <span className="ob-sr-only" aria-live="polite">
            {uploading
              ? "Uploading transcript."
              : uploaded
                ? "Transcript uploaded for this session. It has not been analyzed."
                : ""}
          </span>
        </div>
      )}
    </div>
  )
}

// ── Building blocks ─────────────────────────────────────────────

interface OptionCardProps {
  name: string
  value: string
  checked: boolean
  onSelect: () => void
  title: string
  description?: string
  icon?: ReactNode
  variant?: "stack" | "row" | "compact"
}

function OptionCard({
  name,
  value,
  checked,
  onSelect,
  title,
  description,
  icon,
  variant = "stack",
}: OptionCardProps) {
  return (
    <label
      className={`ob-card ob-card-${variant}${checked ? " is-selected" : ""}`}
    >
      <input
        className="ob-sr-input"
        type="radio"
        name={name}
        value={value}
        checked={checked}
        onChange={onSelect}
      />
      {icon && (
        <span className="ob-card-icon" aria-hidden="true">
          {icon}
        </span>
      )}
      <span className="ob-card-body">
        <span className="ob-card-title">{title}</span>
        {description && <span className="ob-card-desc">{description}</span>}
      </span>
      <span className="ob-indicator" aria-hidden="true">
        <CheckIcon />
      </span>
    </label>
  )
}

interface HighlightProps {
  text: string
  query: string
}

function Highlight({ text, query }: HighlightProps) {
  const index = query ? text.toLowerCase().indexOf(query.toLowerCase()) : -1
  if (index < 0) return <>{text}</>
  return (
    <>
      {text.slice(0, index)}
      <mark className="ob-mark">{text.slice(index, index + query.length)}</mark>
      {text.slice(index + query.length)}
    </>
  )
}

// ── Icons (24px grid, 1.6 stroke) ───────────────────────────────

function Icon({
  children,
  size = 20,
  strokeWidth = 1.6,
}: {
  children: ReactNode
  size?: number
  strokeWidth?: number
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  )
}

function BookIcon() {
  return (
    <Icon>
      <path d="M12 6.6C10.2 5.35 8 4.75 4 4.75v13c4 0 6.2.6 8 1.85 1.8-1.25 4-1.85 8-1.85v-13c-4 0-6.2.6-8 1.85Z" />
      <path d="M12 6.6v13" />
    </Icon>
  )
}

function CalendarIcon() {
  return (
    <Icon>
      <rect x="3.75" y="5" width="16.5" height="15" rx="2.25" />
      <path d="M3.75 9.75h16.5M8 3.25v3.5M16 3.25v3.5" />
      <path
        d="M8 13.5h.01M12 13.5h.01M16 13.5h.01M8 16.75h.01M12 16.75h.01"
        strokeWidth={2.2}
      />
    </Icon>
  )
}

function GraduationIcon() {
  return (
    <Icon>
      <path d="M12 4.75 2.75 9.25 12 13.75l9.25-4.5L12 4.75Z" />
      <path d="M6.5 11.4v4.1c0 1.25 2.45 2.75 5.5 2.75s5.5-1.5 5.5-2.75v-4.1" />
      <path d="M21.25 9.25v4.5" />
    </Icon>
  )
}

function UploadDocIcon() {
  return (
    <Icon>
      <path d="M13.75 3.5H7.5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V8.25L13.75 3.5Z" />
      <path d="M13.75 3.5v4.75h4.75" />
      <path d="M12 17.25v-5.5M9.75 14 12 11.75 14.25 14" />
    </Icon>
  )
}

function ChatIcon() {
  return (
    <Icon>
      <path d="M5.25 5h13.5a1.75 1.75 0 0 1 1.75 1.75v8.5A1.75 1.75 0 0 1 18.75 17H11.5l-4.25 3.5V17h-2a1.75 1.75 0 0 1-1.75-1.75v-8.5A1.75 1.75 0 0 1 5.25 5Z" />
      <path d="M8 9.75h8M8 12.75h5" />
    </Icon>
  )
}

function FileIcon() {
  return (
    <Icon size={18}>
      <path d="M13.75 3.5H7.5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V8.25L13.75 3.5Z" />
      <path d="M13.75 3.5v4.75h4.75M9 13h6M9 16.25h4" />
    </Icon>
  )
}

function UploadIcon() {
  return (
    <Icon size={22}>
      <path d="M12 15V4.75M7.75 9 12 4.75 16.25 9" />
      <path d="M4.75 14.5v3a2 2 0 0 0 2 2h10.5a2 2 0 0 0 2-2v-3" />
    </Icon>
  )
}

function CheckIcon() {
  return (
    <Icon size={12} strokeWidth={3}>
      <path d="m5.5 12.5 4 4 9-9.5" />
    </Icon>
  )
}

function SearchIcon() {
  return (
    <Icon size={18}>
      <circle cx="11" cy="11" r="6.25" />
      <path d="m20 20-4.5-4.5" />
    </Icon>
  )
}

function ArrowLeftIcon() {
  return (
    <Icon size={16}>
      <path d="M19 12H5M11 6l-6 6 6 6" />
    </Icon>
  )
}

function ArrowRightIcon() {
  return (
    <Icon size={16} strokeWidth={2}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </Icon>
  )
}

function InfoIcon() {
  return (
    <Icon size={15}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 7.75h.01" />
    </Icon>
  )
}

function AlertIcon() {
  return (
    <Icon size={15}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.5v5.25M12 16.25h.01" />
    </Icon>
  )
}
