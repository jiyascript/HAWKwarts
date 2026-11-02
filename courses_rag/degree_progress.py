
"""Structured data retrieval for degree-progress questions."""

from .requirements_lookup import get_requirements


def get_degree_progress_context(
    program_id: str,
    student_history: dict,
) -> dict:
    """Retrieve complete program requirements and student history."""

    print(
        f"\n[TOOL] get_degree_progress_context("
        f"program_id={program_id})"
    )

    program = get_requirements("program", program_id)

    if program is None:
        return {
            "error": f"Program not found: {program_id}"
        }

    return {
        "program": {
            "program_id": program.get("program_id"),
            "title": program.get("title"),
            "total_credits": program.get("total_credits"),
            "requirements": program.get("requirements", []),
            "credit_constraints": program.get("credit_constraints", []),
            "notes": program.get("notes", []),
            "url": program.get("url"),
        },
        "student": {
            "completed_courses": student_history.get(
                "completed_courses", []
            ),
            "transfer_courses": student_history.get(
                "transfer_courses", []
            ),
            "in_progress_courses": student_history.get(
                "in_progress_courses", []
            ),
            "all_institution_records": student_history.get(
                "all_institution_records", []
            ),
        },
        "warnings": [
            "This is a preliminary degree-progress comparison.",
            "Transfer equivalencies and course substitutions require verification.",
            "In-progress courses do not count as completed.",
            "The transcript may not reflect recent coursework.",
        ],
    }
