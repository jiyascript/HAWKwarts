from backend.scheduler.requirement_resolver import (
    resolve_requirements
)

from backend.scheduler.pathway_scheduler import (
    prepare_pathway_options
)


program = {
    "program_id": "computer-science:bs-bac-ba",
    "requirements": [
        {
            "name": "Programming Foundation",
            "items": [
                {"type": "course", "course": "CS 115"},
                {"type": "course", "course": "CS 116"}
            ]
        }
    ]
}


# Test 1: Preserve alternative pathway choices.
history = {
    "completed_courses": [
        {"code": "CS 115", "grade": "A"}
    ],
    "transfer_courses": [],
    "in_progress_courses": []
}

resolved = resolve_requirements(program, history)

prepared = prepare_pathway_options(
    unsatisfied_pathways=resolved["unsatisfied_pathways"],
    completed_codes={"CS 115"},
    in_progress_codes=set()
)

print("\nUpdate 22 — Test 1")
print("Prepared pathways:", prepared)

assert len(prepared) == 1

assert prepared[0]["mode"] == "required", (
    "A started pathway must become mandatory."
)

assert prepared[0]["required_courses"] == ["CS 116"], (
    "A student who completed CS 115 must be "
    "required to take CS 116 next."
)

assert prepared[0]["options"] == [], (
    "The scheduler must not offer CS 201 as an "
    "alternative after CS 115 was completed."
)

print("PASS: Started programming pathway requires CS 116.")

# Test 2: Student has not started a programming pathway.

history_unstarted = {
    "completed_courses": [],
    "transfer_courses": [],
    "in_progress_courses": []
}

resolved_unstarted = resolve_requirements(
    program,
    history_unstarted
)

prepared_unstarted = prepare_pathway_options(
    unsatisfied_pathways=resolved_unstarted["unsatisfied_pathways"],
    completed_codes=set(),
    in_progress_codes=set()
)

print("\nUpdate 22 — Test 2")
print("Prepared pathways:", prepared_unstarted)

assert len(prepared_unstarted) == 1

assert prepared_unstarted[0]["mode"] == "choice", (
    "An unstarted pathway must preserve its alternatives."
)

assert prepared_unstarted[0]["required_courses"] == [], (
    "No individual course should be mandatory "
    "before a pathway is selected."
)

assert prepared_unstarted[0]["options"] == [
    ["CS 115", "CS 116"],
    ["CS 201"]
], (
    "Both valid programming alternatives must remain available."
)

assert prepared_unstarted[0]["recommended_pathway"] is None

print("PASS: Unstarted programming pathway preserves both alternatives.")