import "./IconButton.css";

function IconButton({
    icon,
    label,
    onClick,
    disabled = false,
    size = "medium",
    type = "button",
    className = "",
}) {
    return (
        <button
            type={type}
            className={`icon-button icon-button--${size} ${className}`}
            aria-label={label}
            title={label}
            onClick={onClick}
            disabled={disabled}
        >
            {icon}
        </button>
    );
}

export default IconButton;