import "./LoadingIndicator.css";

function LoadingIndicator({
    message = "Loading...",
    size = "medium",
    className = "",
}) {
    return (
        <div
            className={`loading-indicator loading-indicator--${size} ${className}`}
            role="status"
            aria-live="polite"
        >
            <div className="loading-spinner"></div>

            {message && (
                <span className="loading-message">
                    {message}
                </span>
            )}
        </div>
    );
}

export default LoadingIndicator;