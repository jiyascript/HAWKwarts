import { useEffect, useLayoutEffect, useRef, useState, type Ref } from "react"
import {
  afterNextPaint,
  freshGif,
  loadGifBlob,
  sleep,
  type FreshGif,
} from "./gifPlayback"

/*
 * The advisor bird patrols the lane above the conversation. Clicking it lands it
 * where it is; clicking again sends it back into flight.
 *
 * Every asset shares one 512×512 canvas: the landing GIF's first frame is the
 * flight GIF's first frame, the seated PNG is the landing GIF's last frame, and
 * the takeoff GIF is the landing frames reversed. Drawing every state in the same
 * box with the same flip therefore keeps the bird's apparent size, anchor, and
 * facing steady across swaps, with no per-asset offsets.
 */

const PERCH_SRCS = {
  landing: "/assets/hawkwarts-flight-to-sit.gif",
  seated: "/assets/hawkwarts-landing-end.png",
  takeoff: "/assets/hawkwarts-sit-to-flight.gif",
} as const

/** Total frame delays. Both GIFs play once and hold their last frame. */
const LANDING_MS = 1210
const TAKEOFF_MS = 690
/** Swap a little late: a held last frame is invisible, a skipped one is not. */
const SWAP_SLACK_MS = 50
/** One there-and-back patrol across the lane. */
const PATROL_MS = 12_000
/** Ease from hovering back up to patrol speed after a takeoff. */
const RAMP_MS = 900
/** Patrol geometry, in step with `.chat-hawk`: from -10px to (100% - 62px). */
const LANE_START_PX = -10
const LANE_INSET_PX = 52

type BirdPhase = "flying" | "landing" | "seated" | "takeoff"

let seatedImage: HTMLImageElement | null = null

/** Fetch the transition GIFs and decode the seated pose so no swap shows a blank frame. */
export function preloadPerchAssets(flightSrc: string) {
  for (const src of [PERCH_SRCS.landing, PERCH_SRCS.takeoff, flightSrc]) {
    loadGifBlob(src).catch(() => undefined)
  }
  if (!seatedImage) {
    seatedImage = new Image()
    seatedImage.src = PERCH_SRCS.seated
    seatedImage.decode().catch(() => undefined)
  }
}

/**
 * Position along the lane (0 = left end, 1 = right end) and horizontal scale for a
 * point in the patrol cycle: right for 49%, a quick squash-turn, left for 49%, turn.
 */
function patrolPose(progress: number): { along: number; scaleX: number } {
  if (progress < 0.49) return { along: progress / 0.49, scaleX: 1 }
  if (progress < 0.5) return { along: 1, scaleX: 1 - (progress - 0.49) * 200 }
  if (progress < 0.99) return { along: 1 - (progress - 0.5) / 0.49, scaleX: -1 }
  return { along: 0, scaleX: -1 + (progress - 0.99) * 200 }
}

/** A bird caught mid-turn finishes the turn on the spot rather than landing squashed. */
function settleTurn(progress: number): number {
  if (progress >= 0.49 && progress < 0.5) return progress < 0.495 ? 0.49 : 0.5
  if (progress >= 0.99) return progress < 0.995 ? 0.99 : 0
  return progress
}

function applyPose(el: HTMLElement, progress: number) {
  const { along, scaleX } = patrolPose(progress)
  // Percentages keep the bird inside the lane when the panel resizes, even while seated.
  el.style.left = `calc(${LANE_START_PX}px + (100% - ${LANE_INSET_PX}px) * ${along.toFixed(5)})`
  el.style.transform = scaleX === 1 ? "" : `scaleX(${scaleX.toFixed(4)})`
}

function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches
}

interface AdvisorBirdProps {
  flightSrc: string
  /** True once the chat is the settled screen; the bird only patrols and responds then. */
  active: boolean
  /** Hidden while the transformation flyer stands in for it. */
  hidden: boolean
  /** The image the screen transitions measure the bird's position from. */
  imgRef: Ref<HTMLImageElement>
}

