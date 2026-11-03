"""
Retrieves all available sections for each requested course, generates section combinations, compares meetings between pairs, rejects combinations that overlap
"""
from datetime import datetime
from itertools import product

VALID_DAYS = set("MTWRFSU")

def parse_days(days: str) -> set[str] | None:
    days = (days or "").strip().upper()
    if not days or any(day not in VALID_DAYS for day in days):
        return None
    return set(days)

def to_minutes(value: str) -> int:
    parsed = datetime.strptime(value, "%I:%M %p")
    return parsed.hour * 60 + parsed.minute
def parse_time_range(value: str) -> tuple[int, int] | None:
    """Convert Banner time ranges to minutes since midnight."""
    try:
        start, end = value.split(" - ", 1)
        def minutes(text):
            t = datetime.strptime(text.strip(), "%I:%M %p")
            return t.hour * 60 + t.minute

        start_min, end_min = minutes(start), minutes(end)
        if end_min <= start_min:
            return None
        return start_min, end_min

    except (ValueError, AttributeError):
        return None


def check_meeting_conflict(a: dict, b: dict) -> dict:
    """Compare two individual Banner meeting records."""
    days_a = parse_days(a.get("days", ""))
    days_b = parse_days(b.get("days", ""))

    time_a = parse_time_range(a.get("time", ""))
    time_b = parse_time_range(b.get("time", ""))

    if days_a is None or days_b is None:
        return {"status": "unknown", "reason": "Missing meeting days"}

    if time_a is None or time_b is None:
        return {"status": "unknown", "reason": "Missing meeting time"}

    common_days = sorted(days_a & days_b)

    if not common_days:
        return {"status": "no_conflict"}

    start_a, end_a = time_a
    start_b, end_b = time_b

    if start_a < end_b and start_b < end_a:
        return {
            "status": "conflict",
            "days": common_days,
            "overlap_start": max(start_a, start_b),
            "overlap_end": min(end_a, end_b),
        }
    return {"status": "no_conflict"}

def check_section_conflict(section_a: dict, section_b: dict) -> dict:
    """Compare every meeting of two course sections."""

    meetings_a = section_a.get("meetings", [])
    meetings_b = section_b.get("meetings", [])
    if not meetings_a or not meetings_b:
        return {
            "status": "unknown",
            "reason": "One or both sections have no meeting records",
        }

    conflicts = []
    unknowns = []
    for meeting_a in meetings_a:
        for meeting_b in meetings_b:
            result = check_meeting_conflict(meeting_a, meeting_b)
            if result["status"] == "conflict":
                conflicts.append(result)
            elif result["status"] == "unknown":
                unknowns.append(result)

    if conflicts:
        return {"status": "conflict", "details": conflicts}

    if unknowns:
        return {"status": "unknown", "details": unknowns}

    return {"status": "no_conflict"}



def find_compatible_sections(
    course_ids: list[str],
    term: str,
    max_results: int = 10,
) -> dict:
    """Find time-compatible section combinations.

    Multi-component courses are treated as provisional because
    Banner does not provide explicit section-linkage rules.
    """
    from itertools import product
    from .banner_lookup import get_course_offerings

    data = get_course_offerings(course_ids, term)
    course_map = {
        course["course_id"]: course
        for course in data.get("courses", [])
        if "error" not in course
    }

    missing_courses = [
        course_id for course_id in course_ids
        if course_id not in course_map
        or not course_map[course_id].get("sections")
    ]

    if missing_courses:
        return {
            "status": "missing_courses",
            "missing_courses": missing_courses,
        }

    # Each course has options. An option may contain multiple
    # sections, e.g. one lecture and one lab.
    course_options = []

    for course_id in course_ids:
        components = get_section_components(course_map[course_id])

        # Choose one section per component type.
        options = list(product(*components.values()))
        course_options.append(options)

    compatible = []
    unverified = []

    for chosen_options in product(*course_options):
        # Flatten sections across all selected courses.
        selected_sections = [
            (course_id, section)
            for course_id, option in zip(course_ids, chosen_options)
            for section in option
        ]

        has_unknown_time = False
        has_conflict = False

        for i, (_, section_a) in enumerate(selected_sections):
            for _, section_b in selected_sections[i + 1:]:
                result = check_section_conflict(section_a, section_b)

                if result["status"] == "conflict":
                    has_conflict = True
                    break

                if result["status"] == "unknown":
                    has_unknown_time = True

            if has_conflict:
                break

        if has_conflict:
            continue

        has_unverified_linkage = any(
            len(get_section_components(course_map[course_id])) > 1
            for course_id in course_ids
        )

        schedule = {
            "sections": [
                {
                    "course_id": course_id,
                    "section": section.get("section"),
                    "crn": section.get("crn"),
                    "schedule_type": section.get("schedule_type"),
                    "campus": section.get("campus"),
                    "meetings": section.get("meetings", []),
                }
                for course_id, section in selected_sections
            ],
            "time_status": (
                "unknown" if has_unknown_time else "no_conflict"
            ),
            "enrollment_status": (
                "unverified_linkage"
                if has_unverified_linkage
                else "not_checked"
            ),
        }

        if has_unknown_time:
            unverified.append(schedule)
        else:
            compatible.append(schedule)

        if len(compatible) + len(unverified) >= max_results:
            break

    return {
        "term": term,
        "requested_courses": course_ids,
        "compatible_schedules": compatible,
        "unverified_schedules": unverified,
        "count": len(compatible),
        "note": (
            "No known meeting-time conflicts in compatible_schedules. "
            "Lecture/lab enrollment linkage is not verified. "
            "Seat availability and registration eligibility are not guaranteed."
        ),
    }

def get_section_components(course: dict) -> dict:
    """Group Banner sections by their section-level schedule type."""
    components = {}

    for section in course.get("sections", []):
        component_type = (
            section.get("schedule_type") or "Unknown"
        ).strip().lower()

        components.setdefault(component_type, []).append(section)

    return components