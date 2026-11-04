import type { KeyboardEvent } from "react"
import { panelBodyId, panelTabId, type PanelItem } from "../custom/panelTabs"
import "./faculty.css"

interface PanelTabsProps {
  items: readonly PanelItem[]
  activeKey: string
  onSelect: (key: string) => void
  onClose: (key: string) => void
}

/** One tab per professor or course the advisor has looked up, so earlier ones stay reachable. */
export function PanelTabs({ items, activeKey, onSelect, onClose }: PanelTabsProps) {
  const keys = items.map((item) => item.key)

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
      document.getElementById(panelTabId(keys[nextIndex]))?.focus(),
    )
  }

  return (
    <div
      className="facprof-tabs"
      role="tablist"
      aria-label="Professors and courses"
      onKeyDown={handleKeyDown}
    >
      {items.map((item) => {
        const active = item.key === activeKey
        const kindLabel = item.kind === "course" ? "Course" : "Professor"
        return (
          <div
            key={item.key}
            className="facprof-tab"
            role="presentation"
            data-active={active}
            data-kind={item.kind}
          >
            <button
              type="button"
              role="tab"
              id={panelTabId(item.key)}
              className="facprof-tab-select"
              aria-selected={active}
              aria-controls={active ? panelBodyId(item.key) : undefined}
              tabIndex={active ? 0 : -1}
              title={`${kindLabel}: ${item.label}`}
              onClick={() => onSelect(item.key)}
            >
              {item.label}
            </button>
            <button
              type="button"
              className="facprof-tab-close"
              aria-label={`Close ${kindLabel.toLowerCase()} ${item.label}`}
              tabIndex={active ? 0 : -1}
              onClick={() => onClose(item.key)}
            >
              ×
            </button>
          </div>
        )
      })}
    </div>
  )
}