export function AdvisorBird({
  flightSrc,
  active,
  hidden,
  imgRef,
}: AdvisorBirdProps) {
  const buttonRef = useRef<HTMLButtonElement>(null)
  const [phase, setPhase] = useState<BirdPhase>("flying")
  const [src, setSrc] = useState(flightSrc)
  // Synchronous copy of `phase`, so repeat clicks are rejected before React re-renders.
  const phaseRef = useRef<BirdPhase>("flying")
  // Bumped to abandon a landing or takeoff that is still in progress.
  const runRef = useRef(0)
  // Where the bird is in its patrol cycle [0, 1), and when its post-takeoff acceleration began.
  const patrol = useRef<{ progress: number; rampStart: number | null }>({
    progress: 0,
    rampStart: null,
  })
  // The restarted flight GIF shown after a takeoff; revoked once replaced.
  const flightGif = useRef<FreshGif | null>(null)

  function enter(next: BirdPhase) {
    phaseRef.current = next
    setPhase(next)
  }

  // Away from the chat the bird goes back to the start of its patrol, flying on the
  // shared flight GIF, so the next transformation hands off to it seamlessly.
  useLayoutEffect(() => {
    if (active) return
    runRef.current++
    patrol.current = { progress: 0, rampStart: null }
    if (buttonRef.current) applyPose(buttonRef.current, 0)
    phaseRef.current = "flying"
    setPhase("flying")
    setSrc(flightSrc)
    flightGif.current?.release()
    flightGif.current = null
  }, [active, flightSrc])

  useEffect(
    () => () => {
      runRef.current++
      flightGif.current?.release()
    },
    [],
  )

  // Patrol: advances only while flying, so landing and sitting hold the bird exactly in place.
  useEffect(() => {
    const el = buttonRef.current
    if (!active || !el) return
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)")
    let frame = 0
    let last = performance.now()
    const tick = (now: number) => {
      // Cap each step so returning to a backgrounded tab doesn't make the bird jump.
      const elapsed = Math.min(Math.max(now - last, 0), 64)
      last = now
      const state = patrol.current
      if (phaseRef.current === "flying" && !reducedMotion.matches) {
        let speed = 1
        if (state.rampStart !== null) {
          const t = Math.min(Math.max((now - state.rampStart) / RAMP_MS, 0), 1)
          speed = (1 - Math.cos(Math.PI * t)) / 2
          if (t === 1) state.rampStart = null
        }
        state.progress = (state.progress + (elapsed * speed) / PATROL_MS) % 1
        applyPose(el, state.progress)
      }
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [active])

  async function land() {
    const run = ++runRef.current
    // Entering "landing" stops the patrol on this frame, at the clicked position.
    enter("landing")
    const state = patrol.current
    state.rampStart = null
    state.progress = settleTurn(state.progress)
    if (buttonRef.current) applyPose(buttonRef.current, state.progress)

    if (prefersReducedMotion()) {
      setSrc(PERCH_SRCS.seated)
      enter("seated")
      return
    }
    // A fresh URL restarts the landing from its first frame every time.
    const landing = await freshGif(PERCH_SRCS.landing)
    if (run !== runRef.current) return landing.release()
    setSrc(landing.url)
    await afterNextPaint()
    await sleep(LANDING_MS + SWAP_SLACK_MS)
    if (run !== runRef.current) return landing.release()
    setSrc(PERCH_SRCS.seated)
    enter("seated")
    await afterNextPaint()
    landing.release()
  }

  async function takeOff() {
    const run = ++runRef.current
    enter("takeoff")
    if (prefersReducedMotion()) {
      setSrc(flightSrc)
      enter("flying")
      return
    }
    // Decode a restarted flight GIF now: it opens on the frame the takeoff ends with.
    const nextFlight = freshGif(flightSrc)
    const takeoff = await freshGif(PERCH_SRCS.takeoff)
    if (run !== runRef.current) {
      takeoff.release()
      void nextFlight.then((gif) => gif.release())
      return
    }
    setSrc(takeoff.url)
    await afterNextPaint()
    await sleep(TAKEOFF_MS + SWAP_SLACK_MS)
    const flight = await nextFlight
    if (run !== runRef.current) {
      takeoff.release()
      flight.release()
      return
    }
    flightGif.current?.release()
    flightGif.current = flight
    setSrc(flight.url)
    patrol.current.rampStart = performance.now()
    enter("flying")
    await afterNextPaint()
    takeoff.release()
  }

  function handleClick() {
    if (!active) return
    if (phaseRef.current === "flying") void land()
    else if (phaseRef.current === "seated") void takeOff()
    // Clicks mid-landing or mid-takeoff are ignored so animations never overlap.
  }

  const inTransition = phase === "landing" || phase === "takeoff"

  return (
    <button
      ref={buttonRef}
      type="button"
      className="chat-hawk"
      data-phase={phase}
      aria-label="Perch the HAWKwarts bird"
      aria-pressed={phase === "landing" || phase === "seated"}
      aria-disabled={inTransition || undefined}
      onClick={handleClick}
      // Mouse clicks leave focus (and the student's caret) in the composer.
      onMouseDown={(event) => event.preventDefault()}
      style={{
        opacity: hidden ? 0 : 1,
        pointerEvents: hidden ? "none" : undefined,
      }}
    >
      <img
        ref={imgRef}
        src={src}
        alt=""
        className="chat-hawk-img"
        draggable={false}
      />
    </button>
  )
}
