
import z3

from backend.scheduler.prerequisite_expression import parse_expression
from backend.scheduler.prerequisite_validator import (
    check_course_prerequisite,
    extract_prerequisite_details,
)

def build_prerequisite_constraint(
    expression,
    history,
    target_start,
    scheduled_tasks,
    detail_lookup=None,
    in_progress_terms=None
):
    """
    Convert a prerequisite expression tree into a Z3 constraint.

    target_start: Z3 start variable for the target course
    scheduled_tasks: mapping of course codes to ProcessScheduler tasks
    in_progress_terms: mapping of in-progress course codes to term indices

    Returns a Z3 Boolean expression.
    """

    detail_lookup = detail_lookup or {}
    in_progress_terms = in_progress_terms or {}

    node_type = expression["type"]

    if node_type == "course":
        code = expression["code"]
        detail = detail_lookup.get(code, {})

        minimum_grade = detail.get("minimum_grade")
        concurrent_allowed = detail.get("concurrent_allowed", False)

        # Prevent a course from satisfying its own prerequisite.
        if code in scheduled_tasks:
            prerequisite_start = scheduled_tasks[code]._start

            if concurrent_allowed:
                return prerequisite_start <= target_start

            return prerequisite_start < target_start

        # Already completed prerequisites.
        result = check_course_prerequisite(
            prerequisite_code=code,
            minimum_grade=minimum_grade,
            history=history
        )

        if result["status"] == "satisfied":
            return z3.BoolVal(True)

        # Existing in-progress courses must occur early enough.
        if result["status"] == "in_progress":
            if code not in in_progress_terms:
                return z3.BoolVal(False)

            prerequisite_term = in_progress_terms[code]

            if concurrent_allowed:
                return z3.IntVal(prerequisite_term) <= target_start

            return z3.IntVal(prerequisite_term) < target_start

        # Missing or unverified prerequisites cannot be assumed met.
        return z3.BoolVal(False)

    if node_type == "AND":
        return z3.And(*[
            build_prerequisite_constraint(
                child,
                history,
                target_start,
                scheduled_tasks,
                detail_lookup,
                in_progress_terms
            )
            for child in expression["children"]
        ])

    if node_type == "OR":
        return z3.Or(*[
            build_prerequisite_constraint(
                child,
                history,
                target_start,
                scheduled_tasks,
                detail_lookup,
                in_progress_terms
            )
            for child in expression["children"]
        ])

    raise ValueError(f"Unsupported prerequisite node: {node_type}")
