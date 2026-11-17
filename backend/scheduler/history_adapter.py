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
