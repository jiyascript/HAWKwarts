import type { CourseCard } from "../custom/api"
import "./course-card.css"

/** Only http(s) links are rendered, since the URL comes from tool output. */
function safeUrl(url: string | null | undefined): string | null {
  if (!url) return null
  try {
    const parsed = new URL(url)
    return parsed.protocol === "https:" || parsed.protocol === "http:"
      ? parsed.toString()
      : null
  } catch {
    return null
  }
}

const PERSON_NAME = /^[A-Za-z][A-Za-z.'’-]*(?: [A-Za-z][A-Za-z.'’-]*){1,3}$/

interface CourseInfoCardProps {
  course: CourseCard
  onAsk: (question: string) => void
}

export function CourseInfoCard({ course, onAsk }: CourseInfoCardProps) {
  const { code, title, credits, description, prerequisites, corequisites, satisfies, sections } =
    course
  const catalogUrl = safeUrl(course.catalog_url)
  const column = {
    section: sections.some((s) => s.section),
    crn: sections.some((s) => s.crn),
    instructor: sections.some((s) => s.instructor),
    meeting: sections.some((s) => s.meeting),
    seats: sections.some((s) => s.seats),
  }
  const instructors = Array.from(
    new Set(
      sections
        .map((s) => s.instructor)
        .filter((name): name is string => !!name && PERSON_NAME.test(name)),
    ),
  )
  const creditsLabel = credits ? `${credits} ${credits === "1" ? "credit" : "credits"}` : null

  return (
    <article className="degree-card panelcourse-card" aria-labelledby="panelcourse-title">
      <header className="panelcourse-head">
        <h3 id="panelcourse-title" className="degree-card-title panelcourse-title">
          {code}
          {title && <span className="panelcourse-name">{title}</span>}
        </h3>
        {(creditsLabel || satisfies) && (
          <ul className="panelcourse-tags" aria-label="Credits and requirements met">
            {creditsLabel && <li>{creditsLabel}</li>}
            {satisfies && <li>Satisfies {satisfies}</li>}
          </ul>
        )}
      </header>

      {description && (
        <section className="panelcourse-section" aria-label="Description">
          <p className="panelcourse-text">{description}</p>
        </section>
      )}

      {(prerequisites || corequisites) && (
        <section className="panelcourse-section" aria-label="Prerequisites and corequisites">
          {prerequisites && (
            <p className="panelcourse-fact">
              <span className="panelcourse-label">Prerequisites</span>
              <span className="panelcourse-text">{prerequisites}</span>
            </p>
          )}
          {corequisites && (
            <p className="panelcourse-fact">
              <span className="panelcourse-label">Corequisites</span>
              <span className="panelcourse-text">{corequisites}</span>
            </p>
          )}
        </section>
      )}

      {sections.length > 0 && (
        <section className="panelcourse-section" aria-labelledby="panelcourse-sections">
          <h4 id="panelcourse-sections" className="panelcourse-heading">
            Sections{course.term ? ` for ${course.term}` : ""}
          </h4>
          <div className="panelcourse-scroll" tabIndex={0} aria-label="Course sections table">
            <table className="panelcourse-table">
              <thead>
                <tr>
                  {column.section && <th scope="col">Section</th>}
                  {column.crn && <th scope="col">CRN</th>}
                  {column.instructor && <th scope="col">Instructor</th>}
                  {column.meeting && <th scope="col">Meets</th>}
                  {column.seats && <th scope="col">Seats</th>}
                </tr>
              </thead>
              <tbody>
                {sections.map((s, index) => (
                  <tr key={`${s.crn ?? s.section ?? "section"}-${index}`}>
                    {column.section && <td>{s.section ?? ""}</td>}
                    {column.crn && <td>{s.crn ?? ""}</td>}
                    {column.instructor && <td>{s.instructor ?? ""}</td>}
                    {column.meeting && <td>{s.meeting ?? ""}</td>}
                    {column.seats && <td>{s.seats ?? ""}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {instructors.length > 0 && (
            <div className="panelcourse-ask">
              {instructors.map((name) => (
                <button
                  key={name}
                  type="button"
                  className="panelcourse-ask-btn"
                  onClick={() => onAsk(`Tell me about Prof. ${name}`)}
                >
                  Ask about {name}
                </button>
              ))}
            </div>
          )}
        </section>
      )}

      {catalogUrl && (
        <section className="panelcourse-section" aria-label="Catalog link">
          <a href={catalogUrl} target="_blank" rel="noreferrer noopener">
            View in the course catalog
          </a>
        </section>
      )}

      <p className="panelcourse-source">
        From the Illinois Tech course catalog
        {sections.length > 0 ? " and Banner. Banner data is a snapshot, so seats and times can change." : "."}
      </p>
    </article>
  )
}
