import "./Card.css";

function Card({
    children,
    variant = "default",
    className = "",
}) {
    return (
        <div className={`card card--${variant} ${className}`}>
            {children}
        </div>
    );
}

export default Card;