interface SuggestedQuestionChipsProps {
  questions: readonly string[]
  /** Routed through the chat's existing suggestion handler; chips never answer on their own. */
  onPick: (question: string) => void
  label: string
  className?: string
}

export function SuggestedQuestionChips({
  questions,
  onPick,
  label,
  className,
}: SuggestedQuestionChipsProps) {
  return (
    <div
      className={`chat-suggestions${className ? ` ${className}` : ""}`}
      role="group"
      aria-label={label}
    >
      {questions.map((question) => (
        <button
          key={question}
          type="button"
          className="chat-suggestion"
          onClick={() => onPick(question)}
        >
          {question}
        </button>
      ))}
    </div>
  )
}
