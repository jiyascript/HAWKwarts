
GRADE_POINTS = {
    "A": 4.0,
    "B": 3.0,
    "C": 2.0,
    "D": 1.0,
    "F": 0.0,
}

def check_course_prerequisite(
    prerequisite_code,
    minimum_grade,
    history
):
    """
    Check a prerequisite against validated academic history.

    Returns:
        satisfied
        not_satisfied
        in_progress
        unverified
    """

    completed = [
        course
        for course in history["completed_courses"]
        if course["code"] == prerequisite_code
    ]

    transfers = [
        course
        for course in history["transfer_courses"]
        if course["code"] == prerequisite_code
    ]

    in_progress = [
        course
        for course in history["in_progress_courses"]
        if course["code"] == prerequisite_code
    ]

    verified_grades = []

    for course in completed:
        grade = course.get("grade")

        if grade in GRADE_POINTS:
            verified_grades.append(grade)

    if verified_grades:
        if minimum_grade is None:
            passing_grades = [
                grade
                for grade in verified_grades
                if GRADE_POINTS[grade] >= GRADE_POINTS["D"]
            ]

            if passing_grades:
                return {
                    "status": "satisfied",
                    "code": prerequisite_code,
                    "grades": verified_grades
                }

            return {
                "status": "not_satisfied",
                "code": prerequisite_code,
                "grades": verified_grades,
                "reason": "No passing grade found"
            }

        required = GRADE_POINTS.get(minimum_grade)

        if required is None:
            return {
                "status": "unverified",
                "code": prerequisite_code,
                "reason": "Unsupported minimum grade"
            }

        if any(
            GRADE_POINTS[grade] >= required
            for grade in verified_grades
        ):
            return {
                "status": "satisfied",
                "code": prerequisite_code,
                "grades": verified_grades
            }

        return {
            "status": "not_satisfied",
            "code": prerequisite_code,
            "grades": verified_grades,
            "minimum_grade": minimum_grade
        }

    if transfers:
        verified = any(
            course.get("equivalency_verified") is True
            for course in transfers
        )

        if not verified:
            return {
                "status": "unverified",
                "code": prerequisite_code,
                "reason": "Transfer equivalency has not been verified"
            }

        if minimum_grade is not None:
            return {
                "status": "unverified",
                "code": prerequisite_code,
                "reason": "Transfer grade equivalency requires verification",
                "minimum_grade": minimum_grade
            }

        return {
            "status": "satisfied",
            "code": prerequisite_code,
            "reason": "Verified transfer equivalency"
        }

    if in_progress:
        return {
            "status": "in_progress",
            "code": prerequisite_code,
            "term": in_progress[0].get("term")
        }

    return {
        "status": "not_satisfied",
        "code": prerequisite_code,
        "reason": "Prerequisite not found in academic history"
    }


from backend.scheduler.prerequisite_parser import (
    parse_prerequisites,
    extract_prerequisite_details,
)

def validate_course_prerequisites(course, history):
    """
    Validate a course's prerequisites against academic history.

    Supports:
    - No listed prerequisites
    - Single prerequisites
    - OR alternatives
    - Nested AND/OR expressions

    Unsupported catalog syntax remains unverified.
    """

    from backend.scheduler.prerequisite_expression import parse_expression

    course_code = course["course_id"]

    indicator = (course.get("prerequisites") or "").strip()
    general = (course.get("general_requirements") or "").strip()

    if not indicator and not general:
        return {
            "course": course_code,
            "status": "eligible",
            "prerequisites": []
        }

    # The detailed Banner requirements contain grade metadata.
    if general:
        parsed = parse_prerequisites(indicator, general)

        if parsed["status"] != "parsed":
            return {
                "course": course_code,
                "status": "unverified",
                "reason": "Unsupported Banner prerequisite requirements",
                "raw": general
            }

        details = extract_prerequisite_details(general)
        detail_lookup = {item["code"]: item for item in details}

        results = []

        for code in parsed["courses"]:
            detail = detail_lookup.get(code)

            if detail is None:
                return {
                    "course": course_code,
                    "status": "unverified",
                    "reason": f"Missing prerequisite metadata: {code}"
                }

            results.append(
                check_course_prerequisite(
                    prerequisite_code=code,
                    minimum_grade=detail["minimum_grade"],
                    history=history
                )
            )

        statuses = [result["status"] for result in results]

        if parsed["logic"] == "SINGLE":
            status = statuses[0]

        elif parsed["logic"] == "OR":
            if "satisfied" in statuses:
                status = "satisfied"
            elif "in_progress" in statuses:
                status = "in_progress"
            elif "unverified" in statuses:
                status = "unverified"
            else:
                status = "not_satisfied"

        else:
            status = "unverified"

        return {
            "course": course_code,
            "status": {
                "satisfied": "eligible",
                "in_progress": "conditional",
                "not_satisfied": "not_eligible",
                "unverified": "unverified"
            }[status],
            "prerequisites": results
        }

    # Some courses, such as CS 450, store a full expression
    # directly in the prerequisites field.
    try:
        expression = parse_expression(indicator)
    except ValueError:
        return {
            "course": course_code,
            "status": "unverified",
            "reason": "Unsupported prerequisite expression",
            "raw": indicator
        }

    result = evaluate_prerequisite_expression(expression, history)

    return {
        "course": course_code,
        "status": {
            "satisfied": "eligible",
            "in_progress": "conditional",
            "not_satisfied": "not_eligible",
            "unverified": "unverified"
        }[result["status"]],
        "prerequisites": result
    }


