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

export function facultyKey(name: string): string {
  const [first, last] = firstLast(name)
  return `${first} ${last}`
}
