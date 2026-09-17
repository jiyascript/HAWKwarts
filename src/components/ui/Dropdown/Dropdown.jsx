import "./Dropdown.css";

function Dropdown({
    options = [],
    value,
    onChange,
    placeholder = "Select an option",
    disabled = false,
    name,
    id,
    className = "",
}) {
    return (
        <select
            value={value}
            onChange={onChange}
            disabled={disabled}
            name={name}
            id={id}
            className={`dropdown ${className}`}
        >
            <option value="" disabled>
                {placeholder}
            </option>

            {options.map((option) => (
                <option key={option} value={option}>
                    {option}
                </option>
            ))}
        </select>
    );
}

export default Dropdown;