def evaluate_prerequisite_expression(expression, history):
    """
    Recursively evaluate an AND/OR prerequisite expression
    against validated academic history.
    """

    node_type = expression["type"]

    # Individual course requirement
    if node_type == "course":
        return check_course_prerequisite(
            prerequisite_code=expression["code"],
            minimum_grade=expression.get("minimum_grade"),
            history=history
        )

    if node_type not in ("AND", "OR"):
        return {
            "status": "unverified",
            "reason": f"Unsupported expression type: {node_type}"
        }

    children = [
        evaluate_prerequisite_expression(child, history)
        for child in expression["children"]
    ]

    statuses = [child["status"] for child in children]

    if node_type == "AND":
        if "not_satisfied" in statuses:
            status = "not_satisfied"
        elif "unverified" in statuses:
            status = "unverified"
        elif "in_progress" in statuses:
            status = "in_progress"
        else:
            status = "satisfied"

    else:  # OR
        if "satisfied" in statuses:
            status = "satisfied"
        elif "in_progress" in statuses:
            status = "in_progress"
        elif "unverified" in statuses:
            status = "unverified"
        else:
            status = "not_satisfied"

    return {
        "type": node_type,
        "status": status,
        "children": children
    }


def check_prerequisite_timing(
    prerequisite_code,
    prerequisite_term,
    target_term,
    concurrent_allowed=False
):
    """
    Check whether a prerequisite is scheduled early enough.

    Terms must be supplied in chronological order using
    comparable integer indices:
        Fall 2026  = 0
        Spring 2027 = 1

    This function checks timing only, not grades or completion.
    """

    if prerequisite_term is None:
        return {
            "status": "unverified",
            "reason": "Prerequisite term is unknown"
        }

    if prerequisite_term < target_term:
        return {
            "status": "satisfied",
            "reason": "Prerequisite occurs in an earlier semester"
        }

    if prerequisite_term == target_term:
        if concurrent_allowed:
            return {
                "status": "satisfied",
                "reason": "Concurrent enrollment is permitted"
            }

        return {
            "status": "not_satisfied",
            "reason": "Concurrent enrollment is not permitted"
        }

    return {
        "status": "not_satisfied",
        "reason": "Prerequisite occurs after the target course"
    }

def validate_prerequisite_for_term(
    prerequisite_code,
    minimum_grade,
    history,
    target_term,
    prerequisite_term=None,
    concurrent_allowed=False
):
    """
    Validate one prerequisite for a target semester.

    prerequisite_term:
        None = no planned/in-progress term supplied
        int  = chronological semester index

    Returns:
        satisfied
        conditional
        not_satisfied
        unverified
    """

    result = check_course_prerequisite(
        prerequisite_code=prerequisite_code,
        minimum_grade=minimum_grade,
        history=history
    )

    status = result["status"]

    # Already completed and verified.
    if status == "satisfied":
        return {
            "status": "satisfied",
            "code": prerequisite_code,
            "reason": "Prerequisite already completed"
        }

    # Transfer equivalency or other uncertain evidence.
    if status == "unverified":
        return {
            "status": "unverified",
            "code": prerequisite_code,
            "reason": result.get(
                "reason",
                "Prerequisite requires verification"
            )
        }

    # In-progress or proposed prerequisite.
    if prerequisite_term is not None:
        timing = check_prerequisite_timing(
            prerequisite_code=prerequisite_code,
            prerequisite_term=prerequisite_term,
            target_term=target_term,
            concurrent_allowed=concurrent_allowed
        )

        if timing["status"] == "not_satisfied":
            return {
                "status": "not_satisfied",
                "code": prerequisite_code,
                "reason": timing["reason"]
            }

        return {
            "status": "conditional",
            "code": prerequisite_code,
            "reason": (
                "Prerequisite must be successfully completed "
                "or concurrently enrolled as permitted"
            )
        }

    if status == "in_progress":
        return {
            "status": "unverified",
            "code": prerequisite_code,
            "reason": "In-progress prerequisite term is unknown"
        }

    return {
        "status": "not_satisfied",
        "code": prerequisite_code,
        "reason": "Prerequisite has not been completed or scheduled"
    }

