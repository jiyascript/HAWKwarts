import re
from .prerequisite_expression import parse_expression

COURSE_PATTERN = r"[A-Z]{2,5}\s+\d{3}"

def extract_expression_courses(expression):
    """
    Extract individual course codes from an expression tree.

    Course ranges are deliberately excluded because they
    represent multiple possible courses, not one exact code.
    """
    if expression["type"] == "course":
        return [expression["code"]]

    if expression["type"] in (
        "course_range",
        "placement_requirement"
    ):
        return []

    courses = []

    for child in expression.get("children", []):
        courses.extend(extract_expression_courses(child))

    return courses

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
        r"Minimum Grade of\s+(?:[A-F][+-]?|S)\b",
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

    cleaned = re.sub(
        r"May be taken concurrently\.",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    # Validate course-based AND/OR expressions using
    # the existing expression-tree parser.
    try:
        expression_tree = parse_expression(cleaned)
    except ValueError:
        return {
            "status": "unverified",
            "courses": [],
            "logic": "complex",
            "raw": requirement
        }

    # Extract exact course codes without confusing
    # course ranges with individual courses.
    courses = extract_expression_courses(expression_tree)

    if expression_tree["type"] in ("AND", "OR", "course_range", "placement_requirement"):
        return {
            "status": "parsed",
            "courses": courses,
            "logic": expression_tree["type"],
            "expression": expression_tree,
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
        r"(?:\s+to\s+(\d{3}))?"
        r"(?:\s+Minimum Grade of\s+((?:[A-F][+-]?|S)\b))?"
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
            "code": match.group(1).upper(),
            "range_end": (
                int(match.group(2))
                if match.group(2) is not None
                else None
            ),
            "minimum_grade": match.group(3),
            "concurrent_allowed": match.group(4) is None
        })

    return details