"""Controlled transfer-equivalency status updates."""

from copy import deepcopy

from .transcript_validator import validate_academic_history


def apply_transfer_verification(
    history,
    index,
    verified,
    *,
    institutional_confirmation=False,
):
    """Apply a confirmed transfer-equivalency decision.

    The caller must independently establish authorization and
    confirm that the decision came from an institutional source.
    """
    if type(verified) is not bool:
        raise ValueError(
            "Verification status must be a boolean."
        )

    if institutional_confirmation is not True:
        raise PermissionError(
            "An authorized institutional confirmation "
            "is required to change transfer verification."
        )

    if not isinstance(history, dict):
        raise ValueError(
            "Academic history must be a dictionary."
        )

    if history.get("validation_errors"):
        raise ValueError(
            "Cannot verify transfers in a history "
            "containing recorded validation errors."
        )

    validated = validate_academic_history(history)

    if validated["validation_errors"]:
        raise ValueError(
            "Cannot verify transfers in an invalid "
            "academic history."
        )

    if type(index) is not int or index < 0:
        raise ValueError(
            "Transfer index must be a nonnegative integer."
        )

    if index >= len(validated["transfer_courses"]):
        raise IndexError(
            "Transfer record index is out of range."
        )

    updated = deepcopy(validated)

    updated["transfer_courses"][index][
        "equivalency_verified"
    ] = verified

    result = validate_academic_history(updated)

    if result["validation_errors"]:
        raise ValueError(
            "Transfer verification produced "
            "academic-history validation errors."
        )

    return result
