import "./ChatPanel.css";

function ChatPanel({
    children,
    className = "",
}) {
    return (
        <section className={`chat-panel ${className}`}>
            <div className="chat-panel__messages">
                {children}
            </div>
        </section>
    );
}

export default ChatPanel;