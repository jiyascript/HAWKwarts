import "./ChatMessage.css";

function ChatMessage({
    role = "advisor",
    children,
    className = "",
}) {
    const validRole = role === "user" ? "user" : "advisor";

    return (
        <div
            className={`chat-message chat-message--${validRole} ${className}`}
        >
            <div className="chat-message__content">
                {children}
            </div>
        </div>
    );
}

export default ChatMessage;