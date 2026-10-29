import "./TypingIndicator.css";

function TypingIndicator({
    message = "Advisor is thinking",
    className = "",
}) {
    return (
        <div
            className={`typing-indicator ${className}`}
            role="status"
            aria-live="polite"
        >
            <span className="typing-indicator__message">
                {message}
            </span>

            <div
                className="typing-indicator__dots"
                aria-hidden="true"
            >
                <span className="typing-indicator__dot"></span>
                <span className="typing-indicator__dot"></span>
                <span className="typing-indicator__dot"></span>
            </div>
        </div>
    );
}

export default TypingIndicator;