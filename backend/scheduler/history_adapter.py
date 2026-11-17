"""Prepare in-memory academic histories for scheduling."""

from copy import deepcopy

from backend.transcript.transcript_validator import (
    validate_academic_history,
)


def prepare_scheduler_history(raw_history):
    """Validate history and derive scheduler-ready course sets."""
    if not isinstance(raw_history, dict):
        raise ValueError(
            "Academic history must be a dictionary."
        )

    if raw_history.get("validation_errors"):
        raise ValueError(
            "Academic history contains validation errors. "
            "Correct them before scheduling."
        )

    history = validate_academic_history(
        deepcopy(raw_history)
    )

    if history["validation_errors"]:
        raise ValueError(
            f"Invalid academic history: {history['validation_errors']}"
        )

    completed_codes = set(
        history["scheduler_course_codes"]
    )

    in_progress_codes = {
        course["code"]
        for course in history["in_progress_courses"]
    }

    return history, completed_codes, in_progress_codes


def load_scheduler_history(*, history_path=None, raw_history=None):
    """Load and validate scheduler history from one trusted input source.

    A history dictionary remains in memory. A file path is supported
    for backward-compatible command-line execution.
    """
    import json
    from pathlib import Path

    if (history_path is None) == (raw_history is None):
        raise ValueError(
            "Provide exactly one of history_path or raw_history."
        )

    if history_path is not None:
        path = Path(history_path)

        with path.open("r", encoding="utf-8") as file:
            raw_history = json.load(file)

    return prepare_scheduler_history(raw_history)


def load_scheduler_history(*, history_path=None, raw_history=None):
    """Load and validate scheduler history from one trusted input source.

    A history dictionary remains in memory. A file path is supported
    for backward-compatible command-line execution.
    """
    import json
    from pathlib import Path

    if (history_path is None) == (raw_history is None):
        raise ValueError(
            "Provide exactly one of history_path or raw_history."
        )

    if history_path is not None:
        path = Path(history_path)

        with path.open("r", encoding="utf-8") as file:
            raw_history = json.load(file)

    return prepare_scheduler_history(raw_history)
