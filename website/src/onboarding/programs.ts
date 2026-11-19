export interface Program {
  id: string // "computer-science:bs-bac-ba" — used for scheduling
  name: string // "Computer Science" — display name
  credential: string // "BS/BAC/BA"
  level: "undergraduate" | "graduate"
}
let cache: Program[] | null = null

export async function loadPrograms(): Promise<Program[]> {
  if (cache) return cache
  // const response = await fetch("http://localhost:8000/programs")
  const response = await fetch("/programs")
  if (!response.ok) throw new Error("Could not load the program list.")
  const raw: {
    id: string
    name: string
    credential: string
    level: string
  }[] = await response.json()

  cache = raw
    .filter((p) => p.level === "undergraduate" || p.level === "graduate")
    .map((p) => ({
      id: p.id,
      name: p.name,
      credential: p.credential,
      level: p.level as "undergraduate" | "graduate",
    }))
  return cache
}

/** Matches by substring or by initials, so "cs" finds Computer Science. */
export function matchesProgram(program: Program, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const name = program.name.toLowerCase()
  if (name.includes(q)) return true
  const initials = name
    .split(/\s+/)
    .filter((word) => word !== "and")
    .map((word) => word[0])
    .join("")
  return initials.startsWith(q.replace(/\s+/g, ""))
}
