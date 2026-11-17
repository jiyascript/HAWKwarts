
"""Read-only access to Banner course and section data."""

import re
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


def _name_tokens(name):
    return re.findall(r"[a-z]+", (name or "").lower())


_TITLES = {"prof", "professor", "dr", "doctor", "mr", "mrs", "ms"}


def _same_instructor(query_tokens, db_name):
    """Does Banner's name ("Matthew J Bauer") match what was asked ("Matthew Bauer",
    "Prof. Bauer")? Last names must match; a first name, when given, must match exactly or
    as a nickname prefix (Matt / Matthew). Banner's "Last, First" order is also accepted."""
    db = _name_tokens(db_name)
    if not db or not query_tokens:
        return False
    q_first, q_last = (query_tokens[0], query_tokens[-1]) if len(query_tokens) > 1 else (None, query_tokens[0])
    for first, last in ((db[0], db[-1]), (db[-1], db[0])):
        if last != q_last:
            continue
        if q_first is None:
            return True
        short, long_ = sorted((first, q_first), key=len)
        if first == q_first or (len(short) >= 3 and long_.startswith(short)):
            return True
    return False


def get_instructor_offerings(instructor_name: str, term: str = "") -> dict:
    """Find the course sections a specific instructor (professor) teaches in Banner.

    Use this when a student asks what classes or sections a named professor is
    teaching. It looks the instructor up by name, so no course code is needed.

    Args:
        instructor_name: The professor's name, for example "Matthew Bauer".
        term: Semester, for example "Fall 2026". Leave empty to list every term
            in the Banner snapshot.

    Returns:
        The matched instructor name(s) and, for each course, its sections with
        CRN, meeting days, times, locations and all instructors.
    """
    print(f"\n[TOOL] get_instructor_offerings(instructor_name={instructor_name}, term={term})")
    tokens = [t for t in _name_tokens(instructor_name) if t not in _TITLES]
    term = (term or "").strip()

    if not tokens:
        return {"error": "No instructor name was given"}
    if not DB_PATH.is_file():
        return {"error": "Banner database not found"}

    with sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row

        professors = [
            dict(row)
            for row in conn.execute("SELECT professor_id, name FROM professors")
            if _same_instructor(tokens, row["name"])
        ]
        if not professors:
            return {
                "error": "No instructor with that name was found in the Banner data. "
                         "This does not mean they are not on the faculty; they may not "
                         "be teaching in the terms Banner covers, or the name may be "
                         "spelled differently.",
                "instructor_query": instructor_name,
            }

        names = sorted({p["name"] for p in professors})
        if len(tokens) == 1 and len(names) > 1:
            return {
                "error": "More than one instructor matches that last name. Ask which one is meant.",
                "matches": names,
            }

        marks = ",".join("?" for _ in professors)
        params = [p["professor_id"] for p in professors]
        sql = f"""
            SELECT DISTINCT c.course_id, c.title, o.term, s.section_id
            FROM meeting_instructors mi
            JOIN meetings m ON m.meeting_id = mi.meeting_id
            JOIN sections s ON s.section_id = m.section_id
            JOIN course_offerings o ON o.offering_id = s.offering_id
            JOIN courses c ON c.course_id = o.course_id
            WHERE mi.professor_id IN ({marks})
        """
        if term:
            sql += " AND o.term = ?"
            params.append(term)
        sql += " ORDER BY o.term, c.course_id, s.section_id"
        rows = conn.execute(sql, params).fetchall()

        if not rows:
            terms = [
                r["term"] for r in conn.execute(
                    f"""SELECT DISTINCT o.term
                        FROM meeting_instructors mi
                        JOIN meetings m ON m.meeting_id = mi.meeting_id
                        JOIN sections s ON s.section_id = m.section_id
                        JOIN course_offerings o ON o.offering_id = s.offering_id
                        WHERE mi.professor_id IN ({marks})""",
                    [p["professor_id"] for p in professors],
                )
            ]
            return {
                "instructors": names,
                "term": term or None,
                "courses": [],
                "message": "No sections found for this instructor in that term.",
                "terms_with_sections": sorted(terms),
            }

        courses = {}
        for row in rows:
            key = (row["term"], row["course_id"])
            entry = courses.setdefault(
                key, {"course_id": row["course_id"], "title": row["title"], "term": row["term"], "sections": []}
            )
            section = dict(conn.execute("SELECT * FROM sections WHERE section_id = ?", (row["section_id"],)).fetchone())
            meetings = conn.execute(
                """
                SELECT m.days, m.time, m.location, m.schedule_type,
                       GROUP_CONCAT(p.name, ', ') AS instructors
                FROM meetings m
                LEFT JOIN meeting_instructors mi ON mi.meeting_id = m.meeting_id
                LEFT JOIN professors p ON p.professor_id = mi.professor_id
                WHERE m.section_id = ?
                GROUP BY m.meeting_id
                """,
                (row["section_id"],),
            ).fetchall()
            section["meetings"] = [dict(m) for m in meetings]
            entry["sections"].append(section)

        return {
            "instructors": names,
            "term": term or None,
            "courses": list(courses.values()),
            "data_note": "Banner database snapshot. Seat counts and offerings may have changed.",
        }
