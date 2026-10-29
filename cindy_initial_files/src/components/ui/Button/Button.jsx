import "./Button.css";

function Button({
    children,
    variant = "primary",
    size = "medium",
    disabled = false,
    type = "button",
    onClick,
    className = "",
}) {
    return (
        <button
            type={type}
            className={`button button--${variant} button--${size} ${className}`}
            disabled={disabled}
            onClick={onClick}
        >
            {children}
        </button>
    );
}

export default Button;