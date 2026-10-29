import "./Tooltip.css";

function Tooltip({
    text,
    position = "top",
    children,
    className = "",
}) {
    return (
        <span className={`tooltip ${className}`}>
            {children}

            <span
                className={`tooltip-text tooltip-text--${position}`}
                role="tooltip"
            >
                {text}
            </span>
        </span>
    );
}

export default Tooltip;