def validate_banner_prerequisites_for_term(
    course,
    history,
    target_term,
    planned_terms=None
):
    """
    Validate simple Banner prerequisite rules for a target term.

    planned_terms maps prerequisite codes to semester indices.

    Example:
        {"CS 430": 0}

    Returns:
        eligible
        conditional
        not_eligible
        unverified

    Supports SINGLE and OR requirements from general_requirements.
    Complex or unsupported rules remain unverified.
    """

    planned_terms = planned_terms or {}

    course_code = course["course_id"]

    parsed = parse_prerequisites(
        course.get("prerequisites", ""),
        course.get("general_requirements", "")
    )

    if parsed["status"] == "none_listed":
        return {
            "course": course_code,
            "status": "eligible",
            "prerequisites": []
        }

    
    if parsed["status"] != "parsed":
        # Some Banner records, such as CS 450, contain a
        # nested course-code expression in prerequisites.
        # Only attempt this fallback when there are no
        # separate general requirements.
        indicator = (course.get("prerequisites") or "").strip()
        general = (course.get("general_requirements") or "").strip()

        if general:
            return {
                "course": course_code,
                "status": "unverified",
                "reason": "Unsupported Banner general requirements",
                "raw": general
            }

        try:
            from backend.scheduler.prerequisite_expression import (
                parse_expression
            )

            expression = parse_expression(indicator)

        except ValueError:
            return {
                "course": course_code,
                "status": "unverified",
                "reason": "Unsupported prerequisite expression",
                "raw": indicator
            }

        result = evaluate_prerequisite_expression_for_term(
            expression=expression,
            history=history,
            target_term=target_term,
            planned_terms=planned_terms
        )

        status_mapping = {
            "satisfied": "eligible",
            "conditional": "conditional",
            "not_satisfied": "not_eligible",
            "unverified": "unverified"
        }

        return {
            "course": course_code,
            "status": status_mapping[result["status"]],
            "prerequisites": result
        }

    details = extract_prerequisite_details(
        course.get("general_requirements", "")
    )

    # If Banner provides a detailed requirement, every referenced
    # course must have corresponding metadata.
    detail_lookup = {
        item["code"]: item
        for item in details
    }

    results = []

    for code in parsed["courses"]:
        detail = detail_lookup.get(code)

        if course.get("general_requirements") and detail is None:
            return {
                "course": course_code,
                "status": "unverified",
                "reason": f"Missing Banner metadata for {code}"
            }

        result = validate_prerequisite_for_term(
            prerequisite_code=code,
            minimum_grade=(
                detail["minimum_grade"]
                if detail else None
            ),
            history=history,
            target_term=target_term,
            prerequisite_term=planned_terms.get(code),
            concurrent_allowed=(
                detail["concurrent_allowed"]
                if detail else False
            )
        )

        results.append(result)

    statuses = [result["status"] for result in results]

    if parsed["logic"] == "SINGLE":
        status = statuses[0]

    elif parsed["logic"] == "OR":
        if "satisfied" in statuses:
            status = "satisfied"
        elif "conditional" in statuses:
            status = "conditional"
        elif "unverified" in statuses:
            status = "unverified"
        else:
            status = "not_satisfied"

    else:
        status = "unverified"

    return {
        "course": course_code,
        "status": {
            "satisfied": "eligible",
            "conditional": "conditional",
            "not_satisfied": "not_eligible",
            "unverified": "unverified"
        }[status],
        "prerequisites": results
    }

def evaluate_prerequisite_expression_for_term(
    expression,
    history,
    target_term,
    planned_terms=None,
    detail_lookup=None
):
    """
    Evaluate nested AND/OR prerequisites for a target semester.

    Supports completed, in-progress, and planned prerequisites.
    """

    planned_terms = planned_terms or {}
    detail_lookup = detail_lookup or {}

    node_type = expression["type"]

    if node_type == "course":
        code = expression["code"]
        detail = detail_lookup.get(code, {})

        return validate_prerequisite_for_term(
            prerequisite_code=code,
            minimum_grade=detail.get("minimum_grade"),
            history=history,
            target_term=target_term,
            prerequisite_term=planned_terms.get(code),
            concurrent_allowed=detail.get(
                "concurrent_allowed", False
            )
        )

    if node_type not in ("AND", "OR"):
        return {
            "status": "unverified",
            "reason": f"Unsupported expression type: {node_type}"
        }

    children = [
        evaluate_prerequisite_expression_for_term(
            expression=child,
            history=history,
            target_term=target_term,
            planned_terms=planned_terms,
            detail_lookup=detail_lookup
        )
        for child in expression["children"]
    ]

    statuses = [child["status"] for child in children]

    if node_type == "AND":
        if "not_satisfied" in statuses:
            status = "not_satisfied"
        elif "unverified" in statuses:
            status = "unverified"
        elif "conditional" in statuses:
            status = "conditional"
        else:
            status = "satisfied"

    else:  # OR
        if "satisfied" in statuses:
            status = "satisfied"
        elif "conditional" in statuses:
            status = "conditional"
        elif "unverified" in statuses:
            status = "unverified"
        else:
            status = "not_satisfied"

    return {
        "type": node_type,
        "status": status,
        "children": children
    }

