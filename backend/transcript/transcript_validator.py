
import re


# =========================================================
# HAWKwarts Shared Transcript Validator
# =========================================================

PASSING_GRADES = {
    "A", "A-", "B+", "B", "B-",
    "C+", "C", "C-", "D+", "D", "D-",
    "P", "S"
}

VALID_GRADES = PASSING_GRADES | {
    "F", "W", "I", "IP", "AU", "NR", "TR"
}

VALID_STATUSES = {
    "institution",
    "transfer",
    "in_progress"
}

VALID_LEVELS = {"UG", "GR"}

COURSE_CODE_PATTERN = re.compile(
    r"^([A-Z]{2,6})\s*(\d{3,4}[A-Z]?)$"
)

TERM_PATTERN = re.compile(
    r"^(Spring|Summer|Fall|Winter)\s+\d{4}$",
    re.IGNORECASE
)


# =========================================================
# 1. Normalize and validate individual courses
# =========================================================

def normalize_course(course):

    if not isinstance(course, dict):
        raise ValueError("Course must be a dictionary.")

    raw_code = str(course.get("code") or "").upper().strip()
    match = COURSE_CODE_PATTERN.fullmatch(raw_code)

    if not match:
        raise ValueError(
            f"Invalid course code: {raw_code}. Example: CS 331"
        )

    code = f"{match.group(1)} {match.group(2)}"

    title = " ".join(
        str(course.get("title") or "").split()
    )

    if not title:
        raise ValueError(f"Missing title for {code}.")

    try:
        credits = float(course.get("credits"))
    except (TypeError, ValueError):
        raise ValueError(f"Invalid credits for {code}.")

    if not 0 < credits <= 20:
        raise ValueError(
            f"Credits must be greater than 0 and at most 20 for {code}."
        )

    status = str(
        course.get("status") or ""
    ).strip().lower()

    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status for {code}: {status}"
        )

    grade = str(
        course.get("grade") or ""
    ).strip().upper()

    level = str(
        course.get("level") or ""
    ).strip().upper()

    if level and level not in VALID_LEVELS:
        raise ValueError(
            f"Invalid level for {code}: {level}"
        )

    term = " ".join(
        str(course.get("term") or "").split()
    )

    if term and not TERM_PATTERN.fullmatch(term):
        raise ValueError(
            f"Invalid term for {code}: {term}. "
            "Example: Fall 2025"
        )

    if term:
        season, year = term.split()
        term = f"{season.capitalize()} {year}"

    if status == "transfer":
        if grade not in ("", "TR"):
            raise ValueError(
                f"Transfer course {code} must use grade TR."
            )
        grade = "TR"

    elif status == "in_progress":
        if grade not in ("", "IP"):
            raise ValueError(
                f"In-progress course {code} cannot have "
                "a final grade."
            )
        grade = None

    else:
        if grade not in VALID_GRADES - {"TR", "IP"}:
            raise ValueError(
                f"Invalid institution grade for {code}: {grade}"
            )

    return {
        "code": code,
        "title": title,
        "grade": grade,
        "credits": credits,
        "term": term or None,
        "level": level or None,
        "status": status
    }


# =========================================================
# 2. Validate a list of course records
# =========================================================

def validate_courses(courses):

    valid_courses = []
    errors = []

    for index, course in enumerate(courses, start=1):
        try:
            normalized = normalize_course(course)
            valid_courses.append(normalized)

        except ValueError as error:
            errors.append({
                "record": index,
                "error": str(error)
            })

    return valid_courses, errors


# =========================================================
# 3. Build academic history JSON
# =========================================================

def build_academic_history(courses):

    normalized, errors = validate_courses(courses)

    completed = [
        course for course in normalized
        if (
            course["status"] == "institution"
            and course["grade"] in PASSING_GRADES
        )
    ]

    transfer = [
        course for course in normalized
        if course["status"] == "transfer"
    ]

    in_progress = [
        course for course in normalized
        if course["status"] == "in_progress"
    ]

    institution_records = [
        course for course in normalized
        if course["status"] == "institution"
    ]

    scheduler_codes = sorted({
        course["code"]
        for course in completed + transfer
    })

    warnings = [
        "Completion is provisional. Verify grades, repeated "
        "courses, transfer equivalencies, and degree requirements "
        "before scheduling."
    ]

    # Detect courses appearing in more than one status
    statuses_by_code = {}

    for course in normalized:
        statuses_by_code.setdefault(
            course["code"], set()
        ).add(course["status"])

    for code, statuses in statuses_by_code.items():
        if len(statuses) > 1:
            warnings.append(
                f"{code} appears in multiple categories: "
                f"{', '.join(sorted(statuses))}. "
                "Review whether these represent distinct attempts "
                "or different course topics."
            )

    # Detect possible co-terminal or duplicate records
    seen = set()

    for course in normalized:
        key = (
            course["code"],
            course["term"],
            course["status"]
        )

        if key in seen:
            warnings.append(
                f"{course['code']} has multiple records in "
                f"{course['term'] or 'an unspecified term'}. "
                "Review UG/GR co-terminal credit or duplicates."
            )

        seen.add(key)

    return {
        "completed_courses": completed,
        "transfer_courses": transfer,
        "in_progress_courses": in_progress,
        "all_institution_records": institution_records,
        "scheduler_course_codes": scheduler_codes,
        "warnings": warnings,
        "validation_errors": errors
    }


# =========================================================
# 4. Validate complete academic history
# =========================================================

def validate_academic_history(history):

    if not isinstance(history, dict):
        raise ValueError(
            "Academic history must be a dictionary."
        )

    required_keys = [
        "completed_courses",
        "transfer_courses",
        "in_progress_courses",
        "all_institution_records",
        "scheduler_course_codes"
    ]

    missing = [
        key for key in required_keys
        if key not in history
    ]

    if missing:
        raise ValueError(
            f"Missing academic history fields: {missing}"
        )

    # Reconstruct from the non-overlapping source collections.
    # Completed courses are already part of institution records.
    all_courses = (
        history["all_institution_records"]
        + history["transfer_courses"]
        + history["in_progress_courses"]
    )

    return build_academic_history(all_courses)
