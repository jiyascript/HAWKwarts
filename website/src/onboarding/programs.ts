// Academic programs offered for the major question. Prototype list — replace with
// the registrar's program catalog when one is connected.
export const ILLINOIS_TECH_PROGRAMS: readonly string[] = [
  "Aerospace Engineering",
  "Applied Cybersecurity and Information Technology",
  "Applied Mathematics",
  "Architectural Engineering",
  "Architecture",
  "Artificial Intelligence",
  "Biochemistry",
  "Biology",
  "Biomedical Engineering",
  "Business Administration",
  "Chemical Engineering",
  "Chemistry",
  "Civil Engineering",
  "Communication",
  "Computer Engineering",
  "Computer Science",
  "Data Science",
  "Design",
  "Electrical Engineering",
  "Engineering Management",
  "Environmental Engineering",
  "Finance",
  "Food Science and Nutrition",
  "Humanities",
  "Industrial Technology and Operations",
  "Information Technology and Management",
  "Materials Science and Engineering",
  "Mechanical Engineering",
  "Physics",
  "Political Science",
  "Psychological Science",
  "Social and Economic Development Policy",
]

/** Matches by substring or by initials, so "cs" finds Computer Science. */
export function matchesProgram(program: string, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const name = program.toLowerCase()
  if (name.includes(q)) return true
  const initials = name
    .split(/\s+/)
    .filter((word) => word !== "and")
    .map((word) => word[0])
    .join("")
  return initials.startsWith(q.replace(/\s+/g, ""))
}
