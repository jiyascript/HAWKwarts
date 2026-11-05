"""
The schedule shown on the website. The agent changes it through the tool
functions at the bottom, and ask_agent() publishes the result so the API
can send it to the page.
"""
import re
from contextvars import ContextVar

from .schedule_adapter import schedule_to_frontend
from .schedule_conflicts import find_compatible_sections

last_schedule: ContextVar = ContextVar("last_schedule", default=None)

# find_compatible_sections tries combinations, so keep the course list short
MAX_COURSES = 7

# One schedule for the whole server for now (no per-student sessions yet)
_state = {"term": None, "courses": [], "crns": [], "payload": None}


def begin_turn():
    """Call at the start of each question so an old update isn't sent twice."""
    _state["payload"] = None


def take_update():
    """The schedule payload if it changed during this question, else None."""
    payload = _state["payload"]
    _state["payload"] = None
    return payload


# ----- Helpers -----

def _normalize(course_id):
    """'cs331' or 'cs 331' -> 'CS 331'."""
    text = (course_id or "").strip()
    match = re.fullmatch(r"([A-Za-z]{2,6})\s*(\d{3,4}[A-Za-z]?)", text)
    if match:
        return f"{match.group(1).upper()} {match.group(2).upper()}"
    return text.upper()


def _meetings_for_page(data):
    """The adapter gives one entry per meeting with a list of days;
    the weekly grid wants one block per day."""
    blocks = []

    for item in data["courses"]:
        kind = (item.get("schedule_type") or "").lower()
        code = item["code"] + (" Lab" if "lab" in kind else "")
        location = "" if item.get("location") in (None, "TBA") else item["location"]

        for day in item["days"]:
            blocks.append({
                "code": code,
                "title": code,
                "day": day,
                "start": item["start"],
                "end": item["end"],
                "location": location,
            })

    return blocks


def _describe(section):
    """What the agent sees about one chosen section."""
    return {
        "course_id": section["course_id"],
        "section": section.get("section"),
        "crn": section.get("crn"),
        "schedule_type": section.get("schedule_type"),
        "meetings": [
            {key: meeting.get(key)
             for key in ("days", "time", "location", "building", "room")
             if meeting.get(key)}
            for meeting in section.get("meetings", [])
        ],
    }


def _apply(term, courses, previous_crns):
    """Pick sections for these courses, save them, and return what the agent
    should tell the student. Nothing is saved if this fails."""
    if len(courses) > MAX_COURSES:
        return {"error": f"Too many courses (maximum {MAX_COURSES}).", "schedule_changed": False}

    result = find_compatible_sections(courses, term, max_results=50)

    if result.get("status") == "missing_courses":
        return {
            "error": "Some of these courses have no sections in this term.",
            "missing_courses": result["missing_courses"],
            "schedule_changed": False,
        }

    options = result["compatible_schedules"]
    if not options:
        if result["unverified_schedules"]:
            return {
                "error": "Every combination includes a section with a TBA or missing "
                         "meeting time, so a schedule with confirmed times can't be shown.",
                "schedule_changed": False,
            }
        return {"error": "Every combination of sections has a meeting-time conflict.",
                "schedule_changed": False}

    def kept(schedule):
        return sum(1 for section in schedule["sections"] if section["crn"] in previous_crns)

    # Try the combinations that keep the student's current sections first;
    # the adapter rejects some (for example weekend meetings), so move on if it does.
    picked = None
    data = None
    last_error = ""
    for option in sorted(options, key=kept, reverse=True):
        try:
            data = schedule_to_frontend(option, term)
            picked = option
            break
        except ValueError as exc:
            last_error = str(exc)

    if picked is None:
        return {"error": last_error or "This schedule can't be displayed.",
                "schedule_changed": False}

    _state["term"] = term
    _state["courses"] = courses
    _state["crns"] = [section["crn"] for section in picked["sections"]]
    _state["payload"] = {
        "term": term,
        "meetings": _meetings_for_page(data),
        "time_status": data["time_status"],
        "enrollment_status": data["enrollment_status"],
    }

    return {
        "schedule_changed": True,
        "term": term,
        "courses": courses,
        "sections": [_describe(section) for section in picked["sections"]],
        "time_status": data["time_status"],
        "enrollment_status": data["enrollment_status"],
        "note": "The schedule panel on the website now shows this schedule. " + data["note"],
    }


# ----- Tools the agent can call -----

def show_sample_schedule(term: str, course_ids: list[str]) -> dict:
    """Build a weekly class schedule for one semester from the given courses
    and show it in the student's schedule panel, replacing any schedule already
    shown. Use this when the student asks to see, build, or preview a schedule.
    The term looks like 'Spring 2027' and course ids like 'CS 331'.
    """
    print(f"\n[TOOL] show_sample_schedule(term={term}, course_ids={course_ids})")
    courses = list(dict.fromkeys(_normalize(c) for c in course_ids))
    return _apply(term, courses, previous_crns=[])


def add_course_to_schedule(course_id: str, term: str = "") -> dict:
    """Add one course to the schedule shown in the student's panel and show the
    updated schedule. Leave term empty to use the semester already shown.
    """
    print(f"\n[TOOL] add_course_to_schedule(course_id={course_id}, term={term})")
    code = _normalize(course_id)
    term = term or _state["term"]

    if not term:
        return {"error": "No schedule is shown yet. Use show_sample_schedule with a semester.",
                "schedule_changed": False}
    if _state["term"] and term != _state["term"]:
        return {"error": f"The schedule shown is for {_state['term']}. "
                         f"Use show_sample_schedule to start one for {term}.",
                "schedule_changed": False}
    if code in _state["courses"]:
        return {"error": f"{code} is already in the schedule.", "schedule_changed": False}

    return _apply(term, _state["courses"] + [code], _state["crns"])


def remove_course_from_schedule(course_id: str) -> dict:
    """Remove one course from the schedule shown in the student's panel and
    show the updated schedule."""
    print(f"\n[TOOL] remove_course_from_schedule(course_id={course_id})")
    code = _normalize(course_id)

    if code not in _state["courses"]:
        return {"error": f"{code} is not in the schedule.",
                "courses_in_schedule": _state["courses"],
                "schedule_changed": False}

    remaining = [c for c in _state["courses"] if c != code]
    if not remaining:
        return clear_schedule()

    return _apply(_state["term"], remaining, _state["crns"])


def show_current_schedule() -> dict:
    """Show the student's current schedule again in the schedule panel."""
    print("\n[TOOL] show_current_schedule()")
    if not _state["courses"]:
        return {"error": "No schedule is shown yet."}
    return _apply(_state["term"], _state["courses"], _state["crns"])


def clear_schedule() -> dict:
    """Remove every course and clear the student's schedule panel."""
    print("\n[TOOL] clear_schedule()")
    _state.update(term=None, courses=[], crns=[])
    _state["payload"] = {"term": "", "meetings": []}
    return {"schedule_changed": True, "note": "The schedule panel was cleared."}