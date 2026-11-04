import type { FacultyProfile } from "./api"

// The advisor only reports what its tools returned THIS turn, so a directory
// lookup and a research lookup for the same professor arrive as separate
// results. These helpers fold them into one card instead of replacing it.

/** First + last name tokens, ignoring case, periods and middle names. */
function firstLast(name: string): [string, string] {
  const tokens = name
    .toLowerCase()
    .split(/\s+/)
    .map((token) => token.replace(/\./g, ""))
    .filter(Boolean)
  return [tokens[0] ?? "", tokens[tokens.length - 1] ?? ""]
}

export function samePerson(a: string, b: string): boolean {
  const [aFirst, aLast] = firstLast(a)
  const [bFirst, bLast] = firstLast(b)
  return aFirst !== "" && aFirst === bFirst && aLast === bLast
}

function hasDirectoryData(profile: FacultyProfile): boolean {
  return (
    profile.titles.length > 0 ||
    !!profile.email ||
    !!profile.profile_url ||
    !!profile.bio
  )
}

/**
 * Combine a new lookup with the professor already on screen. Same person:
 * newer non-empty values win and nothing already known is lost. Different
 * person (or nothing shown yet): the new profile replaces the old one.
 */
export function mergeFacultyProfile(
  prev: FacultyProfile | null,
  next: FacultyProfile,
): FacultyProfile {
  if (!prev || !samePerson(prev.name, next.name)) return next

  return {
    name:
      hasDirectoryData(next) || !hasDirectoryData(prev) ? next.name : prev.name,
    titles: next.titles.length > 0 ? next.titles : prev.titles,
    email: next.email ?? prev.email,
    profile_url: next.profile_url ?? prev.profile_url,
    bio: next.bio ?? prev.bio,
    position: next.position ?? prev.position,
    education: next.education ?? prev.education,
    research_interests: next.research_interests ?? prev.research_interests,
    phones: next.phones.length > 0 ? next.phones : prev.phones,
    office: next.office ?? prev.office,
    research: next.research ?? prev.research,
  }
}

// ── Several professors at once (the tab strip in the Courses & Faculty panel) ──

/** Stable identity for a professor: first + last name. */
export function facultyKey(name: string): string {
  const [first, last] = firstLast(name)
  return `${first} ${last}`
}

export interface FacultyTabsState {
  profiles: FacultyProfile[]
  activeKey: string | null
}

export const EMPTY_FACULTY_TABS: FacultyTabsState = { profiles: [], activeKey: null }

const MAX_FACULTY_TABS = 8

/**
 * A professor the advisor just looked up. Already open: merge the new details
 * into their existing tab (position unchanged). New: add a tab. Either way that
 * professor becomes the one shown.
 */
export function addFacultyProfile(
  state: FacultyTabsState,
  incoming: FacultyProfile,
): FacultyTabsState {
  const key = facultyKey(incoming.name)
  const index = state.profiles.findIndex((p) => facultyKey(p.name) === key)

  let profiles: FacultyProfile[]
  if (index >= 0) {
    profiles = state.profiles.slice()
    profiles[index] = mergeFacultyProfile(state.profiles[index], incoming)
  } else {
    profiles = [...state.profiles, incoming]
    if (profiles.length > MAX_FACULTY_TABS) {
      profiles = profiles.slice(profiles.length - MAX_FACULTY_TABS)
    }
  }
  return { profiles, activeKey: key }
}

export function selectFacultyTab(
  state: FacultyTabsState,
  key: string,
): FacultyTabsState {
  return state.profiles.some((p) => facultyKey(p.name) === key)
    ? { ...state, activeKey: key }
    : state
}

export function closeFacultyTab(
  state: FacultyTabsState,
  key: string,
): FacultyTabsState {
  const index = state.profiles.findIndex((p) => facultyKey(p.name) === key)
  if (index < 0) return state

  const profiles = state.profiles.filter((_, i) => i !== index)
  if (state.activeKey !== key) return { ...state, profiles }

  const neighbour = profiles[index] ?? profiles[index - 1]
  return { profiles, activeKey: neighbour ? facultyKey(neighbour.name) : null }
}

export function activeFacultyProfile(state: FacultyTabsState): FacultyProfile | null {
  if (state.profiles.length === 0) return null
  return (
    state.profiles.find((p) => facultyKey(p.name) === state.activeKey) ??
    state.profiles[state.profiles.length - 1]
  )
}

const idSafe = (key: string) => key.replace(/[^a-z0-9]+/g, "-")
export const facultyTabId = (key: string) => `facprof-tab-${idSafe(key)}`
export const facultyPanelId = (key: string) => `facprof-panel-${idSafe(key)}`
