import "./Badge.css";

function Badge({
    text,
    variant = "default",
    className = "",
}) {
    return (
        <span className={`badge badge--${variant} ${className}`}>
            {text}
        </span>
    );
}

export default Badge;