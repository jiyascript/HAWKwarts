"""convert conflict-resolver schedules into the frontend JSON"""
import json
from pathlib import Path
from .schedule_conflicts import parse_days, parse_time_range

FRONTENDDAYS = "MTWRF"

def schedule_to_frontend(schedule: dict, term: str) -> dict:
    """Convert one time-compatible schedule into frontend JSON."""

    if schedule.get("time_status") != "no_conflict":
        raise ValueError("Cannot export a schedule with unverified times.")

    courses = []

    for section in schedule["sections"]:
        meetings = section.get("meetings", [])

        if not meetings:
            raise ValueError(
                f"{section['course_id']}: missing meeting records."
            )

        for meeting in meetings:
            days = parse_days(meeting.get("days", ""))
            time_range = parse_time_range(meeting.get("time", ""))

            if days is None or time_range is None:
                raise ValueError(f"{section['course_id']}: unknown meeting time.")

            if not days.issubset(set(FRONTENDDAYS)):
                raise ValueError(f"{section['course_id']}: weekend meetings are not supported by the current frontend.")

            start, end = time_range

            def format_time(minutes):
                return f"{minutes // 60:02d}:{minutes % 60:02d}"

            courses.append({
                "code": section["course_id"],
                "title": section.get("schedule_type") or "",
                "days": [
                    day for day in FRONTENDDAYS if day in days
                ],
                "start": format_time(start),
                "end": format_time(end),
                "location": meeting.get("location") or "TBA",
                "section": section.get("section"),
                "crn": section.get("crn"),
                "schedule_type": section.get("schedule_type"),
            })

    if not courses:
        raise ValueError("Schedule has no meetings to export.")

    return {
        "term": term,
        "courses": courses,
        "time_status": schedule["time_status"],
        "enrollment_status": schedule.get("enrollment_status"),
        "note": (
            "Meeting times checked against the Banner snapshot. "
            "Enrollment eligibility, lecture/lab linkage, "
            "and seat availability are not verified."
        ),
    }


def save_schedule_json(data: dict, output_path: str) -> None:
    Path(output_path).write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )
