import "./AdvisorMessage.css";

function AdvisorMessage({
    children,
    status = "complete",
    className = "",
}) {
    return (
        <div
            className={`advisor-message advisor-message--${status} ${className}`}
        >
            <div className="advisor-message__header">
                <span className="advisor-message__label">
                    Advisor
                </span>
            </div>

            <div className="advisor-message__content">
                {children}
            </div>
        </div>
    );
}

export default AdvisorMessage;