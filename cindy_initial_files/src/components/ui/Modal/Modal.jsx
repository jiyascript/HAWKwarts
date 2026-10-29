import "./Modal.css";
import IconButton from "../IconButton/IconButton";

function Modal({
    isOpen,
    onClose,
    title,
    children,
    className = "",
}) {
    if (!isOpen) {
        return null;
    }

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div
                className={`modal ${className}`}
                onClick={(event) => event.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-labelledby="modal-title"
            >
                <div className="modal-header">
                    <h2 id="modal-title">{title}</h2>

                    <IconButton
                        icon="×"
                        label="Close modal"
                        onClick={onClose}
                    />
                </div>

                <div className="modal-content">
                    {children}
                </div>
            </div>
        </div>
    );
}

export default Modal;