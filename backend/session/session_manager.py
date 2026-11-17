"""In-memory advising sessions for HAWKwarts."""

from datetime import datetime, timedelta, timezone
import secrets
from copy import deepcopy

from backend.transcript.transcript_validator import (
    validate_academic_history,
)
from backend.transcript.transcript_editor import (
    apply_course_correction,
)


SESSION_TIMEOUT = timedelta(minutes=30)


class SessionManager:
    """Manage temporary advising sessions in process memory."""

    def __init__(self):
        self._sessions = {}

    def create_session(self):
        """Create an empty advising session and return its identifier."""
        session_id = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)

        self._sessions[session_id] = {
            "created_at": now,
            "last_activity": now,
            "academic_history": None,
        }

        return session_id

    def store_academic_history(self, session_id, history):
        """Store a validated academic history in an existing session."""
        self._require_active_session(session_id)

        if not isinstance(history, dict):
            raise ValueError("Academic history must be a dictionary.")

        if history.get("validation_errors"):
            raise ValueError(
                "Cannot store academic history containing "
                "recorded validation errors."
            )

        validated = validate_academic_history(history)

        if validated["validation_errors"]:
            raise ValueError(
                "Cannot store invalid academic history: "
                f"{validated['validation_errors']}"
            )

        self._sessions[session_id]["academic_history"] = deepcopy(
            validated
        )
        self._sessions[session_id]["last_activity"] = (
            datetime.now(timezone.utc)
        )

    def get_academic_history(self, session_id):
        """Return an independent copy of a session's academic history."""
        self._require_active_session(session_id)

        history = self._sessions[session_id]["academic_history"]

        result = deepcopy(history)
        self._sessions[session_id]["last_activity"] = (
            datetime.now(timezone.utc)
        )
        return result

    def correct_session_course(
        self, session_id, collection, index, changes
    ):
        """Apply a validated correction to a session's academic history."""
        self._require_active_session(session_id)

        history = self._sessions[session_id]["academic_history"]

        if history is None:
            raise ValueError(
                "Cannot correct a course before storing academic history."
            )

        corrected = apply_course_correction(
            history, collection, index, changes
        )

        self._sessions[session_id]["academic_history"] = deepcopy(
            corrected
        )
        self._sessions[session_id]["last_activity"] = (
            datetime.now(timezone.utc)
        )

        return deepcopy(corrected)

    def delete_session(self, session_id):
        """Remove an advising session and its stored academic history."""
        self._require_active_session(session_id)

        del self._sessions[session_id]

    def cleanup_expired_sessions(self, now=None):
        """Remove sessions inactive for at least SESSION_TIMEOUT."""
        if now is None:
            now = datetime.now(timezone.utc)

        if not isinstance(now, datetime) or (
            now.tzinfo is None or now.utcoffset() is None
        ):
            raise ValueError(
                "Expiration time must be a timezone-aware datetime."
            )

        expired_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if now - session["last_activity"] >= SESSION_TIMEOUT
        ]

        for session_id in expired_ids:
            del self._sessions[session_id]

        return len(expired_ids)

    def _require_active_session(self, session_id):
        """Return an active session or reject missing/expired sessions."""
        session = self._sessions.get(session_id)

        if session is None:
            raise KeyError("Advising session not found.")

        now = datetime.now(timezone.utc)

        if now - session["last_activity"] >= SESSION_TIMEOUT:
            del self._sessions[session_id]
            raise KeyError("Advising session has expired.")

        return session
