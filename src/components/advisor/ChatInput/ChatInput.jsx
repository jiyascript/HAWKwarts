import "./ChatInput.css";

import Input from "../../ui/Input/Input";
import IconButton from "../../ui/IconButton/IconButton";
import Tooltip from "../../ui/Tooltip/Tooltip";

function ChatInput({
    value,
    onChange,
    onSend,
    disabled = false,
    placeholder = "Ask your advisor...",
    className = "",
}) {
    function handleSubmit(event) {
        event.preventDefault();

        if (!value.trim() || disabled) {
            return;
        }

        onSend();
    }

    return (
        <form
            className={`chat-input ${className}`}
            onSubmit={handleSubmit}
        >
            <Input
                value={value}
                onChange={onChange}
                placeholder={placeholder}
                disabled={disabled}
                className="chat-input__field"
            />

            <Tooltip text="Send message">
                <IconButton
                    icon="↑"
                    label="Send message"
                    disabled={disabled || !value.trim()}
                    type="submit"
                />
            </Tooltip>
        </form>
    );
}

export default ChatInput;