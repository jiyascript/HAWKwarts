
"""Read-only access to Banner course and section data."""

import sqlite3
from pathlib import Path

DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "banner_scraper"
    / "advising.db"
)


def get_course_offering(course_id: str, term: str) -> dict:
    """Retrieve Banner details for one course in one semester.

    Args:
        course_id: Course code, for example "CS 487".
        term: Semester, for example "Spring 2027".

    Returns:
        Course information, prerequisites, restrictions,
        and all sections with meeting times and instructors.
    """
    print(f"\n[TOOL] get_course_offering(course_id={course_id}, term={term})")
    course_id = " ".join(course_id.upper().split())
    term = term.strip()

    if not DB_PATH.is_file():
        return {"error": "Banner database not found"}

    with sqlite3.connect(
        f"{DB_PATH.as_uri()}?mode=ro",
        uri=True
    ) as conn:
        conn.row_factory = sqlite3.Row

        offering = conn.execute(
            """
            SELECT c.course_id, c.title,
                   o.term, o.course_description,
                   o.prerequisites, o.general_requirements,
                   o.restrictions, o.mutual_exclusions,
                   o.attributes, o.catalog_entry_url,
                   o.offering_id
            FROM course_offerings o
            JOIN courses c ON c.course_id = o.course_id
            WHERE c.course_id = ? AND o.term = ?
            """,
            (course_id, term)
        ).fetchone()

        if offering is None:
            return {
                "error": "Course offering not found",
                "course_id": course_id,
                "term": term
            }

        result = dict(offering)
        offering_id = result.pop("offering_id")

        sections = conn.execute(
            """
            SELECT *
            FROM sections
            WHERE offering_id = ?
            ORDER BY section
            """,
            (offering_id,)
        ).fetchall()

        result["sections"] = []

        for section in sections:
            item = dict(section)

            meetings = conn.execute(
                """
                SELECT m.days, m.time, m.location,
                       m.schedule_type,
                       GROUP_CONCAT(p.name, ', ') AS instructors
                FROM meetings m
                LEFT JOIN meeting_instructors mi
                    ON mi.meeting_id = m.meeting_id
                LEFT JOIN professors p
                    ON p.professor_id = mi.professor_id
                WHERE m.section_id = ?
                GROUP BY m.meeting_id
                """,
                (item["section_id"],)
            ).fetchall()

            item["meetings"] = [
                dict(meeting) for meeting in meetings
            ]

            result["sections"].append(item)

        result["data_note"] = (
            "Banner database snapshot. Seat counts and "
            "offerings may have changed."
        )

        return result
def get_course_offerings(course_ids: list[str], term: str) -> dict:
    """Look up multiple courses in Banner for a given semester."""
    print(f"\n[TOOL] get_course_offerings(course_ids={course_ids}, term={term})")

    return {
        "term": term,
        "courses": [
            get_course_offering(course_id, term)
            for course_id in course_ids
        ],
    }