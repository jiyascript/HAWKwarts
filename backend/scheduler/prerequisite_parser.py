import re


COURSE_PATTERN = r"[A-Z]{2,5}\s+\d{3}"


def parse_prerequisites(prerequisite_text, general_requirements):
    """
    Extract prerequisite information from Banner catalog fields.

    This initial parser supports simple course requirements and
    OR alternatives. Complex expressions are marked unverified.
    """

    prerequisite_text = (prerequisite_text or "").strip()
    general_requirements = (general_requirements or "").strip()

    # Prefer detailed requirements when available.
    requirement = general_requirements or prerequisite_text

    if not requirement:
        return {
            "status": "none_listed",
            "courses": [],
            "logic": None,
            "raw": requirement
        }

    # Remove Banner-specific annotations.
    cleaned = re.sub(
        r"Course or Test:\s*",
        "",
        requirement,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"Minimum Grade of\s+[A-F][+-]?",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"May not be taken concurrently\.",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    courses = re.findall(COURSE_PATTERN, cleaned)

    # Do not interpret unknown requirement formats as valid.
    if not courses:
        return {
            "status": "unverified",
            "courses": [],
            "logic": None,
            "raw": requirement
        }

    # Parentheses or AND conditions require a richer parser.
    if re.search(r"\band\b", cleaned, re.IGNORECASE):
        return {
            "status": "unverified",
            "courses": courses,
            "logic": "complex",
            "raw": requirement
        }

    # Remove grouping parentheses for simple OR expressions.
    cleaned = cleaned.replace("(", "").replace(")", "").strip()

    simple_or_pattern = (
        rf"^\s*{COURSE_PATTERN}"
        rf"(?:\s+or\s+{COURSE_PATTERN})*\s*$"
    )

    if not re.fullmatch(simple_or_pattern, cleaned, re.IGNORECASE):
        return {
            "status": "unverified",
            "courses": courses,
            "logic": "complex",
            "raw": requirement
        }

    return {
        "status": "parsed",
        "courses": courses,
        "logic": "OR" if len(courses) > 1 else "SINGLE",
        "raw": requirement
    }


def extract_prerequisite_details(general_requirements):
    """
    Extract course-specific grade and concurrency requirements.

    This function extracts metadata only.
    It does not evaluate eligibility or AND/OR logic.
    """

    if not general_requirements:
        return []

    pattern = (
        r"Course or Test:\s*"
        r"([A-Z]{2,5}\s+\d{3})"
        r"(?:\s+Minimum Grade of\s+([A-F][+-]?))?"
        r"(\s+May not be taken concurrently\.)?"
    )

    matches = re.finditer(
        pattern,
        general_requirements,
        flags=re.IGNORECASE
    )

    details = []

    for match in matches:
        details.append({
            "code": match.group(1),
            "minimum_grade": match.group(2),
            "concurrent_allowed": match.group(3) is None
        })

    return details