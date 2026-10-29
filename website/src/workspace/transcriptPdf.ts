export interface ImportedCourse {
  code: string
  name: string
  credits: number
}

export interface ImportedSemester {
  id: string
  label: string
  courses: ImportedCourse[]
}

const TERM_PATTERN = /\b(Fall|Spring|Summer|Winter)\s+(20\d{2})\b/i
const COURSE_PATTERN =
  /\b([A-Z]{2,6})\s*[- ]?\s*(\d{3,4}[A-Z]?)\b\s+(.+?)(?:\s+(\d(?:\.\d+)?)\s*(?:credits?|cr\.?)?)?(?:\s+[A-F][+-]?)?$/i

function cleanName(value: string): string {
  return value
    .replace(/\s+\d(?:\.\d+)?\s*(?:credits?|cr\.?)?\s*$/i, "")
    .replace(/\s+[A-F][+-]?\s*$/i, "")
    .trim()
}

function linesFromItems(
  items: Array<{ str: string; transform: ArrayLike<number> }>,
): string[] {
  const rows: Array<{ y: number; parts: Array<{ x: number; text: string }> }> =
    []

  for (const item of items) {
    const text = item.str.trim()
    if (!text) continue
    const x = item.transform[4] ?? 0
    const y = item.transform[5] ?? 0
    let row = rows.find((candidate) => Math.abs(candidate.y - y) < 2.5)
    if (!row) {
      row = { y, parts: [] }
      rows.push(row)
    }
    row.parts.push({ x, text })
  }

  return rows
    .sort((a, b) => b.y - a.y)
    .map((row) =>
      row.parts
        .sort((a, b) => a.x - b.x)
        .map((part) => part.text)
        .join(" ")
        .replace(/\s+/g, " ")
        .trim(),
    )
}

export async function parseTranscriptPdf(
  file: File,
): Promise<ImportedSemester[]> {
  if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
    throw new Error("Choose a PDF transcript.")
  }
  if (file.size === 0) throw new Error("That PDF is empty.")
  if (file.size > 10 * 1024 * 1024) {
    throw new Error("Choose a PDF smaller than 10 MB.")
  }

  const data = new Uint8Array(await file.arrayBuffer())
  const pdfjs = await import("pdfjs-dist")
  pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    "pdfjs-dist/build/pdf.worker.min.mjs",
    import.meta.url,
  ).toString()
  const document = await pdfjs.getDocument({ data }).promise
  const semesters: ImportedSemester[] = []
  let current: ImportedSemester | undefined
  const seen = new Set<string>()

  for (let pageNumber = 1; pageNumber <= document.numPages; pageNumber += 1) {
    const page = await document.getPage(pageNumber)
    const content = await page.getTextContent()
    const items = content.items
      .filter(
        (item): item is typeof item & { str: string; transform: number[] } =>
          "str" in item && "transform" in item,
      )
      .map((item) => ({ str: item.str, transform: item.transform }))

    for (const line of linesFromItems(items)) {
      const term = line.match(TERM_PATTERN)
      if (term) {
        const label = `${term[1][0].toUpperCase()}${term[1].slice(1).toLowerCase()} ${term[2]}`
        current = semesters.find((semester) => semester.label === label)
        if (!current) {
          current = {
            id: `imported-${term[1].toLowerCase()}-${term[2]}`,
            label,
            courses: [],
          }
          semesters.push(current)
        }
      }

      const course = line.match(COURSE_PATTERN)
      if (!course) continue
      const code = `${course[1].toUpperCase()} ${course[2].toUpperCase()}`
      if (seen.has(code)) continue
      const name = cleanName(course[3])
      if (!name || /^(term|course|grade|credit|hours?)$/i.test(name)) continue

      if (!current) {
        current =
          semesters.find((semester) => semester.id === "imported-courses") ??
          {
            id: "imported-courses",
            label: "Imported transcript",
            courses: [],
          }
        if (!semesters.includes(current)) semesters.push(current)
      }
      current.courses.push({
        code,
        name,
        credits: course[4] ? Number(course[4]) : 3,
      })
      seen.add(code)
    }
  }

  const populated = semesters.filter((semester) => semester.courses.length > 0)
  if (!populated.length) {
    throw new Error(
      "No completed courses were recognized. Try a text-based transcript PDF rather than a scanned image.",
    )
  }
  return populated
}
