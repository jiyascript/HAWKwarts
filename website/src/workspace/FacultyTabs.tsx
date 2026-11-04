import type { KeyboardEvent } from "react"
import type { FacultyProfile } from "../custom/api"
import {
  facultyKey,
  facultyPanelId,
  facultyTabId,
} from "../custom/facultyProfile"
import "./faculty.css"

interface FacultyTabsProps {
  profiles: readonly FacultyProfile[]
  activeKey: string
  onSelect: (key: string) => void
  onClose: (key: string) => void
}

/** One tab per professor the advisor has looked up, so earlier ones stay reachable. */
export function FacultyTabs({ profiles, activeKey, onSelect, onClose }: FacultyTabsProps) {
  const keys = profiles.map((profile) => facultyKey(profile.name))

  // Arrow keys / Home / End move between tabs; Delete closes the focused one.
  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const target = event.target as HTMLElement
    if (!target.matches('[role="tab"]')) return

    const index = keys.indexOf(activeKey)
    let nextIndex = -1
    if (event.key === "ArrowRight") nextIndex = (index + 1) % keys.length
    else if (event.key === "ArrowLeft") nextIndex = (index - 1 + keys.length) % keys.length
    else if (event.key === "Home") nextIndex = 0
    else if (event.key === "End") nextIndex = keys.length - 1
    else if (event.key === "Delete" && index >= 0) {
      event.preventDefault()
      onClose(keys[index])
      return
    }
    if (nextIndex < 0) return

    event.preventDefault()
    onSelect(keys[nextIndex])
    
    window.requestAnimationFrame(() =>
      document.getElementById(facultyTabId(keys[nextIndex]))?.focus(),
    )
  }

  return (
    <div
      className="facprof-tabs"
      role="tablist"
      aria-label="Professors"
      onKeyDown={handleKeyDown}
    >
      {profiles.map((profile, i) => {
        const key = keys[i]
        const active = key === activeKey
        return (
          <div key={key} className="facprof-tab" role="presentation" data-active={active}>
            <button
              type="button"
              role="tab"
              id={facultyTabId(key)}
              className="facprof-tab-select"
              aria-selected={active}
              aria-controls={active ? facultyPanelId(key) : undefined}
              tabIndex={active ? 0 : -1}
              title={profile.name}
              onClick={() => onSelect(key)}
            >
              {profile.name}
            </button>
            <button
              type="button"
              className="facprof-tab-close"
              aria-label={`Close ${profile.name}`}
              tabIndex={active ? 0 : -1}
              onClick={() => onClose(key)}
            >
              ×
            </button>
          </div>
        )
      })}
    </div>
  )
}
