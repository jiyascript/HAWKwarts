import "./SuggestedPrompt.css";

function SuggestedPrompt({
    text,
    onClick,
    disabled = false,
    className = "",
}) {
    return (
        <button
            type="button"
            className={`suggested-prompt ${className}`}
            onClick={() => onClick(text)}
            disabled={disabled}
        >
            {text}
        </button>
    );
}

export default SuggestedPrompt;