import json
from pathlib import Path

def export_failure_json(
    output_path,
    status,
    message,
    candidate_courses,
    unavailable_courses
):
    output = {
        "schema_version": "1.0",
        "status": status,
        "message": message,
        "candidate_courses": candidate_courses,
        "unavailable_courses": unavailable_courses,
        "semesters": [],
        "total_planned_credits": 0,
        "notes": [
            "No valid semester plan was generated.",
            "The schedule is a demonstration, not a verified degree audit."
        ]
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2)

    return output_path