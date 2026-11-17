"""Safe editing helpers for HAWKwarts academic histories."""

from copy import deepcopy

from .transcript_validator import normalize_course, validate_academic_history


EDITABLE_COLLECTIONS = (
    "all_institution_records",
    "transfer_courses",
    "in_progress_courses",
)


def select_course_record(history, collection, index):
    """Return a copy of one course from an authoritative collection."""

    # Reject histories with previously recorded validation errors.
    # Rebuilding may otherwise lose errors from excluded records.
    if not isinstance(history, dict):
        raise ValueError("Academic history must be a dictionary.")

    source_errors = history.get("validation_errors")

    if source_errors:
        raise ValueError(
            "Cannot edit an academic history containing invalid "
            f"course records: {source_errors}"
        )

    validated = validate_academic_history(history)

    if validated["validation_errors"]:
        raise ValueError(
            "Cannot edit an academic history containing invalid "
            f"course records: {validated['validation_errors']}"
        )

    if collection not in EDITABLE_COLLECTIONS:
        raise ValueError(
            f"Invalid editable collection: {collection}"
        )

    if type(index) is not int or index < 0:
        raise ValueError(
            "Course index must be a nonnegative integer."
        )

    records = validated[collection]

    if index >= len(records):
        raise IndexError(
            f"Course index {index} is out of range "
            f"for {collection}."
        )

    return deepcopy(records[index])


EDITABLE_FIELDS = frozenset({
    "code",
    "title",
    "grade",
    "credits",
    "term",
    "level",
})


def apply_course_correction(history, collection, index, changes):
    """Return a newly validated history with one corrected course."""

    if not isinstance(changes, dict) or not changes:
        raise ValueError(
            "Course corrections must be a nonempty dictionary."
        )

    invalid_fields = set(changes) - EDITABLE_FIELDS

    if invalid_fields:
        raise ValueError(
            f"Fields cannot be edited: {sorted(invalid_fields)}"
        )

    # Validate the selection before making any modifications.
    select_course_record(history, collection, index)

    # Work exclusively on a copy of the source history.
    updated = deepcopy(history)
    record = updated[collection][index]

    # Normalize first so equivalent representations compare equally.
    corrected = normalize_course({**record, **changes})

    # Verified equivalency details cannot change without reverification.
    if (
        collection == "transfer_courses"
        and record.get("equivalency_verified") is True
    ):
        protected_fields = {
            "code": "course code",
            "credits": "credits",
            "level": "academic level",
        }

        for field, description in protected_fields.items():
            if corrected[field] != record[field]:
                raise ValueError(
                    f"Cannot change the {description} of a verified "
                    "transfer. Reverification is required."
                )

    # Preserve the course's original classification.
    if corrected["status"] != record["status"]:
        raise ValueError(
            "Course status cannot be changed through corrections."
        )

    updated[collection][index] = corrected

    # Rebuild all derived collections and scheduler eligibility.
    result = validate_academic_history(updated)

    if result["validation_errors"]:
        raise ValueError(
            "Correction produced academic-history validation errors: "
            + "; ".join(result["validation_errors"])
        )

    return result
