
"""Resolve structured degree requirements against student history."""

import re
import json
from pathlib import Path

# These rules must be verified against the applicable
# academic catalog before being used in production.

def normalize_course(course_id: str) -> str:
    """Normalize course IDs such as cs331 and CS 331."""
    text = str(course_id or "").strip().upper()
    match = re.fullmatch(r"([A-Z]{2,6})\s*(\d{3,4}[A-Z]?)", text)

    if match:
        return f"{match.group(1)} {match.group(2)}"

    return text


def _course_codes(records: list) -> set[str]:
    """Extract course codes from strings or transcript dictionaries."""
    codes = set()

    for record in records:
        if isinstance(record, str):
            code = record
        elif isinstance(record, dict):
            code = (
                record.get("course")
                or record.get("course_id")
                or record.get("code")
            )
        else:
            continue

        if code:
            codes.add(normalize_course(code))

    return codes

def load_program_pathways(program_id: str) -> list:
    path = Path(__file__).with_name("program_pathways.json")

    if not path.is_file():
        return []

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return data.get(program_id, {}).get("requirements", [])

def resolve_requirements(program: dict, student_history: dict) -> dict:
    """Identify remaining mandatory courses and unresolved requirements."""

    # Courses completed at the institution.
    completed = _course_codes(
        student_history.get("completed_courses", [])
    )

    # Only count transfer courses with verified equivalencies.
    verified_transfers = _course_codes([
        course
        for course in student_history.get("transfer_courses", [])
        if isinstance(course, dict)
        and course.get("equivalency_verified") is True
    ])

    # Both completed courses and verified transfer equivalents
    # can satisfy degree requirements.
    completed.update(verified_transfers)

    in_progress = _course_codes(
        student_history.get("in_progress_courses", [])
    )

    # Load alternative pathways for this degree program.
    pathways = load_program_pathways(
        program.get("program_id")
    )

    satisfied_pathways = []
    pending_pathways = []
    unsatisfied_pathways = []
    replaced_courses = set()

    for pathway in pathways:
        options = [
            [normalize_course(code) for code in option]
            for option in pathway.get("options", [])
        ]

        if not options or any(not option for option in options):
            raise ValueError(
                f"Invalid pathway: {pathway.get('name')}"
            )

        replaced_courses.update(
            normalize_course(code)
            for code in pathway.get("replaces", [])
        )

        # A pathway is satisfied if all its courses
        # appear in the completed academic history.
        if any(
            all(code in completed for code in option)
            for option in options
        ):
            satisfied_pathways.append(pathway["name"])

        # A pathway is pending if its courses are
        # completed or currently in progress.
        elif any(
            all(
                code in completed or code in in_progress
                for code in option
            )
            for option in options
        ):
            pending_pathways.append(pathway["name"])

        # Otherwise, at least one pathway still
        # needs additional coursework.
        
        else:
            # Identify pathways the student has already started.
            started_options = [
                option
                for option in options
                if any(code in completed for code in option)
            ]

            # Prefer continuing an existing sequence.
            # Otherwise, leave the pathway undecided.
            recommended = (
                min(
                    started_options,
                    key=lambda option: sum(
                        code not in completed for code in option
                    )
                )
                if started_options
                else None
            )

            unsatisfied_pathways.append({
                "name": pathway["name"],
                "options": options,
                "recommended_pathway": recommended,
                "remaining_courses": (
                    [
                        code for code in recommended
                        if code not in completed
                        and code not in in_progress
                    ]
                    if recommended
                    else []
                ),
                "reason": (
                    "Continue an already-started course sequence"
                    if recommended
                    else "No pathway started; selection required"
                )
            })

    remaining_courses = []

    in_progress_requirements = []
    unresolved_requirements = []
    choice_groups = []

    for group in program.get("requirements", []):
        group_name = group.get("name", "Unnamed requirement")
        items = group.get("items", [])

        if not items:
            unresolved_requirements.append({
                "group": group_name,
                "reason": "No structured requirement items available",
            })
            continue

        for item in items:
            item_type = item.get("type")

            if item_type == "course":
                code = normalize_course(item.get("course", ""))

                if not code:
                    unresolved_requirements.append({
                        "group": group_name,
                        "type": item_type,
                        "item": item,
                        "reason": "Missing course code",
                    })
                    continue

                if code in replaced_courses:
                    continue

                if code in completed:
                    continue

                if code in in_progress:
                    in_progress_requirements.append(code)
                    continue

                remaining_courses.append(code)

            elif item_type in ("one_of", "choose"):
                options = [
                    normalize_course(
                        option.get("course", "")
                        if isinstance(option, dict)
                        else option
                    )
                    for option in item.get("options", [])
                ]

                options = [code for code in options if code]

                required_count = (
                    1 if item_type == "one_of"
                    else item.get("count", 1)
                )

                if (
                    not isinstance(required_count, int)
                    or isinstance(required_count, bool)
                    or required_count < 1
                    or not options
                    or required_count > len(set(options))
                ):
                    unresolved_requirements.append({
                        "group": group_name,
                        "type": item_type,
                        "item": item,
                        "reason": "Invalid or incomplete choice group",
                    })
                    continue

                options = list(dict.fromkeys(options))

                completed_count = sum(
                    code in completed for code in options
                )

                in_progress_count = sum(
                    code in in_progress and code not in completed
                    for code in options
                )

                remaining_count = max(
                    0, 
                    required_count - completed_count - in_progress_count
                )

                pending_count = min(
                    in_progress_count,
                    max(0, required_count - completed_count)
                )

                if remaining_count > 0 or pending_count > 0:
                    choice_groups.append({
                        "group": group_name,
                        "type": item_type,
                        "options": [
                            code for code in options
                            if code not in completed
                            and code not in in_progress
                        ],
                        "required_count": required_count,
                        "remaining_count": remaining_count,
                        "in_progress_count": pending_count,
                        "credits_required": item.get(
                            "credits_required",
                            item.get("credits")
                        ),
                    })

            else:
                unresolved_requirements.append({
                    "group": group_name,
                    "type": item_type,
                    "item": item,
                })

    return {
        "program_id": program.get("program_id"),
        "remaining_courses": list(dict.fromkeys(remaining_courses)),
        "in_progress_requirements": list(
            dict.fromkeys(in_progress_requirements)
        ),
        "unresolved_requirements": unresolved_requirements,
        "status": "preliminary",
        "choice_groups": choice_groups,
        "satisfied_pathways": satisfied_pathways,
        "pending_pathways": pending_pathways,
        "unsatisfied_pathways": unsatisfied_pathways,
    }
