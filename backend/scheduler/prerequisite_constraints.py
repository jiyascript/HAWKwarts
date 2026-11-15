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

    # Placement-test results are not yet represented
    # in verified academic history.
    # Unknown placement eligibility must not be
    # assumed satisfied.
    if node_type == "placement_requirement":
        return z3.BoolVal(False)
    
    if node_type == "course":
        code = expression["code"]
        detail = detail_lookup.get(code, {})

        minimum_grade = detail.get("minimum_grade")
        concurrent_allowed = detail.get(
            "concurrent_allowed", False
        )

        # First check whether the prerequisite
        # has already been completed.
        result = check_course_prerequisite(
            prerequisite_code=code,
            minimum_grade=minimum_grade,
            history=history
        )

        if result["status"] == "satisfied":
            return z3.BoolVal(True)

        # Otherwise, check whether the prerequisite
        # is represented by a scheduling task.
        if code in scheduled_tasks:
            prerequisite_task = scheduled_tasks[code]
            prerequisite_start = prerequisite_task._start

            if concurrent_allowed:
                timing_constraint = (
                    prerequisite_start <= target_start
                )
            else:
                timing_constraint = (
                    prerequisite_start < target_start
                )

            if prerequisite_task.optional:
                return z3.And(
                    prerequisite_task._scheduled,
                    timing_constraint
                )

            return timing_constraint

        # Check existing in-progress coursework.
        if result["status"] == "in_progress":
            if code not in in_progress_terms:
                return z3.BoolVal(False)

            prerequisite_term = in_progress_terms[code]

            if concurrent_allowed:
                return (
                    z3.IntVal(prerequisite_term)
                    <= target_start
                )

            return (
                z3.IntVal(prerequisite_term)
                < target_start
            )

        # Missing or unverified prerequisites
        # cannot be assumed satisfied.
        return z3.BoolVal(False)

    if node_type == "course_range":
        subject = expression["subject"] 
        start = expression["start"]
        end = expression["end"]

        range_code = f"{subject} {start:03d}"

        detail = next(
            (
                item
                for item in detail_lookup.values()
                if item["code"] == range_code
                and item.get("range_end") == end
            ),
            None
        )

        # Do not assume eligibility if Banner metadata
        # for this course range is missing.
        if detail is None:
            return z3.BoolVal(False)

        candidate_codes = {
            course["code"]
            for category in (
                "completed_courses",
                "transfer_courses",
                "in_progress_courses"
            )
            for course in history.get(category, [])
        }

        candidate_codes.update(scheduled_tasks.keys())

        from backend.scheduler.prerequisite_validator import (
            course_matches_range
        )

        matching_codes = sorted(
            code
            for code in candidate_codes
            if course_matches_range(
                code, subject, start, end
            )
        )

        if not matching_codes:
            return z3.BoolVal(False)

        constraints = []

        for code in matching_codes:
            course_expression = {
                "type": "course",
                "code": code
            }

            course_details = {
                **detail_lookup,
                code: detail
            }

            constraints.append(
                build_prerequisite_constraint(
                    course_expression,
                    history,
                    target_start,
                    scheduled_tasks,
                    course_details,
                    in_progress_terms
                )
            )

        return z3.Or(*constraints)

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
