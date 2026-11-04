import type { CourseCard, FacultyProfile, PanelData } from "./api"
import { facultyKey, mergeFacultyProfile } from "./facultyProfile"

// One tab per professor or course the advisor has looked up, so earlier ones stay
// reachable. Looking up the same thing again updates its tab instead of adding one.

export type PanelItem =
  | { kind: "professor"; key: string; label: string; profile: FacultyProfile }
  | { kind: "course"; key: string; label: string; course: CourseCard }

export interface PanelTabsState {
  items: PanelItem[]
  activeKey: string | null
}

export const EMPTY_PANEL_TABS: PanelTabsState = { items: [], activeKey: null }

const MAX_PANEL_TABS = 8

export const professorKey = (name: string) => `prof:${facultyKey(name)}`
export const courseKey = (code: string) =>
  `course:${code.replace(/\s+/g, " ").trim().toUpperCase()}`

/** Placeholder answers that shouldn't block a real one arriving later. */
const EMPTY_TEXT = /^(none|n\/a)\.?$/i

/**
 * Descriptive fields stay as first shown. Each lookup is extracted again from whichever
 * tool results ran that turn, and the catalog and Banner word the same prerequisites
 * differently, so letting the newest text win made the card rewrite itself. A missing
 * (or "None") value is still filled in when a later lookup has a real one.
 */
function keepFirst(prev: string | null, next: string | null): string | null {
  if (prev === null || EMPTY_TEXT.test(prev.trim())) return next ?? prev
  return prev
}

/**
 * Fold a new lookup of the same course into its tab. Descriptive text stays as first shown;
 * sections and their term are a snapshot, so a newer set replaces the older one.
 */
export function mergeCourse(prev: CourseCard, next: CourseCard): CourseCard {
  const hasSections = next.sections.length > 0
  return {
    code: next.code,
    title: keepFirst(prev.title, next.title),
    credits: keepFirst(prev.credits, next.credits),
    description: keepFirst(prev.description, next.description),
    prerequisites: keepFirst(prev.prerequisites, next.prerequisites),
    corequisites: keepFirst(prev.corequisites, next.corequisites),
    satisfies: keepFirst(prev.satisfies, next.satisfies),
    catalog_url: keepFirst(prev.catalog_url, next.catalog_url),
    sections: hasSections ? next.sections : prev.sections,
    term: hasSections ? next.term : (prev.term ?? next.term),
  }
}

function itemFor(panel: PanelData): PanelItem {
  return panel.type === "professor"
    ? {
        kind: "professor",
        key: professorKey(panel.profile.name),
        label: panel.profile.name,
        profile: panel.profile,
      }
    : {
        kind: "course",
        key: courseKey(panel.course.code),
        label: panel.course.code,
        course: panel.course,
      }
}

function mergeItem(prev: PanelItem, next: PanelItem): PanelItem {
  if (prev.kind === "professor" && next.kind === "professor") {
    const profile = mergeFacultyProfile(prev.profile, next.profile)
    return { ...next, label: profile.name, profile }
  }
  if (prev.kind === "course" && next.kind === "course") {
    return { ...next, course: mergeCourse(prev.course, next.course) }
  }
  return next
}

/** A lookup the advisor just made. Already open: merge into that tab. New: add a tab. Either way it's shown. */
export function addPanel(state: PanelTabsState, panel: PanelData): PanelTabsState {
  const incoming = itemFor(panel)
  const index = state.items.findIndex((item) => item.key === incoming.key)

  let items: PanelItem[]
  if (index >= 0) {
    items = state.items.slice()
    items[index] = mergeItem(state.items[index], incoming)
  } else {
    items = [...state.items, incoming]
    if (items.length > MAX_PANEL_TABS) items = items.slice(items.length - MAX_PANEL_TABS)
  }
  return { items, activeKey: incoming.key }
}

/** Several lookups from one reply; the last one is the one shown. */
export function addPanels(state: PanelTabsState, panels: readonly PanelData[]): PanelTabsState {
  return panels.reduce(addPanel, state)
}

export function selectPanelTab(state: PanelTabsState, key: string): PanelTabsState {
  return state.items.some((item) => item.key === key) ? { ...state, activeKey: key } : state
}

/** Closing the shown tab moves to its neighbour (next, else previous). */
export function closePanelTab(state: PanelTabsState, key: string): PanelTabsState {
  const index = state.items.findIndex((item) => item.key === key)
  if (index < 0) return state

  const items = state.items.filter((_, i) => i !== index)
  if (state.activeKey !== key) return { ...state, items }

  const neighbour = items[index] ?? items[index - 1]
  return { items, activeKey: neighbour ? neighbour.key : null }
}

/** The tab to show, falling back to the most recent if the key is stale. */
export function activePanelItem(state: PanelTabsState): PanelItem | null {
  if (state.items.length === 0) return null
  return (
    state.items.find((item) => item.key === state.activeKey) ??
    state.items[state.items.length - 1]
  )
}

// DOM ids tying each tab to the panel it controls (keys contain colons and spaces).
const idSafe = (key: string) => key.toLowerCase().replace(/[^a-z0-9]+/g, "-")
export const panelTabId = (key: string) => `panel-tab-${idSafe(key)}`
export const panelBodyId = (key: string) => `panel-body-${idSafe(key)}`
