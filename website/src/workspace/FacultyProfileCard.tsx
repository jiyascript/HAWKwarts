import type { FacultyProfile } from "../custom/api"
import "./faculty.css"

/** Only http(s) links are rendered, since the URLs come from tool output. */
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

const EMAIL_RE = /^[^\s@<>"']+@[^\s@<>"']+\.[^\s@<>"']+$/

interface FacultyProfileCardProps {
  profile: FacultyProfile
  onAsk: (question: string) => void
}

export function FacultyProfileCard({ profile, onAsk }: FacultyProfileCardProps) {
  const { name, titles, email, bio, research, position, education, phones, office } =
    profile
  const interests = profile.research_interests
  const profileUrl = safeUrl(profile.profile_url)
  const openAlexUrl = safeUrl(research?.openalex_url)
  const hasDirectory = titles.length > 0 || !!email || !!profileUrl || !!bio
  const parsedAnything = !!(position || education || interests || office || phones.length)

  return (
    <article className="degree-card facprof-card" aria-labelledby="facprof-name">
      <header className="degree-card-head facprof-head">
        <div>
          <h3 id="facprof-name" className="degree-card-title facprof-name">
            {name}
          </h3>
          {position && <p className="facprof-position">{position}</p>}
          {titles.length > 0 && (
            <ul className="facprof-titles" aria-label="Tags">
              {titles.map((title) => (
                <li key={title}>{title}</li>
              ))}
            </ul>
          )}
        </div>
      </header>

      {(email || profileUrl || phones.length > 0 || office || education) && (
        <section className="facprof-section" aria-label="Contact and background">
          {education && (
            <p className="facprof-fact">
              <span className="facprof-fact-label">Education</span>
              {education}
            </p>
          )}
          {office && (
            <p className="facprof-fact">
              <span className="facprof-fact-label">Office</span>
              {office}
            </p>
          )}
          {phones.length > 0 && (
            <p className="facprof-fact">
              <span className="facprof-fact-label">Phone</span>
              {phones.join(" · ")}
            </p>
          )}
          <ul className="facprof-links">
            {email && EMAIL_RE.test(email) && (
              <li>
                <a href={`mailto:${email}`}>{email}</a>
              </li>
            )}
            {profileUrl && (
              <li>
                <a href={profileUrl} target="_blank" rel="noreferrer noopener">
                  IIT directory profile
                </a>
              </li>
            )}
          </ul>
        </section>
      )}

      {/* Only when nothing could be parsed out of it; otherwise it just repeats the fields above. */}
      {bio && !parsedAnything && (
        <details className="facprof-section facprof-bio">
          <summary>Directory profile text</summary>
          <p>{bio}</p>
        </details>
      )}

      <section className="facprof-section" aria-labelledby="facprof-research-title">
        <h4 id="facprof-research-title" className="facprof-section-title">
          Research
        </h4>

        {interests && (
          <p className="facprof-fact">
            <span className="facprof-fact-label">Interests (directory)</span>
            {interests}
          </p>
        )}

        {research ? (
          <>
            {(research.works_count !== null || research.citations !== null) && (
              <dl className="facprof-stats">
                {research.works_count !== null && (
                  <div>
                    <dt>Works</dt>
                    <dd>{research.works_count.toLocaleString()}</dd>
                  </div>
                )}
                {research.citations !== null && (
                  <div>
                    <dt>Citations</dt>
                    <dd>{research.citations.toLocaleString()}</dd>
                  </div>
                )}
              </dl>
            )}

            {research.publications.length > 0 ? (
              <>
                <p className="facprof-subtitle">Recent publications</p>
                <ol className="facprof-pubs">
                  {research.publications.map((pub, index) => (
                    <li key={`${index}-${pub.title}`}>
                      <span className="facprof-pub-title">{pub.title}</span>
                      {pub.year !== null && (
                        <span className="facprof-year">{pub.year}</span>
                      )}
                    </li>
                  ))}
                </ol>
              </>
            ) : (
              <p className="facprof-muted">No publications were listed for this profile.</p>
            )}

            {openAlexUrl && (
              <p className="facprof-muted">
                <a href={openAlexUrl} target="_blank" rel="noreferrer noopener">
                  View on OpenAlex
                </a>
              </p>
            )}
          </>
        ) : (
          <div className="facprof-missing">
            <p className="facprof-muted">Publications haven’t been looked up yet.</p>
            <button
              type="button"
              className="facprof-ask"
              onClick={() => onAsk(`What are ${name}'s recent publications?`)}
            >
              Ask for recent publications
            </button>
          </div>
        )}
      </section>

      {!hasDirectory && (
        <div className="facprof-missing">
          <p className="facprof-muted">Official title and contact info weren’t looked up yet.</p>
          <button
            type="button"
            className="facprof-ask"
            onClick={() => onAsk(`What is ${name}'s title and contact info?`)}
          >
            Ask for title and contact info
          </button>
        </div>
      )}

      <p className="facprof-source">
        Sources: IIT faculty directory{research ? " · OpenAlex" : ""}. Publications are
        drawn from public research profiles.
      </p>
    </article>
  )
}
