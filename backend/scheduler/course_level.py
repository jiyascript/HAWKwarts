import re

def get_course_level(course_code):
    """
    Classify a course by its numeric course level.

    This is a planning classification, not a determination
    of degree applicability or graduate-credit eligibility.
    """
    if not isinstance(course_code, str):
        return "unknown"

    match = re.fullmatch(
        r"[A-Za-z]+\s+(\d{3})(?:[A-Za-z])?",
        course_code.strip()
    )

    if not match:
        return "unknown"

    course_number = int(match.group(1))

    if 100 <= course_number <= 499:
        return "undergraduate"

    if 500 <= course_number <= 999:
        return "graduate"

    return "unknown"
