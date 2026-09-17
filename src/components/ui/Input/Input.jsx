import "./Input.css";

function Input({
    placeholder = "",
    value,
    onChange,
    type = "text",
    disabled = false,
    name,
    id,
    className = "",
}) {
    return (
        <input
            type={type}
            placeholder={placeholder}
            value={value}
            onChange={onChange}
            disabled={disabled}
            name={name}
            id={id}
            className={`input ${className}`}
        />
    );
}

export default Input;